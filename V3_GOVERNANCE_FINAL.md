# V3 Governance & Evolution Setup — Final Prompt

> **Purpose**: Establish complete governance infrastructure for V3 (ADR + Phase Roadmap + contract tests + architecture invariants) and complete remaining Phase 1 work (Feature Plane + BrightSkin fixture). After this runs, V3 will be a system that evolves continuously without big-bang refactors.
>
> **Execution mode**: Staged. Complete each stage fully, verify acceptance criteria, then proceed. Do not skip stages.
>
> **Non-negotiable**: All existing tests must remain green at the end of every stage. Do not modify or delete pre-existing tests. Only add new tests.

---

## Project Context

You are working on `/Users/yubo/Documents/worksapce/Decision Engine/V3/`.

In previous sessions, V3 was upgraded with V3.5 concepts:
- `PolicyDecision`, `DecisionState`, `DecisionFeatureVector`, `RawCandidate`, `ScoredCandidate` added to `contracts.py`
- `constraints.py` upgraded to return `PolicyDecision` with weighted `risk_penalty` (`_VIOLATION_WEIGHTS` dict)
- `scoring.py` cleaned to consume `PolicyDecision` directly (removed duplicate `ConstraintEngine` call)
- `pipeline.py` updated to store `PolicyDecision` objects
- `CLAUDE.md` created with V3.5 architecture reference
- `README.md` Phase Roadmap updated with dual-track Phase 2 structure
- All 161 tests passing

What is missing:
1. ADR framework — decisions exist in CLAUDE.md and README.md but no formal ADR records with rationale and alternatives
2. Single authoritative `PHASE_ROADMAP.md` — Phase info is scattered across README and CLAUDE.md
3. Contract tests — no enforcement of typed object invariants
4. Architecture invariant tests — no detection of architectural drift
5. Feature Plane module — `DecisionFeatureVector` is defined but not used in pipeline
6. End-to-end fixture — no realistic scenario for demos and testing
7. Evolution guide — no documented workflow for future contributors

This prompt fixes all seven gaps in seven stages.

---

## Hard Constraints

1. Existing 161 tests must stay green at the end of every stage
2. Do not modify the 5 existing V3.5 contract classes (`PolicyDecision`, `DecisionState`, `DecisionFeatureVector`, `RawCandidate`, `ScoredCandidate`)
3. Do not physically restructure `layer2_decision/` or `layer3_value/` (that is Phase 2 Track B work)
4. Do not introduce new external dependencies beyond what `pyproject.toml` already lists
5. Every new file must have a docstring referencing the ADR or section that governs it
6. Read files before modifying them — do not assume codebase state, audit it

---

# Stage 0 — Audit Current State

## Goal
Produce a written audit of V3's current state. This becomes ground truth for everything that follows.

## Tasks

1. List every file under `V3/src/decision_engine/` with one-sentence purpose
2. Read `contracts.py` in full. List every class and its fields. Mark which are pre-existing vs the 5 V3.5 additions
3. Read `constraints.py`. Confirm `check_all()` returns `PolicyDecision`. Record the `_VIOLATION_WEIGHTS` dict
4. Read `scoring.py`. Confirm no direct `ConstraintEngine` import. Record how it consumes `constraints_result`
5. Read `pipeline.py`. Record how `_generate_candidates` stores the policy decision
6. Read `V3/CLAUDE.md`. Extract the V3.5 decisions documented there
7. Read `V3/README.md`. Extract the current Phase Roadmap (it should already have dual-track Phase 2)
8. Run `cd V3 && python -m pytest tests/ -v`. Record exact test count and confirm green
9. Search for TODO/FIXME/XXX comments related to V3.5 upgrade
10. Check if `V3/docs/` exists. If yes, list contents. If no, this stage creates it

## Output

Create `V3/docs/AUDIT_2026_04_09.md`:

```markdown
# V3 State Audit — 2026-04-09

## Purpose
Snapshot of V3 state at the moment governance framework was established.
Baseline reference for all future evolution.

## File Inventory
[from task 1]

## Contracts
### Pre-existing classes
[list]
### V3.5 classes added in previous sessions
[list with fields]

## Interface Status
### constraints.py
[check_all return type + _VIOLATION_WEIGHTS dict]
### scoring.py
[no direct ConstraintEngine import + consumption pattern]
### pipeline.py
[PolicyDecision storage pattern]

## Test Suite
Total: [exact count]
Status: [pass/fail]
Run timestamp: [when]

## V3.5 Decisions in CLAUDE.md
[list]

## Current Phase Roadmap (from README.md)
[reproduce verbatim what's in README about Phases]

## TODOs / FIXMEs Related to V3.5
[list with file:line]
```

## Acceptance Criteria
- `V3/docs/AUDIT_2026_04_09.md` exists with all sections populated from real codebase data
- Test count recorded
- No source files modified

## Checkpoint
Stop. Report findings. If anything in CLAUDE.md or README does not match actual code, flag before proceeding.

---

# Stage 1 — Establish ADR Framework

## Goal
Create ADR system and write 6 retroactive ADRs documenting all decisions already made.

## Tasks

### 1. Create directory and template

Create `V3/docs/adr/` directory.

Create `V3/docs/adr/README.md`:

```markdown
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
[Populated as ADRs are added]

## Contract Tests
Each ADR introducing a typed object is backed by a contract test in 
`V3/tests/contracts/`. These enforce the invariants described in the 
ADR's "Decision" section. To change a typed object: update the contract 
test, write a new ADR superseding the old one, update PHASE_ROADMAP.md.
```

Create `V3/docs/adr/template.md`:

```markdown
# ADR-NNNN: [Short title in imperative mood]

## Status
[Proposed | Accepted | Superseded by ADR-NNNN | Deprecated]
Date: YYYY-MM-DD

## Context
[What situation forces this decision? What constraints apply? 
What previously-tried approaches exist? 1-2 paragraphs of plain fact.]

## Decision
[The decision itself, in 1-2 sentences. Then a short list of what it 
entails concretely.]

## Alternatives Considered
[Each alternative: one paragraph + one sentence explaining why not chosen. 
At least 2 alternatives required — if you cannot think of alternatives, 
the decision is probably not architecturally significant.]

## Consequences
### Positive
[What this enables or improves]

### Negative
[What this costs or constrains]

### Neutral
[Tradeoffs that are neither clearly positive nor negative]

## When to Revisit
[Under what conditions should this be reconsidered?]

## References
[Related ADRs, external docs, issues]
```

### 2. Write ADR-0001: Adopt PolicyDecision unified interface

Create `V3/docs/adr/0001-adopt-policy-decision-unified-interface.md`.

**Status**: Accepted, 2026-04-09

