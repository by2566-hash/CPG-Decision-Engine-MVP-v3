# ADR-0014: Phase A Scope and Runtime Invariants

## Status
Proposed
Date: 2026-04-26

## Context
V3.1 is delivered in two phases. Phase A ships a single-merchant,
single-decision-card, deterministic-first system that establishes the
contracts on which Phase B (Scout Lane, peer benchmark, multi-card
workstreams, LLM-driven candidate expansion) will build. Phase A is not
a prototype — it must be production-grade for pilot merchants — but it
deliberately excludes any feature that cannot be shipped without
introducing learning loops, cross-merchant signals, or non-deterministic
candidate generation.

Without an explicit scope ADR, three drift modes are likely:

1. **Feature creep into Phase A**: "We can just add Scout-style probing
   here" — and Phase A's deterministic guarantees quietly erode.
2. **Implicit contract drift**: Field names, state machines, and edit
   semantics are decided in code review rather than in a contract,
   making Phase B integration a re-implementation rather than an
   extension.
3. **Adapter sprawl**: Temporary glue introduced for Phase A
   (typed-object → dict adapters at L4) becomes permanent because no
   ADR records its removal as a Phase B precondition.

This ADR locks Phase A's runtime invariants — the contracts, identifiers,
edit boundaries, state machine, and adapter strategy — and references
ADR-0016 for the truth posture all Phase A components must conform to.

## Decision

Phase A ships with the following six runtime invariants. Each is
contract-level (Pydantic models, DB schema, or architecture invariant
test), not implementation guidance.

### Invariant 1 — Canonical identifier: `transition_id`
The canonical primary identifier for every decision, card, and outcome
record is `transition_id`. This name is used identically across:

- Database column names — `wsm_transitions_v3.transition_id` already
  exists as `UUID PRIMARY KEY` (see `sql/001_wsm_transition_v3.sql`);
  Phase A's new tables (`decision_cards`, `merchant_response_events`,
  `outcome_reviews`) reuse this name as the FK column
- Pydantic model fields — no `recommendation_id`, no `id`, no `decision_id`
- HTTP API request/response shapes
- Internal log structured fields

