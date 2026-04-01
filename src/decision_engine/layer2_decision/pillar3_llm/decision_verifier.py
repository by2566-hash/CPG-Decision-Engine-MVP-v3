# ── Layer 2 · Pillar 3 — Decision Verifier (Chain Layer 1 of 3) ───────────
# Logic integrity verification BEFORE LLM rendering.
# A failed verification BLOCKS LLM rendering (final_score = -inf).
# All failures are recorded in VerificationChain (stored in WSM).
#
# 4 verification steps (all must pass):
#   1. MSM Trigger — candidate module matches an at-risk dimension
#   2. Margin Gate — post-discount margin >= 0.15
#   3. Inventory Gate — inventory_days_p10 >= 5 for discount actions
#   4. Conflict Check — candidate not suppressed by CrossModuleCorrelator
#
# FAILURE BEHAVIOR: Blocks LLM rendering — wrong reasoning must NOT be expressed.
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging

from ...contracts import MerchantStateVector, VerificationChain, VerificationStep
from ...layer1_msm.state_definitions import DimensionState

log = logging.getLogger(__name__)

# Module → dimension mapping for MSM trigger check
_MODULE_DIMENSION_MAP: dict[str, str] = {
    "retention": "retention",
    "acquisition": "acquisition",
    "conversion": "conversion",
    "promotion": "promotion",
}

# Margin floor from CLAUDE.md: post-discount margin >= 0.15
_MARGIN_FLOOR = 0.15

# Minimum inventory days for discount actions
_INVENTORY_MIN_DAYS = 5

# Action families that are discount-type (require inventory check)
_DISCOUNT_ACTIONS = frozenset({
    "DISCOUNT_5PCT", "DISCOUNT_10PCT", "DISCOUNT_15PCT", "DISCOUNT_20PCT",
    "DISCOUNT_30PCT", "HIGH_DISCOUNT", "FLASH_SALE", "BUNDLE_DISCOUNT",
})


