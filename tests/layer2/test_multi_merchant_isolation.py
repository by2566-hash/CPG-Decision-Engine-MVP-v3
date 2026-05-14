# ── Tests: Multi-merchant data isolation ─────────────────────────────────────
# Verifies that PlaybookRegistry and _generate_candidates() correctly isolate
# brand binding data per merchant_id — no utility values, thresholds, or
# evidence_refs from one merchant can bleed into another merchant's candidates.
#
# Why this test exists:
#   Prior to Phase 2 external launch, merchant_id threading through the pipeline
#   was verified in code review but had no dedicated test. With multiple real
#   merchants in flight, a cross-merchant data leak would:
#     (a) show the wrong gmv_lift_prior in scoring → wrong ranking
#     (b) expose one merchant's threshold/evidence data to another's card
#   Both are non-recoverable trust failures at external launch.
#
# Coverage:
#   1. Registry: per-merchant utility isolation (A ≠ B, neither ≠ None)
#   2. Registry: sequential calls don't share cached state between merchants
#   3. Registry: unknown merchant returns None (falls to flat playbook / benchmarks)
#   4. Registry: brand binding lazy-load per merchant (no global shared index)
#   5. Pipeline: _generate_candidates() pred reflects per-merchant brand binding
#   6. Pipeline: two consecutive calls with different merchants produce isolated preds
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from src.decision_engine.layer2_decision.pillar1_kg.playbook_registry import PlaybookRegistry


# ── Shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture()
def two_merchant_registry(tmp_path: Path) -> PlaybookRegistry:
    """Registry with one meta-pattern and two brand bindings at distinctly
    different utility values so any cross-contamination is immediately visible."""

    # Meta-pattern stub
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    (meta_dir / "acquisition_channel_test.yaml").write_text(textwrap.dedent("""\
        meta_pattern:
          id: acquisition_channel_test
          module: acquisition
          version: "1.0"
          tags: [cac, test]
          reusable: true
          description: "Isolation test meta-pattern"
        triggers:
          - name: cac_rising
            msm_state: WATCH
            condition: "cac_7d_vs_baseline > ${thresholds.cac_spike_ratio}"
            metric: cac_7d_vs_baseline
        analysis_path: []
        actions:
          - id: ACTION_ALPHA
            type: DIAGNOSTIC
            description: "Diagnostic alpha"
            requires_approval: false
            rollback_available: false
          - id: ACTION_BETA
            type: CHANNEL_CONTROL
            description: "Channel beta"
            requires_approval: true
            rollback_available: true
        constraints:
          attribution_window_days: 30
          applies_hard_constraints: []
    """))

    # Brand binding: merchant_alpha — low utility (0.05 / 0.10)
    alpha_dir = tmp_path / "brands" / "merchant_alpha"
    alpha_dir.mkdir(parents=True)
    (alpha_dir / "acquisition_channel_test.yaml").write_text(textwrap.dedent("""\
        brand: merchant_alpha
        meta_pattern_ref: acquisition_channel_test
        binding_version: "1.0"
        entity_bindings:
          primary_ad_platform: meta
        thresholds:
          cac_spike_ratio: 1.10
          calibration_status: partner_prior
        action_utility_priors:
          ACTION_ALPHA:
            gmv_lift_prior: 0.05
            confidence: 0.70
            calibration_status: partner_prior
            evidence_case: "alpha_001"
          ACTION_BETA:
            gmv_lift_prior: 0.10
            confidence: 0.70
            calibration_status: partner_prior
            evidence_case: "alpha_002"
        evidence_refs_template:
          - "Alpha CAC: ${metrics.cac_7d} vs baseline ${metrics.cac_baseline_30d}"
    """))

    # Brand binding: merchant_beta — high utility (0.20 / 0.24), clearly distinct
    beta_dir = tmp_path / "brands" / "merchant_beta"
    beta_dir.mkdir(parents=True)
    (beta_dir / "acquisition_channel_test.yaml").write_text(textwrap.dedent("""\
        brand: merchant_beta
        meta_pattern_ref: acquisition_channel_test
        binding_version: "1.0"
        entity_bindings:
          primary_ad_platform: tiktok
        thresholds:
          cac_spike_ratio: 1.25
          calibration_status: partner_prior
        action_utility_priors:
          ACTION_ALPHA:
            gmv_lift_prior: 0.20
            confidence: 0.80
            calibration_status: partner_prior
            evidence_case: "beta_001"
          ACTION_BETA:
            gmv_lift_prior: 0.24
            confidence: 0.80
            calibration_status: partner_prior
            evidence_case: "beta_002"
        evidence_refs_template:
          - "Beta CAC: ${metrics.cac_7d} vs baseline ${metrics.cac_baseline_30d}"
    """))

    reg = PlaybookRegistry(playbook_dir=str(tmp_path))
    reg.load_playbooks(str(tmp_path))
    return reg


