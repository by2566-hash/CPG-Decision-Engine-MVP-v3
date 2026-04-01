"""Tests for Layer 3: MerchantApprovalGate.

Covers:
  - High discount requires approval
  - Large budget requires approval
  - Low-risk does not require approval (when auto-actions enabled)
  - generate_approval_request returns all required fields
  - check_approval() returns ApprovalCheckResult (approved/pending)
  - /approve endpoint blocks unacknowledged high-risk actions
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from src.decision_engine import db_client
from src.decision_engine.contracts import Counterfactual, ImpactEstimate
from src.decision_engine.layer3_value.merchant_approval_gate import (
    ApprovalCheckResult,
    MerchantApprovalGate,
)

_client = TestClient(app)


gate = MerchantApprovalGate()


class TestMerchantApprovalGate:
    def test_high_discount_requires_approval(self):
        """Discount >= 15% always requires approval."""
        action = {"action_id": "DISCOUNT_15PCT", "discount_pct": 0.15}
        assert gate.requires_approval(action, {}) is True

        action_20 = {"action_id": "DISCOUNT_20PCT", "discount_pct": 0.20}
        assert gate.requires_approval(action_20, {}) is True

    def test_large_budget_requires_approval(self):
        """Budget change >= $1000/day always requires approval."""
        action = {
            "action_id": "INCREASE_AD_BUDGET",
            "budget_change_daily_usd": 1500.0,
        }
        assert gate.requires_approval(action, {}) is True

        action_exact = {
            "action_id": "INCREASE_AD_BUDGET",
            "budget_change_daily_usd": 1000.0,
        }
        assert gate.requires_approval(action_exact, {}) is True

    def test_low_risk_does_not_require_approval(self):
        """Low-risk action (discount < 10%, effort=low) auto-approved when flag on."""
        from src.decision_engine.config import settings

        original = settings.low_risk_auto_actions
        try:
            settings.low_risk_auto_actions = True
            action = {
                "action_id": "SEND_REMINDER",
                "discount_pct": 0.05,
                "effort": "low",
            }
            assert gate.requires_approval(action, {}) is False
        finally:
            settings.low_risk_auto_actions = original

    def test_generate_approval_request_has_all_fields(self):
        """Approval request must include all required keys."""
        action = {
            "action_id": "DISCOUNT_15PCT",
            "module": "retention",
            "description": "Apply 15% discount to top retention-risk SKUs",
        }
        impact = ImpactEstimate(
            conservative=500.0,
            expected=1200.0,
            optimistic=2000.0,
            confidence=0.30,
        )
        cf = Counterfactual(
            runner_up_action="REMINDER_ONLY",
            runner_up_estimate=400.0,
            why_not="REMINDER_ONLY estimated $400 vs $1200 for DISCOUNT_15PCT",
        )

        req = gate.generate_approval_request(action, impact, cf)

        assert "action_summary" in req
        assert "impact_narrative" in req
        assert "counterfactual_summary" in req
        assert "approve_url" in req
        assert "expires_in_hours" in req
        assert req["expires_in_hours"] == 48
        assert "RETENTION" in req["action_summary"]
        assert "$1,200" in req["impact_narrative"]
        assert req["counterfactual_summary"] is not None
        assert "REMINDER_ONLY" in req["counterfactual_summary"]


class TestCheckApproval:
    def test_low_risk_action_auto_approved(self):
        """check_approval() returns approved=True for low-risk action when flag on."""
        from src.decision_engine.config import settings

        original = settings.low_risk_auto_actions
        try:
            settings.low_risk_auto_actions = True
            action = {"action_id": "SEND_REMINDER", "discount_pct": 0.05, "effort": "low"}
            result = gate.check_approval(action, {})
            assert isinstance(result, ApprovalCheckResult)
            assert result.approved is True
            assert result.risk_level == "LOW"
        finally:
            settings.low_risk_auto_actions = original

    def test_high_risk_discount_requires_acknowledgment(self):
        """check_approval() returns approved=False when high-risk and not acknowledged."""
        action = {"action_id": "DISCOUNT_20PCT", "discount_pct": 0.20}
        result = gate.check_approval(action, {"high_risk_acknowledged": False})
        assert isinstance(result, ApprovalCheckResult)
        assert result.approved is False
        assert result.risk_level == "HIGH"
        assert result.requires_acknowledgment is True

    def test_high_risk_approved_with_acknowledgment(self):
        """check_approval() returns approved=True when high-risk and acknowledged."""
        action = {"action_id": "DISCOUNT_20PCT", "discount_pct": 0.20}
        result = gate.check_approval(
            action,
            {"high_risk_acknowledged": True, "risk_reason": "merchant opted in"},
        )
        assert isinstance(result, ApprovalCheckResult)
        assert result.approved is True
        assert result.risk_level == "HIGH"

    def test_approve_endpoint_blocks_unacknowledged_high_risk(self):
        """POST /approve returns pending_acknowledgment for high-risk without ack."""
        tid = db_client.insert_wsm_transition(
            merchant_id="m_gate_test",
            vertical="cpg",
            decision_mode="deep",
            s_json={},
            action_id="DISCOUNT_20PCT",
            action_family="DISCOUNT",
            action_params_json={},
            constraints_passed=True,
            was_executed=False,
        )

        resp = _client.post(
            "/decision/m_gate_test/approve",
            json={
                "transition_id": tid,
                "execution_params": {"discount_pct": 0.20},
                "high_risk_acknowledged": False,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_acknowledgment"
        assert data["risk_level"] == "HIGH"
        assert "rollback_token_id" not in data
