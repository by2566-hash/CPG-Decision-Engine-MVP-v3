# ── Contract Tests — ScoredCandidate ─────────────────────────────────────────
# Enforces the invariants of L3.4 Scoring & Ranking output.
# ScoredCandidate is the typed boundary object between the scoring engine
# and L3.5 Verification / L4 Delivery Plane.
#
# Phase 2 Track B: ScoredCandidate will be returned by ScoringEngine.rank_actions()
# replacing plain dicts. These tests establish the contract before that migration.
#
# Reference: V3/docs/PHASE_ROADMAP.md Phase 2 Track B
# ─────────────────────────────────────────────────────────────────────────────
import math

import pytest
from pydantic import ValidationError

from src.decision_engine.contracts import ScoredCandidate


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sc(**kwargs) -> ScoredCandidate:
    """Return a valid ScoredCandidate with minimum required fields."""
    defaults = dict(action_id="DISCOUNT_10PCT")
    defaults.update(kwargs)
    return ScoredCandidate(**defaults)


# ── Required fields ───────────────────────────────────────────────────────────

def test_scored_candidate_requires_action_id():
    """ScoredCandidate must require action_id — no default."""
    with pytest.raises((ValidationError, TypeError)):
        ScoredCandidate()  # type: ignore[call-arg]


def test_scored_candidate_accepts_all_fields():
    """ScoredCandidate must accept all defined fields."""
    sc = ScoredCandidate(
        action_id="DISCOUNT_10PCT",
        module="retention",
        msm_dimension="retention",
        eligible=True,
        final_score=0.72,
        u_base=0.65,
        u_ucb=0.10,
        risk_penalty=0.03,
        violations=[],
        urgency_score=0.8,
        rank=1,
        beta_snapshot={"beta1": 0.6, "beta2": 0.1, "beta3": 0.3},
    )
    assert sc.action_id == "DISCOUNT_10PCT"
    assert sc.final_score == 0.72
    assert sc.rank == 1


# ── final_score: accepts -inf ─────────────────────────────────────────────────

def test_final_score_accepts_negative_infinity():
    """final_score must accept -inf (hard-rejected candidates).

    Enforces: hard-blocked candidates get final_score=-inf, not an error.
    The scoring engine uses -inf as the sentinel for constraint-blocked actions.
    If this test fails: a ge constraint was added to final_score — remove it.
    """
    sc = _sc(final_score=float("-inf"), eligible=False)
    assert math.isinf(sc.final_score)
    assert sc.final_score < 0


def test_final_score_accepts_positive_infinity():
    """final_score accepts +inf (edge case in testing)."""
    sc = _sc(final_score=float("inf"))
    assert math.isinf(sc.final_score)
    assert sc.final_score > 0


def test_final_score_accepts_zero_and_positive():
    """final_score accepts 0.0 and positive floats."""
    assert _sc(final_score=0.0).final_score == 0.0
    assert _sc(final_score=0.72).final_score == 0.72


def test_final_score_accepts_negative_floats():
    """final_score accepts negative floats (risk-penalized but not hard-blocked)."""
    sc = _sc(final_score=-0.5)
    assert sc.final_score == -0.5


# ── rank field ────────────────────────────────────────────────────────────────

def test_rank_is_positive_integer():
    """rank must be a positive integer (>= 1).

    Enforces: rank is 1-based. rank=1 is the top-scored candidate.
    rank=0 or negative has no meaning in the scoring context.
    If this test fails: the ge=1 constraint was removed from rank field.
    """
    with pytest.raises(ValidationError):
        _sc(rank=0)

    with pytest.raises(ValidationError):
        _sc(rank=-1)


def test_rank_accepts_positive_integers():
    """rank must accept 1, 2, 3 (valid ranking positions)."""
    assert _sc(rank=1).rank == 1
    assert _sc(rank=2).rank == 2
    assert _sc(rank=10).rank == 10


def test_rank_defaults_to_1():
    """rank must default to 1."""
    sc = _sc()
    assert sc.rank == 1


# ── beta_snapshot field ───────────────────────────────────────────────────────

def test_beta_snapshot_defaults_to_empty_dict():
    """beta_snapshot must default to an empty dict."""
    sc = _sc()
    assert sc.beta_snapshot == {}


def test_beta_snapshot_accepts_string_keys_float_values():
    """beta_snapshot must accept a dict with string keys and float values.

    beta_snapshot captures the β weights used at scoring time for auditability.
    Expected shape: {"beta1": 0.6, "beta2": 0.1, "beta3": 0.3}
    """
    snapshot = {"beta1": 0.6, "beta2": 0.1, "beta3": 0.3}
    sc = _sc(beta_snapshot=snapshot)
    assert sc.beta_snapshot["beta1"] == 0.6
    assert sc.beta_snapshot["beta3"] == 0.3


# ── urgency_score bounds ──────────────────────────────────────────────────────

def test_urgency_score_bounds():
    """urgency_score must be in [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        _sc(urgency_score=1.01)
    with pytest.raises(ValidationError):
        _sc(urgency_score=-0.01)
    assert _sc(urgency_score=0.0).urgency_score == 0.0
    assert _sc(urgency_score=1.0).urgency_score == 1.0


# ── Immutability ──────────────────────────────────────────────────────────────

def test_scored_candidate_is_frozen():
    """ScoredCandidate must be immutable (frozen=True).

    ScoredCandidate is a point-in-time scoring result. Downstream stages
    (L3.5 Verification, L4 Delivery) must not modify it — they consume it.
    If this test fails: restore frozen=True to ScoredCandidate.model_config.
    """
    sc = _sc()
    with pytest.raises((ValidationError, TypeError)):
        sc.final_score = 0.99  # type: ignore[misc]


# ── Round-trip serialization ──────────────────────────────────────────────────

def test_scored_candidate_round_trip():
    """ScoredCandidate(**sc.model_dump()) must produce an equal object."""
    original = ScoredCandidate(
        action_id="DISCOUNT_10PCT",
        module="retention",
        eligible=True,
        final_score=0.72,
        u_base=0.65,
        u_ucb=0.10,
        risk_penalty=0.03,
        violations=[],
        urgency_score=0.8,
        rank=1,
        beta_snapshot={"beta1": 0.6, "beta2": 0.1, "beta3": 0.3},
    )
    restored = ScoredCandidate(**original.model_dump())
    assert restored == original


def test_scored_candidate_round_trip_with_neg_inf():
    """Round-trip must preserve -inf final_score for hard-rejected candidates."""
    original = _sc(final_score=float("-inf"), eligible=False, rank=5)
    restored = ScoredCandidate(**original.model_dump())
    assert math.isinf(restored.final_score)
    assert restored.final_score < 0
    assert restored.eligible is False
