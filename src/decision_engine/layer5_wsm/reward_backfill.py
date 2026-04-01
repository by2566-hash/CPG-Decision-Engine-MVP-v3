# ── Layer 5 · World State Model — Reward Backfill ────────────────────────
# Backfills rewards into WSM: 24h (proxy) and 7d (final) after execution.
# Feeds LinUCB Bandit training data (Phase 3).
#
# Reference: V2/src/reward_backfill.py (already in place — preserve)
# ───────────────────────────────────────────────────────────────────────────


class RewardBackfill:
    """Backfills proxy and final rewards into WSM transitions."""

    async def backfill_proxy_rewards(self) -> int:
        """Backfill 24h proxy rewards for recently executed actions. Returns count."""
        # TODO: Find transitions where executed_at + 24h < now and reward_status == 'pending'
        # TODO: Compute proxy reward from short-term metrics
        # TODO: Update reward_status to 'proxy'
        pass

    async def backfill_final_rewards(self) -> int:
        """Backfill 7d final rewards for actions with proxy rewards. Returns count."""
        # TODO: Find transitions where executed_at + 7d < now and reward_status == 'proxy'
        # TODO: Compute final reward from outcome_delta vs baseline_snapshot
        # TODO: Update reward_status to 'final'
        pass

    def compute_reward(self, baseline: dict, outcome: dict) -> float:
        """Compute reward signal from baseline vs outcome comparison."""
        # TODO: Normalize outcome_delta relative to baseline_snapshot
        pass
