# ── Layer 3 Tests · CPG Hard Constraints ─────────────────────────────────
# Tests for ConstraintEngine.check_all() → PolicyDecision.
# Covers all 7 constraints, Phase 1 missing-signal behaviour, pipeline
# integration (constraints_result is real PolicyDecision, not a stub),
# and weighted risk_penalty values.
# ───────────────────────────────────────────────────────────────────────────
import logging
from datetime import datetime, timezone

import pytest

from src.decision_engine.layer3_value.constraints import ConstraintEngine, _VIOLATION_WEIGHTS
from src.decision_engine.contracts import MerchantStateVector, PolicyDecision

_POLICY = {}  # policy param not yet used — placeholder for future extensibility

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    return ConstraintEngine()


@pytest.fixture
def discount_candidate():
    """A DISCOUNT_10PCT candidate with module retention."""
    return {"action_id": "DISCOUNT_10PCT", "module": "retention", "action_family": "DISCOUNT"}


@pytest.fixture
def non_discount_candidate():
    return {"action_id": "REMINDER_ONLY", "module": "retention", "action_family": "REMINDER"}


@pytest.fixture
def full_signals():
    """Complete signals that pass all constraints."""
    return {
        "margin_pct": 0.40,                # post-discount: 0.40 - 0.10 = 0.30 >= 0.15
        "last_action_type": "REMINDER",
        "days_since_last_action": 3,
        "promo_incrementality": 0.50,
        "customer_orders_count": 5,
        "inventory_days_p10": 10.0,
    }


# ── Return type ───────────────────────────────────────────────────────────


def test_check_all_returns_policy_decision(engine, discount_candidate, full_signals):
    """check_all() must return a PolicyDecision instance."""
    pd = engine.check_all(discount_candidate, full_signals, _POLICY)
    assert isinstance(pd, PolicyDecision)
    assert pd.eligible is True
    assert pd.hard_reject is False
    assert pd.risk_penalty == 0.0
    assert pd.violations == []
    assert pd.rollback_required is True


# ── Margin floor ──────────────────────────────────────────────────────────


def test_margin_floor_blocks_loss_making_discount(engine, discount_candidate):
    """Discount leaving post-margin < 0.15 must be blocked."""
    # 0.20 - 0.10 = 0.10 < 0.15
    pd = engine.check_all(discount_candidate, {"margin_pct": 0.20}, _POLICY)
    assert not pd.eligible
    assert pd.hard_reject is True
    assert any("margin_floor" in v for v in pd.violations)
    # Violation encodes the actual post-margin value
    assert any("0.10" in v for v in pd.violations)
    # Weighted penalty: margin_floor = 3.0
    assert pd.risk_penalty == _VIOLATION_WEIGHTS["margin_floor"]


def test_margin_floor_passes_when_margin_sufficient(engine, discount_candidate):
    """Discount leaving post-margin >= 0.15 must not be blocked."""
    # 0.40 - 0.10 = 0.30 >= 0.15
    pd = engine.check_all(discount_candidate, {"margin_pct": 0.40}, _POLICY)
    assert not any("margin_floor" in v for v in pd.violations)


# ── Discount last resort ──────────────────────────────────────────────────


def test_discount_last_resort_blocks_when_no_prior_reminder(engine, discount_candidate):
    """Discount without a prior REMINDER must be blocked."""
    pd = engine.check_all(
        discount_candidate,
        {"last_action_type": "PUSH_NOTIFICATION", "days_since_last_action": 2},
        _POLICY,
    )
    assert not pd.eligible
    assert any("discount_last_resort" in v for v in pd.violations)
    assert any("no_prior_reminder" in v for v in pd.violations)


def test_discount_last_resort_passes_when_reminder_was_sent(engine, discount_candidate):
    """Discount preceded by REMINDER within 7 days must pass."""
    pd = engine.check_all(
        discount_candidate,
        {"last_action_type": "REMINDER", "days_since_last_action": 5},
        _POLICY,
    )
    assert not any("discount_last_resort" in v for v in pd.violations)


# ── Cold prospect gate ────────────────────────────────────────────────────


