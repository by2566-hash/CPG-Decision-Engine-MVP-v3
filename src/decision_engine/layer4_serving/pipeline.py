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
import re as _re_module
from datetime import datetime, timezone

from ..config import settings
from ..contracts import (
    MerchantStateVector, DecisionCard, ImpactEstimate, Counterfactual, VerificationChain,
    EvidenceGraphSnapshot, EvidenceTraceEntry,
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
from ..feature_plane import FeatureBuilder

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
_feature_builder = FeatureBuilder()

# Dimension → module mapping
_DIMENSIONS = ["acquisition", "conversion", "retention", "promotion"]


def run_once(
    merchant_id: str,
    signals: dict | None = None,
) -> tuple[dict, list[dict]]:
    """Execute full Deep Plane cycle. Returns (policy_pack_dict, ranked_actions_with_cards).

    16-step pipeline in strict order. See module docstring for invariants.

    INVARIANT: WSM write (Step 14) executes regardless of pipeline success or
    failure. On crash before scoring, a pipeline_error sentinel record is written
    so L5 always has a trace — even for failed runs.
    """
    # Pre-declare so except/finally can always reference them safely
    ranked: list[dict] = []
    policy: dict = {}
    msm_state = None
    alerts: list = []
    emergency_triggered: bool = False
    policy_version: str = "unknown"
    _pipeline_error: str | None = None

    try:
        # ── Step 1: Load merchant signals ────────────────────────────
        if signals is None:
            signals = _load_signals(merchant_id)

        # ── Step 2: Compute MerchantStateVector via MSM ──────────────
        # IMPORTANT: fetch previous state BEFORE compute() — MSM.compute()
        # upserts the new state to DB, so any fetch after compute() returns
        # the current (new) state, not the previous one. AlertEngine needs the
        # true previous state to detect transitions (HEALTHY→DEGRADING, etc.).
        prev_raw = db_client.fetch_latest_merchant_state(merchant_id)
        previous_msm = _parse_msm(prev_raw) if prev_raw else None

        msm_state = _msm.compute(merchant_id, signals)
        log.info("[pipeline] MSM computed for %s", merchant_id)

        # ── Feature snapshot (L5) — extract BEFORE Step 5 ────────────
        # Must happen before candidate generation so anomaly detector
        # receives HEALTHY-state baseline data, not just anomalous runs.
        # Stored as a local variable; written to decision_log at Step 15b.
        _feature_snapshot = _feature_builder.build(signals, msm_state)

        # ── Step 3: Run AlertEngine — log alerts, flag emergency ─────
        alerts = _alert_engine.check_and_alert(merchant_id, msm_state, previous_msm)
        emergency_triggered = _alert_engine.should_trigger_emergency_decision(
            msm_state, previous_msm,
        )
        if alerts:
            log.info("[pipeline] Alerts for %s: %s", merchant_id, alerts)

        # ── Step 4: Load PolicyPack (with LKG fallback) ──────────────
        policy = db_client.fetch_latest_policy(merchant_id)
        if policy is None:
            policy = _lkg_policy()
            if policy is None:
                raise RuntimeError(
                    f"No policy pack available for merchant {merchant_id} "
                    f"and no LKG fallback found"
                )
        policy_version = policy.get("policy_version", "unknown")

        # ── Step 5: Load candidates from KG Playbooks ────────────────
        candidates = _generate_candidates(msm_state, signals, policy, merchant_id)

        # ── Step 6–8: Score via ScoringEngine ────────────────────────
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

        # ── Step 8b: Build EvidenceGraphSnapshot for top-K eligible ──
        # Snapshots are built for top-3 eligible candidates only (cost control).
        # Each snapshot aggregates the causal chain from L1 through L3 so the
        # LLM Renderer can translate facts without hallucinating new ones (ADR-0009).
        eligible_for_snap = [a for a in ranked if a.get("eligible", True)]
        for action in eligible_for_snap[:3]:
            snapshot = _build_evidence_snapshot(action, msm_state)
            action["evidence_snapshot"] = snapshot

        # ── Step 9: For top 5 eligible → ImpactCalculator.estimate() ─
        eligible = [a for a in ranked if a.get("eligible", True)]
        merchant_state = _merchant_state_dict(msm_state, signals)

        for action in eligible[:5]:
            module = action.get("module", "retention")
            ie = _impact_calc.estimate(action, merchant_state, module)
            action["impact_estimate"] = ie.model_dump()

        # ── Step 10: Counterfactual for top 1 vs runner-up ───────────
        if len(eligible) >= 2:
            cf = _impact_calc.build_counterfactual(
                eligible[0], eligible[1], merchant_state,
                eligible[0].get("module", "retention"),
            )
            if cf:
                eligible[0]["counterfactual"] = cf.model_dump()

        # ── Step 11: BenchmarkEngine for DEGRADING/CRITICAL dimensions
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

        # ── Step 12: Assemble DecisionCards (top 3 only) ─────────────
        # Instantiate real DecisionCard objects — Pydantic validates every field.
        decision_cards: list[DecisionCard] = []
        for i, action in enumerate(eligible[:3]):
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
                card_id=f"dc_{ts}_{merchant_id}_{module}_{i}",
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

        # ── Step 13: Render + 5-Gate for each DecisionCard ───────────
        # decision_cards and eligible[:3] are built in the same loop order —
        # zip them so we can access the evidence_snapshot alongside each card.
        response_cards: list[DecisionCard] = []
        for card, action_dict in zip(decision_cards, eligible[:3]):
            vc = card.verification_chain
            all_passed = vc.all_passed if vc is not None else False

            if not all_passed:
                continue  # DecisionVerifier failed → no LLM call

            # 13a: Render — prefer evidence-grounded snapshot path [ADR-0009].
            # render_from_snapshot() translates the L1→L3 causal chain; the
            # renderer only references facts present in the trace (no hallucination).
            # Falls back to render() when no snapshot (e.g. non-top-3 cards).
            # card_dict is always built so the 5-Gate policy-echo check has access
            # to module/action_id regardless of which render path was taken.
            card_dict = card.model_dump()
            card_dict["signals"] = signals
            snapshot = action_dict.get("evidence_snapshot")
            try:
                if snapshot is not None:
                    merchant_copy = _llm_renderer.render_from_snapshot(snapshot)
                else:
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

        # ── Step 14: Write ALL candidates to WSM ─────────────────────
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
                # Step 14 individual write failure: log and continue — never crash pipeline
                log.exception(
                    "[pipeline] WSM write failed for %s — continuing",
                    action.get("action_id"),
                )

        # ── Step 15: WeeklyPlanner ────────────────────────────────────
        # WeeklyPlanner expects plain dicts — pass model_dump() representations
        weekly_plan = _weekly_planner.plan([c.model_dump() for c in response_cards])

        # ── Step 15b: Decision Log (L5 Time-1 write) ─────────────────
        # Non-fatal — log failure but never crash the pipeline over it.
        # feature_snapshot was extracted before Step 5 so it is always
        # populated regardless of whether candidates were generated.
        try:
            _write_decision_log_record(
                merchant_id=merchant_id,
                msm_state=msm_state,
                feature_snapshot=_feature_snapshot,
                ranked=ranked,
                policy=policy,
                policy_version=policy_version,
            )
        except Exception:
            log.warning(
                "[pipeline] decision_log write failed for %s — non-fatal",
                merchant_id, exc_info=True,
            )

        # ── Step 16: Return ───────────────────────────────────────────
        # Return DecisionCard objects — callers can call .model_dump() for serialization
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
        return policy_out, list(response_cards)

    except Exception as exc:
        # Log with full traceback so the root cause is always visible
        _pipeline_error = f"{type(exc).__name__}: {exc}"
        log.error(
            "[pipeline] run_once FAILED for %s — %s",
            merchant_id, _pipeline_error, exc_info=True,
        )
        raise  # re-raise so caller (API / DAG) knows this run failed

    finally:
        # ── INVARIANT: write WSM failure record when pipeline crashed before scoring
        # If ranked is still empty (crash in Steps 1-5), we have nothing to write
        # in Step 14. Write a single sentinel record so L5 always has a trace.
        if _pipeline_error is not None and not ranked:
            try:
                db_client.insert_wsm_transition(
                    merchant_id=merchant_id,
                    vertical=policy.get("vertical", "cpg") if policy else "cpg",
                    decision_mode="deep",
                    s_json={
                        k: getattr(msm_state, k, None)
                        for k in (
                            "acquisition_state", "conversion_state",
                            "retention_state", "promotion_state",
                        )
                    } if msm_state else {},
                    action_id="pipeline_error",
                    action_family="pipeline_error",
                    action_params_json={"error": _pipeline_error},
                    constraints_passed=False,
                    violations_json=["pipeline_error"],
                    was_executed=False,
                )
            except Exception:
                log.exception(
                    "[pipeline] WSM error-sentinel write also failed for %s", merchant_id
                )


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
    merchant_id: str = "",
) -> list[dict]:
    """Phase 1: generate candidates based on MSM state.

    For each at-risk dimension (WATCH or worse), create candidate actions
    from ImpactCalculator.INDUSTRY_BENCHMARKS.

    merchant_id is used to load brand bindings for U_base priority lookup
    and evidence_refs template rendering. [ADR-0011]
    """
    candidates: list[dict] = []

    # Build DecisionFeatureVector once per pipeline run (signals are constant).
    # Attached to each candidate under "feature_vector" for downstream consumers
    # (scoring engine in Phase 2 Track B, bandit in Phase 3).
    # Existing consumers of the "signals" dict are unchanged — this is additive.
    feature_vector = _feature_builder.build(signals, msm_state)

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
        playbook = _playbook_registry.match_playbook(module, {"msm_state": state.value}, merchant_id=merchant_id)

        module_benchmarks = benchmarks.get(module, {})

        # Determine action vocabulary. [ADR-0011]
        # Meta-patterns are the authoritative source for action_ids — their
        # actions[] list defines the candidate set for this pattern.
        # Flat stub playbooks and no-playbook cases fall back to INDUSTRY_BENCHMARKS.
        if playbook and playbook.get("_is_meta") and playbook.get("actions"):
            action_ids = [a["id"] for a in playbook["actions"] if a.get("id")]
            action_types = {a["id"]: a.get("type", "") for a in playbook["actions"] if a.get("id")}
        else:
            action_ids = list(module_benchmarks.keys())
            action_types = {}

        for action_id in action_ids:
            # Fallback mid_val from INDUSTRY_BENCHMARKS (used when no KG prior).
            bench = module_benchmarks.get(action_id, {})
            values = list(bench.values())
            mid_val = values[1] if len(values) > 1 else 0.0

            # Attempt to get U_base from brand binding (priority 1) or
            # flat playbook expected_utility (priority 2). [ADR-0011]
            # merchant_id enables brand binding lookup in PlaybookRegistry.
            kg_utility = None
            if playbook:
                kg_utility = _playbook_registry.get_base_utility(
                    playbook["id"], {"action_id": action_id, "merchant_id": merchant_id}
                )

            pred = {}
            if kg_utility is not None:
                # KG Playbook source — partner has defined expected_utility
                pred["gmv_lift"] = kg_utility
                log.debug(
                    "[pipeline] U_base from KG playbook %s action=%s utility=%.4f",
                    playbook["id"], action_id, kg_utility,
                )
            else:
                # Fallback: INDUSTRY_BENCHMARKS — no KG prior found.
                # Item 4 fix: explicit warning so incomplete brand bindings are visible.
                log.warning(
                    "[pipeline] U_base fallback to INDUSTRY_BENCHMARKS for "
                    "merchant=%s module=%s action=%s — no KG prior found. "
                    "Check brand binding completeness before external user launch.",
                    merchant_id, module, action_id,
                )
                if module == "retention":
                    pred["retention_lift"] = mid_val
                    pred["gmv_lift"] = mid_val * 0.5
                elif module == "acquisition":
                    pred["gmv_lift"] = mid_val
                elif module == "conversion":
                    pred["gmv_lift"] = mid_val
                elif module == "promotion":
                    pred["margin_lift"] = mid_val

            # Populate evidence_refs from brand binding template. [ADR-0011]
            # Renders ${metrics.*} placeholders with available signal values.
            evidence_refs: list[str] = []
            if playbook:
                binding = _playbook_registry.get_brand_binding(merchant_id, playbook["id"])
                if binding:
                    templates = binding.get("evidence_refs_template", [])
                    flat_signals = {f"metrics.{k}": str(v) for k, v in signals.items() if v is not None}
                    for tmpl in templates:
                        try:
                            rendered = _re_module.sub(
                                r"\$\{([^}]+)\}",
                                lambda m: flat_signals.get(m.group(1), m.group(0)),
                                tmpl,
                            )
                            # Item 3 fix: warn when placeholder was not resolved.
                            # Unresolved ${...} means the signal is missing from
                            # the pipeline run — external users would see raw placeholders.
                            if "${" in rendered:
                                log.warning(
                                    "[pipeline] evidence_refs placeholder unresolved: '%s' "
                                    "(signal not in signals dict for merchant=%s action=%s). "
                                    "Ensure L0 connector populates this signal before use.",
                                    rendered, merchant_id, action_id,
                                )
                            evidence_refs.append(rendered)
                        except Exception:
                            evidence_refs.append(tmpl)

            candidate: dict = {
                "action_id": action_id,
                "action_type": action_types.get(action_id, ""),  # e.g. DIAGNOSTIC / FLOW_CHANGE
                "playbook_id": playbook["id"] if playbook else None,  # for decision_log pattern_matched
                "module": module,
                "msm_dimension": module,
                "urgency_score": urgency,
                "pred": pred,
                "action_family": action_id.split("_")[0],
                "signals": signals,
                "evidence_refs": evidence_refs,
            }
            # Run ConstraintEngine — all 6 CPG hard constraints.
            # Returns PolicyDecision (weighted risk_penalty, typed violations).
            policy_decision = _constraint_engine.check_all(
                candidate=candidate,
                signals=signals,
                policy=policy,
            )
            candidate["constraints_result"] = policy_decision
            candidate["feature_vector"] = feature_vector
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


