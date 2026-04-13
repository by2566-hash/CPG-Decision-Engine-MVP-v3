"""Tests for Layer 2: Decision Verifier and Scoring integration.

Covers:
  - DecisionVerifier: 5 unit tests
  - Scoring integration: 2 tests (failed verification → -inf, urgency boost)
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.decision_engine.contracts import MerchantStateVector, PolicyDecision
from src.decision_engine.layer2_decision.pillar3_llm.decision_verifier import (
    DecisionVerifier,
)
from src.decision_engine.layer2_decision.scoring import ScoringEngine

# Shorthand for tests that only care about scoring logic, not constraint checking.
# Explicitly marks constraints as passed — do not rely on scoring default behavior.
_CONSTRAINTS_PASS = PolicyDecision(eligible=True, hard_reject=False, risk_penalty=0.0, violations=[])


def _make_msv(
    acq: str = "HEALTHY",
    cvr: str = "HEALTHY",
    ret: str = "HEALTHY",
    prm: str = "HEALTHY",
) -> MerchantStateVector:
    return MerchantStateVector(
        merchant_id="m_test",
        computed_at=datetime.now(timezone.utc),
        acquisition_state=acq,
        conversion_state=cvr,
        retention_state=ret,
        promotion_state=prm,
    )


verifier = DecisionVerifier()


# ═══════════════════════════════════════════════════════════════════
# DecisionVerifier unit tests
# ═══════════════════════════════════════════════════════════════════

class TestDecisionVerifier:
    def test_verify_passes_all_conditions_met(self):
        """All 4 gates pass → all_passed = True."""
        msv = _make_msv(ret="DEGRADING")
        candidate = {
            "action_id": "SEND_REMINDER",
            "module": "retention",
            "post_discount_margin": 0.25,
        }
        chain = verifier.verify(
            msm_state=msv,
            candidate=candidate,
            policy={},
            constraints_result=(True, []),
            all_candidates=[candidate],
        )
        assert chain.all_passed is True
        assert chain.msm_trigger.passed is True
        assert chain.margin_gate.passed is True
        assert chain.inventory_gate.passed is True
        assert chain.conflict_check.passed is True

    def test_verify_fails_wrong_module_for_healthy_dimension(self):
        """Retention module fires when retention is HEALTHY → msm_trigger fails."""
        msv = _make_msv(ret="HEALTHY")
        candidate = {
            "action_id": "SEND_REMINDER",
            "module": "retention",
        }
        chain = verifier.verify(
            msm_state=msv,
            candidate=candidate,
            policy={},
            constraints_result=(True, []),
            all_candidates=[candidate],
        )
        assert chain.all_passed is False
        assert chain.msm_trigger.passed is False
        assert "HEALTHY" in chain.msm_trigger.reason
        assert "wasteful" in chain.msm_trigger.reason

    def test_verify_fails_margin_gate_violated(self):
        """Post-discount margin below 15% floor → margin_gate fails."""
        msv = _make_msv(ret="DEGRADING")
        candidate = {
            "action_id": "DISCOUNT_10PCT",
            "module": "retention",
            "post_discount_margin": 0.10,  # below 0.15 floor
        }
        chain = verifier.verify(
            msm_state=msv,
            candidate=candidate,
            policy={},
            constraints_result=(True, []),
            all_candidates=[candidate],
        )
        assert chain.all_passed is False
        assert chain.margin_gate.passed is False
        assert chain.margin_gate.value == 0.10
        assert chain.margin_gate.threshold == 0.15

    def test_verify_fails_inventory_too_low(self):
        """Discount action with inventory_days_p10 < 5 → inventory_gate fails."""
        msv = _make_msv(ret="DEGRADING")
        candidate = {
            "action_id": "DISCOUNT_10PCT",
            "module": "retention",
            "post_discount_margin": 0.25,
            "inventory_days_p10": 3,  # below 5-day minimum
        }
        chain = verifier.verify(
            msm_state=msv,
            candidate=candidate,
            policy={},
            constraints_result=(True, []),
            all_candidates=[candidate],
        )
        assert chain.all_passed is False
        assert chain.inventory_gate.passed is False
        assert chain.inventory_gate.value == 3.0

    def test_verify_fails_conflict_check_suppressed(self):
        """Suppressed candidate → conflict_check fails."""
        msv = _make_msv(acq="DEGRADING")
        candidate = {
            "action_id": "INCREASE_AD_BUDGET",
            "module": "acquisition",
            "suppressed": True,
            "suppression_reason": "CAC rising + CVR dropping",
        }
        chain = verifier.verify(
            msm_state=msv,
            candidate=candidate,
            policy={},
            constraints_result=(True, []),
            all_candidates=[candidate],
        )
        assert chain.all_passed is False
        assert chain.conflict_check.passed is False
        assert "Suppressed" in chain.conflict_check.reason


# ═══════════════════════════════════════════════════════════════════
# Scoring integration tests
# ═══════════════════════════════════════════════════════════════════

class TestScoringIntegration:
    def test_failed_verification_gives_neg_inf_score(self):
        """Failed verification → final_score = -inf, eligible = False."""
        msv = _make_msv(ret="HEALTHY")
        policy = {
            "policy_weights": {
                "gmv_lift": 0.40, "margin_lift": 0.30,
                "inventory_risk_reduction": 0.15, "retention_lift": 0.15,
            },
            "risk_budget": {"max_margin_drop_pct": 0.05, "max_refund_rate_increase_pct": 0.02},
        }
        candidates = [
            {
                "action_id": "SEND_REMINDER",
                "module": "retention",  # fires on HEALTHY → should fail msm_trigger
                "pred": {"gmv_lift": 0.10, "margin_lift": 0.02,
                         "inventory_risk_reduction": 0.05, "retention_lift": 0.08},
            },
        ]
        engine = ScoringEngine()
        ranked = engine.rank_actions(msv, candidates, policy)

        assert len(ranked) == 1
        assert ranked[0]["eligible"] is False
        assert ranked[0]["final_score"] == float("-inf")
        assert ranked[0]["verification_chain"]["all_passed"] is False

    def test_urgency_above_08_boosts_ranking(self):
        """Candidate with urgency > 0.8 should score higher than same without urgency."""
        msv = _make_msv(ret="DEGRADING", prm="DEGRADING")
        policy = {
            "policy_weights": {
                "gmv_lift": 0.40, "margin_lift": 0.30,
                "inventory_risk_reduction": 0.15, "retention_lift": 0.15,
            },
            "risk_budget": {"max_margin_drop_pct": 0.05, "max_refund_rate_increase_pct": 0.02},
        }
        pred = {
            "gmv_lift": 0.10, "margin_lift": 0.02,
            "inventory_risk_reduction": 0.05, "retention_lift": 0.08,
        }
        candidates = [
            {
                "action_id": "SEND_REMINDER_HIGH",
                "module": "retention",
                "urgency_score": 0.9,  # above 0.8 → gets boost
                "pred": pred,
                "constraints_result": _CONSTRAINTS_PASS,  # explicit pass — not a default
            },
            {
                "action_id": "SEND_REMINDER_LOW",
                "module": "promotion",
                "urgency_score": 0.3,  # below 0.8 → no boost
                "pred": pred,
                "constraints_result": _CONSTRAINTS_PASS,  # explicit pass — not a default
            },
        ]
        engine = ScoringEngine()
        ranked = engine.rank_actions(msv, candidates, policy)

        high_urgency = next(r for r in ranked if r["action_id"] == "SEND_REMINDER_HIGH")
        low_urgency = next(r for r in ranked if r["action_id"] == "SEND_REMINDER_LOW")

        assert high_urgency["final_score"] > low_urgency["final_score"]
        assert high_urgency["urgency_score"] == 0.9
