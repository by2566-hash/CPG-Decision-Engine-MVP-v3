# ── Layer 2 · Pillar 3 — LLM Renderer / Mouth (Chain Layer 2 of 3) ────────
# Translates verified_decision into merchant-facing natural language.
# The LLM NEVER decides — it only explains.
# Runs ONLY after DecisionVerifier passes.
#
# Phase 1: DeterministicRenderer (no LLM API call) — template-based
# Phase 2+: LLM API call via llm_adapter
#
# CRITICAL: If verification_chain.all_passed is False, raise ValueError.
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...contracts import EvidenceGraphSnapshot

log = logging.getLogger(__name__)

# Templates by module × action_id
_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "retention": {
        "DISCOUNT_10PCT": {
            "diagnosis": "Customer shows {overdue_ratio:.1f}x overdue ratio, approaching churn",
            "recommendation": "Send 10% discount to re-engage before next expected order date",
        },
        "REMINDER_ONLY": {
            "diagnosis": "Customer is {overdue_ratio:.1f}x overdue on expected purchase cycle",
            "recommendation": "Send a personalized reminder to prompt re-engagement",
        },
        "SUPPRESS": {
            "diagnosis": "Customer retention metrics within normal range",
            "recommendation": "No action needed — continue monitoring",
        },
    },
    "acquisition": {
        "REALLOCATE_BUDGET": {
            "diagnosis": "CAC increased {cac_increase_pct:.0%} above 30-day baseline with declining ROAS",
            "recommendation": "Reallocate ad budget from underperforming channels to top converters",
        },
        "FIX_DESTINATION_ROUTING": {
            "diagnosis": "CAC increased {cac_increase_pct:.0%} above 30-day baseline — on-platform destination (IG/FB Shop) is routing traffic away from website conversion path",
            "recommendation": "Disable on-platform destination setting and route all traffic to website. Do not pause the Meta channel — only the destination needs to change.",
        },
        # UGC creative mix actions (acquisition_ugc_creative pattern — cba_001)
        "AUDIT_CREATIVE_MIX": {
            "diagnosis": "CAC increased {cac_increase_pct:.0%} and CPM rose {cpm_increase_pct:.0%} above baseline with no change in spend, audience, or campaign structure — creative composition is the primary suspect",
            "recommendation": "Audit active creative by content type (UGC vs brand-produced vs offer-led). Confirm format distribution. Do not adjust bids or audiences until creative composition is confirmed as the driver.",
        },
        "SCALE_TOP_CREATIVE": {
            "diagnosis": "Creative audit confirmed UGC format outperforming brand-produced at {ugc_cac_delta:.0%} lower CAC",
            "recommendation": "Scale spend behind top-performing UGC creative types. Shift budget from underperforming formats within the same channel.",
        },
    },
    "conversion": {
        "REORDER_SHELF": {
            "diagnosis": "Mobile add-to-cart rate {mobile_atc_gap:.0%} below desktop, affecting {mobile_traffic_pct:.0%} of traffic",
            "recommendation": "Reorder shelf layout to improve mobile conversion funnel",
        },
        "BUNDLE_SUGGEST": {
            "diagnosis": "Average order value trending {aov_trend} — bundle opportunities detected",
            "recommendation": "Suggest product bundles to increase average order value",
        },
        "DIAGNOSE_MIX": {
            "diagnosis": "Subscription rate decline detected — potential SKU mix or channel mix distortion, not universal funnel failure",
            "recommendation": "Segment subscription rate by SKU and channel before any sitewide changes",
        },
        "FIX_DENOMINATOR": {
            "diagnosis": "Subscription rate may be depressed by structurally non-subscribable channel orders in denominator",
            "recommendation": "Recalculate subscription rate excluding non-subscribable channels; reallocate budget if adjusted rate normalizes",
        },
        # Compliance friction diagnostics (conversion_compliance_friction pattern — cba_002)
        # SOP Section 10 (Proxy Trigger Discipline): recommendation MUST mention
        # timeline / recent changes BEFORE any user-segment or device-segment language.
        "AUDIT_RECENT_CHANGES": {
            "diagnosis": "CVR collapse may be caused by a recent site, flow, or legal/compliance change rather than traffic quality or channel quality",
            "recommendation": "First: audit the timeline of recent site, flow, and legal/compliance deploys against the CVR drop onset. Simulate the conversion path as a new visitor (incognito). Identify any friction points introduced recently. Confirm the root cause before triggering remediation.",
        },
        "REMOVE_COMPLIANCE_FRICTION": {
            "diagnosis": "CVR dropped suddenly across paid and organic with no change in traffic quality — timeline correlation indicates a recent site, flow, or compliance change is the primary suspect, not media or audience performance",
            "recommendation": "First: map CVR drop against timeline of recent site changes, legal/compliance deploys, and flow modifications. Simulate the full conversion path as a new visitor (incognito). Identify all friction points introduced recently. Then remove or redesign compliance-required friction and provide alternative paths for users who exit the primary flow.",
        },
    },
    "promotion": {
        "ROTATE_OFFER": {
            "diagnosis": "Promotion incrementality at {promo_incrementality:.0%} — below threshold, fatigue detected",
            "recommendation": "Rotate offer creative and targeting to restore promotional lift",
        },
        "HOLD_DISCOUNT": {
            "diagnosis": "Margin impact of {promo_margin_delta:.1%} from current promotions",
            "recommendation": "Hold current discount levels to protect margin",
        },
    },
}

