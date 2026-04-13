# ── Contract Tests — DecisionState ───────────────────────────────────────────
# Enforces the invariants of ADR-0005: Feature Plane as logical concept.
# DecisionState carries the 4D MSM routing states for decision routing and
# explainability. It is strictly discrete — continuous values belong in
# DecisionFeatureVector, not here.
#
# Reference: V3/docs/adr/0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md
# ─────────────────────────────────────────────────────────────────────────────
import pytest
from pydantic import ValidationError

from src.decision_engine.contracts import DecisionState, MerchantStateVector


_VALID_STATES = ["HEALTHY", "WATCH", "DEGRADING", "CRITICAL"]
_DIMENSIONS = ["acquisition_state", "conversion_state", "retention_state", "promotion_state"]


# ── Immutability ──────────────────────────────────────────────────────────────

def test_decision_state_is_frozen():
    """DecisionState must be immutable (frozen=True).

    Enforces: ADR-0005 — state snapshot is a point-in-time view.
    If this test fails: restore frozen=True to DecisionState.model_config.
    """
    ds = DecisionState()
    with pytest.raises((ValidationError, TypeError)):
        ds.acquisition_state = "WATCH"  # type: ignore[misc]


# ── Valid literal values ───────────────────────────────────────────────────────

@pytest.mark.parametrize("dimension", _DIMENSIONS)
@pytest.mark.parametrize("state", _VALID_STATES)
def test_dimension_accepts_valid_literal(dimension, state):
    """Each dimension field must accept all 4 valid state literals.

    Enforces: ADR-0005 — MSM has exactly 4 states per dimension.
    """
    ds = DecisionState(**{dimension: state})
    assert getattr(ds, dimension) == state


@pytest.mark.parametrize("dimension", _DIMENSIONS)
def test_dimension_rejects_invalid_literal(dimension):
    """Each dimension field must reject values outside the 4 valid literals.

    Enforces: ADR-0005 — no free-form state strings allowed.
    If this test fails: dimension field was changed from Literal to str.
    Fix: restore Literal["HEALTHY", "WATCH", "DEGRADING", "CRITICAL"] type.
    """
    with pytest.raises(ValidationError):
        DecisionState(**{dimension: "UNKNOWN"})


@pytest.mark.parametrize("dimension", _DIMENSIONS)
def test_dimension_rejects_lowercase(dimension):
    """State literals must be uppercase — 'healthy' is not a valid state."""
    with pytest.raises(ValidationError):
        DecisionState(**{dimension: "healthy"})


# ── Defaults ──────────────────────────────────────────────────────────────────

def test_all_dimensions_default_to_healthy():
    """All dimension state fields must default to 'HEALTHY'.

    Enforces: ADR-0005 — default state is the baseline (no signal = no alert).
    """
    ds = DecisionState()
    for dim in _DIMENSIONS:
        assert getattr(ds, dim) == "HEALTHY"


def test_active_alerts_defaults_to_empty_list():
    """active_alerts must default to an empty list.

    Enforces: ADR-0005 — no alerts is the normal state.
    """
    ds = DecisionState()
    assert ds.active_alerts == []


def test_active_alerts_accepts_strings():
    """active_alerts must accept a list of alert strings."""
    ds = DecisionState(active_alerts=["CAC_SPIKE_7D", "ROAS_BELOW_TARGET"])
    assert len(ds.active_alerts) == 2
    assert "CAC_SPIKE_7D" in ds.active_alerts


# ── from_msv classmethod ──────────────────────────────────────────────────────

def test_from_msv_maps_all_dimensions():
    """from_msv() must map all 4 dimension states from MerchantStateVector.

    Enforces: ADR-0005 — DecisionState.from_msv() is the pipeline entry point.
    """
    from datetime import datetime, timezone
    msv = MerchantStateVector(
        merchant_id="m1",
        computed_at=datetime.now(timezone.utc),
        acquisition_state="WATCH",
        conversion_state="DEGRADING",
        retention_state="HEALTHY",
        promotion_state="CRITICAL",
    )
    ds = DecisionState.from_msv(msv)
    assert ds.acquisition_state == "WATCH"
    assert ds.conversion_state == "DEGRADING"
    assert ds.retention_state == "HEALTHY"
    assert ds.promotion_state == "CRITICAL"


# ── Round-trip serialization ──────────────────────────────────────────────────

def test_decision_state_round_trip():
    """DecisionState(**ds.model_dump()) must produce an equal object.

    Enforces: ADR-0005 — state snapshots must survive serialization.
    """
    original = DecisionState(
        acquisition_state="WATCH",
        conversion_state="DEGRADING",
        retention_state="HEALTHY",
        promotion_state="CRITICAL",
        active_alerts=["LOW_ROAS"],
    )
    restored = DecisionState(**original.model_dump())
    assert restored == original


def test_round_trip_preserves_alerts():
    """Round-trip must preserve active_alerts list."""
    original = DecisionState(active_alerts=["ALERT_A", "ALERT_B"])
    restored = DecisionState(**original.model_dump())
    assert restored.active_alerts == ["ALERT_A", "ALERT_B"]
