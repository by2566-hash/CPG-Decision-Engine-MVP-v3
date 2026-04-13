# ── Layer 2 Tests · PlaybookRegistry validation ────────────────────────────
# Tests for PlaybookRegistry._validate_playbook_structure().
# Ensures structural issues in KG YAML files are detected before they cause
# silent "no candidates generated" failures in production.
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import textwrap
import tempfile
from pathlib import Path

import pytest

from src.decision_engine.layer2_decision.pillar1_kg.playbook_registry import PlaybookRegistry


# ── Helper ────────────────────────────────────────────────────────────────

def _minimal_valid_playbook(
    module: str = "retention",
    action_id: str = "SEND_REMINDER",
    expected_utility: float = 0.6,
    msm_state: str = "DEGRADING",
) -> dict:
    """A structurally complete playbook dict — no issues expected."""
    return {
        "id": "test_playbook_v1",
        "module": module,
        "description": "test",
        "actions": [{"id": action_id, "expected_utility": expected_utility}],
        "triggers": [{"msm_state": msm_state, "condition": "overdue_ratio > 1.5"}],
        "patterns": [],
        "constraints": [],
    }


# ── _validate_playbook_structure unit tests ───────────────────────────────

class TestValidatePlaybookStructure:
    def setup_method(self):
        self.registry = PlaybookRegistry.__new__(PlaybookRegistry)

    def test_valid_playbook_has_no_issues(self):
        issues = self.registry._validate_playbook_structure(_minimal_valid_playbook())
        assert issues == []

    def test_missing_module_is_flagged(self):
        pb = _minimal_valid_playbook()
        pb["module"] = ""
        issues = self.registry._validate_playbook_structure(pb)
        assert any("module is missing" in i for i in issues)

    def test_unknown_module_is_flagged(self):
        pb = _minimal_valid_playbook(module="logistics")
        issues = self.registry._validate_playbook_structure(pb)
        assert any("not a valid CPG module" in i for i in issues)

    def test_all_four_valid_modules_pass(self):
        for module in ("retention", "acquisition", "conversion", "promotion"):
            pb = _minimal_valid_playbook(module=module)
            issues = self.registry._validate_playbook_structure(pb)
            assert not any("module" in i for i in issues), \
                f"module='{module}' should be valid but got: {issues}"

    def test_empty_actions_is_flagged(self):
        pb = _minimal_valid_playbook()
        pb["actions"] = []
        issues = self.registry._validate_playbook_structure(pb)
        assert any("actions list is empty" in i for i in issues)

    def test_action_missing_id_is_flagged(self):
        pb = _minimal_valid_playbook()
        pb["actions"] = [{"expected_utility": 0.5}]  # no 'id'
        issues = self.registry._validate_playbook_structure(pb)
        assert any("missing 'id'" in i for i in issues)

    def test_action_missing_expected_utility_is_flagged(self):
        pb = _minimal_valid_playbook()
        pb["actions"] = [{"id": "SEND_REMINDER"}]  # no expected_utility
        issues = self.registry._validate_playbook_structure(pb)
        assert any("missing 'expected_utility'" in i for i in issues)

    def test_action_non_numeric_expected_utility_is_flagged(self):
        pb = _minimal_valid_playbook()
        pb["actions"] = [{"id": "SEND_REMINDER", "expected_utility": "high"}]
        issues = self.registry._validate_playbook_structure(pb)
        assert any("not numeric" in i for i in issues)

    def test_action_integer_expected_utility_is_valid(self):
        """Integer utility (e.g. 1) is acceptable — isinstance(1, (int, float)) is True."""
        pb = _minimal_valid_playbook()
        pb["actions"] = [{"id": "SEND_REMINDER", "expected_utility": 1}]
        issues = self.registry._validate_playbook_structure(pb)
        assert not any("expected_utility" in i for i in issues)

    def test_empty_triggers_is_flagged(self):
        pb = _minimal_valid_playbook()
        pb["triggers"] = []
        issues = self.registry._validate_playbook_structure(pb)
        assert any("triggers list is empty" in i for i in issues)

    def test_trigger_missing_msm_state_is_flagged(self):
        pb = _minimal_valid_playbook()
        pb["triggers"] = [{"condition": "overdue_ratio > 1.5"}]  # no msm_state
        issues = self.registry._validate_playbook_structure(pb)
        assert any("missing 'msm_state'" in i for i in issues)

    def test_trigger_invalid_msm_state_is_flagged(self):
        pb = _minimal_valid_playbook()
        pb["triggers"] = [{"msm_state": "BROKEN"}]
        issues = self.registry._validate_playbook_structure(pb)
        assert any("not valid" in i for i in issues)

    def test_all_four_valid_msm_states_pass(self):
        for state in ("HEALTHY", "WATCH", "DEGRADING", "CRITICAL"):
            pb = _minimal_valid_playbook(msm_state=state)
            issues = self.registry._validate_playbook_structure(pb)
            assert not any("msm_state" in i for i in issues), \
                f"msm_state='{state}' should be valid but got: {issues}"

    def test_multiple_issues_all_reported(self):
        """A broken playbook reports ALL issues, not just the first."""
        pb = {
            "id": "broken",
            "module": "unknown_module",
            "actions": [],
            "triggers": [],
        }
        issues = self.registry._validate_playbook_structure(pb)
        assert len(issues) >= 3  # module + actions + triggers all broken


