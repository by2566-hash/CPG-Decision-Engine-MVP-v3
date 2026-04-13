# ADR-0002: Incremental V3.5 Upgrade Instead of Full Refactor

## Status
Accepted
Date: 2026-04-09

## Context
V3.5 as proposed by an external architecture review called for a full six-layer physical
restructure: new `l3_decision/` directory with 5 submodules, new `feature_plane/` module,
renaming `layer2_decision/` to `l2_world_model/`, moving `llm_renderer.py` and
`llm_safety_gateway.py` to a new `l4_delivery/` package, and splitting `layer5_wsm/` into
4 tables and modules.

At the time of the review, V3 had:
- 161 passing tests across 10 test files
- Significant implementation investment in `pipeline.py` (16-step orchestrator), `scoring.py`
  (LinUCB formula), `constraints.py` (6 CPG hard constraints), and the full verification chain
- A known funding demo scheduled with first potential customers

A full physical refactor would have required:
1. Rewriting import paths across all 40+ source files and 10 test files
2. Rebuilding the 161-test baseline
3. Introducing regression risk at a critical commercial moment

The V3.5 review also identified three genuine correctness issues worth fixing immediately:
`PolicyDecision` unification (ADR-0001), 6 hardcoded MSM literals (moved to config.py), and
the `/approve` ownership security gap (BUG 1) and rollback race condition (BUG 2).

## Decision
Adopt V3.5 as a **concept and contract upgrade**, not a physical directory restructure.

Concretely:
- V3.5 layer names and sublayer responsibilities documented in `CLAUDE.md` as authoritative
  architecture reference
- New typed objects (`PolicyDecision`, `DecisionState`, `DecisionFeatureVector`, `RawCandidate`,
  `ScoredCandidate`) added to `contracts.py` — the conceptual boundary exists in types, not dirs
- The three real correctness issues fixed immediately (PolicyDecision, config literals, security)
- All existing directories remain in place
- Physical L3 split deferred to Phase 2 Track B (ADR-0003)
- LLM Renderer migration deferred to Phase 2 Track B

## Alternatives Considered

**Full refactor into new directory structure**: Rename all packages, migrate all imports, rebuild
test coverage from scratch. Rejected — 161 tests represent proven working behavior that should
not be discarded before a funding demo. The physical structure mismatch is a documentation and
onboarding problem, not a runtime correctness problem.

**Create parallel `v3_5/` directory, archive `old/v3/`**: Would allow V3.5 to start clean while
keeping V3 running. Rejected — running two parallel implementations doubles maintenance burden
and defers rather than resolves the integration question.

**Do nothing (keep V3 as-is)**: Reject all V3.5 suggestions. Rejected — `PolicyDecision` unification
was a real correctness issue (duplicate constraint evaluation per scoring cycle), not cosmetic.
The three security/correctness fixes were P0.

## Consequences
### Positive
- All 161 tests remain valid with no regression risk
- Immediate value from the three correctness/security fixes
- `CLAUDE.md` provides clear forward architectural direction for all contributors
- Typed contracts in `contracts.py` establish phase boundaries even before physical restructure

### Negative
- Code directory structure does not visually match V3.5 architecture diagram
- New contributors must read `CLAUDE.md` to understand the conceptual mapping
  (e.g. "L3 Decision Core lives in both `layer2_decision/` and `layer3_value/`")
- Physical restructure not avoided, only deferred — accumulated deferred work creates
  a larger Phase 2 Track B task

### Neutral
- The CLAUDE.md-first approach is a common pattern in growing codebases: architectural intent
  outpaces physical structure, documented explicitly rather than hidden

## When to Revisit
When Phase 2 Track B begins (L3 physical split). At that point, execute the restructure
with the benefit of stable test coverage as a regression net.

## References
- V3/CLAUDE.md (full V3.5 architecture reference)
- ADR-0001 (PolicyDecision — the correctness fix that triggered the V3.5 review)
- ADR-0003 (L3 split deferral)
- V3/docs/AUDIT_2026_04_09.md (baseline state at governance establishment)
