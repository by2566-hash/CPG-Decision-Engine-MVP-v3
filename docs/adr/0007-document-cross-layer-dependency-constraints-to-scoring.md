# ADR-0007: Document Cross-Layer Dependency — Constraints to Scoring

## Status
Accepted (retroactive)
Date: 2026-04-09

## Context
`ConstraintEngine` lives in `layer3_value/constraints.py`. Its primary identity is
action safety enforcement — the CPG hard-gate layer (L3.3 Policy Evaluation in
the 6-layer architecture).

However, `layer2_decision/scoring.py` (L2) consumes `PolicyDecision.risk_penalty`
from `ConstraintEngine.check_all()` as the β3·Risk term in the LinUCB scoring
formula. Similarly, `layer2_decision/pillar3_llm/decision_verifier.py` imports
`_MARGIN_FLOOR` from `constraints.py` to avoid duplicating the constant.

Both are upward imports: a lower-numbered layer (L2) importing from a
higher-numbered layer (L3). This violates the general principle that data flows
downward (L0 → L1 → L2 → L3 → L4 → L5), established in CLAUDE.md.

The cross-layer dependency was flagged as a documented exception in
`test_architecture_invariants.py` (`_CROSS_LAYER_ALLOWLIST`) and referenced in
CLAUDE.md under "Cross-Layer Dependency Note", but was not backed by an ADR.
ADR-0001 (PolicyDecision unified interface) was incorrectly cited as the
governing decision for this dependency — ADR-0001 covers the return type
unification, not the cross-layer topology.

## Decision
Formally permit the two documented L2 → L3 upward imports as a named exception
to the downward-flow principle:

1. `layer2_decision/scoring.py` may import `_VIOLATION_WEIGHTS` from
   `layer3_value/constraints.py` to compute β3·Risk without re-invoking
   `ConstraintEngine`. It must NOT import `ConstraintEngine` itself.

2. `layer2_decision/pillar3_llm/decision_verifier.py` may import `_MARGIN_FLOOR`
   from `layer3_value/constraints.py` as the single source of truth for the
   margin floor threshold.

These two exceptions are explicitly enumerated in `_CROSS_LAYER_ALLOWLIST` in
`tests/architecture/test_architecture_invariants.py`. No other L2 → L3 import is
permitted without a new ADR.

## Alternatives Considered

**Move ConstraintEngine to L2**: ConstraintEngine's primary identity is the
safety gate (hard-reject logic, rollback, approval flags). That is inherently an
L3 concern — L3 is Decision Core, where policy evaluation happens. Moving it to
L2 would blur the boundary between world model (L2) and policy execution (L3).
Rejected.

**Duplicate risk logic in L2**: Create a copy of `_VIOLATION_WEIGHTS` in
`scoring.py`. Rejected — two constants that must stay in sync are a maintenance
hazard. One margin floor value changed in one place but not the other was exactly
the class of bug that ADR-0001 fixed.

**Introduce a shared "Contracts/Constants" layer between L2 and L3**: A new
virtual layer L2.5 for cross-cutting constants. Rejected as over-engineering for
two constants. When a third cross-layer dependency appears, this option should be
reconsidered.

## Consequences

### Positive
- `ConstraintEngine` retains its primary identity as the L3 safety gate
- `_MARGIN_FLOOR` and `_VIOLATION_WEIGHTS` remain single source of truth in
  `constraints.py`
- Cross-layer exceptions are explicitly enumerated and machine-verified in the
  architecture invariant test suite

### Negative
- The architecture has a documented exception to the downward-flow principle.
  New contributors must learn this exception.
- Any future L2 → L3 dependency will raise the architecture invariant test —
  the developer must either fix the import or write a new ADR

### Neutral
- The invariant test allowlist (`_CROSS_LAYER_ALLOWLIST`) is the machine-readable
  form of this decision

## When to Revisit
If a second L2 → L3 dependency is introduced (beyond scoring.py and
decision_verifier.py), revisit whether a Shared Constants layer is warranted.

## References
- `V3/src/decision_engine/layer3_value/constraints.py` — ConstraintEngine, _MARGIN_FLOOR, _VIOLATION_WEIGHTS
- `V3/src/decision_engine/layer2_decision/scoring.py` — β3·Risk consumption
- `V3/src/decision_engine/layer2_decision/pillar3_llm/decision_verifier.py` — _MARGIN_FLOOR import
- `V3/tests/architecture/test_architecture_invariants.py` — _CROSS_LAYER_ALLOWLIST
- `V3/CLAUDE.md` — Cross-Layer Dependency Note
- ADR-0001 (PolicyDecision unified interface — the return type decision, not the topology)
