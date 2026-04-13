# ADR-0003: Defer L3 Physical Submodule Split to Phase 2 Track B

## Status
Accepted
Date: 2026-04-09

## Context
V3.5 design calls for L3 Decision Core to be split into 5 physical submodules, each with a
clearly bounded responsibility:

- `candidate_proposal/` — KG-driven raw candidate generation (L3.1)
- `correlation/` — cross-module conflict resolution (L3.2)
- `policy/` — constraint evaluation → PolicyDecision (L3.3)
- `scoring/` — LinUCB formula (L3.4)
- `verification/` — DecisionVerifier safety shell (L3.5)

Currently in V3, these responsibilities are scattered across two directories:
- `layer2_decision/` holds scoring, correlator, decision verifier, and playbook KG
- `layer3_value/` holds constraints, impact calculator, approval gate, and other value modules

The mismatch exists because V3 was built before the V3.5 sublayer model was defined. The
responsibilities are correctly implemented; only the physical boundary is wrong.

Executing the split now would require:
- Renaming 5+ modules
- Updating imports across ~40 source files and 10 test files
- Re-validating the 161-test baseline
- No change in runtime behavior

The benefit (clearer directory structure) is real but proportional to the volume of new
content being added. In Phase 1 with no new submodule content arriving, the split cost
exceeds the benefit.

## Decision
Do not physically split L3 in Phase 1. Document the 5-submodule responsibility map in
`CLAUDE.md` as the authoritative architectural reference. Execute the split as a dedicated
Phase 2 Track B task, timed to coincide with KG content translation (when new files are
actively being added to each submodule).

The conceptual boundary is enforced today through:
- `CLAUDE.md` L3 section documenting the 5-submodule model
- Typed contracts (`RawCandidate`, `PolicyDecision`, `ScoredCandidate`) that define stage
  boundaries even without physical directory separation

## Alternatives Considered

**Split now as part of V3.5 upgrade**: Execute the full directory rename and import migration
alongside the PolicyDecision unification. Rejected — the import migration alone touches every
test file. Combining it with a correctness fix risks obscuring regression from restructuring
noise. The correctness fix (ADR-0001) was higher priority.

**Never split, keep current structure permanently**: Accept the V3 directory layout as final.
Rejected — as KG content volume grows (partner YAML translation in Phase 2 Track B), the lack
of clear submodule boundaries will cause merge conflicts and onboarding confusion. The split
is deferred, not cancelled.

## Consequences
### Positive
- No test disruption in Phase 1
- Engineers have CLAUDE.md as clear conceptual reference without migration risk
- Split can be done cleanly in Phase 2 when new content is being actively added,
  making the value immediately visible

### Negative
- Mental model (V3.5 5-submodule L3) and physical code (two V3 directories) don't match
- New contributors may import from the wrong directory before reading CLAUDE.md
- `pipeline.py` contains the orchestration logic for all 5 submodules in a single 465-line
  file, which will grow harder to navigate before the split happens

### Neutral
- Deferred work is tracked in PHASE_ROADMAP.md Phase 2 Track B
- The LLM Renderer migration (also Phase 2 Track B) should be executed in the same PR as
  this split, to avoid partial restructuring

## When to Revisit
When Phase 2 Track B begins. The trigger should be the first PR adding new KG content to
`playbook_registry.py` — at that point, the submodule boundaries provide immediate value.

## References
- ADR-0002 (incremental upgrade decision)
- V3/CLAUDE.md — L3 Decision Core section
- V3/docs/PHASE_ROADMAP.md — Phase 2 Track B