**Context**: V3's `ConstraintEngine.check_all()` originally returned `(bool, list[str])`. Risk scoring was a separate `compute_risk_score()` returning float. `ApprovalCheckResult` was a third Pydantic model. Three interfaces described the same logical concept (policy evaluation output), causing `scoring.py` to call `ConstraintEngine` twice per candidate and making violation semantics inconsistent across layers.

**Decision**: Unify into a single `PolicyDecision` Pydantic model with fields `eligible`, `hard_reject`, `risk_penalty`, `violations`, `requires_approval`, `rollback_required`, `policy_version`. `ConstraintEngine.check_all()` now returns `PolicyDecision`. `scoring.py` consumes `constraints_result` from the candidate dict.

**Alternatives considered**:
- Introduce OPA as external policy engine — rejected, see ADR-0004
- Keep three separate interfaces but document the contract — rejected because duplicate computation in `scoring.py` was a real correctness issue
- Make `PolicyDecision` a dataclass instead of Pydantic — rejected because Pydantic provides validation for free

**Consequences**:
- Positive: eliminates duplicate `ConstraintEngine` call, enables weighted `risk_penalty` by violation type (margin_floor=3.0, inventory_gate=2.5, etc.), provides single audit record for policy decisions
- Negative: one-time migration of all call sites (completed)
- Neutral: `policy_version` field is currently unused but reserved for Phase 2/3 merchant-specific policy bundles

**When to revisit**: If we need merchant-specific or experiment-specific policy versioning that a single Pydantic model cannot express.

**References**: V3/CLAUDE.md L3.3 section.

### 3. Write ADR-0002: Incremental V3.5 upgrade instead of full refactor

Create `V3/docs/adr/0002-incremental-v3-5-upgrade-instead-of-full-refactor.md`.

**Status**: Accepted, 2026-04-09

**Context**: V3.5 as proposed called for full six-layer physical restructure (new `l3_decision/` with 5 submodules, new `feature_plane/`, new `l2_world_model/`, etc.). V3 already had 159 passing tests, significant implementation investment, and known working behavior. A full refactor would have required rewriting all tests and risked regression before the funding demo.

**Decision**: Adopt V3.5 as a **concept and contract upgrade**, not a physical restructure. V3.5 layer names and sublayer responsibilities are documented in `CLAUDE.md` as the authoritative architecture reference. New typed objects added to `contracts.py`. Existing directories stay in place. Physical L3 split deferred to Phase 2 Track B.

**Alternatives considered**:
- Full refactor into new `v3_5/` directory with archived `old/v3/` — rejected because it would discard 161 tests and introduce regression risk before funding demo
- Do nothing, keep V3 as-is — rejected because PolicyDecision technical debt was real and worth fixing

**Consequences**:
- Positive: all 161 tests remain valid, no regression risk, immediate value from PolicyDecision fix, CLAUDE.md provides clear forward direction
- Negative: code structure does not visually match V3.5 architecture diagram; new engineers must read CLAUDE.md to understand mapping between V3.5 concepts and V3 directories
- Neutral: physical restructure not avoided, only deferred to Phase 2 Track B

**When to revisit**: When Phase 2 Track B begins, or when a contributor reports the mismatch caused a concrete bug or merge conflict.

**References**: V3/CLAUDE.md; ADR-0003.

### 4. Write ADR-0003: Defer L3 physical submodule split to Phase 2 Track B

Create `V3/docs/adr/0003-defer-l3-physical-submodule-split-to-phase-2-track-b.md`.

**Status**: Accepted, 2026-04-09

**Context**: V3.5 design calls for L3 Decision Core split into 5 physical submodules (candidate_proposal, correlation, policy, scoring, verification). V3 currently has these responsibilities scattered across `layer2_decision/` and `layer3_value/`. Split would improve clarity but triggers import changes across the entire test suite.

**Decision**: Do not physically split L3 in Phase 1. Document the 5-submodule responsibility map in CLAUDE.md. Execute split as a dedicated Phase 2 Track B task, after KG content is being actively added and benefits of clearer boundaries outweigh migration cost.

**Alternatives considered**:
- Split now as part of V3.5 upgrade — rejected due to test migration cost and Phase 1 timeline
- Never split, keep current structure — rejected because as content volume grows, the structure will become an obstacle

**Consequences**:
- Positive: no test disruption in Phase 1, engineers rely on CLAUDE.md for conceptual clarity
- Negative: mental model (V3.5 layers) and physical code (V3 directories) don't match, can confuse new contributors
- Neutral: deferred work tracked in PHASE_ROADMAP.md Phase 2 Track B

**When to revisit**: When Phase 2 Track B begins, or when a contributor reports concrete bug from the mismatch.

**References**: ADR-0002; V3/CLAUDE.md.

### 5. Write ADR-0004: Reject OPA integration

Create `V3/docs/adr/0004-reject-opa-integration.md`.

**Status**: Accepted, 2026-04-09

**Context**: V3.5 proposal cited OPA (Open Policy Agent) as industry-standard policy engine and suggested adopting its bundle management for merchant-specific / phase-specific / experiment-specific policy versioning.

**Decision**: Do not integrate OPA. Use `PolicyDecision` Pydantic model and Python-based policy evaluation. Reserve `policy_engine/` package name for future OPA introduction if needed.

**Alternatives considered**:
- Full OPA integration with Rego policies — rejected: ~3 weeks of integration work for a problem 5 config keys in a Pydantic model currently solve
- Lightweight policy DSL like py-rego — rejected: adds learning curve for contributors who already know Python
- Custom YAML rule interpreter — rejected: reinvents OPA without OPA's ecosystem

**Consequences**:
- Positive: no external dependency, contributors only need Python knowledge, fast iteration
- Negative: policy rules encoded in Python rather than declarative DSL, makes non-engineer policy editing harder
- Neutral: `policy_engine/` directory name reserved so future OPA adoption would not require a rename

**When to revisit**: If non-engineers (merchant success, compliance) need to author or audit policies without engineer involvement, or if policy complexity exceeds ~20 rules per merchant.

**References**: V3.5 proposal "Policy Engine显式化" section; V3/CLAUDE.md L3.3.

### 6. Write ADR-0005: Feature Plane as logical concept, no infrastructure in Phase 1

Create `V3/docs/adr/0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md`.

**Status**: Accepted, 2026-04-09

**Context**: V3.5 identifies a Feature Plane as a cross-cutting layer providing continuous numeric features to scoring and bandit. V3 currently has these numbers scattered across `signals` dicts, `ImpactCalculator` inputs, and `scoring.py` candidate dicts, with no unified contract. SageMaker Feature Store would solve this but is heavy infrastructure.

