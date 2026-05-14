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

**Status**: Phase 1 complete (2026-04-10)

### Architecture contracts
- [x] PolicyDecision unified interface [→ADR-0001]
- [x] DecisionFeatureVector typed contract [→ADR-0005]
- [x] DecisionState typed contract [→ADR-0005]
- [x] RawCandidate Pydantic model (frozen=True)
- [x] ScoredCandidate Pydantic model (frozen=True)
- [x] Weighted risk_penalty in ConstraintEngine
- [x] Scoring engine consumes PolicyDecision directly
- [x] EvidenceTraceEntry typed contract [→ADR-0009]
- [x] EvidenceGraphSnapshot typed contract [→ADR-0009]

### Governance infrastructure
- [x] ADR framework established
- [x] 10 ADRs written (6 retroactive + 4 new) [→ADR-0001 through ADR-0010]
- [x] Phase Roadmap (this document)
- [x] Contract test layer for all typed objects (tests/contracts/)
- [x] Architecture invariant tests (tests/architecture/) — 9 invariants
- [x] CLAUDE.md cross-references ADRs throughout
- [x] EVOLUTION_GUIDE.md for future contributors
- [x] DATA_AND_LICENSE_STATUS.md (data provenance — Shopify CSV status PENDING)

### Feature Plane implementation
- [x] feature_plane/ module with FeatureBuilder
- [x] Pipeline integration (signals → FeatureBuilder → DecisionFeatureVector)
- [x] Feature Plane unit tests (21 tests)

### Evidence Graph Snapshot (ADR-0009)
- [x] EvidenceGraphSnapshot typed object [→ADR-0009]
- [x] Pipeline emits EvidenceGraphSnapshot for top-3 eligible candidates [→ADR-0009]
- [x] LLMRenderer.render_from_snapshot() — new pathway, existing render() unchanged [→ADR-0009]
- [x] Architecture invariant test: render_from_snapshot uses snapshot input
- [x] BrightSkin e2e tests: snapshot emitted and renderer consumes it

### BrightSkin end-to-end fixture
- [x] fixtures/brightskin/ with realistic scenario
- [x] End-to-end walkthrough test (8 tests)
- [x] Demo script for funding presentation (prints evidence chain)

### Engineering hardening (completed post-Phase-1)
- [x] pipeline.run_once() wrapped in try/except/finally — WSM write guaranteed even on crash
- [x] scoring.rank_actions() per-candidate try/except — one bad candidate never kills the loop
- [x] scoring.rank_actions() fail-safe for missing constraints_result (was fail-open)
- [x] PlaybookRegistry._validate_playbook_structure() — detects KG content issues on load
- [x] PlaybookRegistry logs structural issues as WARNING (not DEBUG)
- [x] tests/layer2/test_playbook_registry.py — 18 tests for validation logic
- [x] scripts/kg_dryrun.py — dry-run validation script (no data required)

### Deferred from Phase 1 (do not start before Phase 2)
- L3 physical submodule split [→ADR-0003 → Phase 2 Track B]
- L4 physical reorganization [→ Phase 2 Track B]
- CorrelatedCandidate as independent Pydantic type [→ Phase 2 Track B]
- Document compiler [→ Phase 3]

---

## Pre-KG checklist (complete before translating KG content)

**Purpose**: Ensure the system can receive and validate KG content correctly.
Run `python scripts/kg_dryrun.py` after each playbook is translated.

- [x] PlaybookRegistry validates structure on load (warnings for missing expected_utility, bad msm_state, wrong module)
- [x] dry-run script exists: `scripts/kg_dryrun.py`
- [ ] Each translated YAML playbook has a unit test in `tests/layer2/test_playbook_<module>.py`
  - Asserts match_playbook() returns non-None for expected msm_states
  - Asserts get_base_utility() returns numeric value for each action
- [ ] All existing stub playbooks have `expected_utility` filled in (KG partner fills these)
- [ ] dry-run exits 0 (all 4 modules × 4 MSM states route correctly, no utility warnings)

