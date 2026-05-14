# Architecture Decision Records (ADRs)

## What is an ADR?
An ADR captures one architectural decision: what was decided, why, what
alternatives were considered, what was given up. ADRs are append-only —
once written, they are not edited (except status changes). If a decision
is superseded, write a new ADR that references the old one.

## Status lifecycle
- **Proposed**: under discussion
- **Accepted**: decision made, implementation in progress or complete
- **Superseded by ADR-NNNN**: no longer current; see replacement
- **Deprecated**: decision withdrawn without replacement

## How to write a new ADR
1. Copy `template.md` to `NNNN-short-kebab-case-title.md` with the next
   available number
2. Fill in all sections. Keep it short — 1-2 pages max
3. Commit the ADR in the same PR as the code it governs
4. Update the index below

## Index
| Number | Title | Status | Date |
|--------|-------|--------|------|
| [0001](0001-adopt-policy-decision-unified-interface.md) | Adopt PolicyDecision unified interface | Accepted | 2026-04-09 |
| [0002](0002-incremental-v3-5-upgrade-instead-of-full-refactor.md) | Incremental V3.5 upgrade instead of full refactor | Accepted | 2026-04-09 |
| [0003](0003-defer-l3-physical-submodule-split-to-phase-2-track-b.md) | Defer L3 physical submodule split to Phase 2 Track B | Accepted | 2026-04-09 |
| [0004](0004-reject-opa-integration.md) | Reject OPA integration | Accepted | 2026-04-09 |
| [0005](0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md) | Feature Plane as logical concept, no infrastructure in Phase 1 | Accepted | 2026-04-09 |
| [0006](0006-phase-2-dual-track-structure.md) | Phase 2 dual-track structure | Accepted | 2026-04-09 |
| [0007](0007-document-cross-layer-dependency-constraints-to-scoring.md) | Document cross-layer dependency (constraints → scoring) | Accepted | 2026-04-09 |
| [0008](0008-adopt-linucb-over-thompson-sampling.md) | Adopt LinUCB over Thompson Sampling | Accepted | 2026-04-09 |
| [0009](0009-introduce-evidence-graph-snapshot.md) | Introduce Evidence Graph Snapshot | Accepted | 2026-04-10 |
| [0010](0010-data-source-facade-for-l0.md) | Data Source Facade for L0 (concept — Phase 2 Track A) | Accepted (concept) | 2026-04-10 |
| [0011](0011-three-layer-kg-playbook-structure.md) | Three-Layer KG Playbook Structure for Multi-Brand Content | Accepted | 2026-04-12 |
| [0012](0012-match-playbook-single-return-contract.md) | match_playbook() Returns dict \| None (Single-Pattern Routing Contract) | Accepted | 2026-04-13 |
| [0013](0013-msm-state-driven-routing-contract.md) | MSM-State-Driven Playbook Routing Contract | Accepted | 2026-04-14 |
| [0014](0014-phase-a-scope-and-runtime-invariants.md) | V3.1 Phase A Scope and Runtime Invariants | Proposed | 2026-04-26 |
| [0015](0015-outcome-review-v1-directional-post-decision.md) | Outcome Review v1 — Directional, Module-Aware, Post-Decision | Proposed | 2026-04-26 |
| [0016](0016-v3-1-truth-philosophy.md) | V3.1 Truth Philosophy — Multi-Source Truth, Disagreement Policy, Gate Explainability | Proposed | 2026-04-26 |

## Contract Tests
Each ADR introducing a typed object is backed by a contract test in
`V3/tests/contracts/`. These enforce the invariants described in the
ADR's "Decision" section. To change a typed object: update the contract
test, write a new ADR superseding the old one, update PHASE_ROADMAP.md.