class DecisionVerifier:
    """Pre-LLM logic integrity checker — gate 1 of the verification chain.

    Run all 4 steps. Return VerificationChain.
    all_passed = True only if ALL steps pass.
    """

    def verify(
        self,
        msm_state: MerchantStateVector,
        candidate: dict,
        policy: dict,
        constraints_result: tuple[bool, list[str]],
        all_candidates: list[dict],
    ) -> VerificationChain:
        """Run all 4 verification steps. Return VerificationChain.

        all_passed is True only if ALL steps pass.
        """
        step_msm = self._verify_msm_trigger(msm_state, candidate)
        step_margin = self._verify_margin_gate(candidate, policy)
        step_inventory = self._verify_inventory_gate(candidate, candidate)
        step_conflict = self._verify_conflict_check(candidate, msm_state, all_candidates)

        all_passed = all([
            step_msm.passed,
            step_margin.passed,
            step_inventory.passed,
            step_conflict.passed,
        ])

        chain = VerificationChain(
            msm_trigger=step_msm,
            margin_gate=step_margin,
            inventory_gate=step_inventory,
            conflict_check=step_conflict,
            all_passed=all_passed,
        )

        if not all_passed:
            failed = [s.name for s in [step_msm, step_margin, step_inventory, step_conflict] if not s.passed]
            log.warning(
                "DecisionVerifier FAILED for action %s: %s",
                candidate.get("action_id", "?"), failed,
            )

        return chain

    def _verify_msm_trigger(
        self,
        msm_state: MerchantStateVector,
        candidate: dict,
    ) -> VerificationStep:
        """Check: candidate's module matches a dimension that is WATCH/DEGRADING/CRITICAL.

        Pass: module maps to an at-risk dimension (severity >= WATCH)
        Fail: module fires but its dimension is HEALTHY (wasteful action)
        """
        module = candidate.get("module", "")
        dim_name = _MODULE_DIMENSION_MAP.get(module)

        if dim_name is None:
            # Unknown module — pass with note (don't block unknown modules)
            return VerificationStep(
                name="msm_trigger",
                passed=True,
                value=0.0,
                threshold=1.0,
                reason=f"Module '{module}' has no dimension mapping — passed by default",
            )

        state_str = getattr(msm_state, f"{dim_name}_state", "HEALTHY")
        dim_state = DimensionState(state_str)
        severity = dim_state.severity_score()

        passed = severity >= 1  # WATCH (1) or worse
        return VerificationStep(
            name="msm_trigger",
            passed=passed,
            value=float(severity),
            threshold=1.0,
            reason=(
                f"{dim_name} dimension is {dim_state.value} (severity={severity})"
                if passed
                else f"{dim_name} dimension is HEALTHY — {module} action is wasteful"
            ),
        )

    def _verify_margin_gate(
        self,
        candidate: dict,
        policy: dict,
    ) -> VerificationStep:
        """Check: action cost does not violate margin floor (15%).

        Margin floor from CLAUDE.md: post-discount margin >= 0.15
        """
        post_discount_margin = candidate.get("post_discount_margin")

        if post_discount_margin is None:
            # No margin info — pass with note (non-discount actions)
            return VerificationStep(
                name="margin_gate",
                passed=True,
                value=1.0,
                threshold=_MARGIN_FLOOR,
                reason="No margin data — non-discount action, passed by default",
            )

        passed = post_discount_margin >= _MARGIN_FLOOR
        return VerificationStep(
            name="margin_gate",
            passed=passed,
            value=float(post_discount_margin),
            threshold=_MARGIN_FLOOR,
            reason=(
                f"Post-discount margin {post_discount_margin:.2%} >= {_MARGIN_FLOOR:.0%} floor"
                if passed
                else f"Post-discount margin {post_discount_margin:.2%} < {_MARGIN_FLOOR:.0%} floor — BLOCKED"
            ),
        )

    def _verify_inventory_gate(
        self,
        candidate: dict,
        signals: dict,
    ) -> VerificationStep:
        """Check: inventory_days_p10 >= minimum threshold for discount actions.

        If action is a discount: require inventory_days_p10 >= 5
        If signals missing: pass with low confidence (note in reason)
        """
        action_id = candidate.get("action_id", "")

        # Only applies to discount-type actions
        if action_id not in _DISCOUNT_ACTIONS:
            return VerificationStep(
                name="inventory_gate",
                passed=True,
                value=float("inf"),
                threshold=float(_INVENTORY_MIN_DAYS),
                reason="Non-discount action — inventory gate not applicable",
            )

        inventory_days = signals.get("inventory_days_p10")

        if inventory_days is None:
            # Missing signal — pass with low confidence
            return VerificationStep(
                name="inventory_gate",
                passed=True,
                value=0.0,
                threshold=float(_INVENTORY_MIN_DAYS),
                reason="inventory_days_p10 missing — passed with low confidence",
            )

        passed = inventory_days >= _INVENTORY_MIN_DAYS
        return VerificationStep(
            name="inventory_gate",
            passed=passed,
            value=float(inventory_days),
            threshold=float(_INVENTORY_MIN_DAYS),
            reason=(
                f"Inventory {inventory_days}d >= {_INVENTORY_MIN_DAYS}d minimum"
                if passed
                else f"Inventory {inventory_days}d < {_INVENTORY_MIN_DAYS}d minimum — BLOCKED"
            ),
        )

    def _verify_conflict_check(
        self,
        candidate: dict,
        msm_state: MerchantStateVector,
        all_candidates: list[dict],
    ) -> VerificationStep:
        """Check: candidate is not suppressed by CrossModuleCorrelator.

        Pass: candidate["suppressed"] is False or not set
        Fail: candidate["suppressed"] is True
        """
        suppressed = candidate.get("suppressed", False)
        reason = candidate.get("suppression_reason", "")

        return VerificationStep(
            name="conflict_check",
            passed=not suppressed,
            value=1.0 if not suppressed else 0.0,
            threshold=1.0,
            reason=(
                "No cross-module conflict"
                if not suppressed
                else f"Suppressed by CrossModuleCorrelator: {reason}"
            ),
        )
