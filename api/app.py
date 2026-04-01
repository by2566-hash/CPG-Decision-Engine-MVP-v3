# ── API · FastAPI Application ─────────────────────────────────────────────
# Serves Decision Engine V3 endpoints.
# Fast Plane entry point + Deep Plane trigger + approval + feedback + rollback.
#
# Phase 1: Shadow mode — decisions logged but not executed
# Phase 2: Web Dashboard + one-click approval
# Phase 3: Shopline ecosystem embed + REST API
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.decision_engine import db_client
from src.decision_engine.config import settings
from src.decision_engine.layer1_msm.merchant_state_machine import MerchantStateMachine
from src.decision_engine.layer1_msm.alert_engine import AlertEngine
from src.decision_engine.layer4_serving import rollout
from src.decision_engine.layer4_serving.fast_plane import FastPlane
from src.decision_engine.layer4_serving.pipeline import run_once
from src.decision_engine.layer3_value.feedback_collector import FeedbackCollector
from src.decision_engine.layer3_value.rollback_registry import RollbackRegistry
from src.decision_engine.layer3_value.merchant_approval_gate import MerchantApprovalGate, ApprovalCheckResult

log = logging.getLogger(__name__)

app = FastAPI(
    title="CPG Decision Engine V3",
    version="3.0.0",
    description="Operating Intelligence Layer for CPG brands",
)

# ── Shared instances ────────────────────────────────────────────────
_fast_plane = FastPlane()
_msm = MerchantStateMachine()
_alert_engine = AlertEngine()
_feedback_collector = FeedbackCollector()
_rollback_registry = RollbackRegistry()
_approval_gate = MerchantApprovalGate()

_DIMENSIONS = ["acquisition", "conversion", "retention", "promotion"]


# ── Request/Response models ─────────────────────────────────────────

class ApproveRequest(BaseModel):
    transition_id: int
    execution_params: dict = {}
    high_risk_acknowledged: bool = False
    risk_reason: str = ""


class FeedbackRequest(BaseModel):
    transition_id: int
    feedback_type: str
    actual_params: dict = {}
    merchant_note: str = ""


class EmergencyRequest(BaseModel):
    emergency_features: dict = {}


# ── 1. GET /health ──────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ── 2. GET /readiness/{merchant_id} ─────────────────────────────────

@app.get("/readiness/{merchant_id}")
def readiness(merchant_id: str):
    """Go-live readiness checklist for a merchant."""
    checks = rollout.check_readiness(merchant_id)
    all_ok = all(c.passed for c in checks)
    return {
        "merchant_id": merchant_id,
        "ready": all_ok,
        "shadow_mode": rollout.is_shadow_mode(),
        "kill_switch": rollout.is_kill_switch_active(),
        "checks": [c.to_dict() for c in checks],
    }


# ── 3. GET /decision/{merchant_id} ─────────────────────────────────

@app.get("/decision/{merchant_id}")
def decision(merchant_id: str):
    """Deep Plane: run full pipeline and return decision cards.

    Response includes:
      - msm_state: 4 dimension states
      - emergency_triggered: bool
      - mode: "shadow" | "live"
    """
    if rollout.is_kill_switch_active():
        raise HTTPException(
            status_code=503, detail="Kill switch active — decisions disabled",
        )

    policy_pack, ranked = run_once(merchant_id)

    return {
        "merchant_id": merchant_id,
        "mode": policy_pack.get("mode", "shadow"),
        "msm_state": policy_pack.get("msm_state", {}),
        "emergency_triggered": policy_pack.get("emergency_triggered", False),
        "alerts": policy_pack.get("alerts", []),
        "policy_version": policy_pack.get("policy_version", "unknown"),
        "weekly_plan": policy_pack.get("weekly_plan", {}),
        "top_actions": ranked[:3],
    }


# ── 4. POST /decision/{merchant_id}/emergency ──────────────────────

@app.post("/decision/{merchant_id}/emergency")
def emergency(merchant_id: str, body: EmergencyRequest | None = None):
    """Fast Plane emergency path.

    Priority: Redis cache → DB serving cache → 503.
    Applies lightweight deterministic reweighting.
    """
    if rollout.is_kill_switch_active():
        raise HTTPException(
            status_code=503, detail="Kill switch active — decisions disabled",
        )

    t0 = time.perf_counter()

    features = body.emergency_features if body else {}
    result = _fast_plane.serve(merchant_id, emergency_features=features or None)

    latency_ms = (time.perf_counter() - t0) * 1000
    result["latency_ms"] = round(latency_ms, 2)

    return result


# ── 5. POST /decision/{merchant_id}/approve ─────────────────────────