def test_cold_prospect_gate_blocks_first_time_visitor_discount(engine, discount_candidate):
    """customer_orders_count=0 must block discount actions."""
    pd = engine.check_all(discount_candidate, {"customer_orders_count": 0}, _POLICY)
    assert not pd.eligible
    assert any("cold_prospect_gate" in v for v in pd.violations)
    assert any("first_time_visitor" in v for v in pd.violations)


def test_cold_prospect_gate_passes_for_returning_customer(engine, discount_candidate):
    """customer_orders_count > 0 must allow discount actions."""
    pd = engine.check_all(discount_candidate, {"customer_orders_count": 2}, _POLICY)
    assert not any("cold_prospect_gate" in v for v in pd.violations)


# ── Incrementality ────────────────────────────────────────────────────────


def test_incrementality_blocks_when_below_threshold(engine, discount_candidate):
    """promo_incrementality < 0.30 must block discount."""
    pd = engine.check_all(discount_candidate, {"promo_incrementality": 0.15}, _POLICY)
    assert not pd.eligible
    assert any("incrementality" in v for v in pd.violations)
    assert any("0.150" in v for v in pd.violations)


def test_incrementality_passes_when_above_threshold(engine, discount_candidate):
    """promo_incrementality >= 0.30 must allow discount."""
    pd = engine.check_all(discount_candidate, {"promo_incrementality": 0.45}, _POLICY)
    assert not any("incrementality" in v for v in pd.violations)


# ── Missing signal — Phase 1 data gap ────────────────────────────────────


def test_missing_signal_passes_with_warning_not_blocks(
    engine, discount_candidate, caplog
):
    """All constraints with missing signals must PASS (not block) and log a warning."""
    with caplog.at_level(logging.WARNING):
        pd = engine.check_all(discount_candidate, {}, _POLICY)

    # Phase 1: missing signals → no violations (customer_orders_count defaults to 999)
    assert pd.violations == [], f"Expected no violations, got: {pd.violations}"
    assert pd.eligible is True
    assert pd.risk_penalty == 0.0
    # Warnings logged for skipped constraints
    warning_text = caplog.text
    assert "margin_pct not available" in warning_text or "margin_floor skipped" in warning_text


def test_non_discount_action_passes_all_constraints(engine, non_discount_candidate):
    """Non-discount actions are never blocked by discount-specific constraints."""
    # Even with signals that would fail discount constraints
    signals = {
        "margin_pct": 0.05,
        "customer_orders_count": 0,
        "promo_incrementality": 0.0,
        "last_action_type": "PUSH_NOTIFICATION",
        "days_since_last_action": 30,
        "inventory_days_p10": 1.0,
    }
    pd = engine.check_all(non_discount_candidate, signals, _POLICY)
    assert pd.eligible
    assert pd.violations == []
    assert pd.risk_penalty == 0.0


# ── Multiple violations + weighted risk_penalty ───────────────────────────


def test_check_all_returns_all_violations_not_just_first(engine, discount_candidate):
    """check_all must collect ALL violations, not stop at the first one."""
    # Signals that trigger: margin_floor + cold_prospect_gate + incrementality
    signals = {
        "margin_pct": 0.05,         # margin_floor: 0.05 - 0.10 = -0.05 < 0.15
        "customer_orders_count": 0, # cold_prospect_gate
        "promo_incrementality": 0.10,  # incrementality
        "last_action_type": "REMINDER",
        "days_since_last_action": 1,
        "inventory_days_p10": 10.0,
    }
    pd = engine.check_all(discount_candidate, signals, _POLICY)
    assert not pd.eligible
    assert len(pd.violations) >= 3, f"Expected >= 3 violations, got: {pd.violations}"
    assert any("margin_floor" in v for v in pd.violations)
    assert any("cold_prospect_gate" in v for v in pd.violations)
    assert any("incrementality" in v for v in pd.violations)


def test_weighted_risk_penalty_higher_than_count(engine, discount_candidate):
    """risk_penalty uses violation weights, not simple count.

    margin_floor (3.0) + cold_prospect_gate (1.5) = 4.5, not 2.0.
    """
    signals = {
        "margin_pct": 0.05,          # triggers margin_floor (weight 3.0)
        "customer_orders_count": 0,  # triggers cold_prospect_gate (weight 1.5)
        "promo_incrementality": 0.50,
        "last_action_type": "REMINDER",
        "days_since_last_action": 1,
        "inventory_days_p10": 10.0,
    }
    pd = engine.check_all(discount_candidate, signals, _POLICY)
    expected_penalty = (
        _VIOLATION_WEIGHTS["margin_floor"]
        + _VIOLATION_WEIGHTS["cold_prospect_gate"]
    )
    assert pd.risk_penalty == pytest.approx(expected_penalty), (
        f"Expected weighted penalty {expected_penalty}, got {pd.risk_penalty}"
    )


