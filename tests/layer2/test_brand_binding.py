# ── Tests: PlaybookRegistry brand binding (ADR-0011) ─────────────────────────
# Covers:
#   1. load_brand_binding() loads and indexes brand binding YAMLs
#   2. get_base_utility() priority order: brand binding > flat playbook > None
#   3. gmv_lift_prior clip to [0.0, 0.25]
#   4. _flatten_dict() produces correct dot-notation keys
#   5. render_brand_triggers() interpolates ${thresholds.*} correctly
#   6. Graceful handling of missing brand binding dir
# ──────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_playbook_dir(tmp_path: Path) -> Path:
    """Create a minimal playbook directory with meta, brands, and flat stubs."""
    # Flat stub playbook (legacy path)
    stub = tmp_path / "acquisition_efficiency_v1.yaml"
    stub.write_text(textwrap.dedent("""\
        playbook:
          id: acquisition_efficiency_v1
          module: acquisition
          version: "1.0"
          description: "Stub"
        triggers:
          - name: cac_spike
            msm_state: DEGRADING
            condition: "CAC_7d > baseline * 1.15"
        actions:
          - id: PAUSE_CHANNEL
            type: CHANNEL_CONTROL
            expected_utility: 0.10
        patterns: []
        constraints:
          - attribution_window_days: 30
    """))

    # Brand binding for test_brand
    brand_dir = tmp_path / "brands" / "test_brand"
    brand_dir.mkdir(parents=True)
    binding = brand_dir / "acquisition_efficiency_v1.yaml"
    binding.write_text(textwrap.dedent("""\
        brand: test_brand
        meta_pattern_ref: acquisition_efficiency_v1
        binding_version: "1.0"
        entity_bindings:
          primary_ad_platform: meta
        thresholds:
          cac_spike_ratio: 1.20
          calibration_status: partner_prior
        action_utility_priors:
          PAUSE_CHANNEL:
            gmv_lift_prior: 0.15
            confidence: 0.75
            calibration_status: partner_prior
            evidence_case: "tb_001"
          REALLOCATE_BUDGET:
            gmv_lift_prior: 0.08
            confidence: 0.60
            calibration_status: partner_prior
            evidence_case: "tb_002"
        evidence_refs_template:
          - "CAC observed: ${metrics.cac_7d} vs baseline ${metrics.cac_baseline_30d}"
    """))

    # Brand binding for high_aov_brand with explosive prior
    high_aov_dir = tmp_path / "brands" / "high_aov_brand"
    high_aov_dir.mkdir(parents=True)
    high_aov_binding = high_aov_dir / "acquisition_efficiency_v1.yaml"
    high_aov_binding.write_text(textwrap.dedent("""\
        brand: high_aov_brand
        meta_pattern_ref: acquisition_efficiency_v1
        binding_version: "1.0"
        entity_bindings: {}
        thresholds:
          cac_spike_ratio: 1.15
          calibration_status: partner_prior
        action_utility_priors:
          PAUSE_CHANNEL:
            gmv_lift_prior: 1.50
            confidence: 0.30
            calibration_status: partner_prior
            evidence_case: "ha_001"
    """))

    return tmp_path


@pytest.fixture()
def registry(tmp_playbook_dir: Path):
    from src.decision_engine.layer2_decision.pillar1_kg.playbook_registry import PlaybookRegistry
    reg = PlaybookRegistry(playbook_dir=str(tmp_playbook_dir))
    reg.load_playbooks(str(tmp_playbook_dir))
    return reg


# ── Tests: load_brand_binding ─────────────────────────────────────────────────

class TestLoadBrandBinding:
    def test_loads_yaml_files_from_brand_dir(self, registry):
        bindings = registry.load_brand_binding("test_brand")
        assert "acquisition_efficiency_v1" in bindings

    def test_indexes_by_meta_pattern_ref(self, registry):
        bindings = registry.load_brand_binding("test_brand")
        binding = bindings["acquisition_efficiency_v1"]
        assert binding["brand"] == "test_brand"
        assert "action_utility_priors" in binding

    def test_missing_brand_dir_returns_empty_dict(self, registry):
        bindings = registry.load_brand_binding("nonexistent_brand")
        assert bindings == {}

    def test_get_brand_binding_triggers_lazy_load(self, registry):
        # No explicit load_brand_binding() call
        binding = registry.get_brand_binding("test_brand", "acquisition_efficiency_v1")
        assert binding is not None
        assert binding["brand"] == "test_brand"

    def test_get_brand_binding_returns_none_for_unknown(self, registry):
        assert registry.get_brand_binding("test_brand", "nonexistent_pattern") is None


# ── Tests: get_base_utility priority order ────────────────────────────────────

