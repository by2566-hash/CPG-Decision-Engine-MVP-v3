"""Tests for Layer 1: Merchant State Machine.

Covers:
  - 16 state transition tests (4 dimensions × 4 states)
  - 2 fallback tests (missing/partial signals)
  - 3 urgency score tests
  - 5 alert engine tests
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from src.decision_engine.layer1_msm.state_definitions import DimensionState
from src.decision_engine.layer1_msm.merchant_state_machine import MerchantStateMachine
from src.decision_engine.layer1_msm.alert_engine import AlertEngine
from src.decision_engine.contracts import MerchantStateVector

msm = MerchantStateMachine()
alert_engine = AlertEngine()


# ═══════════════════════════════════════════════════════════════════
# Helper: build full signal dicts with sane defaults
# ═══════════════════════════════════════════════════════════════════

def _base_signals(**overrides) -> dict:
    """All-healthy baseline signals. Override individual keys as needed."""
    defaults = {
        # Acquisition
        "cac_7d": 10.0,
        "cac_baseline_30d": 10.0,
        "roas_7d": 5.0,
        "roas_baseline_30d": 5.0,
        # Conversion
        "mobile_atc_rate": 0.20,
        "desktop_atc_rate": 0.20,
        "mobile_traffic_pct": 0.55,
        "checkout_cvr": 0.04,
        # Retention
        "overdue_ratio": 0.8,
        "repeat_purchase_rate": 0.40,
        "days_since_last_order_p50": 20.0,
        # Promotion
        "promo_incrementality": 0.65,
        "existing_customer_promo_pct": 0.30,
        "promo_margin_delta": 0.02,
    }
    defaults.update(overrides)
    return defaults


def _make_msv(
    merchant_id: str = "m_test",
    acq: str = "HEALTHY",
    cvr: str = "HEALTHY",
    ret: str = "HEALTHY",
    prm: str = "HEALTHY",
    acq_u: float = 0.0,
    cvr_u: float = 0.0,
    ret_u: float = 0.0,
    prm_u: float = 0.0,
) -> MerchantStateVector:
    """Build a MerchantStateVector with explicit dimension states."""
    return MerchantStateVector(
        merchant_id=merchant_id,
        computed_at=datetime.now(timezone.utc),
        acquisition_state=acq,
        conversion_state=cvr,
        retention_state=ret,
        promotion_state=prm,
        acquisition_urgency=acq_u,
        conversion_urgency=cvr_u,
        retention_urgency=ret_u,
        promotion_urgency=prm_u,
    )


# ═══════════════════════════════════════════════════════════════════
# Acquisition dimension (4 states)
# ═══════════════════════════════════════════════════════════════════

class TestAcquisitionStates:
    def test_acquisition_healthy(self):
        """CAC at baseline → HEALTHY."""
        signals = _base_signals(cac_7d=10.0, cac_baseline_30d=10.0)
        state, _ = msm._compute_acquisition_state(signals)
        assert state == DimensionState.HEALTHY

    def test_acquisition_watch(self):
        """CAC above degrading multiplier but ROAS stable → WATCH."""
        # cac_7d = 12.0 > 10.0 * 1.15 = 11.5, but roas NOT declining
        signals = _base_signals(
            cac_7d=12.0, cac_baseline_30d=10.0,
            roas_7d=5.0, roas_baseline_30d=5.0,
        )
        state, _ = msm._compute_acquisition_state(signals)
        assert state == DimensionState.WATCH

    def test_acquisition_degrading(self):
        """CAC above degrading multiplier AND ROAS declining → DEGRADING."""
        # cac_7d = 12.0 > 11.5 AND roas_7d = 4.0 < 5.0 * 0.9 = 4.5
        signals = _base_signals(
            cac_7d=12.0, cac_baseline_30d=10.0,
            roas_7d=4.0, roas_baseline_30d=5.0,
        )
        state, _ = msm._compute_acquisition_state(signals)
        assert state == DimensionState.DEGRADING

    def test_acquisition_critical(self):
        """CAC above critical multiplier → CRITICAL regardless of ROAS."""
        # cac_7d = 14.0 > 10.0 * 1.35 = 13.5
        signals = _base_signals(cac_7d=14.0, cac_baseline_30d=10.0)
        state, _ = msm._compute_acquisition_state(signals)
        assert state == DimensionState.CRITICAL


# ═══════════════════════════════════════════════════════════════════
# Conversion dimension (4 states)
# ═══════════════════════════════════════════════════════════════════

class TestConversionStates:
    def test_conversion_healthy(self):
        """Mobile ATC rate at par with desktop → HEALTHY."""
        signals = _base_signals(mobile_atc_rate=0.20, desktop_atc_rate=0.20)
        state, _ = msm._compute_conversion_state(signals)
        assert state == DimensionState.HEALTHY

    def test_conversion_watch(self):
        """Mobile ATC below watch ratio with high mobile traffic → WATCH."""
        # mobile = 0.13 < 0.20 * 0.70 = 0.14, mobile_traffic_pct >= 0.5
        signals = _base_signals(
            mobile_atc_rate=0.13, desktop_atc_rate=0.20,
            mobile_traffic_pct=0.55,
        )
        state, _ = msm._compute_conversion_state(signals)
        assert state == DimensionState.WATCH

    def test_conversion_degrading(self):
        """Mobile ATC below degrading ratio → DEGRADING."""
        # mobile = 0.09 < 0.20 * 0.50 = 0.10
        signals = _base_signals(
            mobile_atc_rate=0.09, desktop_atc_rate=0.20,
            checkout_cvr=0.04,  # stable float, no trend
        )
        state, _ = msm._compute_conversion_state(signals)
        assert state == DimensionState.DEGRADING

    def test_conversion_critical(self):
        """Mobile ATC below degrading AND CVR trending down → CRITICAL."""
        signals = _base_signals(
            mobile_atc_rate=0.09, desktop_atc_rate=0.20,
            checkout_cvr={"current": 0.03, "3d_ago": 0.04},  # downward trend
        )
        state, _ = msm._compute_conversion_state(signals)
        assert state == DimensionState.CRITICAL


# ═══════════════════════════════════════════════════════════════════
# Retention dimension (4 states)
# ═══════════════════════════════════════════════════════════════════

class TestRetentionStates:
    def test_retention_healthy(self):
        """Overdue ratio below watch threshold → HEALTHY."""
        signals = _base_signals(overdue_ratio=1.0)
        state, _ = msm._compute_retention_state(signals)
        assert state == DimensionState.HEALTHY

    def test_retention_watch(self):
        """Overdue ratio at watch threshold → WATCH."""
        # settings.msm_overdue_watch_threshold = 1.20
        signals = _base_signals(overdue_ratio=1.25)
        state, _ = msm._compute_retention_state(signals)
        assert state == DimensionState.WATCH

    def test_retention_degrading(self):
        """Overdue ratio at degrading threshold → DEGRADING."""
        # settings.msm_overdue_degrading_threshold = 1.50
        signals = _base_signals(overdue_ratio=1.55)
        state, _ = msm._compute_retention_state(signals)
        assert state == DimensionState.DEGRADING

    def test_retention_critical(self):
        """Overdue ratio at critical threshold → CRITICAL."""
        # settings.msm_overdue_critical_threshold = 1.80
        signals = _base_signals(overdue_ratio=1.85)
        state, _ = msm._compute_retention_state(signals)
        assert state == DimensionState.CRITICAL


# ═══════════════════════════════════════════════════════════════════
# Promotion dimension (4 states)
# ═══════════════════════════════════════════════════════════════════

class TestPromotionStates:
    def test_promotion_healthy(self):
        """Incrementality above 0.60 → HEALTHY."""
        signals = _base_signals(promo_incrementality=0.65)
        state, _ = msm._compute_promotion_state(signals)
        assert state == DimensionState.HEALTHY

    def test_promotion_watch(self):
        """Incrementality below watch but above degrading → WATCH."""
        # settings.msm_promo_incrementality_watch = 0.40
        signals = _base_signals(promo_incrementality=0.35, promo_margin_delta=0.01)
        state, _ = msm._compute_promotion_state(signals)
        assert state == DimensionState.WATCH

    def test_promotion_degrading(self):
        """Incrementality below degrading threshold, margin still positive → DEGRADING."""
        # settings.msm_promo_incrementality_degrading = 0.25
        signals = _base_signals(promo_incrementality=0.20, promo_margin_delta=0.01)
        state, _ = msm._compute_promotion_state(signals)
        assert state == DimensionState.DEGRADING

    def test_promotion_critical(self):
        """Incrementality below degrading AND margin delta negative → CRITICAL."""
        signals = _base_signals(promo_incrementality=0.20, promo_margin_delta=-0.03)
        state, _ = msm._compute_promotion_state(signals)
        assert state == DimensionState.CRITICAL


# ═══════════════════════════════════════════════════════════════════
# Fallback tests
# ═══════════════════════════════════════════════════════════════════

class TestMissingSignals:
    def test_missing_signals_returns_watch_not_healthy(self):
        """When required signals are missing, fallback must return WATCH (never HEALTHY)."""
        state = msm.missing_signals_fallback("retention", {})
        assert state == DimensionState.WATCH
        assert state != DimensionState.HEALTHY

    def test_partial_signals_does_not_crash(self):
        """MSM should not crash when only some signals are provided."""
        partial_signals = {
            "cac_7d": 10.0,
            # missing cac_baseline_30d, roas_7d, roas_baseline_30d
            "overdue_ratio": 1.5,
            # missing repeat_purchase_rate, days_since_last_order_p50
        }
        # Should fall back to WATCH for dimensions with missing signals
        state_acq, _ = msm._compute_acquisition_state(partial_signals)
        assert state_acq == DimensionState.WATCH

        state_cvr, _ = msm._compute_conversion_state(partial_signals)
        assert state_cvr == DimensionState.WATCH

        state_ret, _ = msm._compute_retention_state(partial_signals)
        assert state_ret == DimensionState.WATCH  # missing repeat_purchase_rate

        state_prm, _ = msm._compute_promotion_state(partial_signals)
        assert state_prm == DimensionState.WATCH


# ═══════════════════════════════════════════════════════════════════
# Urgency score tests
# ═══════════════════════════════════════════════════════════════════

class TestUrgencyScores:
    def test_urgency_critical_higher_than_degrading(self):
        """CRITICAL base urgency (0.8) must exceed DEGRADING base (0.5)."""
        signals = _base_signals()
        u_critical = msm._compute_urgency_score(
            DimensionState.CRITICAL, signals, DimensionState.CRITICAL,
        )
        u_degrading = msm._compute_urgency_score(
            DimensionState.DEGRADING, signals, DimensionState.DEGRADING,
        )
        assert u_critical > u_degrading

    def test_urgency_higher_when_state_just_worsened(self):
        """Urgency should be higher when state just transitioned to worse."""
        signals = _base_signals()
        # Stable DEGRADING (no transition bonus)
        u_stable = msm._compute_urgency_score(
            DimensionState.DEGRADING, signals, DimensionState.DEGRADING,
        )
        # Just worsened from WATCH to DEGRADING (+0.1 transition bonus)
        u_worsened = msm._compute_urgency_score(
            DimensionState.DEGRADING, signals, DimensionState.WATCH,
        )
        assert u_worsened > u_stable

    def test_urgency_lower_when_state_stable(self):
        """Urgency for stable WATCH should equal base (0.2), no bonuses."""
        signals = _base_signals()
        u = msm._compute_urgency_score(
            DimensionState.WATCH, signals, DimensionState.WATCH,
        )
        assert u == 0.2


# ═══════════════════════════════════════════════════════════════════
# Alert engine tests
# ═══════════════════════════════════════════════════════════════════

class TestAlertEngine:
    def test_alert_fires_on_critical_transition(self):
        """Alert should fire when a dimension transitions TO CRITICAL."""
        prev = _make_msv(ret="DEGRADING")
        new = _make_msv(ret="CRITICAL")
        alerts = alert_engine.check_and_alert("m_test", new, prev)
        critical_alerts = [a for a in alerts if "[CRITICAL]" in a]
        assert len(critical_alerts) >= 1
        assert "retention" in critical_alerts[0]

    def test_alert_fires_on_skipped_watch(self):
        """Alert should fire when a dimension jumps HEALTHY → DEGRADING."""
        prev = _make_msv(acq="HEALTHY")
        new = _make_msv(acq="DEGRADING")
        alerts = alert_engine.check_and_alert("m_test", new, prev)
        skip_alerts = [a for a in alerts if "[SKIP_WATCH]" in a]
        assert len(skip_alerts) >= 1
        assert "acquisition" in skip_alerts[0]

    def test_alert_empty_when_no_change(self):
        """No alerts when all dimensions are stable HEALTHY."""
        prev = _make_msv()
        new = _make_msv()
        alerts = alert_engine.check_and_alert("m_test", new, prev)
        assert alerts == []

    def test_emergency_trigger_true_on_new_critical(self):
        """Emergency trigger should be True when dimension newly becomes CRITICAL."""
        prev = _make_msv(ret="DEGRADING")
        new = _make_msv(ret="CRITICAL")
        assert alert_engine.should_trigger_emergency_decision(new, prev) is True

    def test_emergency_trigger_false_when_already_critical(self):
        """Emergency trigger should be False when dimension was already CRITICAL."""
        prev = _make_msv(ret="CRITICAL")
        new = _make_msv(ret="CRITICAL")
        assert alert_engine.should_trigger_emergency_decision(new, prev) is False


class TestMSMConfigurableThresholds:
    def test_msm_roas_decline_uses_config(self):
        """MSM acquisition state reads msm_roas_decline_ratio from settings.

        Default: roas_7d >= roas_baseline * 0.9 → HEALTHY.
        Patch ratio to 1.5 → same signals now trigger DEGRADING.
        """
        from src.decision_engine.config import settings

        # Signals: cac is elevated (triggers degrading check) but roas looks fine
        # at default ratio 0.9 (roas_7d=4.5 >= 5.0*0.9=4.5 → exactly at boundary)
        signals = _base_signals(
            cac_7d=11.6,          # > 10 * 1.15 → cac_exceeds_degrading = True
            cac_baseline_30d=10.0,
            roas_7d=4.6,          # >= 5.0 * 0.9 (4.5) → NOT declining at default
            roas_baseline_30d=5.0,
        )

        original = settings.msm_roas_decline_ratio
        try:
            # At default ratio=0.9: roas_7d(4.6) >= 5.0*0.9(4.5) → not declining → WATCH
            state_default, _ = msm._compute_acquisition_state(signals)
            assert state_default.value == "WATCH", (
                f"Expected WATCH at default ratio, got {state_default.value}"
            )

            # Patch ratio to 0.95: roas_7d(4.6) < 5.0*0.95(4.75) → declining → DEGRADING
            settings.msm_roas_decline_ratio = 0.95
            state_patched, _ = msm._compute_acquisition_state(signals)
            assert state_patched.value == "DEGRADING", (
                f"Expected DEGRADING after patching ratio to 0.95, got {state_patched.value}"
            )
        finally:
            settings.msm_roas_decline_ratio = original
