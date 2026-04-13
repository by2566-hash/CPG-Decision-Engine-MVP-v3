# ADR-0004: Reject OPA Integration

## Status
Accepted
Date: 2026-04-09

## Context
The V3.5 architectural review cited OPA (Open Policy Agent) as an industry-standard policy
engine and suggested adopting its bundle management for merchant-specific, phase-specific,
and experiment-specific policy versioning. OPA uses a declarative DSL (Rego) for policy
authoring and supports HTTP-based policy evaluation, bundle distribution, and audit logging.

The argument for OPA: our CPG hard constraints (margin floor, inventory gate, etc.) are
rules that non-engineers (merchant success, compliance teams) might want to audit or modify.
A declarative DSL would make this possible without Python knowledge.

At the time of evaluation (Phase 1), V3 had:
- 6 CPG hard constraints, all in a single `ConstraintEngine` class (~300 lines)
- 4 approval gate rules (discount threshold, budget threshold)
- No non-engineer policy authoring requirement yet established
- A `PolicyDecision` Pydantic model already providing a clean interface

## Decision
Do not integrate OPA. Use `PolicyDecision` Pydantic model and Python-based policy
evaluation in `ConstraintEngine`. Reserve `policy_engine/` as a package name placeholder
in case OPA adoption is needed in future.

## Alternatives Considered

**Full OPA integration with Rego policies**: Migrate all 6 constraints and approval rules
to `.rego` files. Add OPA sidecar or embedded Go library. Connect via HTTP or WASM.
Rejected — approximately 3 weeks of integration and testing work for a problem that
5 config keys in `config.py` and a Pydantic model currently solve completely. The complexity
is not justified until non-engineer policy authoring is a confirmed requirement.

**Lightweight py-rego or similar Python Rego parser**: Avoid the Go/HTTP dependency, author
policies in Rego-like syntax but evaluate in Python. Rejected — adds contributor learning
curve without solving the core problem (policies are still code). Contributors already know
Python; a new DSL slows everyone down.

**Custom YAML rule interpreter**: Define a domain-specific YAML schema for policy rules and
write a Python interpreter. Rejected — this is reinventing OPA without OPA's ecosystem,
documentation, or tooling support. If we're going to invest in a rule DSL, OPA is the
standard choice.

## Consequences
### Positive
- No new external runtime dependency
- All policy logic remains in Python — contributors need only Python knowledge
- Fast iteration: adding a constraint is adding a method to `ConstraintEngine`
- `PolicyDecision` already provides the clean typed interface that OPA would have provided
  for downstream consumers

### Negative
- Policy rules encoded in Python rather than a declarative DSL
- Non-engineers (merchant success, compliance) cannot audit or modify policies without
  reading Python
- If policy complexity grows beyond ~20 rules per merchant, the Python approach becomes
  harder to manage than a rule engine

### Neutral
- `policy_engine/` directory name is reserved so future OPA adoption would not require
  a rename — migration path is preserved
- The decision to adopt `PolicyDecision` (ADR-0001) provides the same clean interface
  boundary that OPA would have provided, reducing the cost of future OPA adoption

## When to Revisit
Either of these conditions should trigger re-evaluation:
1. A non-engineer stakeholder (merchant success, legal, compliance) needs to author or
   audit constraint rules without engineer involvement
2. Policy complexity exceeds ~20 rules per merchant or requires dynamic per-merchant
   customization that Python config cannot express cleanly

## References
- ADR-0001 (PolicyDecision — provides OPA-equivalent interface boundary)
- V3/CLAUDE.md — L3.3 Policy Evaluation section (notes OPA decision explicitly)
- V3.5 proposal — "Policy Engine显式化" section
