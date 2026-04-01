# ── Layer 2 · Cross-Module Correlator ──────────────────────────────────────
# Runs BEFORE individual Pillar scoring. Detects cross-module contradictions
# and suppresses conflicting actions.
#
# Rules loaded from CONFLICT_RULES, not hardcoded in scoring logic.
# Suppressed candidates remain in the list but are flagged — never silently
# dropped — so the verification chain and WSM can record the suppression.
#
# Examples:
#   - CAC↑ + CVR↓ simultaneously → suppress INCREASE_AD_BUDGET, fix conversion first
#   - Retention CRITICAL + Promotion WATCH → suppress HIGH_DISCOUNT
#     (avoids training wait-for-discount behavior in at-risk customers)
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging

from ..contracts import MerchantStateVector
from ..layer1_msm.state_definitions import DimensionState

log = logging.getLogger(__name__)

# Conflict rules: each rule has a condition (dimension→state) and actions to suppress.
# All thresholds reference DimensionState values, not raw numbers.
CONFLICT_RULES: list[dict] = [
    {
        "condition": {"acquisition": "DEGRADING", "conversion": "DEGRADING"},
        "suppress_actions": ["INCREASE_AD_BUDGET", "REALLOCATE_BUDGET_UP"],
        "reason": "CAC rising + CVR dropping = fix conversion first, not add spend",
    },
    {
        "condition": {"retention": "CRITICAL", "promotion": "WATCH"},
        "suppress_actions": ["HIGH_DISCOUNT", "DISCOUNT_15PCT"],
        "reason": "Discounting trains wait-for-sale behavior in at-risk customers",
    },
]


class CrossModuleCorrelator:
    """Detects cross-module conflicts and suppresses contradictory actions."""

    def __init__(self, rules: list[dict] | None = None):
        self.rules = rules if rules is not None else CONFLICT_RULES

    def correlate(
        self,
        msm_state: MerchantStateVector,
        candidates: list[dict],
    ) -> list[dict]:
        """Check each candidate against conflict rules given MSM state.

        For each candidate, if any CONFLICT_RULE applies and the candidate's
        action_id is in suppress_actions:
          - Set candidate["suppressed"] = True
          - Set candidate["suppression_reason"] = rule["reason"]

        Suppressed candidates remain in the list but are flagged.
        Returns modified candidates list.
        """
        # Build dimension→state lookup from MSM vector
        dim_states = {
            "acquisition": msm_state.acquisition_state,
            "conversion": msm_state.conversion_state,
            "retention": msm_state.retention_state,
            "promotion": msm_state.promotion_state,
        }

        # Find which rules are active given the current MSM state
        active_suppressions: list[tuple[str, str]] = []  # (action_id, reason)
        for rule in self.rules:
            condition = rule["condition"]
            # Rule applies if ALL dimension conditions match (at-or-worse)
            rule_applies = True
            for dim, required_state_str in condition.items():
                actual = DimensionState(dim_states.get(dim, "HEALTHY"))
                required = DimensionState(required_state_str)
                if actual < required:
                    rule_applies = False
                    break

            if rule_applies:
                for action_id in rule["suppress_actions"]:
                    active_suppressions.append((action_id, rule["reason"]))

        # Apply suppressions to candidates
        suppression_map: dict[str, str] = {}
        for action_id, reason in active_suppressions:
            suppression_map[action_id] = reason

        for candidate in candidates:
            action_id = candidate.get("action_id", "")
            if action_id in suppression_map:
                candidate["suppressed"] = True
                candidate["suppression_reason"] = suppression_map[action_id]
                log.info(
                    "Suppressed action %s: %s",
                    action_id, suppression_map[action_id],
                )
            else:
                candidate.setdefault("suppressed", False)

        return candidates

    def get_suppressed_actions(self, candidates: list[dict]) -> list[str]:
        """Return action_ids of all suppressed candidates."""
        return [
            c["action_id"]
            for c in candidates
            if c.get("suppressed", False)
        ]