---

## Pre-data checklist (complete before connecting Shopline)

**Purpose**: Prevent "no candidates but no error" failures caused by real data
field names and types not matching system expectations.

- [ ] `docs/SHOPLINE_SIGNAL_CONTRACT.md` created
  - Maps every system field name → Shopline API field name
  - Documents type, range, and missing-signal behavior for each field
  - Covers: margin_pct, inventory_days, repeat_rate_7d, last_action_type,
    days_since_last_action, promo_incrementality, customer_orders_count,
    churn_score / overdue_ratio, cvr_7d, cvr_30d, checkout_cvr
- [ ] ShoplineConnector `_normalize_*` methods designed (interface only, impl in Track A)
  - fetch_orders → _normalize_orders (field mapping + type coercion)
  - fetch_products → _normalize_products
  - fetch_customers → _normalize_customers
- [ ] FeatureBuilder missing-signal logs upgraded from DEBUG → WARNING
  - All `log.debug("[FeatureBuilder] * missing")` → `log.warning`
  - Reason: production runs at INFO level; missing signals must be visible

---

## Post-data / operational checklist (complete before first real merchant run)

**Purpose**: Observability and operational hygiene for production runs.

- [ ] Structured log format adopted for key pipeline steps
  - Every critical log includes: merchant_id, step name, result
  - Enables `grep merchant_id=X` to reconstruct full decision chain
- [ ] Pipeline decision summary log added (Step 16, before return)
  - Format: `merchant=%s cards=%d eligible=%d suppressed=%d policy=%s`
  - Lets ops see per-run health without querying DB
- [ ] Bandit context_vec shape validation added to scoring.py (before Phase 3)
  - Validate `len(x) == arm.d` before calling `arm.predict(x)`
  - Fail-safe: log error + u_ucb = 0.0 on mismatch (never crash)

---

## Phase 2 — Dual Track [→ADR-0006]

**Goal**: Activate the system commercially (Track A) while deepening
architecture and KG content (Track B), in parallel.

**Entry criteria**: Phase 1 complete, funding decision made, partner
ready to deliver KG content.

**Exit criteria**: Both tracks complete (defined per track below).

### Track A — Commercial Activation

**Blocking condition**: First paying customer cannot launch without these.

- [ ] Fast Plane stale-read alert
  - Add `pipeline_ran_at` timestamp to DecisionCard
  - Fast Plane checks `now - pipeline_ran_at > 48h` → attach `stale=True` flag to response
  - Never blocks response; makes stale state visible to ops without querying DB
  - Background: Fast Plane never calls pipeline — if Deep Plane has been failing silently,
    merchants receive expired decision cards with no visible indicator

- [ ] L0 DataSourceConnector Protocol [→ADR-0010]
- [ ] Shopline connector productionization [→ADR-0010]
  - Implements DataSourceConnector Protocol
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
- [~] YAML-based KG loader implementation [→ADR-0011]
  - [x] Loads from `playbooks/*.yaml` (existing)
  - [x] Validates against schema (PlaybookRegistry._validate_playbook_structure)
  - [x] Brand binding loader: `load_brand_binding(merchant_id)` — three-layer support
  - [x] Template rendering: `${thresholds.*}` interpolation via string.Template
  - [x] `get_base_utility()` with brand binding priority + gmv_lift_prior clip [0.0, 0.25]
  - [ ] Conforms to `KnowledgeGraph` Protocol (Phase 2 Track B, after L3 split)
- [x] Partner KG content translation workflow [→ADR-0011]
  - [x] Partner content format specification — see `docs/playbook_authoring_sop.md`
  - [x] Per-brand content directory structure — three-layer: `playbooks/meta/`,
    `playbooks/brands/{merchant_id}/`, `use_cases/{brand}/`
  - [ ] Validation pipeline for partner-submitted content
    (kg_dryrun.py covers meta-pattern validation; brand binding validation is Phase 2)