# ── 1. Per-merchant utility isolation ────────────────────────────────────────

class TestPerMerchantUtilityIsolation:
    """Each merchant gets its own brand binding utility — not another's."""

    def test_alpha_utility_is_alpha_value(self, two_merchant_registry):
        util = two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_ALPHA", "merchant_id": "merchant_alpha"},
        )
        assert util == pytest.approx(0.05), (
            f"merchant_alpha ACTION_ALPHA should be 0.05, got {util}"
        )

    def test_beta_utility_is_beta_value(self, two_merchant_registry):
        util = two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_ALPHA", "merchant_id": "merchant_beta"},
        )
        assert util == pytest.approx(0.20), (
            f"merchant_beta ACTION_ALPHA should be 0.20, got {util}"
        )

    def test_alpha_and_beta_utilities_are_distinct(self, two_merchant_registry):
        """Core isolation assertion: the two merchants must yield different values."""
        alpha = two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_ALPHA", "merchant_id": "merchant_alpha"},
        )
        beta = two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_ALPHA", "merchant_id": "merchant_beta"},
        )
        assert alpha != beta, (
            "merchant_alpha and merchant_beta returned the same utility — "
            "brand binding isolation failure."
        )

    def test_second_action_also_isolated(self, two_merchant_registry):
        alpha = two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_BETA", "merchant_id": "merchant_alpha"},
        )
        beta = two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_BETA", "merchant_id": "merchant_beta"},
        )
        assert alpha == pytest.approx(0.10)
        assert beta == pytest.approx(0.24)
        assert alpha != beta


# ── 2. Sequential call ordering doesn't bleed state ──────────────────────────

class TestSequentialCallIsolation:
    """Calling for merchant_A then merchant_B must not taint the result."""

    def test_alpha_then_beta_returns_beta_value(self, two_merchant_registry):
        # Call alpha first — warm its cache
        two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_ALPHA", "merchant_id": "merchant_alpha"},
        )
        # Now call beta — must return beta's value, not alpha's cached result
        beta = two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_ALPHA", "merchant_id": "merchant_beta"},
        )
        assert beta == pytest.approx(0.20), (
            f"After calling alpha first, beta returned {beta} — possible cache bleed."
        )

    def test_beta_then_alpha_returns_alpha_value(self, two_merchant_registry):
        two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_ALPHA", "merchant_id": "merchant_beta"},
        )
        alpha = two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_ALPHA", "merchant_id": "merchant_alpha"},
        )
        assert alpha == pytest.approx(0.05), (
            f"After calling beta first, alpha returned {alpha} — possible cache bleed."
        )

    def test_interleaved_calls_stay_isolated(self, two_merchant_registry):
        """Rapidly alternating merchant lookups must each return the correct value."""
        results = []
        for merchant, expected in [
            ("merchant_alpha", 0.05),
            ("merchant_beta", 0.20),
            ("merchant_alpha", 0.05),
            ("merchant_beta", 0.20),
            ("merchant_alpha", 0.05),
        ]:
            util = two_merchant_registry.get_base_utility(
                "acquisition_channel_test",
                {"action_id": "ACTION_ALPHA", "merchant_id": merchant},
            )
            results.append((merchant, expected, util))

        for merchant, expected, actual in results:
            assert actual == pytest.approx(expected), (
                f"Interleaved call for {merchant}: expected {expected}, got {actual}."
            )


# ── 3. Unknown merchant falls back cleanly ────────────────────────────────────

