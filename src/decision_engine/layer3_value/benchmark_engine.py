# ── Layer 3 · Value Intelligence — Benchmark Engine ───────────────────────
# Cross-merchant comparison:
#   'Your retention DEGRADING vs peer median WATCH'
#
# Phase 1: public CPG industry data
# Phase 2+: multi-merchant MSM aggregates
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging

from ..config import settings

log = logging.getLogger(__name__)


class BenchmarkEngine:
    """Provides peer comparison context for merchant Decision Cards.

    Phase 1: public benchmarks / Phase 2+: multi-merchant MSM aggregates
    """

    # Phase 1: public CPG industry benchmarks
    PUBLIC_BENCHMARKS: dict[str, dict[str, float]] = {
        "overdue_ratio":            {"median": 1.20, "p75": 1.50, "p90": 1.80},
        "repeat_purchase_rate":     {"median": 0.28, "p25": 0.20, "p75": 0.38},
        "cac_vs_baseline_ratio":    {"median": 1.00, "p75": 1.15, "p90": 1.35},
        "mobile_atc_desktop_ratio": {"median": 0.85, "p25": 0.70, "p10": 0.50},
        "promo_incrementality":     {"median": 0.55, "p25": 0.40, "p10": 0.25},
    }

    def compare(
        self,
        merchant_id: str,
        dimension: str,
        merchant_value: float,
        metric_name: str,
        peer_data: list[dict] | None = None,
    ) -> str:
        """Compare merchant metric to industry or peer benchmarks.

        Phase 1 (peer_data None): use PUBLIC_BENCHMARKS
          Return: "Your {metric} ({merchant_value:.2f}) is above/below the
                   industry median of {median:.2f} for CPG brands"

        Phase 2+ (peer_data provided, len >= settings.benchmark_min_peer_count):
          Calculate actual peer percentiles from peer_data
          Return: "Your {metric} ({merchant_value:.2f}) is in the bottom
                   {percentile}th percentile among {len(peer_data)} similar brands"

        Never returns empty string.
        """
        # Phase 2+: multi-merchant MSM aggregates
        if peer_data and len(peer_data) >= settings.benchmark_min_peer_count:
            return self._compare_to_peers(merchant_value, metric_name, peer_data)

        # Phase 1: public benchmarks
        return self._compare_to_public(merchant_value, metric_name)

    def _compare_to_public(self, merchant_value: float, metric_name: str) -> str:
        """Phase 1: compare against public CPG industry benchmarks."""
        bench = self.PUBLIC_BENCHMARKS.get(metric_name)
        if bench is None:
            return (
                f"Your {metric_name} ({merchant_value:.2f}) — "
                f"no industry benchmark available for this metric"
            )

        median = bench["median"]
        if merchant_value >= median:
            position = "above"
        else:
            position = "below"

        return (
            f"Your {metric_name} ({merchant_value:.2f}) is {position} the "
            f"industry median of {median:.2f} for CPG brands"
        )

    def _compare_to_peers(
        self,
        merchant_value: float,
        metric_name: str,
        peer_data: list[dict],
    ) -> str:
        """Phase 2+: compare against actual peer data."""
        peer_values = sorted(
            p.get("value", 0.0) for p in peer_data if "value" in p
        )
        if not peer_values:
            return self._compare_to_public(merchant_value, metric_name)

        # Compute percentile rank
        below_count = sum(1 for v in peer_values if v < merchant_value)
        percentile = int((below_count / len(peer_values)) * 100)

        return (
            f"Your {metric_name} ({merchant_value:.2f}) is in the bottom "
            f"{percentile}th percentile among {len(peer_data)} similar brands"
        )
