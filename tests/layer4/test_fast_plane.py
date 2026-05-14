# ── Layer 4 · Fast Plane Tests ────────────────────────────────────────────
# Covers _emergency_reweight() — previously 0% coverage (S8-1).
# Tests deterministic reweighting logic only; does not require DB or Redis.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import pytest

from src.decision_engine.layer4_serving.fast_plane import FastPlane

# ── Fixture: instantiate without DB (reweight is pure computation) ────────────

@pytest.fixture
def plane():
    return FastPlane.__new__(FastPlane)


# ── Test data ─────────────────────────────────────────────────────────────────

_ACTIONS = [
    {
        "action_id": "A1",
        "u_base": 0.8,
        "u_ucb": 0.5,
        "risk_penalty": 0.2,
        "final_score": 0.70,
    },
    {
        "action_id": "A2",
        "u_base": 0.4,
        "u_ucb": 0.6,
        "risk_penalty": 0.1,
        "final_score": 0.50,
    },
]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestEmergencyReweight:
    def test_output_adds_emergency_score_and_original_score_fields(self, plane):
        result = plane._emergency_reweight(_ACTIONS, {})
        for entry in result:
            assert "emergency_score" in entry
            assert "original_score" in entry

    def test_zero_bias_preserves_relative_order(self, plane):
        """With no bias, A1 (higher u_base) should still outscore A2."""
        result = plane._emergency_reweight(_ACTIONS, {})
        assert result[0]["action_id"] == "A1"
        assert result[0]["emergency_score"] > result[1]["emergency_score"]

    def test_positive_margin_bias_increases_base_contribution(self, plane):
        """positive margin_bias amplifies u_base — A1's lead should widen."""
        result_no_bias = plane._emergency_reweight(_ACTIONS, {})
        result_with_bias = plane._emergency_reweight(_ACTIONS, {"margin_bias": 0.5})
        gap_no_bias = result_no_bias[0]["emergency_score"] - result_no_bias[1]["emergency_score"]
        gap_with_bias = result_with_bias[0]["emergency_score"] - result_with_bias[1]["emergency_score"]
        assert gap_with_bias > gap_no_bias

    def test_bias_clamped_to_unit_interval(self, plane):
        """margin_bias=999 must produce the same result as margin_bias=1.0."""
        result_extreme = plane._emergency_reweight(_ACTIONS, {"margin_bias": 999})
        result_clamped = plane._emergency_reweight(_ACTIONS, {"margin_bias": 1.0})
        assert result_extreme[0]["emergency_score"] == pytest.approx(
            result_clamped[0]["emergency_score"], abs=1e-9
        )
        assert result_extreme[1]["emergency_score"] == pytest.approx(
            result_clamped[1]["emergency_score"], abs=1e-9
        )

    def test_negative_bias_clamped_to_minus_one(self, plane):
        """risk_bias=-999 must produce the same result as risk_bias=-1.0."""
        result_extreme = plane._emergency_reweight(_ACTIONS, {"risk_bias": -999})
        result_clamped = plane._emergency_reweight(_ACTIONS, {"risk_bias": -1.0})
        assert result_extreme[0]["emergency_score"] == pytest.approx(
            result_clamped[0]["emergency_score"], abs=1e-9
        )

    def test_empty_actions_returns_empty_list(self, plane):
        assert plane._emergency_reweight([], {}) == []

    def test_single_action_returns_one_entry(self, plane):
        result = plane._emergency_reweight([_ACTIONS[0]], {"margin_bias": 0.3})
        assert len(result) == 1
        assert result[0]["action_id"] == "A1"
        assert "emergency_score" in result[0]

    def test_original_score_preserved_unchanged(self, plane):
        """original_score must equal the input final_score, not the reweighted score."""
        result = plane._emergency_reweight(_ACTIONS, {"margin_bias": 0.9})
        scores = {e["action_id"]: e for e in result}
        assert scores["A1"]["original_score"] == pytest.approx(0.70)
        assert scores["A2"]["original_score"] == pytest.approx(0.50)

    def test_missing_scoring_fields_default_to_zero(self, plane):
        """Actions without u_base/u_ucb/risk_penalty should not raise."""
        sparse_actions = [{"action_id": "sparse", "final_score": 0.3}]
        result = plane._emergency_reweight(sparse_actions, {"margin_bias": 0.5})
        assert len(result) == 1
        # u_base=0, u_ucb=0, risk=0 → emergency_score = 0
        assert result[0]["emergency_score"] == pytest.approx(0.0)

    def test_result_is_sorted_descending_by_emergency_score(self, plane):
        """Output must always be sorted highest emergency_score first."""
        result = plane._emergency_reweight(_ACTIONS, {"risk_bias": 1.0})
        scores = [e["emergency_score"] for e in result]
        assert scores == sorted(scores, reverse=True)
