# ── Layer 4 · Deep Plane Orchestrator ─────────────────────────────────────
# Orchestrates the Deep Plane in strict 16-step order.
# Cadence: Weekly (planner) + 6h (ranking refresh).
# No latency SLA — runs in background.
#
# CRITICAL:
#   - Step 14 (WSM write) runs ALWAYS, regardless of gate outcomes
#   - DecisionVerifier failure → final_score = -inf → NO LLM rendering
#   - Missing signals → MSM fallback (never crash)
#   - LKG policy failure → raise RuntimeError
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from ..config import settings
from ..contracts import (
    MerchantStateVector, DecisionCard, ImpactEstimate, Counterfactual, VerificationChain,
)
from .. import db_client
from ..layer1_msm.merchant_state_machine import MerchantStateMachine
from ..layer1_msm.alert_engine import AlertEngine
from ..layer1_msm.state_definitions import DimensionState
from ..layer2_decision.scoring import ScoringEngine
from ..layer2_decision.pillar3_llm.llm_renderer import LLMRenderer
from ..layer2_decision.pillar3_llm.llm_safety_gateway import LLMSafetyGateway
from ..layer3_value.impact_calculator import ImpactCalculator
from ..layer3_value.benchmark_engine import BenchmarkEngine
from ..layer3_value.weekly_planner import WeeklyPlanner
from ..layer3_value.constraints import ConstraintEngine
from ..layer2_decision.pillar1_kg.playbook_registry import PlaybookRegistry

log = logging.getLogger(__name__)

# Module components (instantiated once)
_msm = MerchantStateMachine()
_alert_engine = AlertEngine()
_scoring_engine = ScoringEngine()
_llm_renderer = LLMRenderer()
_safety_gateway = LLMSafetyGateway()
_impact_calc = ImpactCalculator()
_benchmark_engine = BenchmarkEngine()
_weekly_planner = WeeklyPlanner()
_constraint_engine = ConstraintEngine()
_playbook_registry = PlaybookRegistry()

# Dimension → module mapping
_DIMENSIONS = ["acquisition", "conversion", "retention", "promotion"]


