# ── Layer 2 · Pillar 2 — LinUCB Contextual Bandit (Phase 3) ───────────────
# LinUCB (Li et al. 2010 WWW) — needs 6 months of action_log with outcomes.
# Outputs: arm_weights, exploration_bonus (U_ucb).
# Cold-start rule: u_ucb = 0 when arm num_pulls == 0.
#
# Scoring contribution: β2 · U_ucb = β2 · (θ̂ᵀx + α·√(xᵀA⁻¹x))
#
# Reference: V2/src/bandit.py (already implements LinUCB — verify before reuse)
# ───────────────────────────────────────────────────────────────────────────


class LinUCBBandit:
    """LinUCB contextual bandit for action exploration/exploitation."""

    def check_data_prerequisites(self, merchant_id: str) -> bool:
        """Verify merchant has 6+ months of action_log with outcomes."""
        # TODO: Query action_log depth and outcome coverage
        pass

    def initialize_arms(self, action_space: list[str], context_dim: int) -> None:
        """Initialize bandit arms with identity matrices."""
        # TODO: Set A = I, b = 0 for each arm
        pass

    def select_arm(self, context: list[float], eligible_arms: list[str]) -> dict:
        """Select best arm using LinUCB formula: θ̂ᵀx + α·√(xᵀA⁻¹x)."""
        # TODO: Compute UCB for each eligible arm, return best
        # TODO: Return { arm: str, u_ucb: float, exploration_bonus: float }
        # TODO: Cold-start: return u_ucb = 0 if arm num_pulls == 0
        pass

    def update(self, arm: str, context: list[float], reward: float) -> None:
        """Update arm parameters with observed reward."""
        # TODO: A = A + xxᵀ, b = b + r·x
        pass
