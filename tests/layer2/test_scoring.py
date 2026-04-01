# ── Layer 2 Tests · Scoring Engine ────────────────────────────────────────
# Tests for the β-weighted scoring formula.
# Score = β1·U_base(KG) + β2·U_ucb(Bandit) − β3·Risk(Constraints)
# ───────────────────────────────────────────────────────────────────────────


class TestScoringEngine:
    """Tests for ScoringEngine formula and ranking."""

    def test_phase1_scoring_no_bandit(self):
        """Phase 1: u_ucb must be 0, score = β1·U_base − β3·Risk."""
        # TODO: Verify bandit component is zero in Phase 1
        pass

    def test_score_decomposition(self):
        """Score breakdown should show all components for explainability."""
        # TODO: Verify get_score_breakdown returns all components
        pass

    def test_ranking_order(self):
        """Actions should be ranked descending by total score."""
        # TODO: Verify rank_actions returns sorted list
        pass

    def test_policy_weights_applied(self):
        """β weights from Policy Pack should be correctly applied."""
        # TODO: Verify different weights produce different scores
        pass