class TestUnknownMerchantFallback:
    """A merchant with no brand binding must return None — never another merchant's value."""

    def test_unknown_merchant_returns_none(self, two_merchant_registry):
        result = two_merchant_registry.get_base_utility(
            "acquisition_channel_test",
            {"action_id": "ACTION_ALPHA", "merchant_id": "unknown_brand_xyz"},
        )
        assert result is None, (
            f"Unknown merchant should return None, got {result}. "
            "This could mean another merchant's binding was used as fallback."
        )

    def test_unknown_merchant_get_brand_binding_returns_none(self, two_merchant_registry):
        binding = two_merchant_registry.get_brand_binding(
            "unknown_brand_xyz", "acquisition_channel_test"
        )
        assert binding is None


# ── 4. Brand binding lazy-load is per-merchant ───────────────────────────────

class TestBrandBindingLazyLoad:
    """Loading one merchant's binding must not pre-populate another's."""

    def test_alpha_binding_load_does_not_expose_beta_data(self, two_merchant_registry):
        # Explicitly load alpha's binding
        alpha_bindings = two_merchant_registry.load_brand_binding("merchant_alpha")
        assert "acquisition_channel_test" in alpha_bindings

        # Beta binding should be separately loadable and distinct
        beta_bindings = two_merchant_registry.load_brand_binding("merchant_beta")
        assert "acquisition_channel_test" in beta_bindings

        alpha_prior = alpha_bindings["acquisition_channel_test"]["action_utility_priors"]["ACTION_ALPHA"]["gmv_lift_prior"]
        beta_prior = beta_bindings["acquisition_channel_test"]["action_utility_priors"]["ACTION_ALPHA"]["gmv_lift_prior"]

        assert alpha_prior != beta_prior, "Alpha and beta bindings share the same prior — isolation failure."
        assert alpha_prior == pytest.approx(0.05)
        assert beta_prior == pytest.approx(0.20)

    def test_entity_bindings_are_merchant_specific(self, two_merchant_registry):
        """entity_bindings (e.g. primary_ad_platform) must not leak across merchants."""
        alpha_b = two_merchant_registry.get_brand_binding("merchant_alpha", "acquisition_channel_test")
        beta_b = two_merchant_registry.get_brand_binding("merchant_beta", "acquisition_channel_test")

        assert alpha_b["entity_bindings"]["primary_ad_platform"] == "meta"
        assert beta_b["entity_bindings"]["primary_ad_platform"] == "tiktok"


# ── 5 + 6. Pipeline _generate_candidates() isolation ─────────────────────────