# ── load_playbooks integration: validation warnings emitted ──────────────

class TestLoadPlaybooksValidation:
    def _write_yaml(self, tmp_path: Path, name: str, content: str) -> None:
        (tmp_path / name).write_text(textwrap.dedent(content))

    def test_valid_playbook_loads_cleanly(self, tmp_path, caplog):
        import logging
        self._write_yaml(tmp_path, "good.yaml", """
            playbook:
              id: good_v1
              module: retention
            triggers:
              - msm_state: DEGRADING
                condition: "overdue_ratio > 1.0"
            actions:
              - id: SEND_REMINDER
                expected_utility: 0.6
        """)
        registry = PlaybookRegistry(playbook_dir=str(tmp_path))
        with caplog.at_level(logging.WARNING):
            registry.load_playbooks(str(tmp_path))
        # No structural warnings expected
        warnings = [r for r in caplog.records if r.levelname == "WARNING"
                    and "structural issue" not in r.message
                    and "good.yaml" in r.message]
        assert warnings == []
        assert registry.get_playbook("good_v1") is not None

    def test_playbook_missing_expected_utility_logs_warning(self, tmp_path, caplog):
        import logging
        self._write_yaml(tmp_path, "no_utility.yaml", """
            playbook:
              id: no_utility_v1
              module: acquisition
            triggers:
              - msm_state: WATCH
            actions:
              - id: PAUSE_LOW_ROAS
        """)
        registry = PlaybookRegistry(playbook_dir=str(tmp_path))
        with caplog.at_level(logging.WARNING):
            registry.load_playbooks(str(tmp_path))
        assert any("expected_utility" in r.message for r in caplog.records)
        # Still loaded despite warning
        assert registry.get_playbook("no_utility_v1") is not None

    def test_playbook_wrong_module_logs_warning(self, tmp_path, caplog):
        import logging
        self._write_yaml(tmp_path, "bad_module.yaml", """
            playbook:
              id: bad_module_v1
              module: logistics
            triggers:
              - msm_state: DEGRADING
            actions:
              - id: DO_SOMETHING
                expected_utility: 0.5
        """)
        registry = PlaybookRegistry(playbook_dir=str(tmp_path))
        with caplog.at_level(logging.WARNING):
            registry.load_playbooks(str(tmp_path))
        assert any("not a valid CPG module" in r.message for r in caplog.records)


# ── Smoke test: existing playbooks in repo pass validation ────────────────

class TestExistingPlaybooksAreValid:
    """Regression guard: all playbooks in V3/playbooks/ must pass structure checks.

    This test fails if a new KG translation introduces structural issues.
    Add exceptions only with an explicit comment explaining why.
    """

    def test_all_repo_playbooks_have_no_critical_issues(self):
        """All existing playbooks load without module or actions errors."""
        registry = PlaybookRegistry()
        registry._ensure_loaded()

        for pb_id, pb in registry._by_id.items():
            issues = registry._validate_playbook_structure(pb)
            # Only fail on critical issues (module wrong / actions empty).
            # Missing expected_utility is acceptable for stub playbooks.
            critical = [i for i in issues if
                        "not a valid CPG module" in i
                        or "actions list is empty" in i
                        or "module is missing" in i]
            assert critical == [], (
                f"Playbook '{pb_id}' ({pb.get('_source_file')}) has critical issues: {critical}"
            )
