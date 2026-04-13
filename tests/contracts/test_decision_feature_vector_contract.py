# ── Contract Tests — DecisionFeatureVector ────────────────────────────────────
# Enforces the invariants of ADR-0005: Feature Plane as logical concept.
# DecisionFeatureVector is the authoritative continuous-feature contract for
# scoring models and the Phase 3 LinUCB bandit. Any change that causes these
# tests to fail must be accompanied by an ADR update or a new superseding ADR.
#
# Reference: V3/docs/adr/0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md
# ─────────────────────────────────────────────────────────────────────────────
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.decision_engine.contracts import DecisionFeatureVector


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dfv(**kwargs) -> DecisionFeatureVector:
    """Return a valid DecisionFeatureVector with all fields None (default)."""
    return DecisionFeatureVector(**kwargs)


# ── Immutability ──────────────────────────────────────────────────────────────

def test_decision_feature_vector_is_frozen():
    """DecisionFeatureVector must be immutable (frozen=True).

    Enforces: ADR-0005 — feature vector is a point-in-time snapshot.
    Mutation after construction would violate the logging contract.
    If this test fails: restore frozen=True to DecisionFeatureVector.model_config.
    """
    dfv = _dfv()
    with pytest.raises((ValidationError, TypeError)):
        dfv.inventory_days = 10.0  # type: ignore[misc]


# ── computed_at field ─────────────────────────────────────────────────────────

def test_computed_at_exists_and_is_datetime():
    """computed_at must exist on every DecisionFeatureVector instance.

    Enforces: ADR-0005 — feature snapshots must be timestamped for offline replay.
    If this test fails: computed_at was removed from DecisionFeatureVector.
    """
    dfv = _dfv()
    assert hasattr(dfv, "computed_at")
    assert isinstance(dfv.computed_at, datetime)


def test_computed_at_default_is_utc():
    """computed_at default must be timezone-aware (UTC)."""
    dfv = _dfv()
    assert dfv.computed_at.tzinfo is not None


def test_computed_at_accepts_explicit_datetime():
    """computed_at can be set explicitly."""
    ts = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
    dfv = _dfv(computed_at=ts)
    assert dfv.computed_at == ts


# ── Valid values accepted ─────────────────────────────────────────────────────

def test_all_fields_accept_valid_values():
    """All feature fields accept valid positive values in their valid ranges.

    Enforces: ADR-0005 — all fields named in the contract must be settable.
    """
    dfv = DecisionFeatureVector(
        inventory_days=14.5,
        margin_pct=0.35,
        repeat_rate_7d=0.22,
        cvr_7d=0.03,
        cvr_30d=0.04,
        promo_redemption_30d=0.60,
        stock_pressure_score=0.75,
        churn_score=0.15,
        seasonality_index=1.2,
        benchmark_gap_score=-0.05,
    )
    assert dfv.inventory_days == 14.5
    assert dfv.margin_pct == 0.35
    assert dfv.repeat_rate_7d == 0.22


def test_all_fields_default_to_none():
    """All feature fields default to None (Phase 1: incomplete signals).

    Enforces: ADR-0005 — from_signals() populates what is available.
    """
    dfv = _dfv()
    assert dfv.inventory_days is None
    assert dfv.margin_pct is None
    assert dfv.repeat_rate_7d is None
    assert dfv.cvr_7d is None
    assert dfv.cvr_30d is None
    assert dfv.promo_redemption_30d is None
    assert dfv.stock_pressure_score is None
    assert dfv.churn_score is None


# ── Rate fields: [0.0, 1.0] ───────────────────────────────────────────────────

_RATE_FIELDS = [
    "repeat_rate_7d",
    "cvr_7d",
    "cvr_30d",
    "promo_redemption_30d",
    "churn_score",
    "stock_pressure_score",
]


@pytest.mark.parametrize("field", _RATE_FIELDS)
def test_rate_field_rejects_above_1(field):
    """Rate fields must reject values above 1.0.

    Enforces: ADR-0005 — rate fields are fractions in [0, 1].
    If this test fails for field {field}: the ge/le constraint was removed.
    """
    with pytest.raises(ValidationError):
        DecisionFeatureVector(**{field: 1.01})


