# ── Layer 3 · Value Intelligence — Impact Calculator ──────────────────────
# Estimates dollar impact with confidence interval:
#   { conservative, expected, optimistic, confidence }
#
# Phase 1: Industry CPG benchmarks as prior (confidence = settings.impact_confidence_floor)
# Phase 2+: Real WSM outcome data replaces benchmarks (confidence scales with data)
#
# Dollar conversion per module:
#   retention:   benchmark_pct × monthly_gmv
#   acquisition: benchmark_pct × monthly_ad_spend
#   conversion:  benchmark_pct × avg_order_value × monthly_orders
#   promotion:   benchmark_pct × monthly_gmv × avg_margin_pct
#
# Reference: V0/recommendation_scorer.py (add $ impact proxy)
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
import statistics

from ..config import settings
from ..contracts import Counterfactual, ImpactEstimate

log = logging.getLogger(__name__)


class ImpactCalculator:
    """Estimates dollar impact of recommended actions."""

    # Phase 1: public CPG industry benchmarks as prior
    # Phase 2+: replaced by WSM outcome data
    INDUSTRY_BENCHMARKS: dict[str, dict[str, dict[str, float]]] = {
        "retention": {
            "DISCOUNT_10PCT": {"lift_pct_low": 0.08, "lift_pct_mid": 0.15, "lift_pct_high": 0.25},
            "REMINDER_ONLY":  {"lift_pct_low": 0.03, "lift_pct_mid": 0.08, "lift_pct_high": 0.12},
            "SUPPRESS":       {"lift_pct_low": 0.00, "lift_pct_mid": 0.00, "lift_pct_high": 0.00},
        },
        "acquisition": {
            "REALLOCATE_BUDGET": {"cac_reduction_low": 0.05, "cac_reduction_mid": 0.12, "cac_reduction_high": 0.20},
            "PAUSE_CHANNEL":     {"cac_reduction_low": 0.08, "cac_reduction_mid": 0.15, "cac_reduction_high": 0.25},
        },
        "conversion": {
            "REORDER_SHELF":  {"cvr_lift_low": 0.05, "cvr_lift_mid": 0.10, "cvr_lift_high": 0.18},
            "BUNDLE_SUGGEST": {"aov_lift_low": 0.08, "aov_lift_mid": 0.15, "aov_lift_high": 0.22},
        },
        "promotion": {
            "ROTATE_OFFER":  {"margin_lift_low": 0.02, "margin_lift_mid": 0.05, "margin_lift_high": 0.08},
            "HOLD_DISCOUNT": {"margin_lift_low": 0.03, "margin_lift_mid": 0.06, "margin_lift_high": 0.10},
        },
    }

    def estimate(
        self,
        action: dict,
        merchant_state: dict,
        module: str,
        historical_outcomes: list[dict] | None = None,
    ) -> ImpactEstimate:
        """Compute impact estimate: { conservative, expected, optimistic, confidence }.

        Phase 1 (historical_outcomes is None or empty):
          Use INDUSTRY_BENCHMARKS as prior.
          confidence = settings.impact_confidence_floor (0.30)

        Phase 2+ (historical_outcomes provided):
          Use actual WSM outcome_delta from similar past actions.
          confidence = min(1.0, len(historical_outcomes) / 30)
        """
        if historical_outcomes:
            return self._estimate_from_history(historical_outcomes)
        return self._estimate_from_benchmarks(action, merchant_state, module)

    def _estimate_from_benchmarks(
        self,
        action: dict,
        merchant_state: dict,
        module: str,
    ) -> ImpactEstimate:
        """Phase 1: benchmark-derived estimate with low confidence."""
        action_id = action.get("action_id", "")
        module_benchmarks = self.INDUSTRY_BENCHMARKS.get(module, {})
        bench = module_benchmarks.get(action_id, {})

        if not bench:
            # Unknown action — return zero estimate
            return ImpactEstimate(confidence=settings.impact_confidence_floor)

        # Extract low/mid/high percentages from benchmark keys
        values = list(bench.values())
        pct_low = values[0] if len(values) > 0 else 0.0
        pct_mid = values[1] if len(values) > 1 else 0.0
        pct_high = values[2] if len(values) > 2 else 0.0

        # Dollar conversion: benchmark_pct × relevant merchant metric
        base_dollars = self._get_dollar_base(merchant_state, module)

        return ImpactEstimate(
            conservative=round(pct_low * base_dollars, 2),
            expected=round(pct_mid * base_dollars, 2),
            optimistic=round(pct_high * base_dollars, 2),
            confidence=settings.impact_confidence_floor,
        )

    def _estimate_from_history(
        self,
        historical_outcomes: list[dict],
    ) -> ImpactEstimate:
        """Phase 2+: outcome-derived estimate with scaled confidence."""
        deltas = [
            h.get("outcome_delta", {}).get("dollar_impact", 0.0)
            for h in historical_outcomes
        ]
        deltas = [d for d in deltas if d != 0.0] or [0.0]

        sorted_deltas = sorted(deltas)
        n = len(sorted_deltas)

        # Percentile-based: conservative=p25, expected=p50, optimistic=p75
        conservative = sorted_deltas[max(0, n // 4 - 1)] if n >= 4 else sorted_deltas[0]
        expected = statistics.median(sorted_deltas)
        optimistic = sorted_deltas[min(n - 1, 3 * n // 4)] if n >= 4 else sorted_deltas[-1]

        confidence = min(1.0, len(historical_outcomes) / 30)

        return ImpactEstimate(
            conservative=round(conservative, 2),
            expected=round(expected, 2),
            optimistic=round(optimistic, 2),
            confidence=round(confidence, 4),
        )

    def _get_dollar_base(self, merchant_state: dict, module: str) -> float:
        """Get the dollar base for impact conversion by module.

        retention:   monthly_gmv
        acquisition: monthly_ad_spend
        conversion:  avg_order_value × monthly_orders
        promotion:   monthly_gmv × avg_margin_pct
        """
        if module == "retention":
            return float(merchant_state.get("monthly_gmv", 0))
        elif module == "acquisition":
            return float(merchant_state.get("monthly_ad_spend", 0))
        elif module == "conversion":
            aov = float(merchant_state.get("avg_order_value", 0))
            orders = float(merchant_state.get("monthly_orders", 0))
            return aov * orders
        elif module == "promotion":
            gmv = float(merchant_state.get("monthly_gmv", 0))
            margin = float(merchant_state.get("avg_margin_pct", 0))
            return gmv * margin
        return 0.0

    def build_counterfactual(
        self,
        top_action: dict,
        runner_up: dict,
        merchant_state: dict,
        module: str,
    ) -> Counterfactual | None:
        """Compare top action vs runner-up for explainability.

        Returns Counterfactual with runner_up estimate and why_not narrative.
        Returns None if no runner-up exists.
        """
        if not runner_up:
            return None

        top_estimate = self.estimate(top_action, merchant_state, module)
        runner_estimate = self.estimate(runner_up, merchant_state, module)

        top_id = top_action.get("action_id", "unknown")
        runner_id = runner_up.get("action_id", "unknown")

        why_not = (
            f"{runner_id} estimated ${runner_estimate.expected:,.0f} "
            f"vs ${top_estimate.expected:,.0f} for {top_id}"
        )

        return Counterfactual(
            runner_up_action=runner_id,
            runner_up_estimate=runner_estimate.expected,
            why_not=why_not,
        )