_DEFAULT_TEMPLATE = {
    "diagnosis": "Merchant health metric requires attention in {module} dimension",
    "recommendation": "Recommended action: {action_id}",
}


class LLMRenderer:
    """Translates verified decisions into merchant-readable explanations.

    Layer 2 of the three-layer verification chain.
    ONLY runs after DecisionVerifier.all_passed = True.
    NEVER makes decisions — only renders verified decisions into merchant language.
    """

    def __init__(self) -> None:
        from ...config import settings
        if settings.llm_provider != "template" and not settings.llm_api_key:
            log.warning(
                "[LLMRenderer] llm_provider=%r but llm_api_key is empty — "
                "LLM rendering will fail at Phase 2 activation. "
                "Set LLM_API_KEY env var before switching from 'template'.",
                settings.llm_provider,
            )

    def render(self, verified_decision: dict) -> dict:
        """Render a verified decision into merchant-facing copy.

        CRITICAL: Raises ValueError if verification_chain.all_passed is False.
        This method must NEVER be called with a failed verification.

        Returns dict with:
          diagnosis, recommendation, impact_narrative,
          counterfactual_narrative, confidence_statement
        """
        vc = verified_decision.get("verification_chain", {})
        all_passed = (
            vc.get("all_passed", False) if isinstance(vc, dict)
            else getattr(vc, "all_passed", False)
        )
        if not all_passed:
            raise ValueError(
                f"LLMRenderer.render() called with failed verification for "
                f"action {verified_decision.get('action_id', '?')}. "
                f"This method must NEVER be called with a failed verification."
            )

        # Phase 1: deterministic rendering (no LLM API call)
        return self._deterministic_render(verified_decision)

    def _deterministic_render(self, verified_decision: dict) -> dict:
        """Phase 1 template-based rendering."""
        module = verified_decision.get("module", "unknown") or "unknown"
        action_id = verified_decision.get("action_id", "unknown")

        template = _TEMPLATES.get(module, {}).get(action_id, _DEFAULT_TEMPLATE)
        ctx = self._build_template_context(verified_decision)

        diagnosis = template["diagnosis"].format_map(_SafeDict(ctx))
        recommendation = template["recommendation"].format_map(_SafeDict(ctx))

        return {
            "diagnosis": diagnosis,
            "recommendation": recommendation,
            "impact_narrative": self._render_impact_narrative(verified_decision),
            "counterfactual_narrative": self._render_counterfactual(verified_decision),
            "confidence_statement": self._render_confidence(verified_decision),
        }

    def _build_template_context(self, vd: dict) -> dict:
        """Extract template context values from the verified decision."""
        ctx: dict = {
            "module": vd.get("module", "unknown"),
            "action_id": vd.get("action_id", "unknown"),
        }
        signals = vd.get("signals", {}) or vd.get("metrics_snapshot", {}) or {}

        ctx["overdue_ratio"] = signals.get("overdue_ratio", 0.0)
        ctx["repeat_purchase_rate"] = signals.get("repeat_purchase_rate", 0.0)

        cac_7d = signals.get("cac_7d", 0)
        cac_baseline = signals.get("cac_baseline_30d", 1)
        ctx["cac_increase_pct"] = (
            (cac_7d - cac_baseline) / cac_baseline if cac_baseline > 0 else 0.0
        )

        mobile_atc = signals.get("mobile_atc_rate", 0)
        desktop_atc = signals.get("desktop_atc_rate", 1)
        ctx["mobile_atc_gap"] = 1.0 - (mobile_atc / desktop_atc) if desktop_atc > 0 else 0.0
        ctx["mobile_traffic_pct"] = signals.get("mobile_traffic_pct", 0.0)
        ctx["aov_trend"] = "down" if signals.get("aov_trend_negative") else "stable"

        ctx["promo_incrementality"] = signals.get("promo_incrementality", 0.0)
        ctx["promo_margin_delta"] = signals.get("promo_margin_delta", 0.0)

        # cba_001 (acquisition_ugc_creative) context fields
        cpm_7d = signals.get("cpm_7d", 0)
        cpm_baseline = signals.get("cpm_baseline_30d", 1)
        ctx["cpm_increase_pct"] = (
            (cpm_7d - cpm_baseline) / cpm_baseline if cpm_baseline > 0 else 0.0
        )
        ctx["ugc_cac_delta"] = signals.get("ugc_cac_delta", 0.0)

        return ctx

    def _render_impact_narrative(self, vd: dict) -> str:
        """Render impact estimate into human-readable narrative."""
        ie = vd.get("impact_estimate")
        if ie is None:
            return "Impact estimate not available"

        if isinstance(ie, dict):
            conservative = ie.get("conservative", 0)
            expected = ie.get("expected", 0)
            optimistic = ie.get("optimistic", 0)
            confidence = ie.get("confidence", 0)
        else:
            conservative = getattr(ie, "conservative", 0)
            expected = getattr(ie, "expected", 0)
            optimistic = getattr(ie, "optimistic", 0)
            confidence = getattr(ie, "confidence", 0)

        return (
            f"Expected impact: ${expected:,.0f} "
            f"(range ${conservative:,.0f}\u2013${optimistic:,.0f}, "
            f"confidence {confidence:.0%})"
        )

    def _render_counterfactual(self, vd: dict) -> str | None:
        """Render counterfactual comparison into narrative."""
        cf = vd.get("counterfactual")
        if cf is None:
            return None

        why_not = cf.get("why_not", "") if isinstance(cf, dict) else getattr(cf, "why_not", "")
        runner_up = (
            cf.get("runner_up_action", "")
            if isinstance(cf, dict)
            else getattr(cf, "runner_up_action", "")
        )

        if not why_not:
            return None
        return f"Alternative considered: {runner_up}. {why_not}"

    def _render_confidence(self, vd: dict) -> str:
        """Render confidence level into human-readable statement."""
        ie = vd.get("impact_estimate")
        if ie is None:
            return "Confidence: insufficient data for estimate"

        confidence = (
            ie.get("confidence", 0) if isinstance(ie, dict) else getattr(ie, "confidence", 0)
        )

        if confidence >= 0.7:
            level = "high"
        elif confidence >= 0.4:
            level = "moderate"
        else:
            level = "low"

        source = "based on historical outcomes" if confidence > 0.30 else "based on industry benchmarks"
        return f"Confidence: {level} ({confidence:.0%}) \u2014 {source}"


    def render_from_snapshot(self, snapshot: "EvidenceGraphSnapshot") -> dict:
        """Render a decision explanation from an EvidenceGraphSnapshot. [ADR-0009]

        The snapshot is the SOLE substantive input. The renderer must only
        reference facts present in the trace — it must never add facts that are
        not in snapshot.evidence_trace[*].source_data.

        Phase 1 (deterministic mode): formats the trace into a readable paragraph.
        Phase 2+: LLM API call with prompt: "Translate this logic chain into
        merchant-facing language. Do not add facts not present in the trace."

        This method does NOT enforce verification_chain.all_passed — callers must
        only call it for verified (eligible) candidates. The snapshot itself
        carries the verification result in an L3_Verification trace entry.
        """
        # Phase 1: deterministic formatting — no LLM call
        return self._format_snapshot(snapshot)

    def _format_snapshot(self, snapshot: "EvidenceGraphSnapshot") -> dict:
        """Phase 1 deterministic renderer for EvidenceGraphSnapshot.

        Produces two distinct narratives:
          impact_narrative    — merchant-facing copy, no raw floats (Gate 3 compliant)
          evidence_narrative  — technical trace for debugging / L5 logging
        """
        diagnosis = ""
        recommendation = f"Action: {snapshot.winner_action}"
        scoring_summary = ""
        kg_finding = ""
        constraint_finding = ""

        for entry in snapshot.evidence_trace:
            if entry.step == "L1_State":
                diagnosis = entry.finding
            elif entry.step == "L2_KG":
                kg_finding = entry.finding
            elif entry.step == "L3_Scoring":
                scoring_summary = entry.finding
            elif entry.step == "L3_Constraint" and entry.source_data.get("eligible"):
                constraint_finding = entry.finding
                recommendation = (
                    f"Action: {snapshot.winner_action} — "
                    f"{entry.finding.lower()}"
                )

        # impact_narrative: merchant-facing summary — no raw floats (Gate 3 compliant).
        # Describes the situation and action in qualitative terms only.
        impact_parts = []
        if diagnosis:
            impact_parts.append(diagnosis)
        if kg_finding:
            impact_parts.append(kg_finding)
        if constraint_finding:
            impact_parts.append(constraint_finding)
        if not impact_parts:
            impact_parts.append(f"Decision basis available for {snapshot.winner_action}")
        impact_narrative = " | ".join(impact_parts)

        # evidence_narrative: full technical trace for L5 logging / offline analysis.
        # Contains raw numerics — not passed through Gate 3.
        evidence_parts = [
            f"[{entry.step}] {entry.finding}"
            for entry in snapshot.evidence_trace
        ]
        evidence_narrative = " | ".join(evidence_parts)

        # confidence_statement and impact_narrative are 5-Gate Gate-1 required fields.
        confidence_stmt = (
            f"Evidence grounded from {len(snapshot.evidence_trace)}-step causal trace "
            f"(L1→L2→L3). Confidence: based on partner calibration prior."
        )
        return {
            "diagnosis": diagnosis or f"Decision trace for {snapshot.winner_action}",
            "recommendation": recommendation,
            "impact_narrative": impact_narrative,    # 5-Gate required, no raw floats
            "confidence_statement": confidence_stmt, # 5-Gate required
            "evidence_narrative": evidence_narrative, # technical trace for L5 logging
            "scoring_summary": scoring_summary,
            "snapshot_candidate_id": snapshot.candidate_id,
        }


class _SafeDict(dict):
    """Dict that returns placeholder for missing keys during format_map."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
