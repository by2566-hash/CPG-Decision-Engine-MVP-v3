# ── Layer 4 Tests · Rollout Manager ──────────────────────────────────────
# Tests for shadow mode, kill-switch, and rollout state management.
# ───────────────────────────────────────────────────────────────────────────


class TestRolloutManager:
    """Tests for RolloutManager — shadow mode and kill-switch."""

    def test_default_shadow_mode(self):
        """New features should default to shadow mode."""
        # TODO: Implement test
        pass

    def test_kill_switch_blocks_serving(self):
        """Kill-switched features must not be served to merchants."""
        # TODO: Implement test
        pass

    def test_rollout_state_transitions(self):
        """Valid transitions: shadow → canary → live, any → killed."""
        # TODO: Implement test
        pass
