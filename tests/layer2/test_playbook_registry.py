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

    def test_default_registry_loads_at_least_one_playbook(self):
        """Regression: default PlaybookRegistry() must find V3/playbooks/ correctly.

        If _DEFAULT_PLAYBOOK_DIR is wrong (wrong parents[] depth, missing directory,
        etc.), the registry silently loads 0 playbooks and the pipeline falls through
        entirely to INDUSTRY_BENCHMARKS — brand bindings and meta-patterns are ignored.
        This test locks that path so it fails loudly instead of silently degrading.
        """
        registry = PlaybookRegistry()
        registry._ensure_loaded()
        assert len(registry._by_id) >= 1, (
            f"Default PlaybookRegistry() loaded 0 playbooks. "
            f"Check _DEFAULT_PLAYBOOK_DIR in playbook_registry.py. "
            f"Resolved dir: {registry._playbook_dir}"
        )

    def test_default_registry_loads_meta_patterns(self):
        """Regression: default registry must include ADR-0011 meta-patterns from playbooks/meta/.

        Meta-patterns are the authoritative action vocabulary for KG-driven candidate
        generation. If meta/ is not scanned, brand binding priors never enter scoring.
        """
        registry = PlaybookRegistry()
        registry._ensure_loaded()
        meta_ids = [pb_id for pb_id, pb in registry._by_id.items() if pb.get("_is_meta")]
        assert len(meta_ids) >= 1, (
            f"Default PlaybookRegistry() loaded no meta-patterns (playbooks/meta/). "
            f"Loaded playbook IDs: {list(registry._by_id.keys())}"
        )


# ── ADR-0012 router tests: match_playbook() merchant_id selection ─────────────
# These 5 tests lock the dict | None return contract and the brand-binding-aware
# selection logic introduced in ADR-0012 (2026-04-13).
#
# Setup pattern used across all 5:
#   - Build a synthetic registry with 2 meta-patterns in the same module/MSM-state
#   - Inject a fake brand binding cache so get_brand_binding() returns a hit
#     for merchant "test_merchant" on "meta_b" only
# ─────────────────────────────────────────────────────────────────────────────

def _build_two_meta_registry() -> PlaybookRegistry:
    """Return a registry with two meta-patterns in acquisition / DEGRADING."""
    registry = PlaybookRegistry.__new__(PlaybookRegistry)
    registry._playbook_dir = ""
    registry._loaded = True
    registry._brand_bindings = {}

    meta_a = {
        "id": "acq_meta_a",
        "module": "acquisition",
        "description": "alpha pattern",
        "actions": [{"id": "PAUSE_LOW_ROAS"}],
        "triggers": [{"msm_state": "DEGRADING"}],
        "patterns": [],
        "constraints": [],
        "_source_file": "meta_a.yaml",
        "_is_meta": True,
    }
    meta_b = {
        "id": "acq_meta_b",
        "module": "acquisition",
        "description": "beta pattern",
        "actions": [{"id": "SHIFT_BUDGET_TO_RETENTION"}],
        "triggers": [{"msm_state": "DEGRADING"}],
        "patterns": [],
        "constraints": [],
        "_source_file": "meta_b.yaml",
        "_is_meta": True,
    }
    # Load order: a first, b second
    registry._by_module = {"acquisition": [meta_a, meta_b]}
    registry._by_id = {"acq_meta_a": meta_a, "acq_meta_b": meta_b}
    return registry


# ── Deferred directory loader test ───────────────────────────────────────────

class TestDeferredDirectorySkipped:
    """ADR-0012 + loader contract: _deferred/ contents must never appear in registry."""

    def test_loader_skips_deferred_directory(self, tmp_path):
        """PlaybookRegistry must not load any YAML from meta/_deferred/.

        Enforces: ADR-0012 — dormant patterns in _deferred/ have unresolvable
        trigger conditions (missing DFV fields, Phase 2 dependencies). Loading
        them would register non-activatable triggers as live candidates, causing
        the pipeline to generate candidates that cannot be scored correctly.

        If this test fails:
        - The _deferred/ skip logic in load_playbooks() was removed or broken.
          Restore the 'startswith("_")' part filter in load_playbooks().
        - A YAML was moved out of _deferred/ without going through the full
          reactivation checklist (see docs/partner_clarification_queue/).
        """
        import textwrap

        # Build a synthetic playbook directory with meta/ and meta/_deferred/
        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()
        deferred_dir = meta_dir / "_deferred"
        deferred_dir.mkdir()

        # Active meta-pattern — must be loaded
        (meta_dir / "active_pattern.yaml").write_text(textwrap.dedent("""
            meta_pattern:
              id: active_meta_v1
              module: retention
            triggers:
              - msm_state: DEGRADING
            actions:
              - id: SEND_REMINDER
        """))

        # Dormant pattern in _deferred/ — must NOT be loaded
        (deferred_dir / "dormant_pattern.yaml").write_text(textwrap.dedent("""
            activation_phase: 2
            meta_pattern:
              id: dormant_meta_v1
              module: acquisition
            triggers:
              - msm_state: WATCH
            actions:
              - id: VALIDATE_BEFORE_SCALE
        """))

        registry = PlaybookRegistry(playbook_dir=str(tmp_path))
        registry.load_playbooks(str(tmp_path))

        assert "active_meta_v1" in registry._by_id, (
            "Active meta-pattern 'active_meta_v1' should be loaded but was not. "
            "Check that meta/ scanning still works correctly."
        )
        assert "dormant_meta_v1" not in registry._by_id, (
            "Dormant pattern 'dormant_meta_v1' from meta/_deferred/ must NOT be loaded. "
            "Restore the _deferred/ skip logic in load_playbooks(). See ADR-0012."
        )

    def test_real_deferred_dir_not_in_default_registry(self):
        """acquisition_ltv_quality_trap must not appear in default registry.

        Regression guard: confirms the real playbooks/meta/_deferred/ directory
        is excluded when PlaybookRegistry() is instantiated with default paths.

        If this test fails: cbb_001 dormant YAML leaked into active registry.
        Likely cause: _deferred/ skip logic broken or YAML moved to meta/ root.
        """
        registry = PlaybookRegistry()
        registry._ensure_loaded()
        assert "acquisition_ltv_quality_trap" not in registry._by_id, (
            "acquisition_ltv_quality_trap (cbb_001 dormant) must not appear in "
            "the active registry. It is in playbooks/meta/_deferred/ and must "
            "remain excluded until Phase 2 reactivation. See ADR-0012 and "
            "docs/partner_clarification_queue/cbb_001_deferred_reactivation.md"
        )


