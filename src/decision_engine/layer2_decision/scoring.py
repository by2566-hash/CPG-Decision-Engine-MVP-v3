# ── Layer 2 · Scoring Engine ───────────────────────────────────────────────
# Implements the explicit scoring formula (LinUCB — Li et al. 2010 WWW):
#
#   Score = β1·U_base(KG) + β2·U_ucb(Bandit) − β3·Risk(Constraints)
#
# β weights are dynamically set by Policy Pack (NOT hardcoded).
# Phase 1 cold-start: u_ucb = 0.0, scoring = β1·U_base − β3·Risk only.
#
# Integration points:
#   1. CrossModuleCorrelator.correlate() — suppress conflicting candidates
#   2. DecisionVerifier.verify() — block candidates that fail verification
#   3. constraints check — compute risk penalty
#   4. Urgency boost — CRITICAL dimension actions ranked higher
#
# Risk(Constraints) is computed by layer3_value.constraints.ConstraintEngine
# — single source of truth for all CPG hard constraints.
# This cross-layer import is intentional and documented in CLAUDE.md.
#
# Reference: V2/src/scoring.py (β formula verified and adapted)
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging

from ..contracts import MerchantStateVector, PolicyDecision
from .cross_module_correlator import CrossModuleCorrelator
from .pillar3_llm.decision_verifier import DecisionVerifier

log = logging.getLogger(__name__)


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    """Clip value to [lo, hi] range."""
    return max(lo, min(hi, x))


def base_utility(pred: dict, weights: dict) -> float:
    """Compute weighted base utility from KG predictions.

    Normalizes each lift component to [-1, 1] range before weighting.
    Weights come from PolicyPack.policy_weights — never hardcoded.

    Expected input ranges for meaningful (non-clipped) output:
      gmv_lift:                  [0.0, 0.30]  — GMV lift as fraction of monthly GMV
      margin_lift:               [0.0, 0.10]  — margin improvement fraction
      inventory_risk_reduction:  [0.0, 0.20]  — inventory risk reduction fraction
      retention_lift:            [0.0, 0.20]  — retention improvement fraction

    PlaybookRegistry.get_base_utility() clips gmv_lift_prior to [0.0, 0.25]
    before writing to pred["gmv_lift"] — two-layer defence. [ADR-0011]
    Values above the normalization denominator are clipped to ±1.0.
    """
    g = _clip(pred.get("gmv_lift", 0) / 0.30)
    m = _clip(pred.get("margin_lift", 0) / 0.10)
    i = _clip(pred.get("inventory_risk_reduction", 0) / 0.20)
    r = _clip(pred.get("retention_lift", 0) / 0.20)
    return (
        weights.get("gmv_lift", 0) * g
        + weights.get("margin_lift", 0) * m
        + weights.get("inventory_risk_reduction", 0) * i
        + weights.get("retention_lift", 0) * r
    )


def risk_penalty(pred: dict, budget: dict) -> float:
    """Compute risk penalty from constraint violations.

    Each budget violation adds 1.0 to the penalty.
    """
    p = 0.0
    if pred.get("margin_drop_pct", 0) > budget.get("max_margin_drop_pct", 1):
        p += 1.0
    if pred.get("refund_rate_increase_pct", 0) > budget.get("max_refund_rate_increase_pct", 1):
        p += 1.0
    return p


