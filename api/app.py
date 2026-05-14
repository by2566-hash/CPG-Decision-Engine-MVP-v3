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
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
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

# ── API Key authentication ───────────────────────────────────────────
# All merchant-data endpoints require X-API-Key header.
# Key value is settings.api_key (env var: API_KEY).
# /health is intentionally unauthenticated (load-balancer probe).

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)


def _verify_api_key(api_key: str = Security(_API_KEY_HEADER)) -> str:
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


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


class PolicyCreateRequest(BaseModel):
    """Request body for POST /policy/{merchant_id}.

    Required: policy_version, vertical.
    Optional: policy_weights (validated to sum ≈ 1.0 when provided),
    expires_at, plus any additional merchant-specific fields via extra="allow".
    """
    policy_version: str
    vertical: str = "cpg"
    policy_weights: Optional[dict] = None
    expires_at: Optional[datetime] = None

    model_config = {"extra": "allow"}


class PolicyCreateResponse(BaseModel):
    status: str
    merchant_id: str
    policy_version: str
    vertical: str


class HealthResponse(BaseModel):
    status: str


class ReadinessCheckItem(BaseModel):
    name: str
    passed: bool
    detail: Optional[str] = None


class ReadinessResponse(BaseModel):
    merchant_id: str
    ready: bool
    shadow_mode: bool
    kill_switch: bool
    checks: list[ReadinessCheckItem]


class DimensionHealth(BaseModel):
    state: str
    urgency: float


class MerchantHealthResponse(BaseModel):
    merchant_id: str
    dimensions: dict[str, DimensionHealth]
    active_alerts: list[str]


class ApproveResponse(BaseModel):
    """Response for POST /decision/{merchant_id}/approve.

    status="approved": transition_id, rollback_token_id, rollback_available_until set.
    status="pending_acknowledgment": risk_level, message, instructions set.
    Phase 2: split into discriminated union when approval UX is formalised.
    """
    status: str
    # approved path
    transition_id: Optional[int] = None
    rollback_token_id: Optional[str] = None
    rollback_available_until: Optional[str] = None
    # pending_acknowledgment path
    risk_level: Optional[str] = None
    message: Optional[str] = None
    instructions: Optional[str] = None


class RollbackResponse(BaseModel):
    status: str
    token_id: str
    merchant_id: str
    action_id: Optional[str] = None
    note: Optional[str] = None


class DecisionResponse(BaseModel):
    merchant_id: str
    mode: str
    msm_state: dict[str, str]
    emergency_triggered: bool
    alerts: list[str]
    policy_version: str
    weekly_plan: dict[str, Any]
    top_actions: list[dict[str, Any]]


# ── 1. GET /health ──────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ── 2. GET /readiness/{merchant_id} ─────────────────────────────────

@app.get("/readiness/{merchant_id}", response_model=ReadinessResponse, dependencies=[Depends(_verify_api_key)])
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

@app.get("/decision/{merchant_id}", response_model=DecisionResponse, dependencies=[Depends(_verify_api_key)])
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

    try:
        policy_pack, ranked = run_once(merchant_id)
    except Exception as exc:
        log.exception("[api] /decision pipeline failure merchant=%s", merchant_id)
        raise HTTPException(status_code=500, detail="Pipeline error") from exc

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

@app.post("/decision/{merchant_id}/emergency", dependencies=[Depends(_verify_api_key)])
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