def run_once(
    merchant_id: str,
    signals: dict | None = None,
) -> tuple[dict, list[dict]]:
    """Execute full Deep Plane cycle. Returns (policy_pack_dict, ranked_actions_with_cards).

    16-step pipeline in strict order. See module docstring for invariants.
    """
    # ── Step 1: Load merchant signals ────────────────────────────────
    if signals is None:
        signals = _load_signals(merchant_id)

    # ── Step 2: Compute MerchantStateVector via MSM ──────────────────
    msm_state = _msm.compute(merchant_id, signals)
    log.info("[pipeline] MSM computed for %s", merchant_id)

    # ── Step 3: Run AlertEngine — log alerts, flag emergency ─────────
    prev_raw = db_client.fetch_latest_merchant_state(merchant_id)
    previous_msm = _parse_msm(prev_raw) if prev_raw else None
    alerts = _alert_engine.check_and_alert(merchant_id, msm_state, previous_msm)
    emergency_triggered = _alert_engine.should_trigger_emergency_decision(
        msm_state, previous_msm,
    )
    if alerts:
        log.info("[pipeline] Alerts for %s: %s", merchant_id, alerts)

    # ── Step 4: Load PolicyPack (with LKG fallback) ──────────────────
    policy = db_client.fetch_latest_policy(merchant_id)
    if policy is None:
        policy = _lkg_policy()
        if policy is None:
            raise RuntimeError(
                f"No policy pack available for merchant {merchant_id} "
                f"and no LKG fallback found"
            )
    policy_version = policy.get("policy_version", "unknown")

    # ── Step 5: Load candidates from KG Playbooks ────────────────────
    candidates = _generate_candidates(msm_state, signals, policy)

    # ── Step 6–8: Score via ScoringEngine ────────────────────────────
    # ScoringEngine internally runs:
    #   6. CrossModuleCorrelator.correlate()
    #   7a. constraints_result (attached to candidates)
    #   7b. DecisionVerifier.verify()
    #   7c/d. Score or -inf
    #   8. Sort by final_score DESC
    ranked = _scoring_engine.rank_actions(
        msm_state=msm_state,
        candidates=candidates,
        policy=policy,
        bandit=None,  # Phase 1: no bandit
    )

    # ── Step 9: For top 5 eligible → ImpactCalculator.estimate() ─────
    eligible = [a for a in ranked if a.get("eligible", True)]
    merchant_state = _merchant_state_dict(msm_state, signals)

    for action in eligible[:5]:
        module = action.get("module", "retention")
        ie = _impact_calc.estimate(action, merchant_state, module)
        action["impact_estimate"] = ie.model_dump()

    # ── Step 10: Counterfactual for top 1 vs runner-up ───────────────
    if len(eligible) >= 2:
        cf = _impact_calc.build_counterfactual(
            eligible[0], eligible[1], merchant_state,
            eligible[0].get("module", "retention"),
        )
        if cf:
            eligible[0]["counterfactual"] = cf.model_dump()

    # ── Step 11: BenchmarkEngine for DEGRADING/CRITICAL dimensions ───
    benchmarks: list[str] = []
    for dim in _DIMENSIONS:
        state_str = getattr(msm_state, f"{dim}_state")
        if DimensionState(state_str).severity_score() >= 2:  # DEGRADING+
            metric_name, metric_val = _get_benchmark_metric(dim, signals)
            if metric_name:
                narrative = _benchmark_engine.compare(
                    merchant_id, dim, metric_val, metric_name,
                )
                benchmarks.append(narrative)

    # ── Step 12: Assemble DecisionCards (top 3 only) ─────────────────
    # Instantiate real DecisionCard objects — Pydantic validates every field.
    decision_cards: list[DecisionCard] = []
    for action in eligible[:3]:
        ie_raw = action.get("impact_estimate")
        if isinstance(ie_raw, dict):
            ie_obj = ImpactEstimate(**ie_raw)
        elif isinstance(ie_raw, ImpactEstimate):
            ie_obj = ie_raw
        else:
            ie_obj = ImpactEstimate(conservative=0, expected=0, optimistic=0, confidence=0.30)

        cf_raw = action.get("counterfactual")
        if isinstance(cf_raw, dict):
            cf_obj = Counterfactual(**cf_raw)
        elif isinstance(cf_raw, Counterfactual):
            cf_obj = cf_raw
        else:
            cf_obj = None

        vc_raw = action.get("verification_chain")
        if isinstance(vc_raw, dict):
            vc_obj = VerificationChain(**vc_raw)
        elif isinstance(vc_raw, VerificationChain):
            vc_obj = vc_raw
        else:
            vc_obj = None

        module = action.get("module", "retention")
        confidence = ie_obj.confidence
        classification = DecisionCard.classify_from_confidence(confidence)
        ts = int(datetime.now(timezone.utc).timestamp())

        card = DecisionCard(
            card_id=f"dc_{ts}_{merchant_id}_{module}",
            merchant_id=merchant_id,
            module=module,
            classification=classification,
            validation_status=classification,
            msm_state=getattr(msm_state, f"{module}_state", "WATCH"),
            pattern_detected=action.get("pattern_detected", ""),
            evidence=action.get("evidence", []),
            diagnosis=action.get("diagnosis", ""),
            action_id=action.get("action_id", ""),
            recommended_action=action.get("action_id", ""),
            action_params=action.get("action_params", {}),
            impact_estimate=ie_obj,
            counterfactual=cf_obj,
            benchmark_context=benchmarks[0] if benchmarks else None,
            constraints_passed=action.get("eligible", True),
            violations=action.get("violations", []),
            urgency_score=min(max(action.get("urgency_score", 0.0), 0.0), 1.0),
            quality_score=action.get("quality_score", 0.5),
            base_utility_score=action.get("u_base"),
            final_score=action.get("final_score"),
            policy_version=policy_version,
            verification_chain=vc_obj,
            alerts=alerts,
            msm_state_summary={d: getattr(msm_state, f"{d}_state") for d in _DIMENSIONS},
        )
        decision_cards.append(card)

    # ── Step 13: Render + 5-Gate for each DecisionCard ───────────────
    response_cards: list[DecisionCard] = []
    for card in decision_cards:
        vc = card.verification_chain
        all_passed = vc.all_passed if vc is not None else False

        if not all_passed:
            continue  # DecisionVerifier failed → no LLM call

        # 13a: LLMRenderer.render() — pass card as dict (renderer expects dict)
        card_dict = card.model_dump()
        # Restore signals (not stored on DecisionCard, needed by LLMRenderer templates)
        card_dict["signals"] = signals
        try:
            merchant_copy = _llm_renderer.render(card_dict)
        except ValueError:
            log.warning(
                "[pipeline] LLMRenderer rejected %s — skipping",
                card.action_id,
            )
            continue

        # 13b: 5-Gate Bouncer
        evidence = [signals] if signals else []
        gate_errors = _safety_gateway.validate(merchant_copy, card_dict, evidence)

        if gate_errors:
            # 13d: 5-Gate fails → log, exclude from response; update validation_status
            log.warning(
                "[pipeline] 5-Gate failed for %s: %s",
                card.action_id, gate_errors,
            )
            card.validation_status = "HYPOTHESIS"
            continue

        # 13c: 5-Gate passes → set merchant_copy on card, include in response
        card.merchant_copy = merchant_copy
        response_cards.append(card)

    # ── Step 14: Write ALL candidates to WSM ─────────────────────────
    # was_executed=False — shadow mode always, regardless of gate outcomes
    for action in ranked:
        try:
            db_client.insert_wsm_transition(
                merchant_id=merchant_id,
                vertical=policy.get("vertical", "cpg"),
                decision_mode="deep",
                s_json={
                    k: getattr(msm_state, k, None)
                    for k in (
                        "acquisition_state", "conversion_state",
                        "retention_state", "promotion_state",
                    )
                },
                action_id=action.get("action_id", "unknown"),
                action_family=action.get("action_family", action.get("action_id", "unknown")),
                action_params_json={
                    k: action[k]
                    for k in ("action_id", "final_score", "u_base", "u_ucb", "risk_penalty")
                    if k in action
                },
                constraints_passed=action.get("eligible", False),
                violations_json=action.get("violations", []),
                base_utility_score=action.get("u_base"),
                bandit_ucb_score=action.get("u_ucb"),
                final_rank_score=action.get("final_score"),
                planner_policy_version=policy_version,
                was_executed=False,
                verification_chain=action.get("verification_chain"),
                impact_estimate=action.get("impact_estimate"),
                counterfactual=action.get("counterfactual"),
                urgency_score=action.get("urgency_score"),
                module=action.get("module"),
                msm_dimension=action.get("msm_dimension"),
                msm_state=getattr(
                    msm_state,
                    f"{action.get('module', 'retention')}_state",
                    None,
                ),
            )
        except Exception:
            # Step 14 failure: log error, do NOT crash pipeline
            log.exception(
                "[pipeline] WSM write failed for %s — continuing",
                action.get("action_id"),
            )

    # ── Step 15: WeeklyPlanner ───────────────────────────────────────
    # WeeklyPlanner expects plain dicts — pass model_dump() representations
    weekly_plan = _weekly_planner.plan([c.model_dump() for c in response_cards])

    # ── Step 16: Return ──────────────────────────────────────────────
    # Return DecisionCard objects — callers can call .model_dump() for serialization
    result_actions = list(response_cards)

    policy_out = {
        "policy_version": policy_version,
        "vertical": policy.get("vertical", "cpg"),
        "mode": "shadow" if settings.shadow_mode else "live",
        "emergency_triggered": emergency_triggered,
        "alerts": alerts,
        "msm_state": {
            d: getattr(msm_state, f"{d}_state") for d in _DIMENSIONS
        },
        "weekly_plan": weekly_plan,
    }

    return policy_out, result_actions


