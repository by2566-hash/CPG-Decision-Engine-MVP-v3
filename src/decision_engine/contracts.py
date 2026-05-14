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
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .layer1_msm.state_definitions import DimensionState


class CalibrationStatus(str, Enum):
    """Valid values for calibration_status in brand binding YAMLs. [ADR-0011]

    Two-state machine:
      partner_prior        — initial value from partner business judgment
      outcome_calibrated   — updated after N ≥ 10 real L5 outcome records
                             (reward_backfill.py writes outcome_delta)

    SHADOW_DATA_COLLECTED is reserved per ADR-0011 but NOT active in Phase 2.
    It tracks data completeness only, not calibration quality.
    """
    PARTNER_PRIOR = "partner_prior"
    OUTCOME_CALIBRATED = "outcome_calibrated"
    # SHADOW_DATA_COLLECTED = "shadow_data_collected"  — reserved, not active in Phase 2


class MerchantStateVector(BaseModel):
    """Layer 1 MSM output — 4 dimensions × 4 states with urgency scores.

    Used by db_client.upsert_merchant_state_vector and fetch_latest_merchant_state.
    """
    model_config = ConfigDict(frozen=True)

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
    model_config = ConfigDict(frozen=True)

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
    model_config = ConfigDict(frozen=True)

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
    model_config = ConfigDict(frozen=True)

    conservative: float = 0.0
    expected: float = 0.0
    optimistic: float = 0.0
    confidence: float = 0.0


class Counterfactual(BaseModel):
    """Runner-up comparison for explainability.

    Answers: 'Why this action over the next-best alternative?'
    """
    model_config = ConfigDict(frozen=True)

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
    alerts: list[str] = Field(default_factory=list)

    # ── dict-style access for backward compatibility ───────────────────────

    def __getitem__(self, key: str):
        """Support card["field"] access for backward compat with dict consumers.

        Uses getattr() — O(1) — instead of model_dump() — O(n fields).
        Note: returns the Python value (e.g. datetime), not a serialized string.
        Any caller that needs serialized output should call .model_dump() explicitly.
        """
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        """Support 'field' in card for backward compat."""
        return key in DecisionCard.model_fields

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


# ── V3.5 Core Data Objects ────────────────────────────────────────────────
# These 5 types form the typed backbone of the Decision Core (L3).
# They eliminate plain-dict passing between pipeline stages and provide
# explicit contracts for each stage boundary.

class PolicyDecision(BaseModel):
    """L3.3 Policy Engine output — unified constraint evaluation result.

    Replaces the former tuple[bool, list[str]] from check_all() and the
    separate float from compute_risk_score(). Single authoritative contract
    for the output of the constraint engine.

    risk_penalty is a weighted sum (not a raw count): violation severity
    is encoded by type, so a margin_floor violation outweighs a process
    violation in the scoring formula.

    requires_approval is set by MerchantApprovalGate, not ConstraintEngine.
    rollback_required is always True: every write action has a 48h undo window.
    """
    model_config = ConfigDict(frozen=True)

    eligible: bool                          # False = hard block, score → -inf
    hard_reject: bool = False               # alias for not eligible
    risk_penalty: float = Field(default=0.0, ge=0.0)  # feeds β3·Risk in scoring formula
    violations: list[str] = Field(default_factory=list)  # "constraint_name:detail"
    requires_approval: bool = False         # set by MerchantApprovalGate
    rollback_required: bool = True          # every write action: 48h undo window
    policy_version: str = ""

    @model_validator(mode="after")
    def _validate_eligibility_consistency(self) -> "PolicyDecision":
        """Enforce semantic consistency between eligible, hard_reject, and violations.

        Enforces ADR-0001: PolicyDecision is a single authoritative contract.
        Inconsistent states (eligible=True but violations present, or
        hard_reject=True but eligible=True) indicate a bug at the call site.
        """
        if self.eligible and self.violations:
            raise ValueError(
                "eligible=True is inconsistent with non-empty violations list"
            )
        if self.hard_reject and self.eligible:
            raise ValueError(
                "hard_reject=True is inconsistent with eligible=True"
            )
        return self