**Decision**: Introduce `DecisionFeatureVector` and `DecisionState` as typed Pydantic contracts in `contracts.py`. Create `feature_plane/` module with `FeatureBuilder` that produces these objects from raw signals. No storage, no online/offline sync, no feature store infrastructure in Phase 1. Phase 2 considers persistent feature history. Phase 3 may introduce a real feature store.

**Alternatives considered**:
- Introduce SageMaker Feature Store now — rejected as over-engineering for Phase 1
- Keep features in scattered dicts — rejected because this is the training/serving skew risk V3.5 flags
- Build custom lightweight feature store — rejected: no current need justifies the complexity

**Consequences**:
- Positive: bandit and scoring engine have stable testable contract for numeric inputs; training/serving skew risk reduced
- Negative: no persistent feature history in Phase 1, so historical replay and offline evaluation not yet possible
- Neutral: `feature_plane/` module is a clean extension point for Phase 3 infrastructure

**When to revisit**: When LinUCB bandit training begins (Phase 3) and requires historical feature snapshots for offline policy evaluation.

**References**: V3/CLAUDE.md Feature Plane section.

### 7. Write ADR-0006: Phase 2 dual-track structure

Create `V3/docs/adr/0006-phase-2-dual-track-structure.md`.

**Status**: Accepted, 2026-04-09

**Context**: Initial Phase 2 planning attempted to combine commercial activation (real Shopline data, LLM API, Dashboard, paying customers) with architectural deepening (KG translation, L3 split, document compiler) into a single phase. This created two problems: first, the items have different blocking conditions (Shopline integration blocks first paying customer; KG translation depends on partner delivery cadence); second, attempting both simultaneously means neither completes cleanly. A separate dependency analysis revealed that real data ingestion (Shopline connector) is a hard prerequisite for first paying customer and cannot be deferred to Phase 3.

**Decision**: Phase 2 splits into two parallel tracks with independent progress:

**Track A — Commercial Activation** (blocks first paying customer):
- Shopline connector productionization
- Real LLM API integration (replacing deterministic template)
- External write APIs (Shopline action execution)
- Web Dashboard + merchant approval workflow
- ImpactCalculator upgrade based on real `was_executed` data
- First paying customer onboarding
- Performance billing infrastructure (built in Track A; activation deferred to first complete reward cycle)

**Track B — Architecture & KG Deepening** (partner-dependent, runs in parallel):
- KG Protocol interface + YAML loader
- Partner KG content translation workflow
- L3 physical submodule split (candidate_proposal / correlation / policy / scoring / verification)
- LLM Renderer migration from `layer2_decision` to `layer4_serving`
- `CorrelatedCandidate` Pydantic typing
- Second real brand fixture

The two tracks are independent — Track A is not blocked by Track B and vice versa. They reinforce each other (Track A produces real execution data that Phase 3 needs; Track B improves DecisionCard quality that Track A delivers to customers) but neither blocks the other. Phase 3 entry requires both tracks complete.

**Alternatives considered**:
- Single Phase 2 with all items mixed — rejected because dependency conflicts make sequencing impossible
- Three separate phases (commercial / architecture / KG) — rejected as artificial; KG content and architecture work are tightly coupled and should stay together
- Defer Shopline connector to Phase 3 — rejected as dependency inversion: real data is prerequisite for commercial activation, not a learning-layer optimization

**Consequences**:
- Positive: clear blocking conditions per track; commercial work and architecture work proceed at their own cadence; partner delivery does not block first paying customer
- Negative: requires coordinating two tracks simultaneously, more project management overhead than single linear phase
- Neutral: Phase 3 entry condition (both tracks complete + 6 months action_log) is more complex than single-track Phase 2 would have been

**When to revisit**: If Track A completes much faster than Track B (or vice versa), evaluate whether to begin Phase 3 partial work. If one track stalls, evaluate splitting it further.

**References**: V3/README.md Phase Roadmap; V3/CLAUDE.md Phase definition section; previous Claude Code session 2026-04-09 dependency analysis.

### 8. Update ADR index in README.md

Update `V3/docs/adr/README.md` Index section:

```markdown
## Index
| Number | Title | Status | Date |
|--------|-------|--------|------|
| [0001](0001-adopt-policy-decision-unified-interface.md) | Adopt PolicyDecision unified interface | Accepted | 2026-04-09 |
| [0002](0002-incremental-v3-5-upgrade-instead-of-full-refactor.md) | Incremental V3.5 upgrade instead of full refactor | Accepted | 2026-04-09 |
| [0003](0003-defer-l3-physical-submodule-split-to-phase-2-track-b.md) | Defer L3 physical submodule split to Phase 2 Track B | Accepted | 2026-04-09 |
| [0004](0004-reject-opa-integration.md) | Reject OPA integration | Accepted | 2026-04-09 |
| [0005](0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md) | Feature Plane as logical concept, no infrastructure in Phase 1 | Accepted | 2026-04-09 |
| [0006](0006-phase-2-dual-track-structure.md) | Phase 2 dual-track structure | Accepted | 2026-04-09 |
```

## Acceptance Criteria
- `V3/docs/adr/README.md` and `V3/docs/adr/template.md` exist
- 6 ADR files exist with the exact filenames listed in the index
- Each ADR has all template sections filled with real content
- Index table populated with all 6 entries
- No source code modified

## Checkpoint
Stop. Confirm 6 ADRs are written and readable. Human review before proceeding — flag any ADR rationale that doesn't match real reasoning.

---

# Stage 2 — Establish Phase Roadmap

## Goal
Create the single authoritative document listing all Phase 1 / 2 / 3 work, cross-referenced with ADRs.

## Tasks

Create `V3/docs/PHASE_ROADMAP.md`:

