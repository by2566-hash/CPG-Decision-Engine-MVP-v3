# ── Layer 1 · Merchant State Machine ──────────────────────────────────────
# Evaluates merchant health across 4 dimensions, each with 4 states.
# ALL thresholds come from settings (config.py). Zero hardcoded numbers.
#
# Dimensions: acquisition, conversion, retention, promotion
# States per dimension: HEALTHY → WATCH → DEGRADING → CRITICAL
#
# Reference: V0/compute_risk.py for overdue_ratio logic (retention dimension).
#   overdue_ratio = days_since_last_purchase / avg_replenishment_cycle_days
#   V0 threshold: overdue_ratio > 1.2 triggers at-risk.
#   V3 uses configurable thresholds via settings.msm_overdue_*.
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..config import settings
from ..contracts import MerchantStateVector
from .. import db_client
from .state_definitions import DimensionState

log = logging.getLogger(__name__)

# Required signals per dimension
_REQUIRED_SIGNALS: dict[str, list[str]] = {
    "acquisition": ["cac_7d", "cac_baseline_30d", "roas_7d", "roas_baseline_30d"],
    "conversion": ["mobile_atc_rate", "desktop_atc_rate", "mobile_traffic_pct", "checkout_cvr"],
    "retention": ["overdue_ratio", "repeat_purchase_rate", "days_since_last_order_p50"],
    "promotion": ["promo_incrementality", "existing_customer_promo_pct", "promo_margin_delta"],
}