# ── Internal helpers ─────────────────────────────────────────────────

def _load_signals(merchant_id: str) -> dict:
    """Phase 1: load signals from DB or return empty dict (MSM uses fallback)."""
    state = db_client.fetch_latest_merchant_state(merchant_id)
    if state and state.get("metrics_snapshot"):
        return state["metrics_snapshot"]
    return {}


def _lkg_policy() -> dict | None:
    """Return last-known-good policy or a sensible default for Phase 1."""
    return {
        "policy_version": "default_v1",
        "vertical": "cpg",
        "policy_weights": {
            "gmv_lift": 0.4,
            "margin_lift": 0.3,
            "inventory_risk_reduction": 0.2,
            "retention_lift": 0.1,
        },
        "risk_budget": {
            "max_margin_drop_pct": 0.05,
            "max_refund_rate_increase_pct": 0.02,
        },
        "beta1": settings.beta1,
        "beta2": settings.beta2,
        "beta3": settings.beta3,
    }


def _generate_candidates(
    msm_state: MerchantStateVector,
    signals: dict,
    policy: dict,
) -> list[dict]:
    """Phase 1: generate candidates based on MSM state.

    For each at-risk dimension (WATCH or worse), create candidate actions
    from ImpactCalculator.INDUSTRY_BENCHMARKS.
    """
    candidates: list[dict] = []

    dim_fields = {
        "retention": ("retention_state", "retention_urgency"),
        "acquisition": ("acquisition_state", "acquisition_urgency"),
        "conversion": ("conversion_state", "conversion_urgency"),
        "promotion": ("promotion_state", "promotion_urgency"),
    }

    benchmarks = ImpactCalculator.INDUSTRY_BENCHMARKS

    for module, (state_field, urgency_field) in dim_fields.items():
        state = DimensionState(getattr(msm_state, state_field))
        urgency = getattr(msm_state, urgency_field)

        if state.severity_score() < 1:  # HEALTHY — skip
            continue

        # Try PlaybookRegistry first; fallback to INDUSTRY_BENCHMARKS when
        # partner YAML content (expected_utility) is not yet defined.
        playbook = _playbook_registry.match_playbook(module, {"msm_state": state.value})

        module_benchmarks = benchmarks.get(module, {})
        for action_id, bench in module_benchmarks.items():
            values = list(bench.values())
            mid_val = values[1] if len(values) > 1 else 0.0

            # Attempt to get U_base from Playbook YAML (partner-defined)
            kg_utility = None
            if playbook:
                kg_utility = _playbook_registry.get_base_utility(
                    playbook["id"], {"action_id": action_id}
                )

            pred = {}
            if kg_utility is not None:
                # KG Playbook source — partner has defined expected_utility
                pred["gmv_lift"] = kg_utility
                log.debug(
                    "[pipeline] U_base from KG playbook %s action=%s utility=%.4f",
                    playbook["id"], action_id, kg_utility,
                )
            elif module == "retention":
                # Fallback: INDUSTRY_BENCHMARKS
                pred["retention_lift"] = mid_val
                pred["gmv_lift"] = mid_val * 0.5
            elif module == "acquisition":
                pred["gmv_lift"] = mid_val
            elif module == "conversion":
                pred["gmv_lift"] = mid_val
            elif module == "promotion":
                pred["margin_lift"] = mid_val

            candidate: dict = {
                "action_id": action_id,
                "module": module,
                "msm_dimension": module,
                "urgency_score": urgency,
                "pred": pred,
                "action_family": action_id.split("_")[0],
                "signals": signals,
            }
            # Run ConstraintEngine — all 6 CPG hard constraints
            constraints_passed, violations = _constraint_engine.check_all(
                candidate=candidate,
                signals=signals,
                policy=policy,
            )
            candidate["constraints_result"] = (constraints_passed, violations)
            candidates.append(candidate)

    return candidates


