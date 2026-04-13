# ── Contract Tests — PolicyDecision ──────────────────────────────────────────
# Enforces the invariants of ADR-0001: PolicyDecision as the unified interface
# for L3.3 Policy Evaluation. These tests are the architecture's constitution
# for this object — any change to PolicyDecision that causes these tests to fail
# must be accompanied by a new ADR superseding ADR-0001.
#
# Reference: V3/docs/adr/0001-adopt-policy-decision-unified-interface.md
# ─────────────────────────────────────────────────────────────────────────────
import pytest
from pydantic import ValidationError

from src.decision_engine.contracts import PolicyDecision


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pd_pass(**kwargs) -> PolicyDecision:
    """Return a valid passing PolicyDecision with sensible defaults."""
    defaults = dict(eligible=True, violations=[], risk_penalty=0.0)
    defaults.update(kwargs)
    return PolicyDecision(**defaults)


def _pd_fail(**kwargs) -> PolicyDecision:
    """Return a valid failing PolicyDecision with sensible defaults."""
    defaults = dict(eligible=False, hard_reject=True, risk_penalty=3.0,
                    violations=["margin_floor:0.10 < 0.15"])
    defaults.update(kwargs)
    return PolicyDecision(**defaults)


# ── Immutability ───────────────────────────────────────────────────────────────

def test_policy_decision_is_frozen():
    """PolicyDecision must be immutable (frozen=True).

    Enforces: ADR-0001 (PolicyDecision unified interface).

    If this test fails: either contracts.py regressed (re-add frozen=True to
    PolicyDecision.model_config), or the decision is being intentionally
    reversed (write a new ADR superseding ADR-0001 and update this test).
    """
    pd = _pd_pass()
    with pytest.raises((ValidationError, TypeError)):
        pd.eligible = False  # type: ignore[misc]


# ── Required fields ────────────────────────────────────────────────────────────

def test_policy_decision_requires_eligible():
    """PolicyDecision must require eligible — no default value.

    Enforces: ADR-0001.

    If this test fails: eligible has been given a default, making it possible
    to create a PolicyDecision with unknown constraint status.
    """
    with pytest.raises((ValidationError, TypeError)):
        PolicyDecision()  # type: ignore[call-arg]


# ── Semantic consistency validators ───────────────────────────────────────────

def test_eligible_true_requires_empty_violations():
    """eligible=True must be inconsistent with non-empty violations.

    Enforces: ADR-0001 — a passing policy decision cannot have violations.
    If this test fails: the model_validator in PolicyDecision was removed.
    Fix: restore the _validate_eligibility_consistency validator.
    """
    with pytest.raises(ValidationError) as exc_info:
        PolicyDecision(eligible=True, violations=["margin_floor:0.10 < 0.15"])
    assert "violations" in str(exc_info.value).lower() or "eligible" in str(exc_info.value).lower()


def test_hard_reject_true_requires_eligible_false():
    """hard_reject=True must be inconsistent with eligible=True.

    Enforces: ADR-0001 — hard_reject is a semantic alias for 'not eligible'.
    If this test fails: the model_validator in PolicyDecision was removed.
    Fix: restore the _validate_eligibility_consistency validator.
    """
    with pytest.raises(ValidationError):
        PolicyDecision(eligible=True, hard_reject=True)


def test_eligible_false_allows_violations():
    """eligible=False with violations must be accepted — normal constraint failure."""
    pd = _pd_fail()
    assert pd.eligible is False
    assert len(pd.violations) > 0


def test_hard_reject_false_with_eligible_true():
    """eligible=True, hard_reject=False (default) must be accepted."""
    pd = _pd_pass()
    assert pd.eligible is True
    assert pd.hard_reject is False


# ── Field constraints ─────────────────────────────────────────────────────────

def test_risk_penalty_must_be_non_negative():
    """risk_penalty must be >= 0.0.

    Enforces: ADR-0001 — risk_penalty feeds β3·Risk in scoring formula.
    Negative penalty would invert the risk direction.
    If this test fails: remove the ge=0.0 Field constraint from risk_penalty.
    """
    with pytest.raises(ValidationError):
        PolicyDecision(eligible=True, risk_penalty=-0.1)


def test_risk_penalty_zero_accepted():
    """risk_penalty=0.0 is the normal passing state."""
    pd = _pd_pass(risk_penalty=0.0)
    assert pd.risk_penalty == 0.0


def test_risk_penalty_large_value_accepted():
    """risk_penalty of any positive value is accepted."""
    pd = _pd_fail(risk_penalty=99.9)
    assert pd.risk_penalty == 99.9


# ── Field types ───────────────────────────────────────────────────────────────

def test_policy_version_field_is_string():
    """policy_version must exist and be a string (possibly empty).

    Enforces: ADR-0001 — policy_version is required for auditability.
    If this test fails: policy_version was removed or renamed.
    """
    pd = _pd_pass()
    assert isinstance(pd.policy_version, str)

    pd_versioned = _pd_pass(policy_version="v2.3.1-cpg")
    assert pd_versioned.policy_version == "v2.3.1-cpg"


# ── Round-trip serialization ──────────────────────────────────────────────────

def test_policy_decision_round_trip_passing():
    """PolicyDecision(**pd.model_dump()) must produce an equal object (passing case).

    Enforces: ADR-0001 — serialization stability is required for WSM logging.
    """
    original = _pd_pass(policy_version="v1.0")
    restored = PolicyDecision(**original.model_dump())
    assert restored == original


def test_policy_decision_round_trip_failing():
    """Round-trip must work for failing PolicyDecision (with violations)."""
    original = _pd_fail(policy_version="v1.0")
    restored = PolicyDecision(**original.model_dump())
    assert restored == original
    assert restored.violations == original.violations
    assert restored.risk_penalty == original.risk_penalty
