# ── Layer 2/3 Tests · CPG Hard Constraints (legacy interface) ────────────
# Tests for ConstraintEngine using the canonical check_all(candidate, signals, policy)
# → PolicyDecision interface. Covers blocking behavior and ScoringEngine integration.
# ───────────────────────────────────────────────────────────────────────────
from datetime import datetime, timezone

import pytest

from src.decision_engine.layer3_value.constraints import ConstraintEngine
from src.decision_engine.layer2_decision.scoring import ScoringEngine
from src.decision_engine.contracts import MerchantStateVector, PolicyDecision

_POLICY = {}  # policy not yet used by constraints — placeholder


class TestConstraints:
    """Tests for ConstraintEngine — CPG hard constraints."""

    def test_margin_floor_blocks_deep_discount(self):
        """Discount that leaves post-margin below 0.15 must be blocked."""
        engine = ConstraintEngine()

        # margin_pct=0.10, DISCOUNT_10PCT → post = 0.00 < 0.15
        candidate = {"action_id": "DISCOUNT_10PCT"}
        pd = engine.check_all(candidate, {"margin_pct": 0.10}, _POLICY)
        assert not pd.eligible
        assert any("margin_floor" in v for v in pd.violations)

        # margin_pct=0.20, DISCOUNT_15PCT → post = 0.05 < 0.15
        candidate2 = {"action_id": "DISCOUNT_15PCT"}
        pd2 = engine.check_all(candidate2, {"margin_pct": 0.20}, _POLICY)
        assert not pd2.eligible
        assert any("margin_floor" in v for v in pd2.violations)

        # margin_pct=0.30, DISCOUNT_10PCT → post = 0.20 >= 0.15 → pass
        candidate_ok = {"action_id": "DISCOUNT_10PCT"}
        pd_ok = engine.check_all(candidate_ok, {"margin_pct": 0.30}, _POLICY)
        assert not any("margin_floor" in v for v in pd_ok.violations)

        # Non-discount action always passes margin check
        candidate_nd = {"action_id": "REMINDER_ONLY"}
        pd_nd = engine.check_all(candidate_nd, {"margin_pct": 0.05}, _POLICY)
        assert not any("margin_floor" in v for v in pd_nd.violations)

    def test_discount_last_resort_requires_reminder(self):
        """DISCOUNT must be preceded by a REMINDER."""
        engine = ConstraintEngine()

        # last_action_type is MERCHANDISING (not REMINDER) → fail
        candidate = {"action_id": "DISCOUNT_10PCT"}
        pd = engine.check_all(
            candidate,
            {"last_action_type": "MERCHANDISING", "days_since_last_action": 3},
            _POLICY,
        )
        assert not pd.eligible
        assert any("discount_last_resort" in v for v in pd.violations)

        # last_action_type is REMINDER within 7 days → pass
        pd_ok = engine.check_all(
            candidate,
            {"last_action_type": "REMINDER", "days_since_last_action": 3},
            _POLICY,
        )
        assert not any("discount_last_resort" in v for v in pd_ok.violations)

        # Missing last_action_type → pass (Phase 1 data gap)
        pd_missing = engine.check_all(candidate, {}, _POLICY)
        assert not any("discount_last_resort" in v for v in pd_missing.violations)

    def test_incrementality_required_for_discount(self):
        """No discount without promo_incrementality >= 0.30."""
        engine = ConstraintEngine()

        # promo_incrementality = 0.10 (below threshold) → fail
        candidate = {"action_id": "DISCOUNT_10PCT"}
        pd = engine.check_all(candidate, {"promo_incrementality": 0.10}, _POLICY)
        assert not pd.eligible
        assert any("incrementality" in v for v in pd.violations)

        # promo_incrementality = 0.40 → pass
        pd_ok = engine.check_all(candidate, {"promo_incrementality": 0.40}, _POLICY)
        assert not any("incrementality" in v for v in pd_ok.violations)

        # Missing promo_incrementality → pass (Phase 1 data gap)
        pd_missing = engine.check_all(candidate, {}, _POLICY)
        assert not any("incrementality" in v for v in pd_missing.violations)

    def test_cold_prospect_gate_blocks_discount(self):
        """First-time visitors must not receive discount offers."""
        engine = ConstraintEngine()

        # customer_orders_count=0 → fail
        candidate = {"action_id": "DISCOUNT_10PCT"}
        pd = engine.check_all(candidate, {"customer_orders_count": 0}, _POLICY)
        assert not pd.eligible
        assert any("cold_prospect_gate" in v for v in pd.violations)

        # customer_orders_count=3 → pass
        pd_ok = engine.check_all(candidate, {"customer_orders_count": 3}, _POLICY)
        assert not any("cold_prospect_gate" in v for v in pd_ok.violations)

        # Missing customer_orders_count → pass (Phase 1 default 999)
        pd_missing = engine.check_all(candidate, {}, _POLICY)
        assert not any("cold_prospect_gate" in v for v in pd_missing.violations)

    def test_attribution_windows(self):
        """Correct attribution windows per module."""
        engine = ConstraintEngine()
        assert engine.get_attribution_window("retention") == 7
        assert engine.get_attribution_window("acquisition") == 30
        assert engine.get_attribution_window("promotion") == 14
        assert engine.get_attribution_window("conversion") == 0

    def test_constraints_cannot_be_overridden(self):
        """Hard constraint violations give final_score=-inf regardless of ML/policy weights.

        Even a candidate with maximum predicted utility gets -inf score
        when it violates a CPG hard constraint.
        """
        scoring = ScoringEngine()
        msm_state = MerchantStateVector(
            merchant_id="test_merchant",
            computed_at=datetime.now(timezone.utc),
            retention_state="DEGRADING",
            acquisition_state="HEALTHY",
            conversion_state="HEALTHY",
            promotion_state="HEALTHY",
        )

        # Constraint violation as PolicyDecision (as pipeline now sets it)
        violation = "margin_floor:post_discount_margin_0.10_below_0.15"
        candidate = {
            "action_id": "DISCOUNT_10PCT",
            "module": "retention",
            "msm_dimension": "retention",
            "urgency_score": 0.5,
            "pred": {
                "gmv_lift": 1.0,
                "margin_lift": 1.0,
                "retention_lift": 1.0,
                "inventory_risk_reduction": 1.0,
            },
            "action_family": "DISCOUNT",
            "signals": {},
            "constraints_result": PolicyDecision(
                eligible=False,
                hard_reject=True,
                risk_penalty=3.0,
                violations=[violation],
            ),
        }

        policy = {
            "policy_version": "test_v1",
            "policy_weights": {
                "gmv_lift": 0.4,
                "margin_lift": 0.3,
                "inventory_risk_reduction": 0.2,
                "retention_lift": 0.1,
            },
            "risk_budget": {},
            "beta1": 0.65,
            "beta2": 0.25,
            "beta3": 0.10,
        }

        ranked = scoring.rank_actions(
            msm_state=msm_state,
            candidates=[candidate],
            policy=policy,
        )

        assert len(ranked) == 1
        assert ranked[0]["final_score"] == float("-inf"), (
            "Constraint violation must give -inf score regardless of utility"
        )
        assert ranked[0]["eligible"] is False
        assert violation in ranked[0]["violations"]
