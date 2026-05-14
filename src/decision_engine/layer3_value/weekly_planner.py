# ── Layer 3 · Value Intelligence — Weekly Planner ─────────────────────────
# Top 3 actions ranked by $ impact with conflict detection.
# Runs in Deep Plane (Layer 4) on weekly cadence.
#
# Ranking:
#   primary   = impact_estimate.expected DESC
#   secondary = urgency_score DESC (tiebreaker)
#
# Conflict detection: flag if two top actions target same product/segment.
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class WeeklyPlanner:
    """Generates weekly top-3 action plan ranked by estimated dollar impact."""

    def plan(self, decision_cards: list[dict]) -> dict:
        """Take all triggered Decision Cards (cross-module) and produce weekly plan.

        Returns:
        {
          "top_3_actions": list[dict],        # ranked by impact_estimate.expected
          "conflict_detected": bool,
          "conflict_description": str | None,
          "weekly_narrative": str             # "This week, focus on: ..."
        }

        Ranking: primary = impact_estimate.expected DESC
                 secondary = urgency_score DESC (tiebreaker)
        Conflict detection: flag if two top actions target same product/segment
        """
        if not decision_cards:
            return {
                "top_3_actions": [],
                "conflict_detected": False,
                "conflict_description": None,
                "weekly_narrative": "No actions triggered this week.",
            }

        # Sort: primary = impact_estimate.expected DESC, secondary = urgency_score DESC
        ranked = sorted(
            decision_cards,
            key=lambda c: (
                self._get_expected_impact(c),
                c.get("urgency_score", 0.0),
            ),
            reverse=True,
        )

        top_3 = ranked[:3]

        # Conflict detection: two top actions target same product or segment
        conflict_detected, conflict_description = self._detect_conflicts(top_3)

        # Build weekly narrative
        action_names = [c.get("action_id", "unknown") for c in top_3]
        modules = list({c.get("module", "unknown") for c in top_3})
        narrative = (
            f"This week, focus on: {', '.join(action_names)}. "
            f"Modules: {', '.join(modules)}."
        )
        if conflict_detected:
            narrative += f" Note: {conflict_description}"

        return {
            "top_3_actions": top_3,
            "conflict_detected": conflict_detected,
            "conflict_description": conflict_description,
            "weekly_narrative": narrative,
        }

    def _get_expected_impact(self, card: dict) -> float:
        """Extract expected dollar impact from a decision card."""
        ie = card.get("impact_estimate")
        if ie is None:
            return 0.0
        if isinstance(ie, dict):
            return ie.get("expected", 0.0)
        # ImpactEstimate model
        return getattr(ie, "expected", 0.0)

    def _detect_conflicts(self, top_actions: list[dict]) -> tuple[bool, str | None]:
        """Flag if two top actions target the same product or segment.

        NOTE (Phase 1): 'target_product' and 'target_segment' are not populated
        by the current pipeline candidate generation — this method always returns
        (False, None). Conflict detection will become active when candidate field
        expansion is implemented in Phase 2 (see FIX-17 / S-NEW-4).
        """
        seen_targets: dict[str, str] = {}

        for card in top_actions:
            target = card.get("target_product") or card.get("target_segment")
            if target is None:
                continue

            action_id = card.get("action_id", "unknown")
            if target in seen_targets:
                conflict_desc = (
                    f"Actions '{seen_targets[target]}' and '{action_id}' "
                    f"both target '{target}'"
                )
                return True, conflict_desc

            seen_targets[target] = action_id

        return False, None