class TestGetBaseUtilityPriority:
    def test_brand_binding_takes_priority_over_flat_playbook(self, registry):
        # flat playbook has expected_utility: 0.10
        # brand binding has gmv_lift_prior: 0.15
        result = registry.get_base_utility(
            "acquisition_efficiency_v1",
            {"action_id": "PAUSE_CHANNEL", "merchant_id": "test_brand"},
        )
        assert result == pytest.approx(0.15)

    def test_falls_back_to_flat_playbook_when_no_brand_binding(self, registry):
        # No brand binding for action REALLOCATE_BUDGET in flat playbook stub
        # but flat playbook only has PAUSE_CHANNEL with expected_utility: 0.10
        result = registry.get_base_utility(
            "acquisition_efficiency_v1",
            {"action_id": "PAUSE_CHANNEL"},  # no merchant_id
        )
        assert result == pytest.approx(0.10)

    def test_returns_none_when_action_not_in_flat_playbook(self, registry):
        result = registry.get_base_utility(
            "acquisition_efficiency_v1",
            {"action_id": "UNKNOWN_ACTION"},
        )
        assert result is None

    def test_returns_none_when_playbook_not_found(self, registry):
        result = registry.get_base_utility(
            "nonexistent_playbook",
            {"action_id": "PAUSE_CHANNEL", "merchant_id": "test_brand"},
        )
        assert result is None

    def test_brand_binding_action_not_in_binding_falls_back_to_flat(self, registry):
        # REALLOCATE_BUDGET is in brand binding but NOT in flat playbook actions
        # So priority 1 (brand binding) should return 0.08
        result = registry.get_base_utility(
            "acquisition_efficiency_v1",
            {"action_id": "REALLOCATE_BUDGET", "merchant_id": "test_brand"},
        )
        assert result == pytest.approx(0.08)


# ── Tests: gmv_lift_prior clipping ───────────────────────────────────────────

class TestGmvLiftClip:
    def test_clips_explosive_prior_to_max(self, registry):
        # high_aov_brand has gmv_lift_prior: 1.50 — must be clipped to 0.25
        result = registry.get_base_utility(
            "acquisition_efficiency_v1",
            {"action_id": "PAUSE_CHANNEL", "merchant_id": "high_aov_brand"},
        )
        assert result == pytest.approx(0.25)

    def test_normal_prior_not_clipped(self, registry):
        result = registry.get_base_utility(
            "acquisition_efficiency_v1",
            {"action_id": "PAUSE_CHANNEL", "merchant_id": "test_brand"},
        )
        assert result == pytest.approx(0.15)  # 0.15 < 0.25, no clip

    def test_flat_playbook_utility_also_clipped(self, tmp_playbook_dir, tmp_path):
        from src.decision_engine.layer2_decision.pillar1_kg.playbook_registry import PlaybookRegistry
        # Create a playbook with too-high expected_utility
        overutil = tmp_playbook_dir / "overutil.yaml"
        overutil.write_text(textwrap.dedent("""\
            playbook:
              id: overutil
              module: acquisition
              version: "1.0"
              description: "Test"
            triggers:
              - name: t
                msm_state: WATCH
            actions:
              - id: SOME_ACTION
                expected_utility: 0.99
            patterns: []
            constraints: []
        """))
        reg = PlaybookRegistry(playbook_dir=str(tmp_playbook_dir))
        reg.load_playbooks(str(tmp_playbook_dir))
        result = reg.get_base_utility("overutil", {"action_id": "SOME_ACTION"})
        assert result == pytest.approx(0.25)


# ── Tests: _flatten_dict ─────────────────────────────────────────────────────

class TestFlattenDict:
    def test_flattens_nested_dict(self):
        from src.decision_engine.layer2_decision.pillar1_kg.playbook_registry import _flatten_dict
        d = {"thresholds": {"cac_spike_ratio": 1.15, "calibration_status": "partner_prior"}}
        result = _flatten_dict(d)
        assert result["thresholds.cac_spike_ratio"] == "1.15"
        assert result["thresholds.calibration_status"] == "partner_prior"

    def test_flat_values_use_top_level_key(self):
        from src.decision_engine.layer2_decision.pillar1_kg.playbook_registry import _flatten_dict
        d = {"brand": "wandering_bear", "binding_version": "1.0"}
        result = _flatten_dict(d)
        assert result["brand"] == "wandering_bear"
        assert result["binding_version"] == "1.0"

    def test_all_values_are_strings(self):
        from src.decision_engine.layer2_decision.pillar1_kg.playbook_registry import _flatten_dict
        d = {"thresholds": {"ratio": 1.15, "count": 5, "flag": True}}
        result = _flatten_dict(d)
        for v in result.values():
            assert isinstance(v, str)


# ── Tests: render_brand_triggers ─────────────────────────────────────────────

class TestRenderBrandTriggers:
    def test_interpolates_threshold_variables(self, registry):
        meta_yaml = textwrap.dedent("""\
            triggers:
              - name: cac_spike
                condition: "cac_7d_vs_baseline > ${thresholds.cac_spike_ratio}"
                msm_state: WATCH
        """)
        result = registry.render_brand_triggers(meta_yaml, "test_brand", "acquisition_efficiency_v1")
        assert result is not None
        condition = result["triggers"][0]["condition"]
        # YAML parses 1.20 as float 1.2 (trailing zero dropped) — both forms are correct
        assert ("1.2" in condition or "1.20" in condition)
        assert "${thresholds" not in condition

    def test_undefined_variable_left_as_is(self, registry):
        meta_yaml = textwrap.dedent("""\
            triggers:
              - name: t
                condition: "${thresholds.undefined_key} > 0"
                msm_state: WATCH
        """)
        result = registry.render_brand_triggers(meta_yaml, "test_brand", "acquisition_efficiency_v1")
        assert result is not None
        # safe_substitute leaves undefined vars as-is
        assert "${thresholds.undefined_key}" in result["triggers"][0]["condition"]

    def test_returns_none_for_unknown_merchant(self, registry):
        result = registry.render_brand_triggers("triggers: []", "unknown_merchant", "pattern")
        assert result is None