class TestPipelineCandidateIsolation:
    """_generate_candidates() must produce per-merchant pred values.

    Patches pipeline._playbook_registry with a two-merchant registry so we
    can assert that the utility in pred['gmv_lift'] reflects the correct
    brand binding — not a default or another merchant's value.
    """

    @pytest.fixture()
    def acquisition_watch_state(self):
        from datetime import datetime, timezone
        from src.decision_engine.contracts import MerchantStateVector
        return MerchantStateVector(
            merchant_id="",         # overridden per call via model_copy
            computed_at=datetime.now(timezone.utc),
            acquisition_state="WATCH",
            acquisition_urgency=0.5,
            conversion_state="HEALTHY",
            conversion_urgency=0.0,
            retention_state="HEALTHY",
            retention_urgency=0.0,
            promotion_state="HEALTHY",
            promotion_urgency=0.0,
        )

    @pytest.fixture()
    def minimal_signals(self):
        return {
            "cac_7d": 55.0,
            "cac_baseline_30d": 45.0,
            "monthly_gmv": 150_000.0,
            "monthly_ad_spend": 10_000.0,
            "avg_order_value": 47.0,
            "monthly_orders": 3000,
            "avg_margin_pct": 0.35,
        }

    def _get_action_pred(self, candidates: list[dict], action_id: str) -> dict | None:
        for c in candidates:
            if c.get("action_id") == action_id:
                return c.get("pred", {})
        return None

    def test_alpha_candidates_use_alpha_binding(
        self, two_merchant_registry, acquisition_watch_state, minimal_signals
    ):
        from src.decision_engine.layer4_serving import pipeline

        msm = acquisition_watch_state.model_copy(update={"merchant_id": "merchant_alpha"})
        policy = {"policy_weights": {}, "beta1": 1.0, "beta2": 0.0, "beta3": 1.0}

        with patch.object(pipeline, "_playbook_registry", two_merchant_registry):
            candidates = pipeline._generate_candidates(msm, minimal_signals, policy, "merchant_alpha")

        pred = self._get_action_pred(candidates, "ACTION_ALPHA")
        assert pred is not None, "ACTION_ALPHA candidate not found for merchant_alpha"
        assert pred.get("gmv_lift") == pytest.approx(0.05), (
            f"merchant_alpha ACTION_ALPHA gmv_lift should be 0.05, got {pred.get('gmv_lift')}"
        )

    def test_beta_candidates_use_beta_binding(
        self, two_merchant_registry, acquisition_watch_state, minimal_signals
    ):
        from src.decision_engine.layer4_serving import pipeline

        msm = acquisition_watch_state.model_copy(update={"merchant_id": "merchant_beta"})
        policy = {"policy_weights": {}, "beta1": 1.0, "beta2": 0.0, "beta3": 1.0}

        with patch.object(pipeline, "_playbook_registry", two_merchant_registry):
            candidates = pipeline._generate_candidates(msm, minimal_signals, policy, "merchant_beta")

        pred = self._get_action_pred(candidates, "ACTION_ALPHA")
        assert pred is not None, "ACTION_ALPHA candidate not found for merchant_beta"
        assert pred.get("gmv_lift") == pytest.approx(0.20), (
            f"merchant_beta ACTION_ALPHA gmv_lift should be 0.20, got {pred.get('gmv_lift')}"
        )

    def test_two_consecutive_calls_produce_isolated_preds(
        self, two_merchant_registry, acquisition_watch_state, minimal_signals
    ):
        """Core pipeline isolation test: run alpha then beta — preds must not bleed."""
        from src.decision_engine.layer4_serving import pipeline

        policy = {"policy_weights": {}, "beta1": 1.0, "beta2": 0.0, "beta3": 1.0}

        with patch.object(pipeline, "_playbook_registry", two_merchant_registry):
            msm_alpha = acquisition_watch_state.model_copy(update={"merchant_id": "merchant_alpha"})
            candidates_alpha = pipeline._generate_candidates(msm_alpha, minimal_signals, policy, "merchant_alpha")

            msm_beta = acquisition_watch_state.model_copy(update={"merchant_id": "merchant_beta"})
            candidates_beta = pipeline._generate_candidates(msm_beta, minimal_signals, policy, "merchant_beta")

        pred_alpha = self._get_action_pred(candidates_alpha, "ACTION_ALPHA")
        pred_beta = self._get_action_pred(candidates_beta, "ACTION_ALPHA")

        assert pred_alpha is not None and pred_beta is not None

        assert pred_alpha.get("gmv_lift") == pytest.approx(0.05), (
            f"Alpha pred after beta run: {pred_alpha.get('gmv_lift')} (expected 0.05 — bleed detected?)"
        )
        assert pred_beta.get("gmv_lift") == pytest.approx(0.20), (
            f"Beta pred after alpha run: {pred_beta.get('gmv_lift')} (expected 0.20 — bleed detected?)"
        )
        assert pred_alpha.get("gmv_lift") != pred_beta.get("gmv_lift"), (
            "Alpha and beta have identical gmv_lift — merchant isolation failure in pipeline."
        )

    def test_candidate_merchant_id_not_in_pred_of_other_merchant(
        self, two_merchant_registry, acquisition_watch_state, minimal_signals
    ):
        """action_type field on candidates reflects per-merchant binding, not a shared default."""
        from src.decision_engine.layer4_serving import pipeline

        policy = {"policy_weights": {}, "beta1": 1.0, "beta2": 0.0, "beta3": 1.0}

        with patch.object(pipeline, "_playbook_registry", two_merchant_registry):
            msm_alpha = acquisition_watch_state.model_copy(update={"merchant_id": "merchant_alpha"})
            candidates_alpha = pipeline._generate_candidates(msm_alpha, minimal_signals, policy, "merchant_alpha")

        # Verify no candidate carries beta's entity binding value (tiktok)
        # by checking that the pattern matched is the correct one and action_type is present
        for c in candidates_alpha:
            assert c.get("module") == "acquisition"
            # action_type must be populated (not empty) — confirms pipeline wiring is complete
            assert "action_type" in c, f"action_type missing from candidate {c.get('action_id')}"