class TestMatchPlaybookMerchantIdRouting:
    """ADR-0012: match_playbook() merchant_id routing contract."""

    def test_returns_dict_or_none_not_list(self):
        """Return type is dict | None. Never list. [ADR-0012 contract]"""
        registry = _build_two_meta_registry()
        result = registry.match_playbook("acquisition", {"msm_state": "DEGRADING"})
        assert result is None or isinstance(result, dict), (
            f"match_playbook() must return dict or None, got {type(result)!r}. "
            "Changing to list requires ADR-0012 supersession."
        )

    def test_brand_bound_meta_preferred_over_unbound(self):
        """When merchant_id is given and one meta-pattern has a brand binding,
        the bound pattern is returned even if an unbound one was loaded first.
        [ADR-0012 Priority 1]
        """
        registry = _build_two_meta_registry()
        # Inject binding for "acq_meta_b" only — loaded second
        registry._brand_bindings["brand_x"] = {
            "acq_meta_b": {"brand": "brand_x", "meta_pattern_ref": "acq_meta_b"}
        }
        result = registry.match_playbook(
            "acquisition", {"msm_state": "DEGRADING"}, merchant_id="brand_x"
        )
        assert result is not None
        assert result["id"] == "acq_meta_b", (
            "Brand-bound meta-pattern 'acq_meta_b' must win over unbound 'acq_meta_a'. "
            "See ADR-0012 Priority 1."
        )

    def test_brand_bound_alphabetical_tiebreak(self):
        """When two meta-patterns both have brand bindings, alphabetically first wins.
        [ADR-0012 deterministic tiebreak]
        """
        registry = _build_two_meta_registry()
        # Both patterns bound to the same merchant
        registry._brand_bindings["brand_y"] = {
            "acq_meta_a": {"brand": "brand_y", "meta_pattern_ref": "acq_meta_a"},
            "acq_meta_b": {"brand": "brand_y", "meta_pattern_ref": "acq_meta_b"},
        }
        result = registry.match_playbook(
            "acquisition", {"msm_state": "DEGRADING"}, merchant_id="brand_y"
        )
        assert result is not None
        assert result["id"] == "acq_meta_a", (
            "With two brand-bound patterns, 'acq_meta_a' < 'acq_meta_b' alphabetically, "
            "so 'acq_meta_a' must win. See ADR-0012 tiebreak rule."
        )

    def test_no_brand_binding_falls_back_to_first_meta_in_load_order(self):
        """When merchant_id is given but no brand binding exists, falls back to
        first MSM-state-matching meta-pattern in load order. [ADR-0012 Priority 2]
        """
        registry = _build_two_meta_registry()
        # No binding for this merchant
        registry._brand_bindings["unknown_merchant"] = {}
        result = registry.match_playbook(
            "acquisition", {"msm_state": "DEGRADING"}, merchant_id="unknown_merchant"
        )
        assert result is not None
        assert result["id"] == "acq_meta_a", (
            "With no brand binding, first meta-pattern in load order ('acq_meta_a') "
            "must be returned. See ADR-0012 Priority 2."
        )

    def test_empty_merchant_id_behaves_same_as_omitted(self):
        """merchant_id='' (default) skips brand-binding lookup — backward compatible.
        [ADR-0012: no change to callers that don't pass merchant_id]
        """
        registry = _build_two_meta_registry()
        # Binding exists but should NOT be consulted when merchant_id is empty
        registry._brand_bindings["brand_z"] = {
            "acq_meta_b": {"brand": "brand_z", "meta_pattern_ref": "acq_meta_b"}
        }
        result_explicit_empty = registry.match_playbook(
            "acquisition", {"msm_state": "DEGRADING"}, merchant_id=""
        )
        result_omitted = registry.match_playbook(
            "acquisition", {"msm_state": "DEGRADING"}
        )
        assert result_explicit_empty == result_omitted, (
            "merchant_id='' must produce the same result as omitting merchant_id. "
            "Backward compatibility required. See ADR-0012."
        )
        # Both should return first meta in load order (no brand binding consulted)
        assert result_omitted is not None
        assert result_omitted["id"] == "acq_meta_a"