class ScoringEngine:
    """Computes action scores using the tri-component formula.

    Score = β1·U_base(KG) + β2·U_ucb(Bandit) − β3·Risk(Constraints)

    β weights come from policy["policy_weights"] — never hardcoded.
    Phase 1: u_ucb = 0.0 (cold-start protection, Phase 3 only).
    """

    def __init__(self):
        self.correlator = CrossModuleCorrelator()
        self.verifier = DecisionVerifier()

    def rank_actions(
        self,
        msm_state: MerchantStateVector,
        candidates: list[dict],
        policy: dict,
        bandit=None,
    ) -> list[dict]:
        """Score and rank all candidate actions. Return sorted list.

        Pipeline per candidate:
          1. Run constraints check (from candidate["constraints_result"])
          2. Run CrossModuleCorrelator.correlate() — flag suppressions
          3. Run DecisionVerifier.verify() — block failed verifications
          4. If not verification_chain.all_passed: final_score = -inf, skip scoring
          5. If passed: compute β1·U_base + β2·U_ucb − β3·Risk

        # Score = β1·U_base(KG) + β2·U_ucb(Bandit) − β3·Risk(Constraints)
        # β weights come from policy["policy_weights"] — never hardcoded
        # Phase 1: u_ucb = 0.0 (cold-start protection, Phase 3 only)
        """
        # β weights from policy — never hardcoded
        weights = policy.get("policy_weights", {})
        beta1 = weights.get("gmv_lift", 0) + weights.get("margin_lift", 0) + weights.get("inventory_risk_reduction", 0) + weights.get("retention_lift", 0)
        # Use config defaults if policy doesn't specify β coefficients
        beta1_coeff = policy.get("beta1", 0.65)
        beta2_coeff = policy.get("beta2", 0.25)
        beta3_coeff = policy.get("beta3", 0.10)
        risk_budget = policy.get("risk_budget", {})

        # Step 1: Run CrossModuleCorrelator on all candidates
        candidates = self.correlator.correlate(msm_state, candidates)

        out: list[dict] = []
        for a in candidates:
            action_id = a.get("action_id", "unknown")
            try:
                # Constraints result: PolicyDecision from ConstraintEngine.check_all()
                # (set by pipeline._generate_candidates). Legacy tuple support for
                # test mocks that inject (True, []) directly.
                raw_cr = a.get("constraints_result")
                if isinstance(raw_cr, PolicyDecision):
                    constraints_result = raw_cr
                elif isinstance(raw_cr, tuple):
                    # Legacy bridge: test mocks may inject (bool, list[str]) tuples
                    passed_legacy, viols_legacy = raw_cr
                    from ..layer3_value.constraints import _VIOLATION_WEIGHTS
                    constraints_result = PolicyDecision(
                        eligible=passed_legacy,
                        hard_reject=not passed_legacy,
                        risk_penalty=sum(
                            _VIOLATION_WEIGHTS.get(v.split(":")[0], 1.0)
                            for v in viols_legacy
                        ),
                        violations=list(viols_legacy),
                    )
                else:
                    # FAIL-SAFE: missing constraints_result means ConstraintEngine was
                    # never called — treat as ineligible, not as a silent pass.
                    # Prevents bypassing all 6 CPG hard constraints without detection.
                    log.warning(
                        "[scoring] candidate %s missing constraints_result — "
                        "treating as ineligible (fail-safe). "
                        "Check _generate_candidates() in pipeline.py.",
                        action_id,
                    )
                    constraints_result = PolicyDecision(
                        eligible=False,
                        hard_reject=True,
                        risk_penalty=0.0,
                        violations=["missing_constraints_result:pipeline_error"],
                    )

                # Step 2: Run DecisionVerifier
                verification_chain = self.verifier.verify(
                    msm_state=msm_state,
                    candidate=a,
                    policy=policy,
                    constraints_result=(constraints_result.eligible, constraints_result.violations),
                    all_candidates=candidates,
                )

                # Step 3a: Hard constraint gate — CPG constraints cannot be overridden (CLAUDE.md)
                if not constraints_result.eligible:
                    out.append({
                        "action_id": action_id,
                        "eligible": False,
                        "final_score": float("-inf"),
                        "u_base": float("-inf"),
                        "u_ucb": 0.0,
                        "risk_penalty": float("inf"),
                        "violations": constraints_result.violations,
                        "module": a.get("module"),
                        "msm_dimension": a.get("msm_dimension"),
                        "urgency_score": a.get("urgency_score", 0.0),
                        "verification_chain": verification_chain.model_dump(),
                        "suppressed": a.get("suppressed", False),
                        "trace": {"why_not": constraints_result.violations},
                    })
                    continue

                # Step 3b: If verification fails → final_score = -inf, skip scoring
                if not verification_chain.all_passed:
                    out.append({
                        "action_id": action_id,
                        "eligible": False,
                        "final_score": float("-inf"),
                        "u_base": float("-inf"),
                        "u_ucb": 0.0,
                        "risk_penalty": float("inf"),
                        "violations": [],
                        "module": a.get("module"),
                        "msm_dimension": a.get("msm_dimension"),
                        "urgency_score": a.get("urgency_score", 0.0),
                        "verification_chain": verification_chain.model_dump(),
                        "suppressed": a.get("suppressed", False),
                        "trace": {
                            "why_not": [
                                s.reason
                                for s in [
                                    verification_chain.msm_trigger,
                                    verification_chain.margin_gate,
                                    verification_chain.inventory_gate,
                                    verification_chain.conflict_check,
                                ]
                                if not s.passed
                            ],
                        },
                    })
                    continue

                # Step 4: Compute score — β1·U_base + β2·U_ucb − β3·Risk
                # constraints_result.risk_penalty is pre-computed by ConstraintEngine —
                # no need to re-call check_all() here (eliminates double evaluation).
                pred = a.get("pred", {})
                u_base_val = base_utility(pred, weights)
                p_risk = (
                    risk_penalty(pred, risk_budget)
                    + constraints_result.risk_penalty
                )

                # Phase 3 gate: LinUCB active only after 6 months of action_log data
                u_ucb = 0.0  # Phase 1 cold-start: u_ucb = 0.0
                if bandit is not None:
                    arm_key = f"{policy.get('vertical', 'cpg')}:{a.get('action_family', '')}"
                    arm = bandit.get(arm_key) if hasattr(bandit, 'get') else None
                    if arm is not None and hasattr(arm, 'num_pulls') and arm.num_pulls > 0:
                        x = a.get("context_vec")
                        if x is not None:
                            u_ucb = arm.predict(x)

                # Urgency boost: CRITICAL dimension actions ranked higher
                urgency_score = a.get("urgency_score", 0.0)
                if urgency_score > 0.8:
                    u_base_val = u_base_val * 1.15

                raw_final = beta1_coeff * u_base_val + beta2_coeff * u_ucb - beta3_coeff * p_risk

                # Signal quality overlay (V2 compat)
                sq = a.get("_signal_quality", {})
                conf = sq.get("confidence_weight", 1.0)
                quality = sq.get("quality_factor", 1.0)
                overlay_penalty = conf * quality  # ∈ [0, 1], 1.0 = no penalty
                final = raw_final * overlay_penalty

                out.append({
                    "action_id": action_id,
                    "eligible": True,
                    "final_score": float(final),
                    "u_base": float(u_base_val),
                    "u_ucb": float(u_ucb),
                    "risk_penalty": float(p_risk),
                    "violations": [],
                    "module": a.get("module"),
                    "msm_dimension": a.get("msm_dimension"),
                    "urgency_score": urgency_score,
                    "verification_chain": verification_chain.model_dump(),
                    "suppressed": a.get("suppressed", False),
                    "trace": {
                        "why": [
                            f"base={u_base_val:.4f}",
                            f"ucb={u_ucb:.4f}",
                            f"risk={p_risk:.4f}",
                            f"urgency={urgency_score:.2f}",
                        ],
                        "conf": conf,
                        "quality": quality,
                    },
                })

            except Exception as exc:
                # Per-candidate isolation: one bad candidate never kills the loop.
                # Mark as suppressed with error trace so WSM still has a record.
                log.error(
                    "[scoring] candidate %s raised %s: %s — suppressing, continuing",
                    action_id, type(exc).__name__, exc, exc_info=True,
                )
                out.append({
                    "action_id": action_id,
                    "eligible": False,
                    "final_score": float("-inf"),
                    "u_base": 0.0,
                    "u_ucb": 0.0,
                    "risk_penalty": float("inf"),
                    "violations": [f"internal_error:{type(exc).__name__}"],
                    "module": a.get("module"),
                    "msm_dimension": a.get("msm_dimension"),
                    "urgency_score": a.get("urgency_score", 0.0),
                    "suppressed": True,
                    "trace": {"error": str(exc)},
                })

        out.sort(key=lambda z: z["final_score"], reverse=True)
        return out

    def score(
        self,
        u_base: float,
        u_ucb: float,
        risk: float,
        beta1: float = 0.65,
        beta2: float = 0.25,
        beta3: float = 0.10,
    ) -> float:
        """Compute: β1·U_base + β2·U_ucb − β3·Risk."""
        return beta1 * u_base + beta2 * u_ucb - beta3 * risk

    def get_score_breakdown(self, candidate: dict, weights: dict) -> dict:
        """Return decomposed score for explainability."""
        pred = candidate.get("pred", {})
        u_base_val = base_utility(pred, weights)
        return {
            "u_base": u_base_val,
            "u_ucb": 0.0,  # Phase 1
            "risk": risk_penalty(pred, candidate.get("risk_budget", {})),
            "weights": weights,
            "total_score": candidate.get("final_score", 0.0),
        }
