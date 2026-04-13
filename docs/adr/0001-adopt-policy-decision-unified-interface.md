# ADR-0001: Adopt PolicyDecision Unified Interface

## Status
Accepted
Date: 2026-04-09

## Context
V3's `ConstraintEngine.check_all()` originally returned `(bool, list[str])`.
Risk scoring was a separate `compute_risk_score()` returning `float`. `ApprovalCheckResult`
was a third Pydantic model. Three interfaces described the same logical concept (policy
evaluation output), causing two concrete problems:

1. `scoring.py` called `ConstraintEngine` twice per candidate — once to get the gate result,
   once to get the risk float — meaning constraints were evaluated twice per scoring cycle.
2. Violation semantics were inconsistent: `check_all()` returned a count, `compute_risk_score()`
   returned `float(len(violations))`, treating all violation types as equivalent. A `margin_floor`
   violation (financial risk) had the same weight as a `cold_prospect_gate` violation (targeting
   process). This made the β3·Risk term inaccurate.

The `_VIOLATION_WEIGHTS` dict was introduced to fix the weighting problem, but could not be
applied without a unified return type.

## Decision
Unify into a single `PolicyDecision` Pydantic model returned by `ConstraintEngine.check_all()`.

Concrete changes:
- `check_all(candidate, signals, policy) -> PolicyDecision` (was `-> tuple[bool, list[str]]`)
- `PolicyDecision` fields: `eligible`, `hard_reject`, `risk_penalty` (weighted sum), `violations`,
  `requires_approval`, `rollback_required`, `policy_version`
- `_VIOLATION_WEIGHTS` applied inside `check_all()`: margin_floor=3.0, inventory_gate=2.5,
  incrementality=2.0, discount_last_resort=1.5, cold_prospect_gate=1.5, default=1.0
- `scoring.py` reads `constraints_result` once and uses `pd.risk_penalty` directly
- Legacy tuple bridge in `scoring.py` allows test mocks injecting `(bool, list[str])` to continue working

## Alternatives Considered

**Introduce OPA as external policy engine**: OPA (Open Policy Agent) would provide a declarative
DSL and bundle management for merchant-specific policies. Rejected — ~3 weeks of integration work
for a problem that 5 config keys in a Pydantic model currently solve. See ADR-0004.

**Keep three separate interfaces, document the contract**: Would avoid migration but leaves the
duplicate `ConstraintEngine` call in `scoring.py` unfixed. The double-evaluation is a real
correctness issue (signals could be mutated between calls, and the two evaluations could diverge),
not a cosmetic one. Rejected.

**`PolicyDecision` as a dataclass instead of Pydantic**: Simpler but loses validation for free.
Pydantic is already the project standard. Rejected for consistency.

## Consequences
### Positive
- Eliminates duplicate `ConstraintEngine` call in `scoring.py`
- Weighted `risk_penalty` makes β3·Risk semantically accurate (financial violations penalise more
  than process violations)
- Single typed audit record for all policy decisions — useful for WSM logging in Phase 2+
- `requires_approval` and `rollback_required` fields enable future MerchantApprovalGate integration
  at the PolicyDecision level

### Negative
- One-time migration of all call sites (completed in the same session)
- Test mocks injecting `(bool, list[str])` tuples required a legacy bridge in `scoring.py` —
  adds a conditional branch that should be removed when all tests migrate

### Neutral
- `policy_version` field is currently empty string — reserved for Phase 2/3 merchant-specific
  policy bundle versioning
- `requires_approval` is always `False` from `ConstraintEngine` — `MerchantApprovalGate` sets
  this separately, intentional separation of concerns

## When to Revisit
If we need merchant-specific or experiment-specific policy versioning that a single Pydantic
model cannot express — at that point, evaluate OPA bundle management (ADR-0004 revisit).

## References
- V3/CLAUDE.md — L3.3 Policy Evaluation section
- V3/src/decision_engine/layer3_value/constraints.py
- V3/src/decision_engine/layer2_decision/scoring.py
- ADR-0004 (OPA rejection)
