# ── Feature Plane · FeatureBuilder ───────────────────────────────────────────
# Produces a DecisionFeatureVector from raw signals and MerchantStateVector.
#
# Implements ADR-0005: Feature Plane as logical concept, no infrastructure.
# Phase 1: all derivations are simple signal lookups or arithmetic.
# Phase 2/3: individual helpers will be replaced with real ML-derived scores
#            (churn model, stock pressure forecast, etc.).
#
# Design rules:
#   - Stateless: no instance state, no DB calls, no external I/O
#   - Clamping: out-of-range signal values are clamped before construction
#     (defensive — raw Shopline signals may exceed model assumptions)
#   - Missing signals: log a warning at DEBUG level, use documented default
#   - All helpers are pure and testable in isolation
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..contracts import DecisionFeatureVector, MerchantStateVector

log = logging.getLogger(__name__)


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, value))


class FeatureBuilder:
    """Produces DecisionFeatureVector from raw signals.

    Stateless — safe to use as a module-level singleton.
    """

    def build(
        self,
        signals: dict,
        merchant_state: MerchantStateVector,
    ) -> DecisionFeatureVector:
        """Build a DecisionFeatureVector from raw signals and MSM state.

        Missing keys log a DEBUG warning and fall back to the documented
        default. Out-of-range values are clamped to valid field bounds
        (ge/le from DecisionFeatureVector) before construction, so the
        Pydantic validator never fires on real-world data edge cases.

        Phase 2/3: individual _compute_* helpers will be replaced with
        ML-derived values once real outcome data is available.
        """
        inventory_days = self._extract_inventory_days(signals)
        margin_pct = self._extract_margin_pct(signals)
        repeat_rate_7d = self._extract_repeat_rate(signals)
        cvr_7d = self._extract_cvr_7d(signals)
        cvr_30d = self._extract_cvr_30d(signals)
        promo_redemption_30d = self._extract_promo_redemption(signals)
        stock_pressure_score = self._compute_stock_pressure(inventory_days)
        churn_score = self._extract_churn_score(signals)
        seasonality_index = self._extract_seasonality(signals)
        benchmark_gap_score = self._extract_benchmark_gap(signals)

        return DecisionFeatureVector(
            computed_at=datetime.now(timezone.utc),
            inventory_days=inventory_days,
            margin_pct=margin_pct,
            repeat_rate_7d=repeat_rate_7d,
            cvr_7d=cvr_7d,
            cvr_30d=cvr_30d,
            promo_redemption_30d=promo_redemption_30d,
            stock_pressure_score=stock_pressure_score,
            churn_score=churn_score,
            seasonality_index=seasonality_index,
            benchmark_gap_score=benchmark_gap_score,
        )

    # ── Individual field extractors ───────────────────────────────────────────
    # Each helper is pure: (signals dict) → float.
    # Phase 2/3 replacement: swap the body, keep the signature.

    def _extract_inventory_days(self, signals: dict) -> float:
        """Days of supply from raw signals.

        Phase 2/3: will use `inventory_days_p10` (10th percentile)
        for conservative stock-out risk estimation.
        """
        val = signals.get("inventory_days")
        if val is None:
            log.debug("[FeatureBuilder] inventory_days missing — defaulting to 0.0")
            return 0.0
        return max(0.0, float(val))  # ge=0.0 enforced by contract

    def _extract_margin_pct(self, signals: dict) -> float:
        """Post-discount margin fraction [0, 1].

        Phase 2/3: will account for promotions applied at order time
        rather than the static avg_margin_pct snapshot.
        """
        val = signals.get("margin_pct", signals.get("avg_margin_pct"))
        if val is None:
            log.debug("[FeatureBuilder] margin_pct missing — defaulting to 0.0")
            return 0.0
        return _clamp(float(val), 0.0, 1.0)

    def _extract_repeat_rate(self, signals: dict) -> float:
        """7-day repeat purchase rate [0, 1].

        Phase 2/3: will use rolling 7d cohort repeat rate from order stream.
        """
        val = signals.get("repeat_rate_7d", signals.get("repeat_purchase_rate"))
        if val is None:
            log.debug("[FeatureBuilder] repeat_rate_7d missing — defaulting to 0.0")
            return 0.0
        return _clamp(float(val), 0.0, 1.0)

    def _extract_cvr_7d(self, signals: dict) -> float:
        """Checkout conversion rate for the last 7 days [0, 1].

        checkout_cvr may arrive as a plain float or as {"current": float, ...}
        (Shopline API returns a snapshot dict). Both forms are handled.
        Phase 2/3: will distinguish mobile vs desktop CVR.
        """
        val = signals.get("cvr_7d")
        if val is None:
            raw = signals.get("checkout_cvr")
            val = raw.get("current") if isinstance(raw, dict) else raw
        if val is None:
            log.debug("[FeatureBuilder] cvr_7d missing — defaulting to 0.0")
            return 0.0
        return _clamp(float(val), 0.0, 1.0)

    def _extract_cvr_30d(self, signals: dict) -> float:
        """30-day baseline checkout conversion rate [0, 1].

        Phase 2/3: will be a rolling 30d average, not a snapshot.
        """
        val = signals.get("cvr_30d")
        if val is None:
            log.debug("[FeatureBuilder] cvr_30d missing — defaulting to 0.0")
            return 0.0
        return _clamp(float(val), 0.0, 1.0)

    def _extract_promo_redemption(self, signals: dict) -> float:
        """30-day promo redemption rate as incrementality proxy [0, 1].

        Phase 2/3: will use actual discount redemption logs from L5 outcome log.
        """
        val = signals.get("promo_redemption_30d", signals.get("promo_incrementality"))
        if val is None:
            log.debug("[FeatureBuilder] promo_redemption_30d missing — defaulting to 0.0")
            return 0.0
        return _clamp(float(val), 0.0, 1.0)

    def _compute_stock_pressure(self, inventory_days: float) -> float:
        """Stock pressure score — how urgently inventory needs to move.

        Formula: 1.0 - (inventory_days / 7.0) when inventory_days < 7, else 0.0.
        Interpretation: 0.0 = no pressure (7+ days of stock), 1.0 = stockout.

        Phase 2/3: will incorporate demand forecast velocity and seasonal
        adjustments for a more accurate stock-out probability estimate.
        """
        if inventory_days >= 7.0:
            return 0.0
        return _clamp(1.0 - (inventory_days / 7.0), 0.0, 1.0)

    def _extract_churn_score(self, signals: dict) -> float:
        """Customer churn risk score [0, 1].

        Phase 1: uses overdue_ratio as a proxy (high overdue = high churn risk).
        Phase 2/3: will be replaced with a real churn model trained on
        customer purchase sequences from the L5 feature history.
        """
        val = signals.get("churn_score", signals.get("overdue_ratio"))
        if val is None:
            log.debug("[FeatureBuilder] churn_score missing — defaulting to 0.0")
            return 0.0
        return _clamp(float(val), 0.0, 1.0)

    def _extract_seasonality(self, signals: dict) -> float:
        """Seasonality index (1.0 = baseline, >1.0 = peak, <1.0 = trough).

        No [0,1] bound — unbounded by design (2.0 = 2× normal demand is valid).
        Phase 2/3: will be derived from historical order volume patterns.
        """
        val = signals.get("seasonality_index")
        if val is None:
            log.debug("[FeatureBuilder] seasonality_index missing — defaulting to 1.0")
            return 1.0
        return float(val)

    def _extract_benchmark_gap(self, signals: dict) -> float:
        """Gap vs category benchmark (negative = below benchmark).

        No [0,1] bound — can be negative or >1.0.
        Phase 2/3: will come from BenchmarkEngine peer comparison.
        """
        val = signals.get("benchmark_gap_score")
        if val is None:
            log.debug("[FeatureBuilder] benchmark_gap_score missing — defaulting to 0.0")
            return 0.0
        return float(val)