_DIM_STATE = Literal["HEALTHY", "WATCH", "DEGRADING", "CRITICAL"]


class DecisionState(BaseModel):
    """L1 MSM routing snapshot — discrete states only.

    Decision routing state: routes candidates to the right module,
    drives urgency scoring, and provides explainability context.

    NOT a complete feature representation for ML models — use
    DecisionFeatureVector for continuous model inputs.
    """
    model_config = ConfigDict(frozen=True)

    acquisition_state: _DIM_STATE = "HEALTHY"
    conversion_state: _DIM_STATE = "HEALTHY"
    retention_state: _DIM_STATE = "HEALTHY"
    promotion_state: _DIM_STATE = "HEALTHY"
    active_alerts: list[str] = Field(default_factory=list)

    @classmethod
    def from_msv(cls, msv: "MerchantStateVector") -> "DecisionState":
        """Build from a MerchantStateVector."""
        return cls(
            acquisition_state=msv.acquisition_state,
            conversion_state=msv.conversion_state,
            retention_state=msv.retention_state,
            promotion_state=msv.promotion_state,
        )


class DecisionFeatureVector(BaseModel):
    """Continuous feature inputs for ML scoring — from L0 + L2.

    Separates MSM routing state (DecisionState) from the numerical
    features consumed by scoring models and the LinUCB bandit.

    This is the authoritative feature contract for bandit context vectors.
    Phase 3: bandit.predict() must receive a DecisionFeatureVector,
    never a raw signals dict.

    All feature fields are Optional — Phase 1 has incomplete signals.
    from_signals() populates what is available and leaves the rest as None.
    computed_at is set at construction time (defaults to now).
    """
    model_config = ConfigDict(frozen=True)

    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Physical inventory: non-negative days of supply
    inventory_days: Optional[float] = Field(None, ge=0.0)
    # Margin: [0, 1] as a fraction
    margin_pct: Optional[float] = Field(None, ge=0.0, le=1.0)
    # Rate fields: all [0, 1]
    repeat_rate_7d: Optional[float] = Field(None, ge=0.0, le=1.0)
    cvr_7d: Optional[float] = Field(None, ge=0.0, le=1.0)
    cvr_30d: Optional[float] = Field(None, ge=0.0, le=1.0)
    promo_redemption_30d: Optional[float] = Field(None, ge=0.0, le=1.0)
    stock_pressure_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    churn_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    seasonality_index: Optional[float] = None       # future: seasonal adjustment (unbounded)
    benchmark_gap_score: Optional[float] = None     # from BenchmarkEngine (unbounded)

    @classmethod
    def from_signals(cls, signals: dict) -> "DecisionFeatureVector":
        """Build from a raw signals dict. Missing keys → None."""
        cvr = signals.get("checkout_cvr")
        cvr_current = cvr.get("current") if isinstance(cvr, dict) else cvr

        return cls(
            inventory_days=signals.get("inventory_days_p10"),
            margin_pct=signals.get("avg_margin_pct") or signals.get("margin_pct"),
            repeat_rate_7d=signals.get("repeat_purchase_rate"),
            cvr_7d=float(cvr_current) if cvr_current is not None else None,
            promo_redemption_30d=signals.get("promo_incrementality"),
            churn_score=signals.get("overdue_ratio"),
        )


class RawCandidate(BaseModel):
    """L3.1 Candidate Proposal output — before correlation/policy/scoring.

    Produced by _generate_candidates() (KG-driven).
    Consumed by L3.2 CrossModuleCorrelator and L3.3 PolicyEvaluation.

    Phase 2 Track B: pipeline will instantiate RawCandidate with all fields
    set at construction time (policy_decision, suppressed included). Frozen
    contract ensures stage boundaries are explicit.
    """
    model_config = ConfigDict(frozen=True)

    action_id: str
    module: Literal["retention", "acquisition", "conversion", "promotion"]
    action_type: str = ""                              # action intent label (e.g. "DISCOUNT")
    msm_dimension: str = ""
    urgency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    pred: dict = Field(default_factory=dict)
    action_family: str = ""
    signals: dict = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)   # KG evidence pointers
    policy_decision: Optional["PolicyDecision"] = None
    suppressed: bool = False
    suppression_reason: str = ""


