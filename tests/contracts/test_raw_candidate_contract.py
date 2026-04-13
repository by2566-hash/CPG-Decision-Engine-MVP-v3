# ── Contract Tests — RawCandidate ────────────────────────────────────────────
# Enforces the invariants of L3.1 Candidate Proposal output.
# RawCandidate is the typed stage-boundary object between KG-driven candidate
# generation and the downstream pipeline (L3.2 Correlation, L3.3 Policy).
#
# Phase 2 Track B: RawCandidate will be wired into pipeline.py, replacing
# plain dicts. These tests establish the contract before that migration.
#
# Reference: V3/docs/PHASE_ROADMAP.md Phase 2 Track B
# ─────────────────────────────────────────────────────────────────────────────
import pytest
from pydantic import ValidationError

from src.decision_engine.contracts import PolicyDecision, RawCandidate


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rc(**kwargs) -> RawCandidate:
    """Return a valid RawCandidate with minimum required fields."""
    defaults = dict(action_id="DISCOUNT_10PCT", module="retention")
    defaults.update(kwargs)
    return RawCandidate(**defaults)


# ── Required fields ───────────────────────────────────────────────────────────

def test_raw_candidate_requires_action_id():
    """RawCandidate must require action_id — no default."""
    with pytest.raises((ValidationError, TypeError)):
        RawCandidate(module="retention")  # type: ignore[call-arg]


def test_raw_candidate_requires_module():
    """RawCandidate must require module — no default."""
    with pytest.raises((ValidationError, TypeError)):
        RawCandidate(action_id="DISCOUNT_10PCT")  # type: ignore[call-arg]


def test_raw_candidate_module_must_be_valid_literal():
    """module must be one of the 4 valid pipeline modules."""
    for module in ("retention", "acquisition", "conversion", "promotion"):
        rc = _rc(module=module)
        assert rc.module == module

    with pytest.raises(ValidationError):
        _rc(module="invalid_module")


# ── action_type field ─────────────────────────────────────────────────────────

def test_action_type_defaults_to_empty_string():
    """action_type must exist and default to empty string.

    action_type is the intent label (e.g. 'DISCOUNT', 'REMINDER') —
    distinct from action_id which is the specific instance.
    """
    rc = _rc()
    assert hasattr(rc, "action_type")
    assert isinstance(rc.action_type, str)
    assert rc.action_type == ""


def test_action_type_accepts_non_empty_string():
    """action_type must accept a non-empty string label."""
    rc = _rc(action_type="DISCOUNT")
    assert rc.action_type == "DISCOUNT"


# ── evidence_refs field ───────────────────────────────────────────────────────

def test_evidence_refs_defaults_to_empty_list():
    """evidence_refs must default to an empty list.

    evidence_refs holds KG evidence pointers — empty means no explicit
    evidence attached (valid for stub candidates in Phase 1).
    """
    rc = _rc()
    assert hasattr(rc, "evidence_refs")
    assert rc.evidence_refs == []


def test_evidence_refs_accepts_list_of_strings():
    """evidence_refs must accept a list of KG reference strings."""
    rc = _rc(evidence_refs=["kg://playbook/retention/discount", "kg://benchmark/cvr"])
    assert len(rc.evidence_refs) == 2


# ── Optional fields ───────────────────────────────────────────────────────────

def test_policy_decision_defaults_to_none():
    """policy_decision must default to None (set by L3.3 ConstraintEngine)."""
    rc = _rc()
    assert rc.policy_decision is None


def test_policy_decision_accepts_policy_decision_object():
    """policy_decision must accept a PolicyDecision instance."""
    pd = PolicyDecision(eligible=True)
    rc = _rc(policy_decision=pd)
    assert rc.policy_decision is pd
    assert rc.policy_decision.eligible is True


def test_suppressed_defaults_to_false():
    """suppressed must default to False."""
    rc = _rc()
    assert rc.suppressed is False


def test_urgency_score_bounds():
    """urgency_score must be in [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        _rc(urgency_score=1.01)
    with pytest.raises(ValidationError):
        _rc(urgency_score=-0.01)
    assert _rc(urgency_score=0.0).urgency_score == 0.0
    assert _rc(urgency_score=1.0).urgency_score == 1.0


# ── Immutability ──────────────────────────────────────────────────────────────

def test_raw_candidate_is_frozen():
    """RawCandidate must be immutable (frozen=True).

    Stage boundaries should be explicit: if suppressed or policy_decision
    must be set post-creation, create a new RawCandidate with those fields
    rather than mutating an existing one. This is the Phase 2 Track B
    migration contract.

    If this test fails: either contracts.py regressed (restore frozen=True),
    or the Phase 2 pipeline wiring requires a documented design exception.
    """
    rc = _rc()
    with pytest.raises((ValidationError, TypeError)):
        rc.suppressed = True  # type: ignore[misc]


# ── Round-trip serialization ──────────────────────────────────────────────────

def test_raw_candidate_round_trip():
    """RawCandidate(**rc.model_dump()) must produce an equal object."""
    pd = PolicyDecision(eligible=False, hard_reject=True, risk_penalty=3.0,
                        violations=["margin_floor:0.10 < 0.15"])
    original = _rc(
        action_type="DISCOUNT",
        evidence_refs=["kg://playbook/retention"],
        urgency_score=0.8,
        action_family="DISCOUNT",
        suppressed=False,
        policy_decision=pd,
    )
    restored = RawCandidate(**original.model_dump())
    assert restored.action_id == original.action_id
    assert restored.module == original.module
    assert restored.action_type == original.action_type
    assert restored.evidence_refs == original.evidence_refs
    assert restored.urgency_score == original.urgency_score
    assert restored.policy_decision == original.policy_decision
