# ── Layer 3 · Action Safety — Merchant Approval Gate ──────────────────────
# Architectural embodiment of Principle 3:
#   "Human confirmation before execution"
#
# High-risk actions require explicit merchant approval before execution.
# Thresholds from settings:
#   - discount_pct >= approval_required_discount_threshold (15%)
#   - budget_change_daily_usd >= approval_required_budget_daily_usd ($1000)
# Low-risk auto-approval: when LOW_RISK_AUTO_ACTIONS=True
#   - discount_pct < 10% AND effort == "low"
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from .. import db_client
from ..config import settings
from ..contracts import Counterfactual, ImpactEstimate

log = logging.getLogger(__name__)


class ApprovalCheckResult(BaseModel):
    """Result of MerchantApprovalGate.check_approval()."""
    approved: bool
    risk_level: Literal["LOW", "HIGH"]
    reason: str | None = None
    requires_acknowledgment: bool = False


class MerchantApprovalGate:
    """Gates high-risk actions behind merchant approval.

    Principle 3: Human confirmation before execution.
    Automation is the end state of trust, not the starting point.
    """

    def requires_approval(self, action: dict, policy: dict) -> bool:
        """Returns True if this action requires explicit merchant approval.

        High-risk actions always require approval:
          - discount_pct >= settings.approval_required_discount_threshold (15%)
          - budget_change_daily_usd >= settings.approval_required_budget_daily_usd ($1000)

        Low-risk actions can be auto-approved when low_risk_auto_actions=True:
          - discount_pct < 10% AND effort == "low"
        """
        discount_pct = action.get("discount_pct", 0.0)
        budget_daily = action.get("budget_change_daily_usd", 0.0)

        # High-risk: always require approval
        if discount_pct >= settings.approval_required_discount_threshold:
            return True
        if budget_daily >= settings.approval_required_budget_daily_usd:
            return True

        # Low-risk auto-approval gate
        if settings.low_risk_auto_actions:
            if discount_pct < 0.10 and action.get("effort") == "low":
                return False

        # Default: require approval
        return True

    def check_approval(
        self,
        action: dict,
        request_body: dict,
    ) -> ApprovalCheckResult:
        """Determine whether this action can proceed.

        LOW-RISK actions (discount < 15%, no large budget change):
          → APPROVED automatically (merchant's POST request is sufficient)

        HIGH-RISK actions (discount >= 15% OR budget >= $1000/day):
          → APPROVED only if request_body contains:
              {"high_risk_acknowledged": true, "risk_reason": "<reason>"}
          → PENDING_ACKNOWLEDGMENT (approved=False) otherwise
        """
        is_high_risk = self.requires_approval(action, request_body)

        if not is_high_risk:
            return ApprovalCheckResult(
                approved=True,
                risk_level="LOW",
                reason="Low-risk action — auto-approved",
            )

        # High-risk: require explicit acknowledgment in the request body
        acknowledged = request_body.get("high_risk_acknowledged", False)
        if acknowledged:
            risk_reason = request_body.get("risk_reason", "")
            log.info(
                "[approval_gate] High-risk action acknowledged: %s reason=%r",
                action.get("action_id"), risk_reason,
            )
            return ApprovalCheckResult(
                approved=True,
                risk_level="HIGH",
                reason=f"High-risk acknowledged: {risk_reason}",
            )

        log.warning(
            "[approval_gate] High-risk action requires acknowledgment: %s",
            action.get("action_id"),
        )
        return ApprovalCheckResult(
            approved=False,
            risk_level="HIGH",
            reason="High-risk action requires explicit acknowledgment",
            requires_acknowledgment=True,
        )

    def generate_approval_request(
        self,
        action: dict,
        impact_estimate: ImpactEstimate,
        counterfactual: Counterfactual | None,
    ) -> dict:
        """Generate the approval request payload for merchant dashboard/Slack.

        Returns dict with:
          action_summary: str
          impact_narrative: str
          counterfactual_summary: str | None
          approve_url: str  (placeholder for Phase 2)
          expires_in_hours: int  (from settings.rollback_ttl_hours)
        """
        action_id = action.get("action_id", "unknown")
        module = action.get("module", "unknown")

        action_summary = (
            f"[{module.upper()}] {action_id}: "
            f"{action.get('description', 'Recommended action')}"
        )

        impact_narrative = (
            f"Expected impact: ${impact_estimate.expected:,.0f} "
            f"(range ${impact_estimate.conservative:,.0f}–"
            f"${impact_estimate.optimistic:,.0f}, "
            f"confidence {impact_estimate.confidence:.0%})"
        )

        counterfactual_summary = None
        if counterfactual is not None:
            counterfactual_summary = counterfactual.why_not

        return {
            "action_summary": action_summary,
            "impact_narrative": impact_narrative,
            "counterfactual_summary": counterfactual_summary,
            "approve_url": f"/api/v1/actions/{action_id}/approve",  # Phase 2 placeholder
            "expires_in_hours": settings.rollback_ttl_hours,
        }

    def record_approval(
        self,
        transition_id: int,
        approved_by: str = "merchant",
    ) -> None:
        """Record merchant approval — updates WSM transition to was_executed=True.

        Calls db_client.update_wsm_execution().
        """
        db_client.update_wsm_execution(
            transition_id,
            {"approved_by": approved_by, "approval_source": "merchant_gate"},
        )
        log.info(
            "Approval recorded for transition %s by %s",
            transition_id, approved_by,
        )
