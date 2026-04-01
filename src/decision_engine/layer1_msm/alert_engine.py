# ── Layer 1 · Alert Engine ─────────────────────────────────────────────────
# Phase 1: polling-based threshold check (interval from settings.alert_polling_interval_seconds)
# Phase 2+: replace with webhook/event stream trigger
#
# Reacts to MSM state changes:
#   - CRITICAL state change → immediate Emergency Decision trigger
#   - Skipped WATCH (HEALTHY → DEGRADING) → alert
#   - High urgency (> 0.8) → alert
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging

from ..contracts import MerchantStateVector
from .state_definitions import DimensionState

log = logging.getLogger(__name__)

_DIMENSIONS = ["acquisition", "conversion", "retention", "promotion"]


class AlertEngine:
    """Monitors MSM transitions and generates alerts / emergency triggers."""

    def check_and_alert(
        self,
        merchant_id: str,
        new_state: MerchantStateVector,
        previous_state: MerchantStateVector | None,
    ) -> list[str]:
        """Compare new_state to previous_state across all dimensions.

        Generates alert strings for:
          1. Any dimension that transitioned TO CRITICAL
          2. Any dimension that jumped from HEALTHY directly to DEGRADING (skipped WATCH)
          3. Any dimension with urgency_score > 0.8

        Returns list of alert strings (empty if no alerts).
        """
        alerts: list[str] = []

        for dim in _DIMENSIONS:
            new_val = DimensionState(getattr(new_state, f"{dim}_state"))
            urgency = getattr(new_state, f"{dim}_urgency")

            prev_val = (
                DimensionState(getattr(previous_state, f"{dim}_state"))
                if previous_state is not None
                else None
            )

            # 1. Transitioned TO CRITICAL
            if new_val == DimensionState.CRITICAL:
                if prev_val is None or prev_val != DimensionState.CRITICAL:
                    alert = (
                        f"[CRITICAL] merchant {merchant_id}: "
                        f"{dim} dimension is now CRITICAL"
                    )
                    alerts.append(alert)
                    log.warning(alert)

            # 2. Jumped from HEALTHY directly to DEGRADING (skipped WATCH)
            if (
                prev_val == DimensionState.HEALTHY
                and new_val == DimensionState.DEGRADING
            ):
                alert = (
                    f"[SKIP_WATCH] merchant {merchant_id}: "
                    f"{dim} dimension jumped from HEALTHY to DEGRADING"
                )
                alerts.append(alert)
                log.warning(alert)

            # 3. Urgency > 0.8
            if urgency > 0.8:
                alert = (
                    f"[HIGH_URGENCY] merchant {merchant_id}: "
                    f"{dim} dimension urgency={urgency:.2f}"
                )
                alerts.append(alert)
                log.warning(alert)

        return alerts

    def should_trigger_emergency_decision(
        self,
        new_state: MerchantStateVector,
        previous_state: MerchantStateVector | None,
    ) -> bool:
        """Return True ONLY if at least one dimension just transitioned TO CRITICAL.

        - Was not CRITICAL in previous_state, is CRITICAL in new_state.
        - If previous_state is None, returns True if any dimension is CRITICAL.
        """
        for dim in _DIMENSIONS:
            new_val = DimensionState(getattr(new_state, f"{dim}_state"))
            if new_val != DimensionState.CRITICAL:
                continue

            if previous_state is None:
                return True

            prev_val = DimensionState(getattr(previous_state, f"{dim}_state"))
            if prev_val != DimensionState.CRITICAL:
                return True

        return False