def _merchant_state_dict(msm_state: MerchantStateVector, signals: dict) -> dict:
    """Build merchant_state dict for ImpactCalculator from MSM + signals."""
    return {
        "monthly_gmv": signals.get("monthly_gmv", 0),
        "monthly_ad_spend": signals.get("monthly_ad_spend", 0),
        "avg_order_value": signals.get("avg_order_value", 0),
        "monthly_orders": signals.get("monthly_orders", 0),
        "avg_margin_pct": signals.get("avg_margin_pct", 0),
    }


def _get_benchmark_metric(dimension: str, signals: dict) -> tuple[str, float]:
    """Get the primary benchmark metric for a dimension."""
    mapping = {
        "retention": ("overdue_ratio", signals.get("overdue_ratio", 0)),
        "acquisition": ("cac_vs_baseline_ratio", signals.get("cac_vs_baseline_ratio", 0)),
        "conversion": ("mobile_atc_desktop_ratio", signals.get("mobile_atc_desktop_ratio", 0)),
        "promotion": ("promo_incrementality", signals.get("promo_incrementality", 0)),
    }
    return mapping.get(dimension, ("", 0.0))


def _parse_msm(raw: dict) -> MerchantStateVector | None:
    """Parse a raw DB row into MerchantStateVector."""
    if not raw:
        return None
    try:
        return MerchantStateVector(
            merchant_id=raw.get("merchant_id", ""),
            computed_at=raw.get("computed_at", datetime.now(timezone.utc)),
            acquisition_state=raw.get("acquisition_state", "HEALTHY"),
            conversion_state=raw.get("conversion_state", "HEALTHY"),
            retention_state=raw.get("retention_state", "HEALTHY"),
            promotion_state=raw.get("promotion_state", "HEALTHY"),
            acquisition_urgency=raw.get("acquisition_urgency", 0.0),
            conversion_urgency=raw.get("conversion_urgency", 0.0),
            retention_urgency=raw.get("retention_urgency", 0.0),
            promotion_urgency=raw.get("promotion_urgency", 0.0),
        )
    except Exception:
        return None