- [ ] L3 physical submodule split [→ADR-0003 revisit]
  - Create `l3_decision/candidate_proposal/`, `correlation/`, `policy/`, `scoring/`, `verification/`
  - Migrate code from `layer2_decision/` and `layer3_value/`
  - Update all imports
  - Rewrite affected tests
- [ ] LLM Renderer migration
  - Move from `layer2_decision/pillar3_llm/` to `layer4_serving/`
  - Update import paths
  - Verify renderer only consumes VerifiedDecision (boundary cleanup)
- [ ] DecisionVerifier migration
  - Currently physically in `layer2_decision/pillar3_llm/decision_verifier.py`
  - Conceptually belongs to L3.5 (Verification) — move to `layer3_value/` or new `l3_decision/verification/`
  - Blocked by L3 physical submodule split above
- [ ] LLMSafetyGateway (5-Gate Bouncer) migration
  - Currently physically in `layer2_decision/pillar3_llm/llm_safety_gateway.py`
  - Conceptually belongs to L4.3 (Card QA) — move to `layer4_serving/`
  - Move at same time as LLM Renderer migration (same physical directory)
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

## V3.1 Phase A — Pilot-Grade Single-Merchant System (parallel to Phase 2)

**Goal**: Ship production-grade Phase A — single-merchant, single-decision-card, deterministic-first — that establishes the contracts Phase B (Scout Lane, peer benchmark) will extend.

**Status**: ADRs proposed (2026-04-26); awaiting Codex review concurrence + SPIKE-014-01 entry. Implementation not started.

**Relationship to Phase 2**: Independent of Track A/B. V3.1 Phase A is a vertical slice through L0–L5 with new contracts; Track A/B continue on existing scope.

### Foundational ADRs (proposed, awaiting concurrence)
- [ ] ADR-0014: V3.1 Phase A Scope and Runtime Invariants [→ADR-0014]
- [ ] ADR-0015: Outcome Review v1 — Directional, Module-Aware, Post-Decision [→ADR-0015]
- [ ] ADR-0016: V3.1 Truth Philosophy — Multi-Source Truth, Disagreement Policy, Gate Explainability [→ADR-0016]

### Pending versioned spec docs (referenced by ADRs)
- [~] `docs/contracts/deterministic_canonicalization_v1.md` (in progress; ADR-0014 Invariant 2)
- [ ] `docs/contracts/snapshot_source_contract_v1.md` (ADR-0015 Contract 6)
- [ ] `docs/contracts/confidence_band_table_v1.md` (ADR-0015 Contract 4)
- [ ] `docs/operations/daily_snapshot_contract.md` (ADR-0014 Invariant 5)
- [ ] `docs/operations/disagreement_detection_v1.md` (ADR-0016 Invariant 2)
- [ ] `docs/operations/confidence_calibration_v1.md` (ADR-0015 Contract 4)

### New typed contracts (Pydantic, frozen=True)
- [ ] `DecisionCardV2` — 5-section card (observed / suspected / missing / first_fix / why) + abstain flag
- [ ] `MerchantResponseEvent` — append-only event log row
- [ ] `OutcomeReviewRecord` — directional post-decision review [→ADR-0015]
- [ ] `EvidenceCompleteness` — score + gaps + abstain recommendation
- [ ] `GateRejection` — structured Gate failure record [→ADR-0016 Invariant 3]
- [ ] `SnapshotPayload` — typed snapshot with source/completeness fields [→ADR-0015 Contract 6]
- [ ] `ConfidenceBreakdown` — uncertainty surfacing, not score-fusion [→ADR-0015 Contract 4]
- [ ] `DiagnosticOutcome` — co-observation outcome for DIAGNOSTIC actions [→ADR-0015 Contract 3]

### New runtime modules (non-contract code)
- [ ] `src/decision_engine/canonical/serializer_v1.py` — single canonicalizer for DETERMINISTIC sections; emits `canonical_hash` field with `v1:{sha256}` value [→`docs/contracts/deterministic_canonicalization_v1.md`]