# ── Attribution window metadata ───────────────────────────────────────────


def test_attribution_window_set_on_candidate(engine, discount_candidate, full_signals):
    """check_all must set attribution_window_days on candidate as side effect."""
    candidate = {**discount_candidate, "module": "acquisition"}
    engine.check_all(candidate, full_signals, _POLICY)
    assert candidate["attribution_window_days"] == 30  # acquisition = 30d


def test_attribution_window_never_blocks(engine, discount_candidate, full_signals):
    """attribution_window is metadata-only — never adds a violation."""
    pd = engine.check_all(discount_candidate, full_signals, _POLICY)
    assert not any("attribution" in v for v in pd.violations)


# ── Inventory gate ────────────────────────────────────────────────────────


def test_inventory_gate_blocks_discount_when_stock_critical(engine, discount_candidate):
    """inventory_days_p10 < 5 must block discount."""
    signals = {"inventory_days_p10": 3.0, "margin_pct": 0.40,
               "last_action_type": "REMINDER", "days_since_last_action": 2,
               "promo_incrementality": 0.50, "customer_orders_count": 5}
    pd = engine.check_all(discount_candidate, signals, _POLICY)
    assert not pd.eligible
    assert any("inventory_gate" in v for v in pd.violations)
    assert any("3.0" in v for v in pd.violations)
    # inventory_gate weight = 2.5
    assert pd.risk_penalty == pytest.approx(_VIOLATION_WEIGHTS["inventory_gate"])


def test_inventory_gate_passes_when_stock_sufficient(engine, discount_candidate, full_signals):
    """inventory_days_p10 >= 5 must not block discount."""
    pd = engine.check_all(discount_candidate, full_signals, _POLICY)
    assert not any("inventory_gate" in v for v in pd.violations)


# ── Pipeline integration ──────────────────────────────────────────────────


def test_pipeline_uses_real_constraints_not_stub():
    """pipeline._generate_candidates must wire real ConstraintEngine → PolicyDecision.

    A cold-prospect signal (customer_orders_count=0) must produce PolicyDecision
    with eligible=False on any generated discount candidates.
    """
    from src.decision_engine import layer4_serving as serving
    from src.decision_engine.layer4_serving import pipeline
    from src.decision_engine.contracts import MerchantStateVector

    msm_state = MerchantStateVector(
        merchant_id="test_pipeline_constraints",
        computed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        retention_state="DEGRADING",
        acquisition_state="HEALTHY",
        conversion_state="HEALTHY",
        promotion_state="HEALTHY",
        retention_urgency=0.6,
    )

    signals = {
        "customer_orders_count": 0,   # cold prospect — all discounts must be blocked
        "margin_pct": 0.40,
        "promo_incrementality": 0.50,
        "last_action_type": "REMINDER",
        "days_since_last_action": 3,
        "inventory_days_p10": 10.0,
    }

    policy = {
        "policy_version": "test_v1",
        "policy_weights": {"gmv_lift": 0.4, "margin_lift": 0.3,
                            "inventory_risk_reduction": 0.2, "retention_lift": 0.1},
        "risk_budget": {},
        "beta1": 0.65,
        "beta2": 0.25,
        "beta3": 0.10,
    }

    candidates = pipeline._generate_candidates(msm_state, signals, policy)

    # Every discount candidate must have a real PolicyDecision with eligible=False
    discount_candidates = [
        c for c in candidates if "DISCOUNT" in c.get("action_id", "").upper()
    ]
    assert discount_candidates, "Expected at least one discount candidate for DEGRADING retention"

    for c in discount_candidates:
        result = c.get("constraints_result")
        assert result is not None, f"constraints_result missing on {c['action_id']}"
        assert isinstance(result, PolicyDecision), (
            f"Expected PolicyDecision, got {type(result)} for {c['action_id']}"
        )
        assert not result.eligible, (
            f"{c['action_id']} should be blocked for cold prospect "
            f"(customer_orders_count=0) but got eligible=True"
        )
        assert any("cold_prospect_gate" in v for v in result.violations), (
            f"Expected cold_prospect_gate violation, got: {result.violations}"
        )
        assert result.risk_penalty > 0, (
            f"Expected risk_penalty > 0 for blocked candidate, got: {result.risk_penalty}"
        )


