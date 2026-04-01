# ── Shared Pydantic Contracts ──────────────────────────────────────────────
# Cross-layer data contracts (Pydantic v2 schemas).
# Defines: DecisionCard, MSMState, WSMTransition, PolicyPack,
#          VerificationChain, ImpactEstimate, etc.
#
# V3 additions over V2 contracts.py:
#   - verification_chain field
#   - impact_estimate { conservative, expected, optimistic, confidence }
#   - counterfactual field
#   - baseline_snapshot / outcome_delta for WSM
#   - DecisionCard: complete typed model (all fields, Literal types, Field bounds)
#   - classify_from_confidence(): Blueprint Section 6 threshold (>= 0.60)
#
# Reference: V2/src/contracts.py (verify before reuse)
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .layer1_msm.state_definitions import DimensionState


class MerchantStateVector(BaseModel):
    """Layer 1 MSM output — 4 dimensions × 4 states with urgency scores.

    Used by db_client.upsert_merchant_state_vector and fetch_latest_merchant_state.
    """
    merchant_id: str
    computed_at: datetime
    acquisition_state: str = "HEALTHY"
    conversion_state: str = "HEALTHY"
    retention_state: str = "HEALTHY"
    promotion_state: str = "HEALTHY"
    acquisition_urgency: float = 0.0
    conversion_urgency: float = 0.0
    retention_urgency: float = 0.0
    promotion_urgency: float = 0.0
    metrics_snapshot: Optional[dict] = None


# ── Supporting value types (defined before DecisionCard) ─────────────────

class VerificationStep(BaseModel):
    """Single verification step result."""
    name: str
    passed: bool
    value: float = 0.0
    threshold: float = 0.0
    reason: str = ""


class VerificationChain(BaseModel):
    """Three-layer verification trace: DecisionVerifier → LLM Renderer → 5-Gate.

    Layer 1 (DecisionVerifier) populates: msm_trigger, margin_gate,
    inventory_gate, conflict_check, all_passed.
    Layers 2-3 add their own fields downstream.
    """
    msm_trigger: VerificationStep
    margin_gate: VerificationStep
    inventory_gate: VerificationStep
    conflict_check: VerificationStep
    all_passed: bool = False


class ImpactEstimate(BaseModel):
    """Dollar impact estimate with confidence interval.

    Phase 1: benchmark-derived priors (confidence <= 0.30)
    Phase 2+: WSM outcome-derived (confidence scales with data)
    """
    conservative: float = 0.0
    expected: float = 0.0
    optimistic: float = 0.0
    confidence: float = 0.0


class Counterfactual(BaseModel):
    """Runner-up comparison for explainability.

    Answers: 'Why this action over the next-best alternative?'
    """
    runner_up_action: str
    runner_up_estimate: float = 0.0
    why_not: str = ""


# ── DecisionCard — complete Pydantic model ────────────────────────────────

class DecisionCard(BaseModel):
    """Merchant-facing decision output — all fields per Blueprint Section 4.

    classification follows Blueprint Section 6:
      "RECOMMENDATION" — confidence >= 0.60 (sufficient WSM outcome history)
      "HYPOTHESIS"     — confidence <  0.60 (benchmark prior or insufficient data)

    Phase 1: all cards are HYPOTHESIS (benchmark confidence = 0.30).
    Phase 2+: cards auto-promote to RECOMMENDATION as WSM outcomes accumulate.

    Supports dict-style access (card["field"]) for backward compatibility with
    code that treats cards as plain dicts.
    """
    model_config = ConfigDict(frozen=False)

    # Identity
    card_id: str = ""                        # format: dc_{ts}_{merchant_id}_{module}
    merchant_id: str = ""
    module: Literal[
        "retention", "acquisition", "conversion", "promotion"
    ] = "retention"

    # Blueprint Section 6 — data completeness classification
    classification: Literal["RECOMMENDATION", "HYPOTHESIS"] = "HYPOTHESIS"
    validation_status: Literal["RECOMMENDATION", "HYPOTHESIS"] = "HYPOTHESIS"
    # classification: data-driven (confidence threshold)
    # validation_status: gate-driven (5-Gate Bouncer result)

    # State context
    msm_state: str = "WATCH"                 # DimensionState string value
    pattern_detected: str = ""
    evidence: list[str] = Field(default_factory=list)
    diagnosis: str = ""

    # Action
    action_id: str = ""                      # backward compat alias for recommended_action
    recommended_action: str = ""
    action_params: dict = Field(default_factory=dict)

    # Value intelligence (typed, not plain dict)
    impact_estimate: ImpactEstimate = Field(default_factory=ImpactEstimate)
    counterfactual: Optional[Counterfactual] = None
    benchmark_context: Optional[str] = None

    # Safety
    constraints_passed: bool = True
    violations: list[str] = Field(default_factory=list)

    # Scoring trace
    urgency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0)
    base_utility_score: Optional[float] = None
    final_score: Optional[float] = None

    # Lineage
    policy_version: str = ""
    verification_chain: Optional[VerificationChain] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Rendering — set by LLMRenderer after verification passes
    merchant_copy: Optional[dict] = None

    # MSM context snapshot — set in pipeline Step 12
    msm_state_summary: Optional[dict] = None

    # Alerts at decision time
    alerts: list = Field(default_factory=list)

    # ── dict-style access for backward compatibility ───────────────────────

    def __getitem__(self, key: str):
        """Support card["field"] access for backward compat with dict consumers."""
        try:
            return self.model_dump()[key]
        except KeyError:
            raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        """Support 'field' in card for backward compat."""
        return key in self.model_dump()

    # ── Blueprint Section 6 classification ───────────────────────────────

    @classmethod
    def classify_from_confidence(cls, confidence: float) -> str:
        """Classify based on data completeness proxy (Blueprint Section 6).

        RECOMMENDATION: confidence >= 0.60 (sufficient WSM outcome history)
        HYPOTHESIS:     confidence <  0.60 (benchmark prior or insufficient data)

        Phase 1: benchmark confidence = 0.30 → all HYPOTHESIS.
        Phase 2+: confidence scales with WSM outcomes → RECOMMENDATION auto-promoted.
        """
        return "RECOMMENDATION" if confidence >= 0.60 else "HYPOTHESIS"


# ── Other shared models ───────────────────────────────────────────────────

class MSMState(BaseModel):
    """Alias for MerchantStateVector — kept for backward compatibility.

    Do NOT add new fields here. Use MerchantStateVector everywhere.
    This class exists only to avoid import errors in older code.
    """
    # TODO: Define acquisition, conversion, retention, promotion state fields
    pass


class WSMTransition(BaseModel):
    """World State Model S/A/R/S' transition record.

    Note: Full schema in sql/001_wsm_transition_v3.sql.
    This Pydantic model is used for type safety at the Python layer.
    The DB schema is the authoritative definition.
    """
    transition_id: Optional[int] = None
    merchant_id: str
    module: str = ""
    action_id: str
    was_executed: bool = False
    reward_status: Literal["pending", "proxy", "final"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # TODO: Add baseline_snapshot, outcome_delta, verification_chain


class PolicyPack(BaseModel):
    """Thin wrapper for policy validation.

    Full implementation in layer2_decision/pillar1_kg/policy_pack.py.
    This class is kept here to avoid breaking existing imports.
    Use layer2_decision.pillar1_kg.policy_pack.PolicyPack everywhere instead.
    """
    # TODO: Define policy_weights, risk_budget, exploration_budget
    pass