class ScoredCandidate(BaseModel):
    """L3.4 Scoring & Ranking output — after score computation.

    Produced by ScoringEngine.rank_actions().
    Consumed by L3.5 DecisionVerifier and L4 Delivery Plane.

    final_score may be -inf for hard-rejected candidates (eligible=False).
    rank is 1-based: the top-ranked candidate has rank=1.
    beta_snapshot captures the β weights used at scoring time for auditability.
    """
    model_config = ConfigDict(frozen=True)

    action_id: str
    module: str = ""
    msm_dimension: str = ""
    eligible: bool = True
    final_score: float = 0.0
    u_base: float = 0.0
    u_ucb: float = 0.0
    risk_penalty: float = 0.0
    violations: list[str] = Field(default_factory=list)
    urgency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rank: int = Field(default=1, ge=1)             # 1-based; 1 = highest scored
    beta_snapshot: dict = Field(default_factory=dict)  # {"beta1": float, "beta2": float, "beta3": float}
    # verification_chain is stored as dict (VerificationChain.model_dump()) for JSON
    # serialization compatibility. Use get_verification_chain() for typed access.
    # Phase 2 Track B: change to Optional[VerificationChain] when L3 split is done.
    verification_chain: Optional[dict] = None
    suppressed: bool = False
    trace: dict = Field(default_factory=dict)

    def get_verification_chain(self) -> Optional[VerificationChain]:
        """Return verification_chain as a typed VerificationChain, or None."""
        if self.verification_chain is None:
            return None
        return VerificationChain(**self.verification_chain)


# ── Evidence Graph Snapshot (ADR-0009) ───────────────────────────────────

_EVIDENCE_STEP = Literal["L1_State", "L2_KG", "L3_Constraint", "L3_Scoring", "L3_Verification"]


class EvidenceTraceEntry(BaseModel):
    """Single step in the decision causal chain. [see ADR-0009]

    Captures the finding from one pipeline stage and the raw data that
    backs the finding. The source_data dict is used by the 5-Gate Bouncer's
    evidence grounding check and by the LLM Renderer's hallucination guard.
    """
    model_config = ConfigDict(frozen=True)

    step: _EVIDENCE_STEP
    finding: str                    # human-readable structured fact
    source_data: dict = Field(default_factory=dict)  # raw data backing the finding


class EvidenceGraphSnapshot(BaseModel):
    """Aggregated decision trace from L1 through L3. [see ADR-0009]

    Produced by pipeline._build_evidence_snapshot() for each top-K candidate.
    Consumed by LLMRenderer.render_from_snapshot() as the sole substantive
    input — the LLM translates the trace, it does not add facts.

    Persisted to L5 WSM so that "why did the bandit learn this policy?" can
    be answered with causal features, not just outcomes.
    """
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    winner_action: str
    evidence_trace: list[EvidenceTraceEntry] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Other shared models ───────────────────────────────────────────────────
# NOTE: MSMState stub removed 2026-04-09 — was never imported anywhere.
# Use MerchantStateVector everywhere.
#
# NOTE: PolicyPack stub removed 2026-04-09 — was never imported from contracts.
# Authoritative implementation: layer2_decision/pillar1_kg/policy_pack.py

class WSMTransition(BaseModel):
    """World State Model S/A/R/S' transition record.

    Note: Full schema in sql/001_wsm_transition_v3.sql.
    This Pydantic model is used for type safety at the Python layer.
    The DB schema is the authoritative definition.
    """
    model_config = ConfigDict(frozen=True)

    transition_id: Optional[int] = None
    merchant_id: str
    module: str = ""
    action_id: str
    was_executed: bool = False
    reward_status: Literal["pending", "proxy", "final"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # CLAUDE.md WSM Required Fields — present from Day 1
    baseline_snapshot: Optional[dict] = None    # merchant metrics at decision time
    outcome_delta: Optional[dict] = None        # {metric: {before, after}} post-outcome
    verification_chain: Optional[dict] = None   # VerificationChain.model_dump() at write time