**Current repo state (2026-04-27)**: `transition_id` is already the
canonical name in the SQL schema and in `WSMTransition` (see
[contracts.py:465](../../src/decision_engine/contracts.py#L465)). No
alias such as `recommendation_id` exists in the codebase. This ADR
formalizes the existing choice as an **invariant going forward**, not
as a rename project. The work this ADR creates:

- Phase A's new tables (`decision_cards`, `merchant_response_events`,
  `outcome_reviews`) MUST adopt `transition_id` as the FK column name —
  no per-table renaming
- An architecture invariant test
  (`tests/architecture/test_canonical_ids.py`) greps the codebase for
  `recommendation_id` and `decision_id` outside explicitly allowlisted
  historical-doc files; any *new* occurrence fails CI

**Known type-mismatch — Contract Spike item, not a local fix
(2026-04-28)**: The SQL schema declares `transition_id UUID` but the
Python codebase declares it as `int` / `Optional[int]` across 13 call
sites in 6 modules (L3 rollback / L3 approval / L3 feedback / L4 API /
DB client / contracts), and the test fixture
[tests/conftest.py:45](../../tests/conftest.py#L45) uses
`INTEGER PRIMARY KEY AUTOINCREMENT`. This is **not a `contracts.py`-local
type rename**. The discrepancy carries three distinct contract
surfaces:

1. **Type surface** — 13 Python call sites declared `int` / `Optional[int]`
2. **ID-assignment surface** — `Optional[int] = None` implies DB-assigned
   post-insert; UUID can be assigned client-side pre-insert. Picking one
   is a contract decision, not a typing decision.
3. **Test-coverage surface** — SQLite fixture's `INTEGER AUTOINCREMENT`
   means tests never exercise UUID handling. Switching prod code to UUID
   without updating the fixture creates a class of bugs that pass tests
   and fail in pilot.

This is a Phase A **Contract Spike checklist item**
(`SPIKE-014-01: transition_id type unification`), not a backlog ticket.
It blocks Phase A pilot launch — runtime bugs from int/UUID coercion
across this many surfaces are not safe to ship to a real merchant. It
does not, however, block this ADR's canonicality decision: the
*identifier name* is locked here; the *type and assignment semantics*
are settled in the spike.

### Invariant 2 — Deterministic section canonicalization
Phase A's `DecisionCardV2` partitions fields into `DETERMINISTIC` and
`LLM_RENDERABLE` sections (see ADR-0015 for the Outcome Review parallel).
DETERMINISTIC sections MUST be byte-identical across re-renders given
identical inputs.

Canonicalization rules are defined in
`docs/contracts/deterministic_canonicalization_v1.md` and versioned
independently from this ADR. Any change to the canonicalization rules
requires bumping the contract version (e.g., `v1` → `v2`) and is
backward-incompatible by default.

The principle this ADR locks (the spec doc fills in bit-level rules):

- Re-rendering the same DETERMINISTIC input MUST produce byte-identical
  output, modulo the rules in the versioned spec
- The Deterministic Section Gate rejects any output whose canonical hash
  differs from the canonical hash of its input
- The canonicalization spec is single-sourced — no module-local
  serializer is permitted

This is a contract, not a recommendation. A second canonicalizer in the
codebase is an architecture violation.

### Invariant 3 — Edit whitelist (LOCKED vs EDITABLE fields)
Merchant edits to a `DecisionCardV2` are constrained by two
field-pattern sets, defined as constants in `contracts.py`:

```python
EDITABLE_FIELD_PATTERNS = frozenset({
    "first_fix.action_params.*",        # operator can adjust action knobs
    "first_fix.scheduled_for",          # operator can reschedule
    "first_fix.notes",                  # operator can annotate
})

LOCKED_FIELD_PATTERNS = frozenset({
    "observed.*",                       # observed facts are not editable
    "suspected.*",                      # hypothesis is system output, not operator input
    "missing.*",                        # evidence-gap analysis is system output
    "why.*",                            # explanation is bound to the decision trace
    "abstain", "abstain_reason",        # abstain is system-determined
    "schema_version", "card_id",
    "workstream_id",
})
```

Any field not matching `EDITABLE_FIELD_PATTERNS` is locked.

After every edit, the system MUST re-run the full validation chain
(DecisionVerifier → Renderer → 5-Gate Bouncer). An edit that produces an
invalid card is rejected with a `GateRejection` (per ADR-0016 Invariant
3) targeting the specific edited field. The edit event is still logged
as a `MerchantResponseEvent(event_type="edit", payload.validation_result="rejected")`.

### Invariant 4 — Append-only response state machine
Merchant responses to a card form an append-only event log
(`merchant_response_events` table) with a 7-state state machine:

```
States: PROPOSED → DEFERRED | EDITED | APPROVED | REJECTED | WITHDRAWN | EXPIRED

Legal transitions:
  PROPOSED → DEFERRED       (operator postpones)
  PROPOSED → EDITED         (operator edits; validation must pass)
  PROPOSED → APPROVED       (operator approves)
  PROPOSED → REJECTED       (operator rejects; HARD TERMINAL)
  PROPOSED → EXPIRED        (TTL elapsed)
  DEFERRED → EDITED | APPROVED | REJECTED | EXPIRED
  EDITED   → EDITED | APPROVED | REJECTED | EXPIRED  (multiple edits permitted)
  APPROVED → WITHDRAWN      (within rollback TTL only; SOFT TERMINAL)
  REJECTED → (none)         (HARD TERMINAL — no recovery)
  WITHDRAWN → (none)        (HARD TERMINAL after rollback executed)
  EXPIRED → (none)          (HARD TERMINAL)
```

Terminal semantics:
- `REJECTED` is **hard terminal** — no transition out. The merchant
  must produce a new card (new `transition_id`) to act on the same
  underlying state.
- `APPROVED` is **soft terminal** — it permits exactly one transition,
  to `WITHDRAWN`, and only within the rollback TTL window
  (default 48h, see CPG Hard Constraints). After TTL, `APPROVED` becomes
  hard terminal.
- `WITHDRAWN` requires a `parent_event_id` referencing the specific
  approve event being withdrawn. Withdrawals without a parent reference
  are rejected.

Concurrency: state transitions MUST acquire a row-level lock on the
latest event for the given `transition_id` via `SELECT FOR UPDATE`
before inserting a new event. The `StateTransitionValidator` is the
sole authority — no module may insert into `merchant_response_events`
bypassing it.

### Invariant 5 — Daily signal snapshot contract
Outcome Review (ADR-0015) requires a historical snapshot of merchant
state to compute baselines. Phase A ships `daily_signal_snapshot` with
the following operational contract (full spec:
`docs/operations/daily_snapshot_contract.md`):

- **Timezone**: All snapshots are taken at 00:00 UTC. Per-merchant local
  timezone snapshots are deferred to Phase B.
- **Metric class semantics**:
  - `state` metrics: snapshot value at 00:00 UTC
  - `daily_aggregate` metrics: sum/avg over the preceding UTC day
  - `window` metrics: sum/avg over the preceding N UTC days, with N
    declared per metric
- **Backfill window**: Append-only metrics tolerate up to 7 days of
  late-arriving data. Snapshots older than 7 days are frozen.
- **Missing-day sentinel**: A day with no data writes a sentinel row
  with `data_present=False`; the resolver treats this as inconclusive
  rather than zero (silent zero substitution is a known anti-pattern).
- **Retention**: 90 days. Older rows are aggregated to weekly summary
  in a separate `weekly_signal_snapshot` (Phase B).

### Invariant 6 — Phase A adapter strategy
Phase A introduces typed Pydantic objects at L3 boundaries while L4
serving code (pipeline glue, cache, API) still consumes legacy dict
shapes in places. To bridge this without a full L4 rewrite, Phase A
permits exactly one adapter module:

- Location: `layer4_serving/_adapters.py`
- Scope: typed-Pydantic ↔ legacy-dict translation only
- Underscore prefix and `_` suffix on public symbols enforce
  "internal use only" semantics
- Architecture invariant test
  (`tests/architecture/test_no_adapter_outside_phase_a.py`) asserts:
  (a) no other module imports from `_adapters` outside L4 serving,
  (b) the module is marked deprecated as of Phase B kickoff

Adapter removal is a **Phase B Scout prerequisite**. Scout Lane MUST NOT
ship while `_adapters.py` exists. This is enforced at the Phase B
kickoff gate, not on a per-PR basis.

## Alternatives Considered

**Ship Phase A and Phase B together as a single release**: Rejected.
Phase B requires learning data Phase A produces (response events,
outcome reviews, edit logs). Bundling them means either Phase B ships
without enough data or Phase A is delayed by Phase B's complexity. The
two-phase split is the dependency order, not a marketing choice.

**Permit alternate id names (e.g., `recommendation_id`, `decision_id`)
in Phase A's new tables for "domain readability"**: Rejected. The
existing `wsm_transitions_v3.transition_id` is the join key for every
downstream table (cards, events, outcomes); introducing an alternate
name in any new table would create a class of join bugs and force
per-table id-translation logic. The single canonical name is cheaper.

**Permit per-module deterministic serializers**: Rejected. The whole
point of a deterministic Gate is bit-level reproducibility. Multiple
serializers means multiple definitions of "the same input" — the Gate
becomes a coin flip.

**Make `APPROVED` hard terminal and require a new card for rollback**:
Rejected. Rollback within TTL is a CPG hard constraint (see CLAUDE.md);
forcing a new card per rollback adds friction to a safety-critical
operation. Soft-terminal-with-TTL is the correct trade-off.

**Defer the adapter and rewrite L4 to typed objects directly in Phase A**:
Rejected. Scope explosion. The adapter is acknowledged tech debt with
an explicit removal gate; rewriting L4 in Phase A delays pilot launch
without changing pilot semantics.

## Consequences

### Positive
- Phase B integration is a typed extension, not a re-implementation
- `transition_id` as a single canonical name eliminates a class of
  cross-table join bugs and renames the system around its actual primary
  unit (a state transition, not a recommendation)
- Edit whitelist + re-validation chain prevents the "merchant edited the
  hypothesis to match their preferred conclusion" failure mode
- State machine row-locking eliminates the concurrent-approve /
  concurrent-withdraw race condition class
- Adapter removal gate prevents the most common Phase A → Phase B
  failure mode (temporary glue becoming permanent)

### Negative
- Edit re-validation chain adds latency to the merchant edit loop
  (acceptable: edits are not on the hot path)
- 7-state state machine is more complex than a 3-state (proposed /
  accepted / rejected) version, but the additional states (DEFERRED,
  EDITED, WITHDRAWN, EXPIRED) carry real semantics that are needed
- Daily snapshot at UTC may produce off-by-one-day artifacts for
  merchants in distant time zones; documented and accepted for Phase A

### Neutral
- This ADR does not specify the Outcome Review schema — see ADR-0015
- This ADR does not re-specify the truth posture — see ADR-0016
- Pilot merchants in non-UTC time zones receive a documented operational
  caveat; full timezone support is on the Phase B roadmap

## When to Revisit

- **`SPIKE-014-01` resolution**: Once the transition_id type-unification
  spike completes (all 13 Python call sites + test fixture conform to
  UUID, with ID-assignment semantics chosen and documented), remove the
  "Known type-mismatch — Contract Spike item" callout in Invariant 1
  and add a one-line "resolved 2026-MM-DD per SPIKE-014-01" note
- **Canonicalization spec hits v2**: If the canonicalization rules are
  amended in a backward-incompatible way, this ADR's reference to "v1"
  must be reviewed to ensure Phase A still meets its determinism guarantee
- **Adapter usage exceeds 20 call sites**: If `_adapters.py` accretes
  more surface area than expected, the L4 rewrite-vs-adapter trade-off
  must be re-evaluated before Phase B
- **State machine grows an 8th state**: Adding a state requires
  superseding this ADR — concurrency semantics of the 7-state machine
  are load-bearing
- **Pilot merchant requests local-timezone snapshots**: Documented as
  Phase B; if pilot blocks on this, escalate the Phase B scope decision

## References
- ADR-0016 (V3.1 Truth Philosophy) — Phase A's truth posture and Gate
  explainability invariant; this ADR's runtime contracts must conform
- ADR-0015 (Outcome Review v1) — uses `transition_id` (Invariant 1) and
  `daily_signal_snapshot` (Invariant 5)
- ADR-0001 (PolicyDecision) — prior art for typed contract objects;
  Invariant 3's edit re-validation re-uses the PolicyDecision chain
- ADR-0009 (Evidence Graph Snapshot) — the trace mechanism that
  Invariant 3's re-validation produces an updated snapshot for
- `V3/CLAUDE.md` — CPG Hard Constraints (rollback TTL = 48h, referenced
  in Invariant 4)
- `docs/contracts/deterministic_canonicalization_v1.md` (pending) —
  bit-level spec referenced by Invariant 2
- `docs/operations/daily_snapshot_contract.md` (pending) — operational
  contract referenced by Invariant 5
- `tests/architecture/test_canonical_ids.py` (pending)
- `tests/architecture/test_no_adapter_outside_phase_a.py` (pending)