@app.post("/decision/{merchant_id}/approve")
def approve(merchant_id: str, body: ApproveRequest):
    """Approve a recommended action for execution.

    Steps:
      a. Validate transition belongs to merchant_id
      b. Check rollout.can_execute_write()
      c. Check MerchantApprovalGate.requires_approval()
      d. Register in RollbackRegistry
      e. Call db_client.update_wsm_execution()
      f. Phase 1: log only, no external API call
    """
    transition_id = body.transition_id
    execution_params = body.execution_params

    # a. Ownership validation — verify transition belongs to this merchant
    transition = db_client.fetch_transition_by_id(transition_id)
    if transition is None:
        raise HTTPException(
            status_code=404,
            detail=f"transition_id {transition_id} not found",
        )
    if transition["merchant_id"] != merchant_id:
        raise HTTPException(
            status_code=403,
            detail="transition_id does not belong to this merchant",
        )

    # b. Check rollout
    if not rollout.can_execute_write():
        log.info(
            "[approve] Shadow mode — logging approval for transition %s",
            transition_id,
        )

    # c. MerchantApprovalGate — gate result drives execution decision
    action = {
        "action_id": transition["action_id"],
        "discount_pct": execution_params.get("discount_pct", 0.0),
        "budget_change_daily_usd": execution_params.get("budget_change_daily_usd", 0.0),
        "effort": execution_params.get("effort", ""),
        **execution_params,
    }
    request_body = {
        "high_risk_acknowledged": body.high_risk_acknowledged,
        "risk_reason": body.risk_reason,
    }
    approval_result = _approval_gate.check_approval(action, request_body)

    if not approval_result.approved:
        return {
            "status": "pending_acknowledgment",
            "risk_level": approval_result.risk_level,
            "message": "High-risk action requires explicit acknowledgment.",
            "instructions": (
                "Resubmit with: {'high_risk_acknowledged': true, "
                "'risk_reason': 'your reason here'}"
            ),
        }

    # d. Register in RollbackRegistry
    token = _rollback_registry.register(
        merchant_id=merchant_id,
        action_id=action.get("action_id", "unknown"),
        transition_id=transition_id,
        undo_description=f"Rollback transition {transition_id}",
    )

    # e. Update WSM
    db_client.update_wsm_execution(
        transition_id,
        {**execution_params, "approved_by": "merchant"},
    )

    # f. Phase 1: log only
    log.info(
        "[approve] Transition %s approved for %s, rollback token %s",
        transition_id, merchant_id, token.token_id,
    )

    return {
        "status": "approved",
        "transition_id": transition_id,
        "rollback_token_id": token.token_id,
        "rollback_available_until": token.expires_at.isoformat(),
    }


# ── 6. POST /decision/{merchant_id}/feedback ────────────────────────

@app.post("/decision/{merchant_id}/feedback")
def feedback(merchant_id: str, body: FeedbackRequest):
    """Collect merchant feedback on a Decision Card."""
    _feedback_collector.record_feedback(
        transition_id=body.transition_id,
        feedback_type=body.feedback_type,
        actual_params=body.actual_params or None,
        merchant_note=body.merchant_note or None,
    )
    return {
        "status": "recorded",
        "transition_id": body.transition_id,
        "feedback_type": body.feedback_type,
    }


# ── 7. GET /merchant/{merchant_id}/health ────────────────────────────

@app.get("/merchant/{merchant_id}/health")
def merchant_health(merchant_id: str):
    """Compute fresh MerchantStateVector via MSM.

    Returns all 4 dimension states + urgency_scores + active_alerts.
    """
    prev = db_client.fetch_latest_merchant_state(merchant_id)
    signals = prev.get("metrics_snapshot", {}) if prev else {}

    msm_state = _msm.compute(merchant_id, signals)

    # Check alerts
    prev_raw = db_client.fetch_latest_merchant_state(merchant_id)
    previous_msm = None
    if prev_raw:
        try:
            from src.decision_engine.contracts import MerchantStateVector as MSV
            previous_msm = MSV(
                merchant_id=prev_raw.get("merchant_id", merchant_id),
                computed_at=prev_raw.get("computed_at", msm_state.computed_at),
                acquisition_state=prev_raw.get("acquisition_state", "HEALTHY"),
                conversion_state=prev_raw.get("conversion_state", "HEALTHY"),
                retention_state=prev_raw.get("retention_state", "HEALTHY"),
                promotion_state=prev_raw.get("promotion_state", "HEALTHY"),
            )
        except Exception:
            previous_msm = None

    alerts = _alert_engine.check_and_alert(merchant_id, msm_state, previous_msm)

    return {
        "merchant_id": merchant_id,
        "dimensions": {
            d: {
                "state": getattr(msm_state, f"{d}_state"),
                "urgency": getattr(msm_state, f"{d}_urgency"),
            }
            for d in _DIMENSIONS
        },
        "active_alerts": alerts,
    }


# ── 8. POST /decision/{merchant_id}/rollback/{token_id} ─────────────

@app.post("/decision/{merchant_id}/rollback/{token_id}")
def rollback(merchant_id: str, token_id: str):
    """Rollback a previously executed action (within 48h TTL).

    Validates TTL and merchant ownership.
    Updates WSM.
    """
    # Fetch token BEFORE execute_rollback() deletes it
    token = _rollback_registry.get_token(token_id, merchant_id)
    if token is None:
        raise HTTPException(
            status_code=404,
            detail="Rollback token not found or does not belong to this merchant",
        )

    result = _rollback_registry.execute_rollback(token_id, merchant_id)

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("reason", "Rollback failed"))

    # Update WSM using token data fetched before deletion
    try:
        db_client.rollback_wsm_execution(
            token.transition_id,
            {"rolled_back": True, "rollback_token_id": token_id,
             "rolled_back_at": datetime.now(timezone.utc).isoformat()},
        )
    except Exception:
        log.exception("[rollback] WSM update failed for token %s", token_id)

    return {
        "status": "rolled_back",
        "token_id": token_id,
        "merchant_id": merchant_id,
        "action_id": result.get("action_id"),
        "note": result.get("note"),
    }