def _build_evidence_snapshot(
    candidate: dict,
    msm_state: MerchantStateVector,
) -> EvidenceGraphSnapshot:
    """Build an EvidenceGraphSnapshot for a single top-K candidate. [ADR-0009]

    Aggregates the causal chain from L1 state → L2 KG → L3 constraint
    → L3 scoring → L3 verification into a single sealed object.

    The snapshot is passed to LLMRenderer.render_from_snapshot() so the
    renderer translates facts without hallucinating new ones.
    """
    entries: list[EvidenceTraceEntry] = []

    # ── L1: Merchant state ────────────────────────────────────────────
    module = candidate.get("module", "unknown")
    dim_state = getattr(msm_state, f"{module}_state", "UNKNOWN")
    dim_urgency = getattr(msm_state, f"{module}_urgency", 0.0)
    # Use integer percentage for urgency in the finding text so Gate 3 (no raw floats)
    # passes when this finding is included in merchant-facing impact_narrative.
    urgency_pct = int(round(dim_urgency * 100))
    entries.append(EvidenceTraceEntry(
        step="L1_State",
        finding=f"{module.capitalize()} dimension is {dim_state} (urgency={urgency_pct}%)",
        source_data={
            "module": module,
            "state": dim_state,
            "urgency": dim_urgency,
            "merchant_id": msm_state.merchant_id,
        },
    ))

    # ── L2: KG / Playbook ────────────────────────────────────────────
    evidence_refs = candidate.get("evidence_refs", [])
    pred = candidate.get("pred", {})
    entries.append(EvidenceTraceEntry(
        step="L2_KG",
        finding=(
            f"Playbook matched for {module}; "
            f"evidence refs: {evidence_refs or ['benchmark_prior']}"
        ),
        source_data={
            "evidence_refs": evidence_refs,
            "pred": pred,
            "action_family": candidate.get("action_family", ""),
        },
    ))

    # ── L3: Constraint evaluation ────────────────────────────────────
    # After rank_actions(), `constraints_result` is flattened to `eligible`
    # and `violations` keys.  Accept both forms.
    pd = candidate.get("constraints_result")
    if pd is not None:
        c_eligible = getattr(pd, "eligible", True)
        c_violations = list(getattr(pd, "violations", []))
        c_risk = getattr(pd, "risk_penalty", 0.0)
    else:
        c_eligible = candidate.get("eligible", True)
        c_violations = list(candidate.get("violations", []))
        c_risk = candidate.get("risk_penalty", 0.0)
    if c_eligible:
        constraint_finding = "All constraints passed"
    else:
        constraint_finding = f"Blocked — violations: {', '.join(c_violations)}"
    entries.append(EvidenceTraceEntry(
        step="L3_Constraint",
        finding=constraint_finding,
        source_data={
            "eligible": c_eligible,
            "violations": c_violations,
            "risk_penalty": c_risk,
        },
    ))

    # ── L3: Scoring ──────────────────────────────────────────────────
    u_base = candidate.get("u_base", 0.0)
    u_ucb = candidate.get("u_ucb", 0.0)
    rp = candidate.get("risk_penalty", 0.0)
    final_score = candidate.get("final_score", 0.0)
    entries.append(EvidenceTraceEntry(
        step="L3_Scoring",
        finding=(
            f"final_score={final_score:.4f} "
            f"(β1·U_base={u_base:.4f}, β2·U_ucb={u_ucb:.4f}, β3·Risk={rp:.4f})"
        ),
        source_data={
            "u_base": u_base,
            "u_ucb": u_ucb,
            "risk_penalty": rp,
            "final_score": final_score,
        },
    ))

    # ── L3: Verification ─────────────────────────────────────────────
    vc = candidate.get("verification_chain")
    if vc is not None:
        all_passed = vc.get("all_passed", False) if isinstance(vc, dict) else getattr(vc, "all_passed", False)
        vf = "Verification passed (all gates green)" if all_passed else "Verification failed — final_score set to -inf"
        entries.append(EvidenceTraceEntry(
            step="L3_Verification",
            finding=vf,
            source_data={"all_passed": all_passed},
        ))

    action_id = candidate.get("action_id", "unknown")
    return EvidenceGraphSnapshot(
        candidate_id=f"{msm_state.merchant_id}_{action_id}",
        winner_action=action_id,
        evidence_trace=entries,
    )


