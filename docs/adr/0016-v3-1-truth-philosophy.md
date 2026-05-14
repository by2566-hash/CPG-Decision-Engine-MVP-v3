# ADR-0016: V3.1 Truth Philosophy — Multi-Source Truth, Disagreement Policy, and Gate Explainability

## Status
Proposed
Date: 2026-04-26

## Context
V3.1 introduces three new mechanisms that all make implicit claims about
"what is true": Recommendation Outcome Review (post-hoc directional check),
merchant edits and rejections (operator-side feedback signals), and the
Scout Lane / peer benchmark (cross-merchant baseline, Phase B). Each of
these is a *truth source*, and each can disagree with the others.

Without an explicit philosophy, three failure modes are likely:

1. **Single-source overreach**: One module (e.g., Outcome Review) is
   informally treated as "the truth," and other signals are quietly
   discarded. This is brittle — every truth source has a known blind spot
   (Outcome Review can't see confounders; merchant edits conflate
   disagreement with operator preference; peer benchmark doesn't account
   for merchant-specific positioning).

2. **Silent averaging**: Engineers facing disagreement smooth it into a
   weighted score and present apparent certainty downstream. Disagreement
   carries information about the world; averaging destroys it.

3. **Gate bureaucracy**: As Phase A adds new Gates (deterministic section
   gate, role-contract gate, disagreement gate), failure messages drift
   toward "Gate X rejected this candidate" without localizing *which
   field* or *which clause* triggered the rejection. The system gains
   safety theater without actionable explainability.

ADR-0014 (Phase A Scope) and ADR-0015 (Outcome Review v1) both reference
truth-related decisions. They need a foundational ADR that names the
philosophy explicitly so future modules don't each invent their own.

## Decision

V3.1 commits to three operational invariants. All three are
**system-level**, not module-local — every component that produces or
consumes truth signals must conform.

### Invariant 1 — Truth is multi-source
The system recognizes five distinct truth sources, each with a defined
role and known blind spot:

| Source | Role | Known blind spot |
|--------|------|------------------|
| **Verification** (L3.5) | Internal consistency at decision time | Cannot detect external reality mismatch |
| **Outcome Review** (L5, ADR-0015) | Post-hoc directional check vs. baseline | Confounded by exogenous events |
| **Merchant edits** | Operator-side correction signal | Conflates "wrong" with "operator preference" |
| **Merchant rejections** | Hypothesis mismatch signal | Silent on *why* the hypothesis was rejected |
| **Peer benchmark** (Phase B) | Cross-merchant structural baseline | Insensitive to merchant-specific positioning |

No single source is canonical. A claim labeled "true" by exactly one
source carries lower confidence than one corroborated across two or more
sources. This is non-negotiable.

### Invariant 2 — Disagreement is a signal, not noise
When two or more truth sources disagree about the same proposition, the
system has exactly **three legal responses**:

1. **Degrade confidence** — emit the recommendation with a lower
   confidence band; surface the disagreement in the rendered card
2. **Abstain** — emit no recommendation; return Evidence Gap card; log
   `disagreement_event` to L5
3. **Escalate to human review** — flag for merchant adjudication; do not
   auto-resolve

The system **MUST NOT**:
- silently average across disagreeing sources to produce a single score
- apply majority voting that suppresses minority-source signal
- drop the lowest-confidence source as "noise" without logging

**Transient vs. persistent disagreement.** Disagreement observed within
a single metric latency window (e.g., daily snapshot lag) is *transient*
and is tolerated with a logged `disagreement_event(transient=True)`.
Disagreement persisting across two or more snapshot cycles is
*persistent* and MUST trigger one of the three legal responses above.

### Invariant 3 — Every Gate is explainable
Every Gate that can reject a candidate, card, or outcome MUST emit a
structured rejection record conforming to:

```python
GateRejection(BaseModel, frozen=True):
  gate_id: str                    # canonical gate name, e.g. "deterministic_section_gate"
  target_section: str             # e.g. "DecisionCardV2.observed"
  target_field: str | None        # e.g. "observed.metric_id"
  clause_id: str                  # canonical rule id, e.g. "DSG-002-numeric-precision"
  human_reason: str               # short, operator-readable explanation
  raw_input_hash: str             # for repro / audit
  rejected_at: datetime
```

