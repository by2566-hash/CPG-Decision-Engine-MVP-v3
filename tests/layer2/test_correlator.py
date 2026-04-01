"""Tests for Layer 2: Cross-Module Correlator.

Covers:
  - Suppression when both acquisition and conversion are DEGRADING
  - Suppression when retention CRITICAL + promotion WATCH
  - No suppression when conditions are not met
  - Suppressed candidates remain in list but are flagged
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.decision_engine.contracts import MerchantStateVector
from src.decision_engine.layer2_decision.cross_module_correlator import (
    CrossModuleCorrelator,
)


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


correlator = CrossModuleCorrelator()


class TestCorrelatorSuppression:
    def test_suppress_increase_budget_when_both_degrading(self):
        """INCREASE_AD_BUDGET suppressed when acquisition+conversion both DEGRADING."""
        msv = _make_msv(acq="DEGRADING", cvr="DEGRADING")
        candidates = [
            {"action_id": "INCREASE_AD_BUDGET", "module": "acquisition"},
            {"action_id": "SEND_REMINDER", "module": "retention"},
        ]
        result = correlator.correlate(msv, candidates)

        assert result[0]["suppressed"] is True
        assert "fix conversion first" in result[0]["suppression_reason"]
        assert result[1].get("suppressed", False) is False

    def test_suppress_high_discount_when_retention_critical_promotion_watch(self):
        """HIGH_DISCOUNT suppressed when retention CRITICAL + promotion WATCH."""
        msv = _make_msv(ret="CRITICAL", prm="WATCH")
        candidates = [
            {"action_id": "HIGH_DISCOUNT", "module": "promotion"},
            {"action_id": "SEND_REMINDER", "module": "retention"},
        ]
        result = correlator.correlate(msv, candidates)

        assert result[0]["suppressed"] is True
        assert "wait-for-sale" in result[0]["suppression_reason"]
        assert result[1].get("suppressed", False) is False

    def test_no_suppression_when_conditions_not_met(self):
        """No suppression when MSM state doesn't match any conflict rule."""
        msv = _make_msv(acq="HEALTHY", cvr="HEALTHY", ret="HEALTHY", prm="HEALTHY")
        candidates = [
            {"action_id": "INCREASE_AD_BUDGET", "module": "acquisition"},
            {"action_id": "HIGH_DISCOUNT", "module": "promotion"},
        ]
        result = correlator.correlate(msv, candidates)

        assert result[0].get("suppressed", False) is False
        assert result[1].get("suppressed", False) is False

    def test_suppressed_candidates_remain_in_list_but_flagged(self):
        """Suppressed candidates are flagged but NOT removed from the list."""
        msv = _make_msv(acq="DEGRADING", cvr="DEGRADING")
        candidates = [
            {"action_id": "INCREASE_AD_BUDGET", "module": "acquisition"},
            {"action_id": "REALLOCATE_BUDGET_UP", "module": "acquisition"},
            {"action_id": "SEND_REMINDER", "module": "retention"},
        ]
        result = correlator.correlate(msv, candidates)

        # All 3 candidates must remain in the list
        assert len(result) == 3

        # Both budget actions suppressed
        suppressed = correlator.get_suppressed_actions(result)
        assert "INCREASE_AD_BUDGET" in suppressed
        assert "REALLOCATE_BUDGET_UP" in suppressed
        assert "SEND_REMINDER" not in suppressed


class TestCorrelatorAtOrWorse:
    def test_rule_matches_worse_state(self):
        """Rule requiring DEGRADING also matches CRITICAL (at-or-worse)."""
        msv = _make_msv(acq="CRITICAL", cvr="CRITICAL")
        candidates = [
            {"action_id": "INCREASE_AD_BUDGET", "module": "acquisition"},
        ]
        result = correlator.correlate(msv, candidates)
        assert result[0]["suppressed"] is True

    def test_rule_does_not_match_lesser_state(self):
        """Rule requiring DEGRADING does NOT match WATCH."""
        msv = _make_msv(acq="WATCH", cvr="WATCH")
        candidates = [
            {"action_id": "INCREASE_AD_BUDGET", "module": "acquisition"},
        ]
        result = correlator.correlate(msv, candidates)
        assert result[0].get("suppressed", False) is False
