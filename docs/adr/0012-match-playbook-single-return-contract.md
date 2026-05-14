# ADR-0012: match_playbook() Returns dict | None (Single-Pattern Routing Contract)

## Status
Accepted
Date: 2026-04-13

## Context

Step 0 pre-flight (2026-04-13) for CB-A/CB-B KG intake revealed that
`match_playbook()` is a **pattern routing decision**, not a multi-candidate
ranker. Two options were evaluated:

- **Option 1** (6–8 lines): add `merchant_id` parameter, keep `dict | None`
  return type. Selection among multiple brand-bound patterns uses deterministic
  alphabetical order by `playbook_id`.
- **Option 2** (40–50 lines): change return type to `list[dict]`, let scoring
  layer rank all simultaneously-firing patterns.

Option 2 is architecturally more complete (scoring layer is already built for
multi-candidate ranking). However, it imposes a 40–50-line refactor across the
core pipeline path during demo preparation, with regression risk to WB's 6
existing use cases.

The key insight driving this decision: `match_playbook()` is the **pattern
routing** layer, not the **action ranking** layer. Scoring's job is to rank
actions *within* an activated pattern (across `action_ids`). Deciding *which
pattern activates* is routing. These are categorically different concerns.

Option 2 only becomes necessary if the mutual-exclusivity premise below is
violated. Premature escalation to Option 2 would be speculative complexity.

## Decision

**`match_playbook()` returns `dict | None` (Option 1).**

This contract is valid under the following **premise**:

> Brand-bound patterns within the same module have mutually exclusive trigger
> conditions. For any real merchant signal configuration, at most one
> brand-bound pattern per module will have all its trigger conditions satisfied.

When `merchant_id` is provided and multiple brand-bound meta-patterns are
candidates, selection uses **deterministic alphabetical order by `playbook_id`**.
This is a tiebreak rule for the mutual-exclusivity guarantee, not a ranking
function — if the premise holds, only one will ever match in practice.

## Consequences

**Positive:**
- No regression risk to the existing pipeline (2 callers, both unchanged in
  return-type handling).
- Pattern routing stays in the routing layer; action ranking stays in scoring.
- Architecture invariant test locks the `dict | None` contract machine-checkably.

**Negative:**
- If two brand-bound patterns for the same module have overlapping trigger
  conditions, the alphabetical-first one silently wins. This is a silent failure
  mode if the mutual-exclusivity premise is not enforced at YAML authoring time.
- Per-pattern authoring discipline is required: SOP Section 5 (threshold
  governance) must be extended to include a mutual-exclusivity check for same-
  module patterns at brand binding time.

## Escalation Condition

This decision is **explicitly reversible**. The condition that triggers
escalation to Option 2 is:

```
(same module) AND (trigger conditions are NOT mutually exclusive)
```

That is: two brand-bound patterns in the same module where a real signal
configuration exists that satisfies both patterns' trigger conditions
simultaneously.

If this condition is found during Step 1 Triage (mutual exclusivity check), or
at any future KG intake:

1. Stop. Do not write YAML.
2. Change `match_playbook()` return type to `list[dict]`.
3. Update `pipeline._generate_candidates()` to iterate over list (≈15 lines).
4. Update `scripts/kg_dryrun.py` caller (≈5 lines).
5. Write ADR superseding this one.
6. Update the architecture invariant test (Test 10 in
   `tests/architecture/test_architecture_invariants.py`) to assert `list[dict]`.

Total expected LOC for Option 2 escalation: 40–50 lines + test updates.

## Alternatives Considered

**Option 2 (immediate)**: Rejected for Phase 1 because the mutual-exclusivity
premise has not been violated yet. Changing the core pipeline return type
without a confirmed need is speculative complexity. The premise will be checked
at every future intake (Step 1 Triage mutual exclusivity check).

**Priority-field in YAML**: Rejected. Introducing a `priority:` field on
meta-patterns moves ranking logic into YAML content authored by partners.
Partners should not own architectural tie-breaking decisions.

## MSM-State Separation Corollary

*(Added 2026-04-13, Step 1 Triage finding for CB-A/CB-B intake)*

The mutual-exclusivity argument via MSM state is **architecturally stronger** than
trigger-condition-level analysis, because it relies on a system invariant rather
than on partner trigger-writing discipline.

**Corollary:** MSM-state separation is a *sufficient* condition for Option 1 correctness.

If two brand-bound patterns in the same module target **different MSM states** (e.g.
one fires on WATCH, the other on DEGRADING), they are guaranteed to be mutually
exclusive at runtime — regardless of trigger condition specificity — because:

- MSM state is a mutually exclusive enum per dimension per merchant per timestamp.
  A merchant's acquisition dimension cannot simultaneously be WATCH and DEGRADING.
- `match_playbook()` evaluates `pattern["msm_state"]` against `trigger.msm_state`.
  A pattern targeting WATCH will never match when the dimension is DEGRADING.

**Practical consequence:** Future mutual exclusivity checks in Step 1 Triage are reduced
to a **two-step table lookup**, not full trigger semantic analysis:

1. Do any two new patterns share the same module? → If no, trivially exclusive.
2. Do they target the same MSM state? → If no, guaranteed exclusive by invariant. Done.

Only if the answer to BOTH is yes does the check escalate to trigger-condition
semantic analysis (and potentially to Option 2 escalation).

This was confirmed empirically during CB-A/CB-B intake:
- `cba_001` (acquisition / DEGRADING) and `cbb_001` (acquisition / WATCH) share the
  acquisition module but target different MSM states → guaranteed mutually exclusive
  by this corollary. No trigger analysis required.

## References

- Step 0 pre-flight findings: 2 call sites, neither uses *args/**kwargs
- `match_playbook()` source: `src/decision_engine/layer2_decision/pillar1_kg/playbook_registry.py`
- Architecture invariant: `tests/architecture/test_architecture_invariants.py` Test 10
- Related: ADR-0011 (Three-Layer KG Playbook Structure)
- Related: ADR-0001 (PolicyDecision — scoring consumes ranked actions, not pattern selections)