A Gate rejection without all of `gate_id` / `target_section` / `clause_id`
is a contract violation and is itself a test failure. Test invariant:
`tests/architecture/test_gate_explainability.py` walks all Gate
implementations and asserts every reject path produces a complete
`GateRejection`.

The principle behind this invariant: **truth discipline that the team
cannot reason about becomes gate bureaucracy.** Explainability is not a
feature of Gates — it is the precondition for adding new Gates at all.

## Alternatives Considered

**Single-source truth (e.g., Outcome Review as canonical)**: Rejected.
Every truth source has a known blind spot (table above). Designating one
as canonical exports those blind spots into every downstream decision
and makes the system fragile to that source's failure modes.

**Probabilistic ensemble across truth sources**: Rejected. An ensemble
that produces a single confidence score *is* silent averaging. Even with
weights, disagreement information is destroyed at the aggregation step.
Disagreement-as-signal is incompatible with score-fusion architectures.

**Defer truth philosophy until Phase B**: Rejected. Phase A already
takes implicit positions (e.g., the choice of `expected_direction` per
metric in OutcomeReviewRecord assumes a directional, not causal, truth
posture). Better to make the position explicit now, so ADR-0014 and
ADR-0015 can reference it as a foundation.

**Encode Gate explainability as best practice rather than invariant**:
Rejected. The user explicitly flagged the failure mode ("Gate failed but
team doesn't know why"). Best practices that aren't enforced by tests
decay; an architecture invariant test does not.

## Consequences

### Positive
- Future modules (Scout Lane, peer benchmark, LLM judge if ever
  introduced) inherit a coherent truth posture by default
- `abstain` is normalized as a first-class system outcome, not a failure
  mode — this is the correct semantics for an explainability-first system
- Disagreement events become a learning signal: aggregated across many
  decisions, they identify which truth sources are systematically out of
  alignment, and which propositions the system is structurally bad at
- Gate explainability invariant prevents the "safety theater" failure
  mode where the system blocks decisions without actionable diagnostics

### Negative
- More verbose Gate implementations (every reject path must populate the
  full `GateRejection` schema)
- More code paths to maintain ("what to do when sources disagree" is now
  a first-class concern, not an edge case)
- Disagreement events add log volume; L5 snapshot retention must account
  for them

### Neutral
- This ADR does *not* specify which truth sources are consulted at which
  decision point — that is the job of ADR-0014 (Phase A Scope) and the
  per-module operational specs
- This ADR does *not* specify the implementation of the disagreement
  detector — that is an operational concern, see
  `docs/operations/disagreement_detection_v1.md` (to be written)
- This ADR does *not* attempt to define "truth" philosophically. It
  defines the *posture* the system takes when claims about truth are
  produced and consumed

## When to Revisit

- A sixth truth source is proposed (e.g., LLM-as-judge, external auditor
  feedback). New sources require updating the table in Invariant 1 and
  reconsidering disagreement semantics with N+1 sources
- Abstain rate exceeds 25% sustained over a 30-day window — this signals
  thresholds are too tight, or the system is being asked to decide on
  domains where it structurally lacks evidence
- A new Gate is introduced without `GateRejection` conformance and slips
  into main — this is a discipline-drift signal, revisit the invariant's
  enforcement mechanism (CI gate? mandatory ADR? both?)
- Phase B onboards Scout Lane and peer benchmark. At that point, the
  five-source table grows operational weight and may need a sub-ADR per
  source (e.g., "Peer benchmark truth contract")

## References
- `V3/CLAUDE.md` — Core Philosophy section ("Determinism over Probability",
  "Explainability IS the product")
- ADR-0001 — `PolicyDecision` is itself an explainable-rejection contract
  and is the prior art for `GateRejection`
- ADR-0009 — `EvidenceGraphSnapshot` is the trace mechanism that makes
  per-claim explainability possible at decision time
- ADR-0014 (pending) — Phase A Scope and runtime invariants; references
  this ADR's truth posture
- ADR-0015 (pending) — Outcome Review v1 as one of the five truth sources;
  references Invariant 1 and Invariant 2
- `docs/operations/disagreement_detection_v1.md` (pending) —
  implementation-level disagreement detector spec
- `tests/architecture/test_gate_explainability.py` (pending) — invariant
  test for `GateRejection` conformance across all Gates