@app.post("/decision/{merchant_id}/approve", response_model=ApproveResponse, dependencies=[Depends(_verify_api_key)])
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
    #
    # Phase 1: approval gate checks execution_params supplied by the caller.
    # Phase 2 (TODO): pull discount_pct from stored transition["action_params"]
    # to prevent a caller from bypassing approval thresholds by submitting a
    # lower discount_pct than the pipeline originally recommended.
    original_discount = (transition.get("action_params") or {}).get("discount_pct")
    submitted_discount = execution_params.get("discount_pct", 0.0)
    if original_discount is not None and abs(float(submitted_discount) - float(original_discount)) > 0.01:
        log.warning(
            "[approve] discount_pct mismatch: original=%.4f submitted=%.4f transition=%s "
            "— approval gate evaluating submitted value (Phase 1 behaviour)",
            original_discount, submitted_discount, transition_id,
        )

    action = {
        "action_id": transition["action_id"],
        "discount_pct": submitted_discount,
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

@app.post("/decision/{merchant_id}/feedback", dependencies=[Depends(_verify_api_key)])
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

@app.get("/merchant/{merchant_id}/health", response_model=MerchantHealthResponse, dependencies=[Depends(_verify_api_key)])
def merchant_health(merchant_id: str):
    """Compute fresh MerchantStateVector via MSM.

    Returns all 4 dimension states + urgency_scores + active_alerts.
    """
    # Fetch previous state BEFORE compute() — MSM.compute() upserts the new
    # state immediately, so any fetch after compute() returns the current state.
    # Reuse prev for both signal loading and previous_msm construction.
    prev = db_client.fetch_latest_merchant_state(merchant_id)
    signals = prev.get("metrics_snapshot", {}) if prev else {}

    previous_msm = None
    if prev:
        try:
            from src.decision_engine.contracts import MerchantStateVector as MSV
            previous_msm = MSV(
                merchant_id=prev.get("merchant_id", merchant_id),
                computed_at=prev.get("computed_at", datetime.now(timezone.utc)),
                acquisition_state=prev.get("acquisition_state", "HEALTHY"),
                conversion_state=prev.get("conversion_state", "HEALTHY"),
                retention_state=prev.get("retention_state", "HEALTHY"),
                promotion_state=prev.get("promotion_state", "HEALTHY"),
            )
        except Exception:
            previous_msm = None

    msm_state = _msm.compute(merchant_id, signals)

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

@app.post("/decision/{merchant_id}/rollback/{token_id}", response_model=RollbackResponse, dependencies=[Depends(_verify_api_key)])
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


# ── 9. POST /policy/{merchant_id} ───────────────────────────────────

@app.post(
    "/policy/{merchant_id}",
    response_model=PolicyCreateResponse,
    dependencies=[Depends(_verify_api_key)],
)
def create_or_update_policy(merchant_id: str, body: PolicyCreateRequest):
    """Create or update a PolicyPack for a merchant.

    Required fields: policy_version, vertical.
    Optional: policy_weights (beta1/beta2/beta3 must sum to ≈ 1.0 when provided),
    expires_at, and any additional merchant-specific fields.

    Without a PolicyPack, the pipeline will RuntimeError on Step 4.
    This endpoint is the merchant onboarding entry point for the decision engine.
    """
    # Validate policy_weights sum when provided
    weights = body.policy_weights
    if weights:
        beta_sum = sum(weights.get(k, 0.0) for k in ("beta1", "beta2", "beta3"))
        if beta_sum > 0 and abs(beta_sum - 1.0) > 0.05:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"policy_weights beta1+beta2+beta3 must sum to ≈ 1.0 "
                    f"(got {beta_sum:.4f}, tolerance ±0.05)"
                ),
            )

    # Build full payload — include all extra fields from the request body
    payload = body.model_dump(exclude={"expires_at"})

    db_client.upsert_policy_pack(
        policy_version=body.policy_version,
        merchant_id=merchant_id,
        payload_json=payload,
        expires_at=body.expires_at,
    )

    log.info(
        "[policy] PolicyPack upserted for merchant=%s version=%s vertical=%s",
        merchant_id, body.policy_version, body.vertical,
    )

    return PolicyCreateResponse(
        status="created",
        merchant_id=merchant_id,
        policy_version=body.policy_version,
        vertical=body.vertical,
    )


# ── 10. GET /policy/{merchant_id} ───────────────────────────────────

@app.get("/policy/{merchant_id}", dependencies=[Depends(_verify_api_key)])
def get_policy(merchant_id: str):
    """Return the current active PolicyPack for a merchant.

    Returns 404 if no non-expired PolicyPack exists.
    Used for onboarding verification and ops troubleshooting.
    """
    policy = db_client.fetch_latest_policy(merchant_id)
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active PolicyPack found for merchant {merchant_id}",
        )
    return {
        "merchant_id": merchant_id,
        "policy": policy,
    }