def _write_decision_log_record(
    merchant_id: str,
    msm_state: MerchantStateVector,
    feature_snapshot,           # DecisionFeatureVector
    ranked: list[dict],
    policy: dict,
    policy_version: str,
) -> None:
    """Write one L5 Decision Log record (Time-1 write).

    Called once per pipeline run after Step 15 (WeeklyPlanner).
    Simplified candidate summary — full candidate dicts contain nested
    Pydantic objects that don't JSON-serialize directly.

    Three ML consumers downstream:
      - Anomaly Detector: feature_snapshot (needs HEALTHY runs too)
      - XGBoost: candidates + user_response + outcome_delta pairing
      - LinUCB: full context → action → reward triple
    """
    import uuid
    from ..layer5_wsm.decision_log import DecisionLog, write_decision_log

    candidates_summary = [
        {
            "action_id": a.get("action_id"),
            "module": a.get("module"),
            "playbook_id": a.get("playbook_id"),
            "gmv_lift": a.get("pred", {}).get("gmv_lift"),
            "final_score": a.get("final_score"),
            "eligible": a.get("eligible", True),
            "violations": a.get("violations", []),
        }
        for a in ranked
    ]

    top_action = ranked[0].get("action_id") if ranked else None
    # pattern_matched: playbook_id of the top action (may be None in cold-start)
    pattern_matched = ranked[0].get("playbook_id") if ranked else None

    weights = policy.get("policy_weights", {})
    scoring_snapshot = {
        "beta1": policy.get("beta1", settings.beta1),
        "beta2": policy.get("beta2", settings.beta2),
        "beta3": policy.get("beta3", settings.beta3),
        "policy_version": policy_version,
        "u_base_weight": weights.get("gmv_lift", 0.4),
    }

    record = DecisionLog(
        log_id=str(uuid.uuid4()),
        merchant_id=merchant_id,
        created_at=datetime.now(timezone.utc),
        msm_state={d: getattr(msm_state, f"{d}_state") for d in _DIMENSIONS},
        feature_snapshot=feature_snapshot.model_dump(),
        pattern_matched=pattern_matched,
        candidates=candidates_summary,
        top_action=top_action,
        scoring_snapshot=scoring_snapshot,
    )
    write_decision_log(record)
    log.debug("[pipeline] decision_log written for %s log_id=%s", merchant_id, record.log_id)


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


