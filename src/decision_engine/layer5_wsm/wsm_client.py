# ── Layer 5 · World State Model — WSM Client ─────────────────────────────
# S/A/R/S' transition logging — every decision is logged from Day 1.
# Active in shadow mode: was_executed=false, baseline_snapshot accumulating.
#
# Critical V3 schema fields (must exist Day 1):
#   was_executed, executed_at, execution_params, baseline_snapshot,
#   outcome_delta, verification_chain, impact_estimate, counterfactual,
#   reward_status (pending→proxy→final), planner_policy_version
#
# Reference: V2/src/wsm_transition_v2 (add new fields — verify before reuse)
# ───────────────────────────────────────────────────────────────────────────


class WSMClient:
    """Reads and writes World State Model transition records."""

    async def log_transition(self, transition: dict) -> str:
        """Log a S/A/R/S' transition. Returns transition_id."""
        # TODO: Write transition with all V3 schema fields
        # TODO: Day 1: was_executed=false, baseline_snapshot populated
        pass

    async def get_transitions(self, merchant_id: str, since: str | None = None) -> list[dict]:
        """Query WSM transitions for a merchant."""
        # TODO: Read from DB with optional time filter
        pass

    async def update_outcome(self, transition_id: str, outcome_delta: dict) -> None:
        """Backfill outcome_delta after action execution."""
        # TODO: Update transition with observed outcome
        pass

    async def update_reward_status(self, transition_id: str, status: str, reward: float | None = None) -> None:
        """Update reward status: pending → proxy (24h) → final (7d)."""
        # TODO: Update reward_status field
        pass