# ── Constraint 7: Diagnostic prerequisite ────────────────────────────────


class TestDiagnosticPrerequisite:
    """Constraint 7: FLOW_CHANGE / CREATIVE_CONTROL require a prior DIAGNOSTIC.

    Missing signal → PASS with logged warning (Phase 1 data gap policy).
    Prior DIAGNOSTIC within 14 days → PASS.
    Prior DIAGNOSTIC older than 14 days → VIOLATION.
    Non-DIAGNOSTIC last action → VIOLATION.
    """

    def test_flow_change_without_prior_diagnostic_is_violation(self, engine):
        candidate = {
            "action_id": "FC_001",
            "action_type": "FLOW_CHANGE",
            "module": "conversion",
            "action_family": "FLOW_CHANGE",
        }
        signals = {
            "last_action_type": "DISCOUNT",
            "days_since_last_action": 3,
            "margin_pct": 0.40,
            "customer_orders_count": 5,
        }
        pd = engine.check_all(candidate, signals, _POLICY)
        assert any("diagnostic_prerequisite" in v for v in pd.violations), (
            f"Expected diagnostic_prerequisite violation, got: {pd.violations}"
        )
        assert pd.risk_penalty >= _VIOLATION_WEIGHTS["diagnostic_prerequisite"]

    def test_flow_change_with_recent_diagnostic_passes(self, engine):
        candidate = {
            "action_id": "FC_001",
            "action_type": "FLOW_CHANGE",
            "module": "conversion",
            "action_family": "FLOW_CHANGE",
        }
        signals = {
            "last_action_type": "DIAGNOSTIC",
            "days_since_last_action": 7,   # within 14-day window
            "margin_pct": 0.40,
            "customer_orders_count": 5,
        }
        pd = engine.check_all(candidate, signals, _POLICY)
        assert not any("diagnostic_prerequisite" in v for v in pd.violations)

    def test_diagnostic_expired_over_14_days_is_violation(self, engine):
        candidate = {
            "action_id": "FC_001",
            "action_type": "FLOW_CHANGE",
            "module": "conversion",
            "action_family": "FLOW_CHANGE",
        }
        signals = {
            "last_action_type": "DIAGNOSTIC",
            "days_since_last_action": 15,   # expired
            "margin_pct": 0.40,
            "customer_orders_count": 5,
        }
        pd = engine.check_all(candidate, signals, _POLICY)
        assert any("diagnostic_prerequisite" in v for v in pd.violations)

    def test_missing_last_action_type_passes_with_warning(self, engine, caplog):
        candidate = {
            "action_id": "CC_001",
            "action_type": "CREATIVE_CONTROL",
            "module": "acquisition",
            "action_family": "CREATIVE_CONTROL",
        }
        signals = {
            "margin_pct": 0.40,
            "customer_orders_count": 5,
            # last_action_type intentionally absent — Phase 1 data gap
        }
        with caplog.at_level(logging.WARNING):
            pd = engine.check_all(candidate, signals, _POLICY)
        assert not any("diagnostic_prerequisite" in v for v in pd.violations)
        assert "Phase 1 data gap" in caplog.text

    def test_non_execution_action_type_skips_check(self, engine):
        """REMINDER action_type must not trigger diagnostic prerequisite check."""
        candidate = {
            "action_id": "R_001",
            "action_type": "REMINDER",
            "module": "retention",
            "action_family": "REMINDER",
        }
        signals = {
            "margin_pct": 0.40,
            "customer_orders_count": 5,
            "last_action_type": "DISCOUNT",   # no prior diagnostic — irrelevant for REMINDER
        }
        pd = engine.check_all(candidate, signals, _POLICY)
        assert not any("diagnostic_prerequisite" in v for v in pd.violations)