class MerchantStateMachine:
    """Evaluates and transitions merchant state across 4 health dimensions."""

    def compute(self, merchant_id: str, signals: dict) -> MerchantStateVector:
        """Compute all 4 dimensions. Persist result. Return MerchantStateVector.

        If any required signal is missing for a dimension,
        calls missing_signals_fallback() for that dimension.
        """
        # Fetch previous state for urgency computation
        prev_raw = db_client.fetch_latest_merchant_state(merchant_id)
        previous = self._parse_previous_state(prev_raw) if prev_raw else None

        acq_state, acq_signals = self._compute_acquisition_state(signals)
        cvr_state, cvr_signals = self._compute_conversion_state(signals)
        ret_state, ret_signals = self._compute_retention_state(signals)
        prm_state, prm_signals = self._compute_promotion_state(signals)

        prev_acq = DimensionState(previous["acquisition_state"]) if previous else None
        prev_cvr = DimensionState(previous["conversion_state"]) if previous else None
        prev_ret = DimensionState(previous["retention_state"]) if previous else None
        prev_prm = DimensionState(previous["promotion_state"]) if previous else None

        acq_urgency = self._compute_urgency_score(acq_state, acq_signals, prev_acq)
        cvr_urgency = self._compute_urgency_score(cvr_state, cvr_signals, prev_cvr)
        ret_urgency = self._compute_urgency_score(ret_state, ret_signals, prev_ret)
        prm_urgency = self._compute_urgency_score(prm_state, prm_signals, prev_prm)

        now = datetime.now(timezone.utc)
        msv = MerchantStateVector(
            merchant_id=merchant_id,
            computed_at=now,
            acquisition_state=acq_state.value,
            conversion_state=cvr_state.value,
            retention_state=ret_state.value,
            promotion_state=prm_state.value,
            acquisition_urgency=acq_urgency,
            conversion_urgency=cvr_urgency,
            retention_urgency=ret_urgency,
            promotion_urgency=prm_urgency,
            metrics_snapshot={
                **acq_signals, **cvr_signals, **ret_signals, **prm_signals,
            },
        )
        db_client.upsert_merchant_state_vector(msv)
        return msv

    # ── Dimension evaluators ────────────────────────────────────────

    def _compute_acquisition_state(self, signals: dict) -> tuple[DimensionState, dict]:
        """Acquisition dimension: CAC and ROAS relative to baseline.

        Required signals: cac_7d, cac_baseline_30d, roas_7d, roas_baseline_30d
        """
        required = _REQUIRED_SIGNALS["acquisition"]
        if not self._has_required_signals(signals, required):
            return self.missing_signals_fallback("acquisition", signals), {}

        cac_7d = signals["cac_7d"]
        cac_baseline = signals["cac_baseline_30d"]
        roas_7d = signals["roas_7d"]
        roas_baseline = signals["roas_baseline_30d"]

        signals_used = {
            "cac_7d": cac_7d, "cac_baseline_30d": cac_baseline,
            "roas_7d": roas_7d, "roas_baseline_30d": roas_baseline,
        }

        # Evaluate from most severe to least
        if cac_7d > cac_baseline * settings.msm_cac_critical_multiplier:
            return DimensionState.CRITICAL, signals_used

        cac_exceeds_degrading = cac_7d > cac_baseline * settings.msm_cac_degrading_multiplier
        roas_declining = roas_7d < roas_baseline * settings.msm_roas_decline_ratio

        if cac_exceeds_degrading and roas_declining:
            return DimensionState.DEGRADING, signals_used

        if cac_exceeds_degrading:
            return DimensionState.WATCH, signals_used

        return DimensionState.HEALTHY, signals_used

    def _compute_conversion_state(self, signals: dict) -> tuple[DimensionState, dict]:
        """Conversion dimension: mobile vs desktop ATC gap and CVR trend.

        Required signals: mobile_atc_rate, desktop_atc_rate, mobile_traffic_pct, checkout_cvr
        """
        required = _REQUIRED_SIGNALS["conversion"]
        if not self._has_required_signals(signals, required):
            return self.missing_signals_fallback("conversion", signals), {}

        mobile_atc = signals["mobile_atc_rate"]
        desktop_atc = signals["desktop_atc_rate"]
        mobile_traffic = signals["mobile_traffic_pct"]
        checkout_cvr = signals["checkout_cvr"]

        signals_used = {
            "mobile_atc_rate": mobile_atc, "desktop_atc_rate": desktop_atc,
            "mobile_traffic_pct": mobile_traffic, "checkout_cvr": checkout_cvr,
        }

        # checkout_cvr can be a dict with "current" and "3d_ago" for trend detection,
        # or a simple float (no trend info → assume stable)
        cvr_trending_down = False
        if isinstance(checkout_cvr, dict):
            current = checkout_cvr.get("current", 0)
            three_d_ago = checkout_cvr.get("3d_ago", current)
            cvr_trending_down = (current - three_d_ago) < 0
            signals_used["checkout_cvr"] = checkout_cvr
        # else: single float, no trend info

        mobile_below_degrading = mobile_atc < desktop_atc * settings.msm_mobile_atc_degrading_ratio
        mobile_below_watch = mobile_atc < desktop_atc * settings.msm_mobile_atc_watch_ratio

        # Evaluate from most severe to least
        if mobile_below_degrading and cvr_trending_down:
            return DimensionState.CRITICAL, signals_used

        if mobile_below_degrading:
            return DimensionState.DEGRADING, signals_used

        if mobile_below_watch and mobile_traffic >= settings.msm_mobile_traffic_majority_threshold:
            return DimensionState.WATCH, signals_used

        return DimensionState.HEALTHY, signals_used

    def _compute_retention_state(self, signals: dict) -> tuple[DimensionState, dict]:
        """Retention dimension: overdue ratio thresholds.

        Required signals: overdue_ratio, repeat_purchase_rate, days_since_last_order_p50

        Reference: V0/compute_risk.py
          overdue_ratio = days_since_last_purchase / avg_replenishment_cycle_days
          V0 uses 1.2 as at-risk threshold. V3 uses configurable settings.msm_overdue_*.
        """
        required = _REQUIRED_SIGNALS["retention"]
        if not self._has_required_signals(signals, required):
            return self.missing_signals_fallback("retention", signals), {}

        overdue_ratio = signals["overdue_ratio"]
        repeat_rate = signals["repeat_purchase_rate"]
        days_p50 = signals["days_since_last_order_p50"]

        signals_used = {
            "overdue_ratio": overdue_ratio,
            "repeat_purchase_rate": repeat_rate,
            "days_since_last_order_p50": days_p50,
        }

        # Evaluate from most severe to least (V0: 1.2 was at-risk, V3 uses config)
        if overdue_ratio >= settings.msm_overdue_critical_threshold:
            return DimensionState.CRITICAL, signals_used

        if overdue_ratio >= settings.msm_overdue_degrading_threshold:
            return DimensionState.DEGRADING, signals_used

        if overdue_ratio >= settings.msm_overdue_watch_threshold:
            return DimensionState.WATCH, signals_used

        return DimensionState.HEALTHY, signals_used

    def _compute_promotion_state(self, signals: dict) -> tuple[DimensionState, dict]:
        """Promotion dimension: incrementality floor and margin impact.

        Required signals: promo_incrementality, existing_customer_promo_pct, promo_margin_delta
        """
        required = _REQUIRED_SIGNALS["promotion"]
        if not self._has_required_signals(signals, required):
            return self.missing_signals_fallback("promotion", signals), {}

        incrementality = signals["promo_incrementality"]
        existing_pct = signals["existing_customer_promo_pct"]
        margin_delta = signals["promo_margin_delta"]

        signals_used = {
            "promo_incrementality": incrementality,
            "existing_customer_promo_pct": existing_pct,
            "promo_margin_delta": margin_delta,
        }

        # Evaluate from most severe to least
        is_degrading = incrementality < settings.msm_promo_incrementality_degrading

        if is_degrading and margin_delta < 0:
            return DimensionState.CRITICAL, signals_used

        if is_degrading:
            return DimensionState.DEGRADING, signals_used

        if incrementality < settings.msm_promo_incrementality_watch:
            return DimensionState.WATCH, signals_used

        # HEALTHY: incrementality >= 0.60 (inverse of watch/degrading thresholds)
        return DimensionState.HEALTHY, signals_used

    # ── Urgency scoring ─────────────────────────────────────────────

    def _compute_urgency_score(
        self,
        state: DimensionState,
        signals: dict,
        previous_state: DimensionState | None,
    ) -> float:
        """Compute urgency score 0.0–1.0.

        Base scores:
          CRITICAL:  0.8
          DEGRADING: 0.5
          WATCH:     0.2
          HEALTHY:   0.0

        Bonuses:
          +0.1 if state just worsened (transition this cycle)
          +0.1 if signal is accelerating (trend slope steep)
        """
        base = {
            DimensionState.CRITICAL: 0.8,
            DimensionState.DEGRADING: 0.5,
            DimensionState.WATCH: 0.2,
            DimensionState.HEALTHY: 0.0,
        }[state]

        bonus = 0.0

        # State just worsened: new state is worse than previous
        if previous_state is not None and state > previous_state:
            bonus += settings.msm_urgency_transition_bonus

        # Signal acceleration: check for trend data in signals
        # checkout_cvr may carry trend dict; overdue_ratio acceleration can be
        # inferred from magnitude exceeding the next threshold.
        if self._detect_signal_acceleration(state, signals):
            bonus += settings.msm_urgency_acceleration_bonus

        return min(base + bonus, 1.0)

    def _detect_signal_acceleration(self, state: DimensionState, signals: dict) -> bool:
        """Detect if signals show accelerating deterioration.

        NOTE (FIX-18 / S6-1, deferred): Currently only checks conversion (checkout_cvr)
        and retention (overdue_ratio) dimensions. Acquisition and promotion acceleration
        checks are not implemented — L0 signal schema for these dimensions is not yet
        finalized. Implement after data ingestion is complete.
        Always returns False for acquisition and promotion dimensions.
        """
        # checkout_cvr trend dict
        cvr = signals.get("checkout_cvr")
        if isinstance(cvr, dict):
            current = cvr.get("current", 0)
            three_d_ago = cvr.get("3d_ago", current)
            if (current - three_d_ago) < settings.msm_cvr_acceleration_threshold:
                return True

        # overdue_ratio well above critical threshold = accelerating
        overdue = signals.get("overdue_ratio")
        if overdue is not None and overdue >= settings.msm_overdue_critical_threshold * settings.msm_overdue_acceleration_multiplier:
            return True

        return False

    # ── Fallback ────────────────────────────────────────────────────

    def missing_signals_fallback(self, dimension: str, signals: dict) -> DimensionState:
        """Return WATCH when required signals are missing. Never returns HEALTHY.

        Logs which signals are missing for observability.
        """
        required = _REQUIRED_SIGNALS.get(dimension, [])
        missing = [s for s in required if s not in signals or signals[s] is None]
        log.warning(
            "MSM %s: missing signals %s — falling back to WATCH",
            dimension, missing,
        )
        return DimensionState.WATCH

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _has_required_signals(signals: dict, required: list[str]) -> bool:
        """Check that all required signal keys are present and non-None."""
        return all(k in signals and signals[k] is not None for k in required)

    @staticmethod
    def _parse_previous_state(raw: dict) -> dict:
        """Normalize a raw DB row into a dict with state string values."""
        return raw