@pytest.mark.parametrize("field", _RATE_FIELDS)
def test_rate_field_rejects_below_0(field):
    """Rate fields must reject values below 0.0."""
    with pytest.raises(ValidationError):
        DecisionFeatureVector(**{field: -0.01})


@pytest.mark.parametrize("field", _RATE_FIELDS)
def test_rate_field_accepts_boundary_values(field):
    """Rate fields must accept 0.0 and 1.0 (boundary values)."""
    dfv_low = DecisionFeatureVector(**{field: 0.0})
    assert getattr(dfv_low, field) == 0.0

    dfv_high = DecisionFeatureVector(**{field: 1.0})
    assert getattr(dfv_high, field) == 1.0


@pytest.mark.parametrize("field", _RATE_FIELDS)
def test_rate_field_accepts_none(field):
    """Rate fields must accept None (Phase 1: signal may be missing)."""
    dfv = DecisionFeatureVector(**{field: None})
    assert getattr(dfv, field) is None


# ── inventory_days: non-negative ──────────────────────────────────────────────

def test_inventory_days_rejects_negative():
    """inventory_days must reject negative values.

    Enforces: ADR-0005 — negative days-of-supply has no physical meaning.
    """
    with pytest.raises(ValidationError):
        _dfv(inventory_days=-1.0)


def test_inventory_days_accepts_zero():
    """inventory_days=0.0 means stockout — valid edge case."""
    dfv = _dfv(inventory_days=0.0)
    assert dfv.inventory_days == 0.0


def test_inventory_days_accepts_positive():
    """inventory_days accepts any positive float."""
    dfv = _dfv(inventory_days=30.0)
    assert dfv.inventory_days == 30.0


# ── margin_pct: [0.0, 1.0] ────────────────────────────────────────────────────

def test_margin_pct_rejects_above_1():
    """margin_pct must reject values above 1.0 (100% margin is not a valid state)."""
    with pytest.raises(ValidationError):
        _dfv(margin_pct=1.01)


def test_margin_pct_rejects_negative():
    """margin_pct must reject negative values."""
    with pytest.raises(ValidationError):
        _dfv(margin_pct=-0.01)


def test_margin_pct_accepts_valid_range():
    """margin_pct accepts 0.0 and 1.0 and typical CPG values."""
    assert _dfv(margin_pct=0.0).margin_pct == 0.0
    assert _dfv(margin_pct=0.35).margin_pct == 0.35
    assert _dfv(margin_pct=1.0).margin_pct == 1.0


# ── Round-trip serialization ──────────────────────────────────────────────────

def test_decision_feature_vector_round_trip():
    """DecisionFeatureVector(**dfv.model_dump()) must produce an equal object.

    Enforces: ADR-0005 — feature vectors must survive serialization for offline replay.
    """
    ts = datetime(2026, 4, 9, 0, 0, 0, tzinfo=timezone.utc)
    original = DecisionFeatureVector(
        computed_at=ts,
        inventory_days=10.0,
        margin_pct=0.35,
        repeat_rate_7d=0.22,
        cvr_7d=0.03,
    )
    restored = DecisionFeatureVector(**original.model_dump())
    assert restored == original


def test_from_signals_produces_valid_instance():
    """from_signals() classmethod must return a valid DecisionFeatureVector.

    Enforces: ADR-0005 — from_signals() is the pipeline entry point.
    """
    signals = {
        "inventory_days_p10": 14.0,
        "avg_margin_pct": 0.35,
        "repeat_purchase_rate": 0.22,
        "checkout_cvr": 0.03,
        "overdue_ratio": 0.15,
    }
    dfv = DecisionFeatureVector.from_signals(signals)
    assert isinstance(dfv, DecisionFeatureVector)
    assert dfv.inventory_days == 14.0
    assert dfv.margin_pct == 0.35
