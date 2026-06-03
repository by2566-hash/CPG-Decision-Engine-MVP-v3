from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import app
from src.decision_engine.config import settings
from src.decision_engine.contracts import DecisionCard, ImpactEstimate
from src.decision_engine.layer0_data.partner_signal_adapter import PartnerSignalSnapshot


client = TestClient(app, headers={"X-API-Key": settings.api_key})


def _request() -> dict:
    return {
        "user_id": "u_partner",
        "brand_id": "techhub",
        "growth": 40,
        "margin": 30,
        "inventory": 20,
        "retention": 10,
    }


def _card() -> DecisionCard:
    return DecisionCard(
        card_id="dc_test",
        merchant_id="u_partner",
        module="promotion",
        msm_state="DEGRADING",
        pattern_detected="Low promotion incrementality",
        diagnosis="Promotion efficiency is below the configured threshold.",
        action_id="PROMO_REBALANCE",
        recommended_action="PROMO_REBALANCE",
        impact_estimate=ImpactEstimate(
            conservative=100,
            expected=500,
            optimistic=800,
            confidence=0.30,
        ),
        urgency_score=0.5,
        quality_score=0.7,
        final_score=0.61,
        policy_version="default_v1",
        constraints_passed=True,
        merchant_copy={
            "diagnosis": "Promotion efficiency is below the configured threshold.",
            "recommendation": "Shift discount exposure toward incremental customers.",
            "impact_narrative": "Expected impact is directionally positive.",
            "confidence_statement": "Hypothesis based on benchmark priors.",
        },
    )


def test_partner_decision_cards_returns_json_cards():
    snapshot = PartnerSignalSnapshot(
        user_id="u_partner",
        merchant_id="u_partner",
        brand_id="techhub",
        signals={"promo_incrementality": 0.60},
        data_source="decision_health_score+decision_metric_value",
    )
    policy = {
        "policy_version": "default_v1",
        "mode": "shadow",
        "msm_state": {"promotion": "DEGRADING"},
        "alerts": [],
        "weekly_plan": {},
    }

    with (
        patch("api.app.load_partner_decision_signals", return_value=snapshot, create=True),
        patch("api.app.run_once", return_value=(policy, [_card()])),
    ):
        resp = client.post("/partner/decision-cards", json=_request())

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "u_partner"
    assert data["merchant_id"] == "u_partner"
    assert data["brand_id"] == "techhub"
    assert data["data_source"] == "decision_health_score+decision_metric_value"
    assert data["applied_objective_weights"]["growth"] == 0.4
    assert data["recommendations"][0]["title"] == "Low promotion incrementality"
    assert (
        data["recommendations"][0]["recommendation"]
        == "Shift discount exposure toward incremental customers."
    )
    assert data["recommendations"][0]["revenueImpact"] == "+$500/mo"
    assert data["recommendations"][0]["brand"] == "techhub"
    assert data["recommendations"][0]["policyGates"][0]["status"] == "pass"
    assert {
        gate["status"] for gate in data["recommendations"][0]["policyGates"]
    } <= {"pass", "warn", "block"}
    assert set(data["recommendations"][0]) >= {
        "id",
        "title",
        "module",
        "brand",
        "priority",
        "revenueImpact",
        "marginImpact",
        "confidence",
        "decisionScore",
        "recommendation",
        "whyNow",
        "actions",
        "policyGates",
        "trace",
        "diagnosis",
        "primaryBottleneck",
        "firstAction",
        "estimatedUpside",
        "evidence",
        "decisionRisk",
        "funnel",
        "funnelInsight",
        "whatLooksHealthy",
        "actionsPlan",
        "doNotChangeYet",
    }
    assert data["recommendations"][0]["id"] == "dc_test"
    assert data["recommendations"][0]["module"] == "Promotion"


def test_partner_decision_cards_passes_normalized_signals_into_pipeline():
    snapshot = PartnerSignalSnapshot(
        user_id="u_partner",
        merchant_id="u_partner",
        brand_id="techhub",
        signals={"promo_incrementality": 0.60, "monthly_gmv": 50000},
        data_source="decision_health_score+decision_metric_value",
    )
    policy = {
        "policy_version": "default_v1",
        "mode": "shadow",
        "msm_state": {"promotion": "DEGRADING"},
        "alerts": [],
        "weekly_plan": {},
    }

    with (
        patch("api.app.load_partner_decision_signals", return_value=snapshot, create=True),
        patch("api.app.run_once", return_value=(policy, [_card()])) as run_once,
    ):
        resp = client.post("/partner/decision-cards", json=_request())

    assert resp.status_code == 200
    run_once.assert_called_once()
    assert run_once.call_args.args[0] == "u_partner"
    assert run_once.call_args.kwargs["signals"]["promo_incrementality"] == 0.60
    assert run_once.call_args.kwargs["signals"]["frontend_objective_weights"] == {
        "growth": 0.4,
        "margin": 0.3,
        "inventory": 0.2,
        "retention": 0.1,
    }
    assert run_once.call_args.kwargs["signals"]["policy_weight_overrides"][
        "gmv_lift"
    ] == 0.4


def test_partner_decision_cards_rejects_zero_objective_weights():
    payload = {
        "user_id": "u_partner",
        "growth": 0,
        "margin": 0,
        "inventory": 0,
        "retention": 0,
    }

    resp = client.post("/partner/decision-cards", json=payload)

    assert resp.status_code == 422


def test_partner_decision_cards_rejects_out_of_range_objective_weights():
    payload = {
        "user_id": "u_partner",
        "growth": 101,
        "margin": 0,
        "inventory": 0,
        "retention": 0,
    }

    resp = client.post("/partner/decision-cards", json=payload)

    assert resp.status_code == 422


def test_frontend_recommendation_uses_block_for_failed_constraint_gate():
    from api.app import _decision_card_to_frontend_recommendation

    card = _card()
    card.constraints_passed = False
    card.violations = ["margin_gate:below_floor"]

    mapped = _decision_card_to_frontend_recommendation(card, "u_partner", "techhub")

    assert mapped["brand"] == "techhub"
    assert mapped["policyGates"][0]["status"] == "block"
    assert "margin_gate" in mapped["policyGates"][0]["detail"]


def test_partner_decision_cards_requires_api_key():
    unauthenticated = TestClient(app)

    resp = unauthenticated.post("/partner/decision-cards", json=_request())

    assert resp.status_code in {401, 403}


def test_existing_decision_endpoint_serializes_decision_cards():
    policy = {
        "policy_version": "default_v1",
        "mode": "shadow",
        "msm_state": {"promotion": "DEGRADING"},
        "emergency_triggered": False,
        "alerts": [],
        "weekly_plan": {},
    }

    with (
        patch("api.app.rollout.is_kill_switch_active", return_value=False),
        patch("api.app.run_once", return_value=(policy, [_card()])),
    ):
        resp = client.get("/decision/m_partner")

    assert resp.status_code == 200
    data = resp.json()
    assert data["top_actions"][0]["card_id"] == "dc_test"
    assert isinstance(data["top_actions"][0]["created_at"], str)
