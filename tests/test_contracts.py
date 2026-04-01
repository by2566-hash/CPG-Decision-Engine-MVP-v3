# ── Contract Tests — DecisionCard, WSMTransition, ImpactEstimate ─────────
# Tests for the complete Pydantic models in contracts.py.
# ───────────────────────────────────────────────────────────────────────────
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.decision_engine.contracts import (
    DecisionCard,
    ImpactEstimate,
    Counterfactual,
    VerificationChain,
    VerificationStep,
    WSMTransition,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_verification_chain(all_passed: bool = True) -> VerificationChain:
    step = VerificationStep(name="test", passed=all_passed, value=1.0, threshold=1.0)
    return VerificationChain(
        msm_trigger=step,
        margin_gate=step,
        inventory_gate=step,
        conflict_check=step,
        all_passed=all_passed,
    )


def _make_card(**overrides) -> DecisionCard:
    """Return a valid DecisionCard with sensible defaults, accepting field overrides."""
    defaults = dict(
        card_id="dc_1_m1_retention",
        merchant_id="m1",
        module="retention",
        classification="HYPOTHESIS",
        validation_status="HYPOTHESIS",
        msm_state="DEGRADING",
        recommended_action="DISCOUNT_10PCT",
        action_id="DISCOUNT_10PCT",
        impact_estimate=ImpactEstimate(conservative=100, expected=500,
                                       optimistic=900, confidence=0.30),
        urgency_score=0.5,
        quality_score=0.5,
        policy_version="v1",
        verification_chain=_make_verification_chain(),
    )
    defaults.update(overrides)
    return DecisionCard(**defaults)


# ── Classification ────────────────────────────────────────────────────────


def test_decision_card_classification_recommendation():
    """confidence >= 0.60 → RECOMMENDATION."""
    assert DecisionCard.classify_from_confidence(0.60) == "RECOMMENDATION"
    assert DecisionCard.classify_from_confidence(0.75) == "RECOMMENDATION"
    assert DecisionCard.classify_from_confidence(1.00) == "RECOMMENDATION"


def test_decision_card_classification_hypothesis():
    """confidence < 0.60 → HYPOTHESIS."""
    assert DecisionCard.classify_from_confidence(0.30) == "HYPOTHESIS"
    assert DecisionCard.classify_from_confidence(0.59) == "HYPOTHESIS"
    assert DecisionCard.classify_from_confidence(0.00) == "HYPOTHESIS"


def test_decision_card_classification_boundary():
    """Boundary: exactly 0.60 → RECOMMENDATION."""
    assert DecisionCard.classify_from_confidence(0.60) == "RECOMMENDATION"
    assert DecisionCard.classify_from_confidence(0.5999) == "HYPOTHESIS"


# ── Module validation ─────────────────────────────────────────────────────


def test_decision_card_invalid_module_rejected():
    """module must be one of the 4 valid Literal values."""
    with pytest.raises(ValidationError) as exc_info:
        _make_card(module="invalid_module")
    assert "module" in str(exc_info.value).lower() or "literal" in str(exc_info.value).lower()


def test_decision_card_valid_modules_accepted():
    """All 4 valid module values must be accepted."""
    for module in ("retention", "acquisition", "conversion", "promotion"):
        card = _make_card(module=module)
        assert card.module == module


# ── Field bounds ──────────────────────────────────────────────────────────


def test_decision_card_urgency_score_above_1_rejected():
    """urgency_score > 1.0 must raise ValidationError."""
    with pytest.raises(ValidationError):
        _make_card(urgency_score=1.5)


def test_decision_card_urgency_score_below_0_rejected():
    """urgency_score < 0.0 must raise ValidationError."""
    with pytest.raises(ValidationError):
        _make_card(urgency_score=-0.1)


def test_decision_card_urgency_score_bounds_accepted():
    """urgency_score = 0.0 and 1.0 must be accepted."""
    card_low = _make_card(urgency_score=0.0)
    assert card_low.urgency_score == 0.0
    card_high = _make_card(urgency_score=1.0)
    assert card_high.urgency_score == 1.0


def test_decision_card_quality_score_bounds():
    """quality_score outside [0.0, 1.0] must raise ValidationError."""
    with pytest.raises(ValidationError):
        _make_card(quality_score=1.1)
    with pytest.raises(ValidationError):
        _make_card(quality_score=-0.01)


# ── Typed fields (not plain dict) ────────────────────────────────────────


def test_decision_card_impact_estimate_is_typed():
    """impact_estimate must be ImpactEstimate, not a plain dict."""
    card = _make_card()
    assert isinstance(card.impact_estimate, ImpactEstimate)
    assert card.impact_estimate.confidence == 0.30


def test_decision_card_verification_chain_is_typed():
    """verification_chain must be VerificationChain, not a plain dict."""
    card = _make_card()
    assert isinstance(card.verification_chain, VerificationChain)
    assert card.verification_chain.all_passed is True


def test_decision_card_counterfactual_typed_or_none():
    """counterfactual must be Counterfactual or None."""
    card_none = _make_card(counterfactual=None)
    assert card_none.counterfactual is None

    cf = Counterfactual(runner_up_action="REMINDER_ONLY", why_not="Lower expected lift")
    card_cf = _make_card(counterfactual=cf)
    assert isinstance(card_cf.counterfactual, Counterfactual)
    assert card_cf.counterfactual.runner_up_action == "REMINDER_ONLY"


# ── dict-style access backward compatibility ──────────────────────────────


def test_decision_card_dict_getitem_access():
    """card['field'] access must work for backward compat."""
    card = _make_card()
    assert card["module"] == "retention"
    assert card["action_id"] == "DISCOUNT_10PCT"
    assert card["urgency_score"] == 0.5


def test_decision_card_dict_contains():
    """'field' in card must work for backward compat."""
    card = _make_card()
    assert "module" in card
    assert "action_id" in card
    assert "nonexistent_field" not in card


def test_decision_card_dict_getitem_missing_raises_keyerror():
    """card['nonexistent'] must raise KeyError."""
    card = _make_card()
    with pytest.raises(KeyError):
        _ = card["nonexistent_field_xyz"]


# ── Pipeline integration: cards are DecisionCard instances ────────────────


def test_pipeline_returns_decision_card_objects_not_dicts():
    """run_once() must return DecisionCard instances, not plain dicts."""
    import sys
    from pathlib import Path
    from datetime import datetime, timezone
    from unittest.mock import patch

    # Import only after conftest has set up the DB
    from src.decision_engine.layer4_serving.pipeline import run_once

    signals = {
        "overdue_ratio": 1.6,
        "repeat_purchase_rate": 0.22,
        "days_since_last_order_p50": 45,
        "cac_7d": 10.0, "cac_baseline_30d": 10.0,
        "roas_7d": 3.0, "roas_baseline_30d": 3.0,
        "mobile_atc_rate": 0.15, "desktop_atc_rate": 0.18,
        "mobile_traffic_pct": 0.6, "checkout_cvr": 0.03,
        "promo_incrementality": 0.60, "existing_customer_promo_pct": 0.30,
        "promo_margin_delta": 0.02,
        "monthly_gmv": 50_000.0, "monthly_ad_spend": 5_000.0,
        "avg_order_value": 45.0, "monthly_orders": 1200, "avg_margin_pct": 0.35,
    }

    _, ranked = run_once("test_dc_types", signals=signals)

    # ranked may be empty if no cards passed the 5-Gate, but if any exist:
    for card in ranked:
        assert isinstance(card, DecisionCard), (
            f"Expected DecisionCard instance, got {type(card).__name__}. "
            "pipeline.py must instantiate DecisionCard objects at Step 12."
        )


# ── WSMTransition ─────────────────────────────────────────────────────────


def test_wsm_transition_model_has_required_fields():
    """WSMTransition must have merchant_id, action_id, was_executed, reward_status."""
    t = WSMTransition(merchant_id="m1", action_id="DISCOUNT_10PCT")
    assert t.was_executed is False
    assert t.reward_status == "pending"
    assert t.merchant_id == "m1"
    assert t.action_id == "DISCOUNT_10PCT"
    assert t.transition_id is None  # not set until DB insert


def test_wsm_transition_reward_status_validation():
    """reward_status must be pending / proxy / final."""
    t_proxy = WSMTransition(merchant_id="m1", action_id="X", reward_status="proxy")
    assert t_proxy.reward_status == "proxy"

    with pytest.raises(ValidationError):
        WSMTransition(merchant_id="m1", action_id="X", reward_status="invalid_status")


# ── ImpactEstimate ────────────────────────────────────────────────────────


def test_impact_estimate_defaults():
    """ImpactEstimate defaults to all zeros."""
    ie = ImpactEstimate()
    assert ie.conservative == 0.0
    assert ie.expected == 0.0
    assert ie.optimistic == 0.0
    assert ie.confidence == 0.0


def test_impact_estimate_full():
    """ImpactEstimate accepts and stores all 4 fields."""
    ie = ImpactEstimate(conservative=100, expected=500, optimistic=900, confidence=0.75)
    assert ie.expected == 500
    assert ie.confidence == 0.75