```markdown
# V3 Phase Roadmap

## Purpose
Single source of truth for what work is planned, complete, and deferred. 
Every architectural discussion must result in an update here or an ADR. 
No plan lives only in chat history.

## How to read
- **[x]** Complete
- **[ ]** Planned, not started
- **[~]** In progress
- **[→ADR-NNNN]** Decision documented in ADR

---

## Phase 1 — Foundation + Funding Demo

**Goal**: Establish architectural foundation, document all decisions, 
produce end-to-end demo for leadership funding decision.

**Status**: In progress (governance and Feature Plane completion in this session)

### Architecture contracts (complete)
- [x] PolicyDecision unified interface [→ADR-0001]
- [x] DecisionFeatureVector typed contract [→ADR-0005]
- [x] DecisionState typed contract [→ADR-0005]
- [x] RawCandidate Pydantic model
- [x] ScoredCandidate Pydantic model
- [x] Weighted risk_penalty in ConstraintEngine
- [x] Scoring engine consumes PolicyDecision directly

### Governance infrastructure (this session)
- [x] ADR framework established
- [x] Six retroactive ADRs written [→ADR-0001 through ADR-0006]
- [x] Phase Roadmap (this document)
- [ ] Contract test layer for core objects (Stage 3)
- [ ] Architecture invariant tests (Stage 4)
- [ ] CLAUDE.md cross-references ADRs (Stage 7)

### Feature Plane implementation (this session)
- [ ] feature_plane/ module with FeatureBuilder (Stage 5)
- [ ] Pipeline integration (signals → FeatureBuilder → DecisionFeatureVector)
- [ ] Feature Plane unit tests

### BrightSkin end-to-end fixture (this session)
- [ ] fixtures/brightskin/ with realistic scenario (Stage 6)
- [ ] End-to-end walkthrough test
- [ ] Demo script for funding presentation

### Deferred from Phase 1 (do not start before Phase 2)
- L3 physical submodule split [→ADR-0003 → Phase 2 Track B]
- L2 typed entity graph and evidence graph [→ Phase 2 Track B]
- Document compiler [→ Phase 3]
- L4 physical reorganization [→ Phase 2 Track B]
- CorrelatedCandidate as independent Pydantic type [→ Phase 2 Track B]

---

## Phase 2 — Dual Track [→ADR-0006]

**Goal**: Activate the system commercially (Track A) while deepening 
architecture and KG content (Track B), in parallel.

**Entry criteria**: Phase 1 complete, funding decision made, partner 
ready to deliver KG content.

**Exit criteria**: Both tracks complete (defined per track below).

### Track A — Commercial Activation

**Blocking condition**: First paying customer cannot launch without these.

- [ ] Shopline connector productionization
  - Real OAuth flow
  - Paginated data ingestion (orders, customers, products, price rules)
  - Rate limit handling and retry logic
  - Production credentials management
- [ ] Real LLM API integration
  - Replace deterministic template renderer with actual LLM call
  - Fallback to template on API failure
  - Cost monitoring and rate limiting
- [ ] External write APIs
  - Shopline action execution endpoints
  - Idempotency guarantees
  - Rollback API surface
- [ ] Web Dashboard + merchant approval workflow
  - Decision card display
  - Approval / rejection / request-more-info actions
  - Action history view
  - Rollback UI
- [ ] ImpactCalculator upgrade
  - Replace benchmark prior with real `was_executed` data
  - Outcome attribution from execution log
  - Confidence classification: HYPOTHESIS → RECOMMENDATION → HIGH_CONFIDENCE
- [ ] First paying customer onboarding
- [ ] Performance billing infrastructure
  - Built in Track A
  - Activation deferred until first complete reward cycle (post-onboarding)

**Track A complete when**: First paying customer is live, executing approved actions through real Shopline writes, with ImpactCalculator using real outcome data.

### Track B — Architecture & KG Deepening

**Blocking condition**: Partner delivery cadence. Independent of Track A.

- [ ] KG Protocol interface
  - Abstract base: `KnowledgeGraph` Protocol
  - Stable method signatures: `get_actions_for_dimension`, `get_conflicts`, `get_playbook`, `get_facts_about`
- [ ] YAML-based KG loader implementation
  - Loads from `playbooks/*.yaml`
  - Validates against schema
  - Conforms to `KnowledgeGraph` Protocol
- [ ] Partner KG content translation workflow
  - Partner content format specification
  - Per-brand content directory structure
  - Validation pipeline for partner-submitted content
- [ ] L3 physical submodule split [→ADR-0003 revisit]
  - Create `l3_decision/candidate_proposal/`, `correlation/`, `policy/`, `scoring/`, `verification/`
  - Migrate code from `layer2_decision/` and `layer3_value/`
  - Update all imports
  - Rewrite affected tests
- [ ] LLM Renderer migration
  - Move from `layer2_decision/pillar3_llm/` to `layer4_serving/`
  - Update import paths
  - Verify renderer only consumes VerifiedDecision (boundary cleanup)
- [ ] CorrelatedCandidate Pydantic typing
  - Replace dict-based output of CrossModuleCorrelator
  - Add contract test
  - Update consuming modules
- [ ] Second real brand fixture
  - Validate architecture works for a brand other than BrightSkin
  - Independent fixture file
  - End-to-end test

**Track B complete when**: At least 2 real brands have KG content loaded, L3 is physically split, LLM Renderer is in L4, CorrelatedCandidate is typed.

### Track A and Track B relationship
- Independent: neither blocks the other
- Mutually reinforcing: Track A produces real execution data Phase 3 needs; Track B improves card quality Track A delivers to customers
- Both required for Phase 3 entry

---

## Phase 3 — Learning Layer Activation

**Goal**: Connect remaining data sources, activate learning layer, enable multi-merchant operation.

**Entry criteria**: 
- Phase 2 Track A complete
- Phase 2 Track B complete  
- 6 months of real `action_log` data accumulated from Track A's first paying customer(s)

### Data ingestion expansion
- [ ] Meta Ads connector productionization
- [ ] GA4 connector productionization
- [ ] Event store for high-frequency signals (consider Timestream)

### Document compiler
- [ ] YAML document → graph facts (entities + relations)
- [ ] YAML document → policy candidates (rules)
- [ ] YAML document → retrieval chunks (text for renderer)
- [ ] Compiler validation pipeline
- [ ] Re-build KG facts from compiler output

### Learning fabric
- [ ] WSM table physical split
  - Decision Log table
  - Execution Log table
  - Outcome Log table
  - Feature History table
- [ ] LinUCB bandit activation
  - Training infrastructure
  - β2 weight ramp-up policy
  - Exploration / exploitation monitoring
- [ ] Offline policy evaluation pipeline
  - Replay historical decisions with new policy
  - Counterfactual analysis
  - Inverse propensity weighting

### Scale
- [ ] Multi-merchant BenchmarkEngine
  - Peer comparison data structures
  - Privacy-preserving aggregation
- [ ] Holdout-based billing validation
  - Control group methodology
  - Outcome attribution validation

---

## Explicitly Rejected (Not Planned)
- OPA integration [→ADR-0004]
- Neptune / Neo4j graph database in any phase
- PublishedCard as separate Pydantic type (DecisionCard + cache metadata sufficient)
- Auto-execution without merchant approval (violates core principle)
- Customer-level WSM granularity (merchant-level is committed scope)
- Bandit deployment before Phase 3 data threshold
- Cross-vertical expansion beyond CPG

---

## Roadmap Update Workflow
1. New idea or proposed change → check if it fits in an existing line item
2. If yes → update status of that item
3. If no → write an ADR documenting the decision, then add to appropriate phase
4. Never add work directly without ADR if it's architecturally significant
5. Items marked "Rejected" require a new ADR to revive
```

## Acceptance Criteria
- `V3/docs/PHASE_ROADMAP.md` exists with all sections above
- All 6 ADRs referenced exist
- Completed items match Stage 0 audit findings
- Track A and Track B clearly distinguished
- No source code modified

## Checkpoint
Stop. Verify roadmap matches Stage 0 audit. Any mismatch (item marked `[x]` but not actually done, or vice versa) must be corrected before proceeding.

---

# Stage 3 — Contract Test Layer

## Goal
Write tests enforcing invariants of the 5 core typed objects. These tests are the architecture's constitution.

## Tasks

### 1. Create directory
Create `V3/tests/contracts/` and `V3/tests/contracts/__init__.py` (empty).

### 2. Create `V3/tests/contracts/test_policy_decision_contract.py`

Tests required:
- `PolicyDecision` is `frozen=True` (mutating field raises `ValidationError`)
- `eligible=True` requires `violations=[]` (otherwise raises)
- `hard_reject=True` requires `eligible=False` (otherwise raises)
- `risk_penalty >= 0.0` enforced
- `policy_version` field exists and is a string
- Round-trip: `PolicyDecision(**pd.model_dump())` produces equal object
- All required fields enforced (instantiation without them raises)

Each test docstring cites ADR-0001.

### 3. Create `V3/tests/contracts/test_decision_feature_vector_contract.py`

Tests required:
- All numeric fields accept valid positive values
- Rate fields (`repeat_rate_7d`, `cvr_7d`, `cvr_30d`, `promo_redemption_30d`, `churn_score`, `stock_pressure_score`) reject values outside `[0.0, 1.0]`
- `inventory_days` accepts 0.0 and positive, rejects negative
- `margin_pct` accepts 0.0 to 1.0, rejects outside
- Round-trip serialization works
- Instance is frozen
- `computed_at` is required

Each test cites ADR-0005.

### 4. Create `V3/tests/contracts/test_decision_state_contract.py`

Tests required:
- Each dimension state field accepts only 4 valid literals: `"HEALTHY"`, `"WATCH"`, `"DEGRADING"`, `"CRITICAL"`
- `active_alerts` defaults to empty list
- All dimension state fields required
- Frozen
- Round-trip works

Each test cites ADR-0005.

### 5. Create `V3/tests/contracts/test_raw_candidate_contract.py`

Tests required:
- All required fields enforced
- `action_type` non-empty string
- `evidence_refs` defaults to empty list
- Frozen
- Round-trip works

### 6. Create `V3/tests/contracts/test_scored_candidate_contract.py`

Tests required:
- All required fields enforced
- `final_score` accepts any float including `-inf` (blocked candidates)
- `rank` is positive integer
- `beta_snapshot` is dict with string keys and float values
- Frozen
- Round-trip works

## Acceptance Criteria
- All 5 contract test files exist
- `cd V3 && python -m pytest tests/contracts/ -v` passes
- Full test suite green
- Total test count increased by sum of new contract tests
- No pre-existing tests modified

## Checkpoint
Stop. Report new total test count.

---

# Stage 4 — Architecture Invariant Tests

## Goal
Automated tests detecting architectural drift — code that violates boundaries declared in ADRs.

## Tasks

### 1. Create `V3/tests/architecture/` and `V3/tests/architecture/__init__.py`

### 2. Create `V3/tests/architecture/test_architecture_invariants.py`

Use `ast` for reliable import checking. Use plain string search only as last resort with clear comments.

Required tests:

**test_scoring_does_not_import_constraint_engine**

Uses AST to parse `layer2_decision/scoring.py`, asserts `ConstraintEngine` is not imported. Cites ADR-0001. Docstring explains: if test fails, either fix the regression or write a new ADR superseding ADR-0001.

**test_constraints_check_all_returns_policy_decision**

Uses `inspect` or AST to verify `ConstraintEngine.check_all` has return annotation `PolicyDecision`. Cites ADR-0001.

**test_no_layer_imports_from_higher_numbered_layer**

Layer order: layer0_data (0) → layer1_msm (1) → layer2_decision (2) → layer3_value (3) → layer4_serving (4) → layer5_wsm (5).

For each `.py` file, check imports. Assert no file in layer N imports from layer M where M > N.

**Exception**: `layer2_decision/scoring.py` may import from `layer3_value/constraints.py` — this is the documented cross-layer dependency. Add explicit allowlist with comment citing CLAUDE.md "Cross-Layer Dependency Note" section.

**test_margin_floor_value_only_in_constraints**

The magic number `0.15` (margin floor) should only exist in:
- `layer3_value/constraints.py`
- Test files (`tests/`)
- Policy YAML files (`playbooks/`)
- Fixture files (`fixtures/`)

Search all source files for `0.15`. Assert it appears only in allowed locations. Catches "someone hardcoded margin floor elsewhere" regressions.

**test_all_v3_5_contracts_are_frozen**

Use AST to parse `contracts.py`. For each Pydantic BaseModel subclass, assert `model_config = ConfigDict(frozen=True)` (or equivalent). Cites ADR-0001 and ADR-0005.

**test_constraint_engine_only_instantiated_in_pipeline**

AST-scan all source files except `layer3_value/constraints.py` and `layer4_serving/pipeline.py`. Assert no other file contains `ConstraintEngine(`. Prevents scattered instantiation.

**test_v3_5_contracts_exported_from_contracts_module**

Assert these are importable from `src.decision_engine.contracts`:
- `PolicyDecision`
- `DecisionState`
- `DecisionFeatureVector`
- `RawCandidate`
- `ScoredCandidate`

Catches accidental moves.

### 3. Each test docstring requirement

Every invariant test must have docstring with:
1. The invariant in one sentence
2. The ADR or CLAUDE.md section it enforces
3. What to do if test fails (fix code OR write new ADR superseding the governing one)

Example:
```python
def test_scoring_does_not_import_constraint_engine():
    """Scoring engine must not import ConstraintEngine directly.
    
    Enforces: ADR-0001 (PolicyDecision unified interface).
    
    If this test fails: either the refactor regressed (fix by removing 
    the import and consuming PolicyDecision from candidate dict), or 
    the decision is being intentionally reversed (write a new ADR 
    superseding ADR-0001 and update this test).
    """
    ...
```

## Acceptance Criteria
- `V3/tests/architecture/test_architecture_invariants.py` exists
- All invariant tests pass
- Each test has docstring citing governing ADR
- Full test suite green

## Checkpoint
Stop. Report final test count.

---

# Stage 5 — Feature Plane Module

## Goal
Make `DecisionFeatureVector` actually work — currently defined but unused.

## Tasks

### 1. Create `V3/src/decision_engine/feature_plane/__init__.py`

```python
"""Feature Plane — continuous numeric features for scoring and learning.

Implements ADR-0005: Feature Plane as logical concept.

Computes DecisionFeatureVector instances from raw signals, providing a 
stable typed contract for downstream scoring and future bandit training. 
No storage or online/offline split in Phase 1.

See V3/docs/adr/0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md
See V3/docs/PHASE_ROADMAP.md Phase 1 / Feature Plane implementation
"""

from src.decision_engine.feature_plane.builder import FeatureBuilder

__all__ = ["FeatureBuilder"]
```

### 2. Create `V3/src/decision_engine/feature_plane/builder.py`

Class `FeatureBuilder` with:
- `__init__(self)` — stateless
- `build(self, signals: dict, merchant_state: MerchantStateVector) -> DecisionFeatureVector`
- Private helpers, each pure and testable

The `build` method:
1. Extract each field from `signals` with safe default if missing (log warning matching `constraints.py` pattern)
2. Validate ranges before constructing `DecisionFeatureVector`
3. Return populated `DecisionFeatureVector` with `computed_at=datetime.now(timezone.utc)`

Phase 1 derivations (all simple, no ML):
- `inventory_days` = `signals.get("inventory_days", 0.0)`
- `margin_pct` = `signals.get("margin_pct", 0.0)`
- `repeat_rate_7d` = `signals.get("repeat_rate_7d", 0.0)`
- `cvr_7d` = `signals.get("cvr_7d", 0.0)`
- `cvr_30d` = `signals.get("cvr_30d", 0.0)`
- `promo_redemption_30d` = `signals.get("promo_redemption_30d", 0.0)`
- `stock_pressure_score` = computed: `1.0 - (inventory_days / 7.0)` if `inventory_days < 7` else `0.0`
- `churn_score` = `signals.get("churn_score", 0.0)` (Phase 2/3 will replace with real computation)
- `seasonality_index` = `signals.get("seasonality_index", 1.0)`
- `benchmark_gap_score` = `signals.get("benchmark_gap_score", 0.0)`

Each helper has docstring noting Phase 2/3 replacement plan.

### 3. Create `V3/tests/feature_plane/__init__.py` (empty)

### 4. Create `V3/tests/feature_plane/test_feature_builder.py`

Tests:
- `FeatureBuilder.build()` with complete signals produces valid `DecisionFeatureVector`
- Missing signals produce defaults and log warnings
- `stock_pressure_score == 0.0` when inventory healthy (>= 7 days)
- `stock_pressure_score == 1.0` when inventory is 0 days
- `stock_pressure_score == 0.5` when inventory is 3.5 days
- Values outside `[0, 1]` ranges in signals: clamp or raise (pick one, document with comment)
- `computed_at` is set to current UTC time
- Produced object is frozen

### 5. Integrate FeatureBuilder into pipeline.py

Find `pipeline._generate_candidates()` (or wherever signals are processed). Add a call to `FeatureBuilder.build(signals, msm_state)` to produce a `DecisionFeatureVector`. Attach to each candidate under key `"feature_vector"` (alongside existing `"constraints_result"`).

**Critical**: Do not change any existing behavior. The `signals` dict continues to flow as before. FeatureBuilder is additive — it produces a new artifact that downstream modules **may** consume. Existing consumers of `signals` continue to work unchanged.

### 6. Create `V3/tests/feature_plane/test_pipeline_integration.py`

Test that after running `pipeline._generate_candidates()`, each candidate dict has a `feature_vector` key whose value is a `DecisionFeatureVector` instance.

## Acceptance Criteria
- `feature_plane/` module exists with `builder.py` and `__init__.py`
- `FeatureBuilder` is importable and instantiable
- All Feature Plane tests pass
- Pipeline integration test passes
- Full test suite green
- No existing tests modified

## Checkpoint
Stop. Confirm Feature Plane is wired into pipeline.

---

# Stage 6 — BrightSkin End-to-End Fixture

## Goal
Realistic end-to-end demo scenario for funding presentation and reference testing.

## Tasks

### 1. Create directories
- `V3/fixtures/brightskin/` with `__init__.py`
- `V3/tests/e2e/` with `__init__.py`
- `V3/scripts/` if it doesn't exist

### 2. Create `V3/fixtures/brightskin/scenario.py`

```python
"""BrightSkin end-to-end demo fixture.

BrightSkin is a skincare brand with 2 years of Shopline history. Current 
state: retention DEGRADING (VIP churn risk + dropping repeat rate), 
acquisition WATCH, conversion HEALTHY, promotion HEALTHY.

This is the canonical Phase 1 demo scenario, referenced by:
- V3/tests/e2e/test_brightskin_walkthrough.py
- V3/scripts/demo_brightskin.py
- V3/docs/PHASE_ROADMAP.md Phase 1 / BrightSkin end-to-end fixture

See V3/docs/PHASE_ROADMAP.md
"""

from datetime import datetime, timezone
from src.decision_engine.contracts import MerchantStateVector


def build_brightskin_state() -> MerchantStateVector:
    """BrightSkin's 4D MSM state at decision time."""
    return MerchantStateVector(
        merchant_id="brightskin_042",
        computed_at=datetime(2026, 4, 8, 9, 0, 0, tzinfo=timezone.utc),
        retention_state="DEGRADING",
        acquisition_state="WATCH",
        conversion_state="HEALTHY",
        promotion_state="HEALTHY",
        retention_urgency=0.75,
        # Add other required fields based on actual MerchantStateVector schema 
        # discovered in Stage 0 audit
    )


def build_brightskin_signals() -> dict:
    """Raw signals BrightSkin's pipeline would receive.
    
    Feeds both FeatureBuilder and ConstraintEngine.
    """
    return {
        # Inventory
        "inventory_days": 38.0,
        "inventory_days_p10": 12.0,
        # Margin
        "margin_pct": 0.33,
        # Behavior
        "repeat_rate_7d": 0.18,
        "cvr_7d": 0.024,
        "cvr_30d": 0.027,
        "promo_redemption_30d": 0.42,
        "churn_score": 0.61,
        # Context
        "seasonality_index": 1.0,
        "benchmark_gap_score": -0.23,
        # Customer
        "customer_orders_count": 5,
        # Last action
        "last_action_type": "REMINDER",
        "days_since_last_action": 5,
        # Incrementality
        "promo_incrementality": 0.45,
    }


def build_brightskin_policy() -> dict:
    """BrightSkin's policy pack for the demo."""
    return {
        "policy_version": "brightskin_v1",
        "policy_weights": {
            "gmv_lift": 0.30,
            "margin_lift": 0.25,
            "inventory_risk_reduction": 0.20,
            "retention_lift": 0.25,
        },
        "risk_budget": {},
        "beta1": 0.65,
        "beta2": 0.20,
        "beta3": 0.15,
    }
```

### 3. Create `V3/tests/e2e/test_brightskin_walkthrough.py`

```python
"""BrightSkin end-to-end walkthrough test.

This test is the Phase 1 contract: the full pipeline must produce 
sensible results for BrightSkin's scenario. If this fails, something 
in the decision path is broken.

Enforces: V3/docs/PHASE_ROADMAP.md Phase 1 / BrightSkin end-to-end fixture
"""

import pytest
from src.decision_engine.layer4_serving import pipeline
from src.decision_engine.contracts import PolicyDecision, DecisionFeatureVector
from fixtures.brightskin.scenario import (
    build_brightskin_state,
    build_brightskin_signals,
    build_brightskin_policy,
)


def test_brightskin_pipeline_produces_retention_focused_candidates():
    """DEGRADING retention state should surface retention candidates."""
    candidates = pipeline._generate_candidates(
        build_brightskin_state(),
        build_brightskin_signals(),
        build_brightskin_policy(),
    )
    assert len(candidates) > 0
    retention_candidates = [c for c in candidates if c.get("module") == "retention"]
    assert len(retention_candidates) > 0


def test_brightskin_candidates_have_policy_decisions():
    """Every candidate must have a PolicyDecision attached."""
    candidates = pipeline._generate_candidates(
        build_brightskin_state(),
        build_brightskin_signals(),
        build_brightskin_policy(),
    )
    for c in candidates:
        pd = c.get("constraints_result")
        assert pd is not None
        assert isinstance(pd, PolicyDecision)


def test_brightskin_candidates_have_feature_vectors():
    """Every candidate must have DecisionFeatureVector (added in Stage 5)."""
    candidates = pipeline._generate_candidates(
        build_brightskin_state(),
        build_brightskin_signals(),
        build_brightskin_policy(),
    )
    for c in candidates:
        fv = c.get("feature_vector")
        assert fv is not None
        assert isinstance(fv, DecisionFeatureVector)
        assert fv.margin_pct == 0.33


def test_brightskin_returning_customer_allows_discounts():
    """customer_orders_count=5 means cold_prospect_gate doesn't fire."""
    candidates = pipeline._generate_candidates(
        build_brightskin_state(),
        build_brightskin_signals(),
        build_brightskin_policy(),
    )
    discount_candidates = [
        c for c in candidates 
        if "DISCOUNT" in c.get("action_id", "").upper()
    ]
    if discount_candidates:
        for c in discount_candidates:
            pd = c["constraints_result"]
            violations_str = " ".join(pd.violations)
            assert "cold_prospect_gate" not in violations_str


def test_brightskin_margin_floor_respected():
    """margin_pct=0.33 allows 10% discount (post-margin 0.23 >= 0.15)."""
    candidates = pipeline._generate_candidates(
        build_brightskin_state(),
        build_brightskin_signals(),
        build_brightskin_policy(),
    )
    for c in candidates:
        if "DISCOUNT_10PCT" in c.get("action_id", ""):
            pd = c["constraints_result"]
            violations_str = " ".join(pd.violations)
            assert "margin_floor" not in violations_str
```

### 4. Create `V3/scripts/demo_brightskin.py`

```python
"""BrightSkin demo script for funding presentation.

Run from V3/:
    python scripts/demo_brightskin.py

Prints readable summary of top candidates for BrightSkin scenario.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.decision_engine.layer4_serving import pipeline
from src.decision_engine.layer2_decision.scoring import ScoringEngine
from fixtures.brightskin.scenario import (
    build_brightskin_state,
    build_brightskin_signals,
    build_brightskin_policy,
)


def main():
    print("=" * 70)
    print("CPG Decision Engine V3 — BrightSkin Demo")
    print("=" * 70)
    
    msm = build_brightskin_state()
    signals = build_brightskin_signals()
    policy = build_brightskin_policy()
    
    print(f"\nMerchant: {msm.merchant_id}")
    print(f"Retention: {msm.retention_state}")
    print(f"Acquisition: {msm.acquisition_state}")
    print(f"Conversion: {msm.conversion_state}")
    print(f"Promotion: {msm.promotion_state}")
    
    candidates = pipeline._generate_candidates(msm, signals, policy)
    print(f"\n{len(candidates)} candidates generated.\n")
    
    scoring = ScoringEngine()
    ranked = scoring.rank_actions(msm_state=msm, candidates=candidates, policy=policy)
    
    print("Top 3 recommendations:")
    print("-" * 70)
    for i, c in enumerate(ranked[:3], 1):
        print(f"\n#{i}. {c.get('action_id')} (module: {c.get('module')})")
        print(f"    Final score: {c.get('final_score'):.4f}")
        pd = c.get("constraints_result")
        if pd:
            print(f"    Eligible: {pd.eligible}")
            if pd.violations:
                print(f"    Violations: {', '.join(pd.violations)}")
        fv = c.get("feature_vector")
        if fv:
            print(f"    Margin: {fv.margin_pct:.2%}")
            print(f"    Repeat rate 7d: {fv.repeat_rate_7d:.2%}")
            print(f"    Churn score: {fv.churn_score:.2f}")


if __name__ == "__main__":
    main()
```

## Acceptance Criteria
- `V3/fixtures/brightskin/scenario.py` exists with three factory functions
- `V3/tests/e2e/test_brightskin_walkthrough.py` exists with 5 tests
- All BrightSkin tests pass
- Full test suite green
- `python scripts/demo_brightskin.py` runs successfully and prints readable output

## Checkpoint
Stop. Run demo script. Verify output is presentable for leadership.

---

# Stage 7 — Cross-Reference and Final Audit

## Goal
Ensure all documents reference each other correctly. Total system coherent.

## Tasks

### 1. Update `V3/CLAUDE.md`

Add at the top, after the title:

```markdown
## Governance References
- **Architecture Decision Records**: `docs/adr/` — every major decision documented with rationale and alternatives
- **Phase Roadmap**: `docs/PHASE_ROADMAP.md` — single source of truth for planned work (Phase 1, Phase 2 dual-track, Phase 3)
- **Contract Tests**: `tests/contracts/` — enforce typed object invariants
- **Architecture Invariant Tests**: `tests/architecture/` — detect architectural drift
- **End-to-End Demo**: `tests/e2e/test_brightskin_walkthrough.py` and `scripts/demo_brightskin.py`
- **Evolution Guide**: `docs/EVOLUTION_GUIDE.md` — how to make architectural changes

When making architectural changes, follow the workflow in 
`docs/EVOLUTION_GUIDE.md`: write ADR → update roadmap → update contract 
tests if types change → implement.
```

Throughout CLAUDE.md, wherever a V3.5 decision is mentioned, add `[see ADR-NNNN]` citations:
- PolicyDecision sections → `[see ADR-0001]`
- L3 layer naming → `[see ADR-0002, ADR-0003]`
- Feature Plane → `[see ADR-0005]`
- Phase 2 dual track → `[see ADR-0006]`

### 2. Update `V3/README.md`

Add a "Governance" section at the top of the README (after the project description, before the architecture overview):

```markdown
## Governance
This project follows formal architecture governance:
- **Decisions**: documented in `docs/adr/`
- **Roadmap**: `docs/PHASE_ROADMAP.md`
- **Architecture reference**: `CLAUDE.md`
- **How to contribute**: `docs/EVOLUTION_GUIDE.md`
```

### 3. Create `V3/docs/EVOLUTION_GUIDE.md`

```markdown
# V3 Evolution Guide

## Purpose
How to make changes to V3 without breaking architectural coherence. 
Follow this for any non-trivial change.

## The Five-Step Change Process

### Step 1: Write an ADR draft
Before code, copy `docs/adr/template.md` and answer:
- What are you trying to do?
- What alternatives did you consider?
- What are you giving up?

If you cannot articulate alternatives, the change may not be 
architecturally significant — proceed without an ADR.

### Step 2: Check contracts
Does your change affect a typed object in `contracts.py`?
- If backward-compatible (add fields, don't remove): proceed
- Otherwise: write a new ADR superseding the old one AND update 
  contract tests in `tests/contracts/`

### Step 3: Locate in PHASE_ROADMAP.md
Find where your change fits.
- If not in roadmap: add it
- If in a later phase: reconsider whether now is the right time
- If in a different track of Phase 2: confirm you have the right 
  blocking conditions

### Step 4: Write or update tests first
- New typed object: contract test before implementation
- New module: acceptance test for the module
- Behavior change: update affected tests to reflect new expectation

### Step 5: Implement and verify
- Minimum change needed
- Run full suite: `pytest tests/ -v`
- Run invariants: `pytest tests/architecture/ -v`
- Any invariant failure: fix code OR write new ADR superseding the 
  governing one

## Adding Business Content (KG, Policies, Brand Data)
Business content is not architecture. No ADR needed for:
- Adding a new brand's KG facts
- Adjusting policy weights
- Loading new data

Just:
1. Put content in `fixtures/` or `playbooks/`
2. Ensure content passes existing contract tests
3. Run test suite

## Adding a New Data Source (Phase 2 Track A or Phase 3)
Write an ADR before implementing. Document:
- What fields are extracted
- Defaults for missing data
- Error modes handled
- Where in the pipeline data flows

## Adding a New Module (Phase 2 Track B or Phase 3)
1. Write ADR specifying which layer it belongs to and why
2. Add to PHASE_ROADMAP.md in correct phase/track
3. Update CLAUDE.md architecture section
4. Add architecture invariant tests for its boundaries
5. Write implementation and unit tests

## Working in Phase 2 Dual-Track Mode
Phase 2 has two parallel tracks (see ADR-0006 and PHASE_ROADMAP.md).

When picking up work:
1. Identify which track the task belongs to (Track A: commercial, 
   Track B: architecture/KG)
2. Check track entry conditions are met
3. Check the task is not blocked by another item in the same track
4. Track A tasks may proceed even if Track B is incomplete (and vice 
   versa)
5. Phase 3 entry requires both tracks complete

## When Things Go Wrong
- Test failure on existing test: do not delete it. Investigate.
- Architecture invariant failure: do not bypass it. Fix or supersede.
- Contract test failure: the type was changed. Update contract test 
  AND write new ADR.
- Multiple ADRs cite the same code: that's fine. Cross-references 
  are good.
```

### 4. Final test run

```bash
cd V3 && python -m pytest tests/ -v --tb=short
```

Record final test count.

### 5. Create `V3/docs/SETUP_COMPLETE_2026_04_09.md`

```markdown
# V3 Governance Setup Complete — 2026-04-09

## What was established
- [x] ADR framework with 6 retroactive ADRs
- [x] PHASE_ROADMAP.md with Phase 1 / Phase 2 dual-track / Phase 3
- [x] Contract test layer for 5 V3.5 typed objects
- [x] Architecture invariant tests
- [x] Feature Plane module (previously half-built, now complete)
- [x] BrightSkin end-to-end fixture
- [x] Demo script for funding presentation
- [x] Evolution Guide for future contributors
- [x] Cross-references between CLAUDE.md, ADRs, Roadmap, README

## Test suite status
- Starting: 161 tests passing
- Final: [actual count] tests passing
- Delta: [actual] new tests added

## What to do next
1. Human review of 6 retroactive ADRs — confirm rationale matches reality
2. Run `python scripts/demo_brightskin.py` and verify output
3. When partner delivers first KG content, follow `docs/EVOLUTION_GUIDE.md`
4. Phase 2 entry: funding decision + Phase 1 production-ready
5. Phase 2 Track A and Track B can begin in parallel

## Files created in this session
[actual list]

## Files modified in this session
- contracts.py (no changes — already had V3.5 types from previous session)
- pipeline.py (Feature Plane integration only)
- CLAUDE.md (added governance references and ADR citations)
- README.md (added governance section)
```

## Acceptance Criteria
- `V3/docs/EVOLUTION_GUIDE.md` exists and complete
- `V3/CLAUDE.md` references ADRs throughout
- `V3/README.md` has Governance section
- `V3/docs/SETUP_COMPLETE_2026_04_09.md` exists with accurate counts and file lists
- Full test suite green
- `python scripts/demo_brightskin.py` runs successfully

## Final Checkpoint
Stop. Final report:
- Total new files
- Total modified files
- Starting and final test counts
- Any unresolved questions for human review
- Recommended next concrete action

---

# Execution Instructions for Claude Code

1. **Start with Stage 0**, complete fully before Stage 1
2. **Run test suite at end of every stage**. Failures = stop and report
3. **Do not modify or delete pre-existing tests**. Only add new tests
4. **Read files before modifying**. Audit first, act second
5. **Flag any discrepancy** between this prompt's assumptions and actual codebase. Do not fabricate
6. **Commit per stage** with messages like "Stage N: [description]"
7. **Prefer boring code**. Governance infrastructure should be readable, not clever
8. **At Stage 7 completion**, produce final summary report

Begin with Stage 0.
