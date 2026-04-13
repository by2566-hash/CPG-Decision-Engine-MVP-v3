# ── Feature Plane Tests — FeatureBuilder ─────────────────────────────────────
# Unit tests for FeatureBuilder.build() and its private helpers.
# Each helper is tested in isolation where possible.
#
# Reference: V3/docs/adr/0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md
# ─────────────────────────────────────────────────────────────────────────────
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.decision_engine.contracts import DecisionFeatureVector, MerchantStateVector
from src.decision_engine.feature_plane import FeatureBuilder


# ── Helpers ───────────────────────────────────────────────────────────────────

def _msv(**kwargs) -> MerchantStateVector:
    defaults = dict(
        merchant_id="test_merchant",
        computed_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return MerchantStateVector(**defaults)


def _complete_signals() -> dict:
    return {
        "inventory_days": 14.0,
        "margin_pct": 0.33,
        "repeat_rate_7d": 0.22,
        "cvr_7d": 0.030,
        "cvr_30d": 0.027,
        "promo_redemption_30d": 0.42,
        "churn_score": 0.15,
        "seasonality_index": 1.1,
        "benchmark_gap_score": -0.05,
    }


# ── Instantiation ─────────────────────────────────────────────────────────────

def test_feature_builder_is_instantiable():
    """FeatureBuilder must be importable and instantiable with no arguments."""
    fb = FeatureBuilder()
    assert fb is not None


# ── Complete signals ──────────────────────────────────────────────────────────

def test_build_with_complete_signals_returns_valid_dfv():
    """build() with all signals present must return a valid DecisionFeatureVector."""
    fb = FeatureBuilder()
    dfv = fb.build(_complete_signals(), _msv())

    assert isinstance(dfv, DecisionFeatureVector)
    assert dfv.inventory_days == 14.0
    assert dfv.margin_pct == 0.33
    assert dfv.repeat_rate_7d == 0.22
    assert dfv.cvr_7d == 0.030
    assert dfv.cvr_30d == 0.027
    assert dfv.promo_redemption_30d == 0.42
    assert dfv.churn_score == 0.15
    assert dfv.seasonality_index == 1.1
    assert dfv.benchmark_gap_score == -0.05


# ── Missing signals → defaults + log warning ──────────────────────────────────

def test_build_with_empty_signals_uses_defaults(caplog):
    """Missing signals must produce documented defaults and emit DEBUG warnings."""
    fb = FeatureBuilder()
    import logging
    with caplog.at_level(logging.DEBUG, logger="src.decision_engine.feature_plane.builder"):
        dfv = fb.build({}, _msv())

    assert isinstance(dfv, DecisionFeatureVector)
    assert dfv.inventory_days == 0.0
    assert dfv.margin_pct == 0.0
    assert dfv.repeat_rate_7d == 0.0
    assert dfv.cvr_7d == 0.0
    assert dfv.cvr_30d == 0.0
    assert dfv.promo_redemption_30d == 0.0
    assert dfv.churn_score == 0.0
    assert dfv.seasonality_index == 1.0      # special default: 1.0 = no seasonal effect
    assert dfv.benchmark_gap_score == 0.0

    # At least some missing-signal warnings should have been logged
    assert any("missing" in rec.message.lower() or "defaulting" in rec.message.lower()
               for rec in caplog.records)


def test_build_with_partial_signals_fills_missing():
    """build() with some signals present must use their values and default the rest."""
    fb = FeatureBuilder()
    dfv = fb.build({"inventory_days": 10.0, "margin_pct": 0.30}, _msv())

    assert dfv.inventory_days == 10.0
    assert dfv.margin_pct == 0.30
    assert dfv.repeat_rate_7d == 0.0    # defaulted


# ── stock_pressure_score derivation ──────────────────────────────────────────

def test_stock_pressure_zero_when_inventory_healthy():
    """stock_pressure_score must be 0.0 when inventory_days >= 7."""
    fb = FeatureBuilder()
    dfv = fb.build({"inventory_days": 7.0}, _msv())
    assert dfv.stock_pressure_score == 0.0


def test_stock_pressure_zero_when_inventory_well_above_threshold():
    """stock_pressure_score must be 0.0 for any inventory_days >= 7."""
    fb = FeatureBuilder()
    dfv = fb.build({"inventory_days": 30.0}, _msv())
    assert dfv.stock_pressure_score == 0.0


def test_stock_pressure_one_when_inventory_zero():
    """stock_pressure_score must be 1.0 when inventory_days == 0."""
    fb = FeatureBuilder()
    dfv = fb.build({"inventory_days": 0.0}, _msv())
    assert dfv.stock_pressure_score == pytest.approx(1.0)


def test_stock_pressure_half_at_3_5_days():
    """stock_pressure_score must be 0.5 when inventory_days == 3.5."""
    fb = FeatureBuilder()
    dfv = fb.build({"inventory_days": 3.5}, _msv())
    assert dfv.stock_pressure_score == pytest.approx(0.5)


def test_stock_pressure_below_seven_days_nonzero():
    """stock_pressure_score must be > 0 for any inventory_days in (0, 7)."""
    fb = FeatureBuilder()
    dfv = fb.build({"inventory_days": 4.0}, _msv())
    assert 0.0 < dfv.stock_pressure_score < 1.0


# ── Out-of-range signal values: clamping ──────────────────────────────────────
# Design decision: clamp rather than raise.
# Rationale: raw Shopline signals can have data quality issues (e.g. a CVR
# slightly above 1.0 due to session counting). Clamping keeps the pipeline
# running; the FeatureBuilder logs a warning. Raising would halt the pipeline
# on a data quality issue unrelated to the decision being evaluated.

def test_rate_field_above_1_is_clamped():
    """Rate fields > 1.0 in signals must be clamped to 1.0 (not raise)."""
    fb = FeatureBuilder()
    dfv = fb.build({"cvr_7d": 1.5}, _msv())
    assert dfv.cvr_7d == pytest.approx(1.0)


def test_rate_field_below_0_is_clamped():
    """Rate fields < 0.0 in signals must be clamped to 0.0 (not raise)."""
    fb = FeatureBuilder()
    dfv = fb.build({"repeat_rate_7d": -0.1}, _msv())
    assert dfv.repeat_rate_7d == pytest.approx(0.0)


def test_margin_pct_above_1_is_clamped():
    """margin_pct > 1.0 must be clamped to 1.0."""
    fb = FeatureBuilder()
    dfv = fb.build({"margin_pct": 1.2}, _msv())
    assert dfv.margin_pct == pytest.approx(1.0)


def test_inventory_days_negative_is_clamped():
    """Negative inventory_days must be clamped to 0.0."""
    fb = FeatureBuilder()
    dfv = fb.build({"inventory_days": -5.0}, _msv())
    assert dfv.inventory_days == pytest.approx(0.0)


# ── seasonality and benchmark are unbounded ───────────────────────────────────

def test_seasonality_above_1_accepted():
    """seasonality_index > 1.0 is valid (peak season)."""
    fb = FeatureBuilder()
    dfv = fb.build({"seasonality_index": 2.5}, _msv())
    assert dfv.seasonality_index == 2.5


def test_benchmark_gap_negative_accepted():
    """benchmark_gap_score < 0 is valid (below category benchmark)."""
    fb = FeatureBuilder()
    dfv = fb.build({"benchmark_gap_score": -0.30}, _msv())
    assert dfv.benchmark_gap_score == -0.30


# ── computed_at ───────────────────────────────────────────────────────────────

def test_computed_at_is_set_to_utc():
    """built DecisionFeatureVector must have computed_at in UTC."""
    before = datetime.now(timezone.utc)
    fb = FeatureBuilder()
    dfv = fb.build(_complete_signals(), _msv())
    after = datetime.now(timezone.utc)

    assert dfv.computed_at.tzinfo is not None
    assert before <= dfv.computed_at <= after


# ── Produced object is frozen ─────────────────────────────────────────────────

def test_produced_dfv_is_frozen():
    """DecisionFeatureVector returned by build() must be immutable."""
    fb = FeatureBuilder()
    dfv = fb.build(_complete_signals(), _msv())

    with pytest.raises((ValidationError, TypeError)):
        dfv.inventory_days = 99.0  # type: ignore[misc]


# ── Signal key aliases ────────────────────────────────────────────────────────

def test_avg_margin_pct_alias_accepted():
    """avg_margin_pct is accepted as alias for margin_pct."""
    fb = FeatureBuilder()
    dfv = fb.build({"avg_margin_pct": 0.28}, _msv())
    assert dfv.margin_pct == 0.28


def test_repeat_purchase_rate_alias_accepted():
    """repeat_purchase_rate is accepted as alias for repeat_rate_7d."""
    fb = FeatureBuilder()
    dfv = fb.build({"repeat_purchase_rate": 0.19}, _msv())
    assert dfv.repeat_rate_7d == 0.19


def test_checkout_cvr_alias_accepted():
    """checkout_cvr is accepted as alias for cvr_7d."""
    fb = FeatureBuilder()
    dfv = fb.build({"checkout_cvr": 0.035}, _msv())
    assert dfv.cvr_7d == pytest.approx(0.035)


def test_overdue_ratio_alias_accepted():
    """overdue_ratio is accepted as alias for churn_score."""
    fb = FeatureBuilder()
    dfv = fb.build({"overdue_ratio": 0.40}, _msv())
    assert dfv.churn_score == pytest.approx(0.40)
