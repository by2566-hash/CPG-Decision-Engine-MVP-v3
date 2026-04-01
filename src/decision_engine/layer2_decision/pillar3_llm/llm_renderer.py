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
        "PAUSE_CHANNEL": {
            "diagnosis": "CAC increased {cac_increase_pct:.0%} above 30-day baseline",
            "recommendation": "Pause underperforming channel to reduce spend waste",
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


class _SafeDict(dict):
    """Dict that returns placeholder for missing keys during format_map."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
