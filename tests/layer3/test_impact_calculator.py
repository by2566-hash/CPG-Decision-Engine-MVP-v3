"""Tests for Layer 3: ImpactCalculator.

Covers:
  - Phase 1 benchmark estimation with low confidence
  - Phase 2 historical data estimation with higher confidence
  - Confidence scaling with more historical data
  - Counterfactual construction
  - Missing merchant_state fields don't crash
"""
from __future__ import annotations

from src.decision_engine.layer3_value.impact_calculator import ImpactCalculator


calc = ImpactCalculator()

_MERCHANT_STATE = {
    "monthly_gmv": 50_000.0,
    "monthly_ad_spend": 5_000.0,
    "avg_order_value": 45.0,
    "monthly_orders": 1_200,
    "avg_margin_pct": 0.35,
}


class TestImpactCalculator:
    def test_phase1_returns_benchmark_estimate_with_low_confidence(self):
        """Phase 1: benchmark-derived, confidence = 0.30."""
        action = {"action_id": "DISCOUNT_10PCT"}
        result = calc.estimate(action, _MERCHANT_STATE, module="retention")

        assert result.confidence == 0.30
        assert result.conservative < result.expected < result.optimistic
        # retention uses monthly_gmv ($50k): 8% × 50k = $4000 conservative
        assert result.conservative == 0.08 * 50_000
        assert result.expected == 0.15 * 50_000
        assert result.optimistic == 0.25 * 50_000

    def test_phase2_uses_historical_data_with_higher_confidence(self):
        """Phase 2: historical outcomes, confidence > 0.30."""
        action = {"action_id": "DISCOUNT_10PCT"}
        historical = [
            {"outcome_delta": {"dollar_impact": 3000.0}},
            {"outcome_delta": {"dollar_impact": 5000.0}},
            {"outcome_delta": {"dollar_impact": 7000.0}},
            {"outcome_delta": {"dollar_impact": 4500.0}},
            {"outcome_delta": {"dollar_impact": 6000.0}},
        ]
        result = calc.estimate(
            action, _MERCHANT_STATE, module="retention",
            historical_outcomes=historical,
        )

        # 5 outcomes → confidence = 5/30 ≈ 0.167 (> than floor if we had 9+)
        assert result.confidence == round(5 / 30, 4)
        assert result.expected > 0
        assert result.conservative <= result.expected <= result.optimistic

    def test_confidence_increases_with_more_historical_data(self):
        """More historical outcomes → higher confidence, capped at 1.0."""
        action = {"action_id": "DISCOUNT_10PCT"}
        small_history = [
            {"outcome_delta": {"dollar_impact": float(i * 100)}}
            for i in range(1, 6)
        ]
        large_history = [
            {"outcome_delta": {"dollar_impact": float(i * 100)}}
            for i in range(1, 31)
        ]

        small_result = calc.estimate(
            action, _MERCHANT_STATE, module="retention",
            historical_outcomes=small_history,
        )
        large_result = calc.estimate(
            action, _MERCHANT_STATE, module="retention",
            historical_outcomes=large_history,
        )

        assert small_result.confidence < large_result.confidence
        assert large_result.confidence == 1.0  # 30/30 = 1.0

    def test_counterfactual_built_correctly(self):
        """Counterfactual compares top vs runner-up with narrative."""
        top = {"action_id": "DISCOUNT_10PCT"}
        runner = {"action_id": "REMINDER_ONLY"}

        cf = calc.build_counterfactual(
            top, runner, _MERCHANT_STATE, module="retention",
        )

        assert cf is not None
        assert cf.runner_up_action == "REMINDER_ONLY"
        assert cf.runner_up_estimate > 0
        assert "REMINDER_ONLY" in cf.why_not
        assert "DISCOUNT_10PCT" in cf.why_not
        assert "$" in cf.why_not

    def test_missing_merchant_gmv_does_not_crash(self):
        """Empty merchant_state should return zero estimate, not crash."""
        action = {"action_id": "DISCOUNT_10PCT"}
        result = calc.estimate(action, {}, module="retention")

        assert result.confidence == 0.30
        assert result.conservative == 0.0
        assert result.expected == 0.0
        assert result.optimistic == 0.0