### New DB tables (additive; no rename of existing tables)
- [ ] `decision_cards` (FK → `wsm_transitions_v3.transition_id`)
- [ ] `merchant_response_events` (append-only; row-locked state machine)
- [ ] `outcome_reviews` (one row per reviewed transition)
- [ ] `daily_signal_snapshot` (per-merchant, per-day, UTC; ADR-0014 Invariant 5)
- [ ] `evidence_completeness_log` (per-decision evidence-gap snapshot)

### Additive ALTER on existing tables
- [ ] `wsm_transitions_v3` — workstream_id (Phase B reserve, NULL in Phase A), abstain (BOOLEAN), abstain_reason

### Architecture invariant tests (new; CI-enforced)
- [ ] `tests/architecture/test_canonical_ids.py` — no `recommendation_id` / `decision_id` in new code [→ADR-0014 Invariant 1]
- [ ] `tests/architecture/test_gate_explainability.py` — every Gate emits complete `GateRejection` [→ADR-0016 Invariant 3]
- [ ] `tests/architecture/test_no_adapter_outside_phase_a.py` — `_adapters.py` imports gated to L4 serving [→ADR-0014 Invariant 6]
- [ ] `tests/architecture/test_resolver_dispatch.py` — outcome resolver dispatch invariant [→ADR-0015 Contract 3]
- [ ] `tests/architecture/test_snapshot_source_resolution.py` — no silent zero-substitution; fallback degrades confidence [→ADR-0015 Contract 6]
- [ ] `tests/architecture/test_single_canonicalizer.py` — assert no second canonicalizer of DETERMINISTIC sections (greps for stray `json.dumps(... sort_keys=...)`) [→`docs/contracts/deterministic_canonicalization_v1.md`]

### Frozen test corpus (canonicalization)
- [ ] `tests/canonical/test_canonicalization_v1_corpus.py` — 10 mandatory cases: round-trip stability, cross-platform stability, decimal-vs-float divergence, datetime `Z`/`+00:00` equivalence, NFC normalization, null-vs-empty distinction, list-vs-set semantics, special-float reject, naive-datetime reject, untagged-array reject [→`docs/contracts/deterministic_canonicalization_v1.md` §Testing Requirements]

### Contract Spike items (pilot blockers)
- [ ] **SPIKE-014-01**: `transition_id` type unification — int/UUID across 13 Python call sites + SQLite test fixture; pilot blocker (NOT GA blocker). See ADR-0014 Invariant 1 callout.
- [ ] **SPIKE-014-02**: Edit re-validation chain — verify DecisionVerifier → Renderer → 5-Gate Bouncer reentry semantics for `MerchantResponseEvent(event_type="edit")` [→ADR-0014 Invariant 3]
- [ ] **SPIKE-014-03**: State machine row-lock primitive — `SELECT FOR UPDATE` semantics in production DB; test concurrent approve/withdraw race [→ADR-0014 Invariant 4]
- [ ] **SPIKE-014-04**: Phase A adapter inventory — measure typed↔dict adapter call sites at `layer4_serving/_adapters.py`; if exceeds 20, escalate L4-rewrite-vs-adapter trade-off [→ADR-0014 Invariant 6]

### Two-Layer Acceptance
- [ ] **Engineering GA** (internal) — all contract tests pass, all architecture invariants pass, dogfood pipeline runs end-to-end on synthetic merchant
- [ ] **Pilot Exit** (external) — Engineering GA + all SPIKE-014-* resolved + canonicalization spec frozen at v1 + first real merchant approves at least one card

### Phase A → Phase B handoff requirements
- `_adapters.py` removed (Phase B Scout prerequisite per ADR-0014 Invariant 6)
- `OutcomeReviewRecord.skill_class` activated for sentinel/probe/debunk/repair (currently `None` in Phase A)
- `daily_signal_snapshot` retention extended; `weekly_signal_snapshot` aggregator built
- Per-merchant timezone support (deferred from Phase A; pilot ships UTC-only)

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
