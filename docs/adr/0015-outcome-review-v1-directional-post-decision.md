# ADR-0015: Outcome Review v1 — Directional, Module-Aware, Post-Decision Review

## Status
Proposed
Date: 2026-04-26

## Context
After every executed recommendation, the system must produce some form of
"how did it go?" record. The naïve framing is **outcome attribution**:
"this action caused $X uplift, attributed via window W." That framing is
wrong for V3.1 in two ways:

1. **Causally unsupported**: With a single merchant, no holdout group, and
   confounders we cannot fully enumerate (seasonality, ad platform changes,
   inventory shocks), the system cannot honestly produce causal claims.
   Producing them anyway pushes us into territory the data does not back.

2. **Commercially wrong-shaped**: ADR-0016 establishes that truth is
   multi-source and disagreement is a signal. An attribution engine
   collapses that posture into a single number. It also creates regulatory
   exposure (FTC substantiation standards apply to causal /
   revenue-denominated claims in CPG/DTC contexts).

V3.1 instead ships **Recommendation Outcome Review** — a directional,
module-aware, post-decision check that compares observed change against
expected direction. It is one of five truth sources (ADR-0016 Invariant 1),
not a canonical truth.

A second, separate problem: not every decision produces a
business-metric outcome. DIAGNOSTIC actions (e.g., "investigate why
checkout abandonment spiked") have structural progression outcomes
(evidence gap shrinks, advanced investigation triggered) but no direct
business metric to compare. The review schema must accommodate both
kinds without forcing diagnostic actions into a metric-delta frame they
don't fit.

## Decision

V3.1 ships Outcome Review v1 with the following six contracts.

### Contract 1 — `OutcomeReviewRecord` is directional, not attributional

```python
class OutcomeReviewRecord(BaseModel, frozen=True):
    review_id: str
    transition_id: str                    # canonical id; ADR-0014 Invariant 1
    merchant_id: str
    module: Literal["acquisition", "conversion", "retention", "promotion"]
    action_type: Literal[
        "DIAGNOSTIC", "FLOW_CHANGE", "CREATIVE_CONTROL",
        "PROMO_ACTION", "RETENTION_ACTION",
    ]
    skill_class: Literal["sentinel", "probe", "debunk", "repair"] | None  # Phase B

    executed_status: Literal["executed", "rolled_back", "expired_unexecuted"]
    review_window: ReviewWindow            # baseline_start, observed_start, observed_end

    baseline_snapshot: SnapshotPayload     # see Contract 6 for source resolution
    observed_snapshot: SnapshotPayload     # see Contract 6 for source resolution
    observed_delta: dict                   # per-metric deltas, descriptive

    expected_direction_by_metric: dict[str, Literal["up", "down", "neutral"]]
    direction_match_by_metric: dict[str, Literal["yes", "no", "inconclusive"]]

    confidence: ConfidenceBreakdown        # see Contract 4
    confounders: list[Confounder]          # known exogenous factors

    diagnostic_outcome: DiagnosticOutcome | None  # for action_type=DIAGNOSTIC; see Contract 3

    review_version: Literal["v1"]
    reviewed_at: datetime
```

The record contains **no field named `attributed_uplift`,
`incremental_revenue`, `caused_by`, or any equivalent**. Direction-match
is not attribution: it asks "did the metric move the way we predicted?"
not "how much did this action cause?"

### Contract 2 — Module is the MSM dimension; action_type is the action taxonomy
The earlier conflation of `module` and `action_type` is rejected. They are
orthogonal:

- `module ∈ {acquisition, conversion, retention, promotion}` — answers
  *which 4D MSM dimension* the decision targeted; this is a routing fact
  available at decision time
- `action_type ∈ {DIAGNOSTIC, FLOW_CHANGE, CREATIVE_CONTROL, PROMO_ACTION, RETENTION_ACTION}` —
  answers *what kind of action* was taken; this is a playbook output

A single module hosts multiple action types (e.g., the conversion module
issues both DIAGNOSTIC investigations and FLOW_CHANGE adjustments).
Routing logic, learning aggregation, and outcome resolver dispatch all
key on the (module, action_type) pair.

`skill_class` is reserved for Phase B (Scout Lane skills:
sentinel/probe/debunk/repair). It is `None` in Phase A.

### Contract 3 — Two outcome resolvers, dispatched by `action_type`
Outcome resolution is a `Protocol` with two implementations:

```python
class OutcomeResolver(Protocol):
    def resolve(
        self,
        record_inputs: ResolverInputs,
    ) -> OutcomeResolution: ...
```

**`MetricDeltaResolver`** — handles FLOW_CHANGE, CREATIVE_CONTROL,
PROMO_ACTION, RETENTION_ACTION. Compares observed_snapshot to
baseline_snapshot per metric, populates `expected_direction_by_metric`
and `direction_match_by_metric`. `diagnostic_outcome` is `None`.

**`DiagnosticOutcomeResolver`** — handles `action_type=DIAGNOSTIC`. Does
not require business-metric movement; instead populates
`diagnostic_outcome`:

```python
class DiagnosticOutcome(BaseModel, frozen=True):
    advanced_investigation: bool          # did this lead to a follow-up action?
    evidence_gap_delta: float             # change in evidence completeness score (CO-OBSERVATION, not causal)
    human_confirmed: bool                 # did the merchant confirm the diagnosis?
    elapsed_days: float                   # diagnostic-to-resolution time
```

`evidence_gap_delta` (renamed from earlier draft `evidence_gap_reduction`)
is explicitly a co-observation metric, not a causal effect. The field
docstring states this; aggregated distributions across many diagnostics
are informative, per-decision causal claims are not. v1 deliberately
excludes `hypothesis_correctness` and `diagnostic_value` as fields — both
require ground truth the system does not have at v1.

The dispatch rule is implemented in
`layer5_wsm/outcome_resolver_factory.py` and is an architecture invariant
(test: `tests/architecture/test_resolver_dispatch.py`).

### Contract 4 — Confidence breakdown surfaces uncertainty, not score-fusion

```python
class ConfidenceBreakdown(BaseModel, frozen=True):
    sample_size: int                          # observation window size
    baseline_stability_score: float           # 0.0-1.0; how stable was pre-action baseline
    confounder_count: int                     # number of known exogenous factors in window
    direction_signal_clarity: Literal["clear", "mixed", "inconclusive"]
    overall_band: Literal["high", "medium", "low", "inconclusive"]
```

`overall_band` is **not** a weighted average of the other fields. It is
derived by an explicit decision table that prefers `inconclusive` over
false certainty. This conforms to ADR-0016 Invariant 2 (no silent
averaging, no majority voting). The decision table is single-sourced in
`docs/contracts/confidence_band_table_v1.md`.

### Contract 5 — Merchant-facing wording is a product invariant, not a Gate rule
The terms used in merchant-visible Outcome Review summaries are
constrained by two lists:

```
FORBIDDEN_OUTCOME_TERMS = {
    "attributed ROI", "attributed uplift", "guaranteed uplift",
    "missed revenue", "caused by", "drove $", "incremental revenue",
}

ALLOWED_OUTCOME_TERMS = {
    "directional improvement", "directionally worse", "likely helped",
    "likely hurt", "inconclusive", "mixed signal", "no clear movement",
}
```

This is a **product + compliance invariant**, not merely a renderer
safeguard. The rationale is twofold:

1. **Product**: directional language preserves the merchant's role as
   decision-maker. Causal/revenue language replaces that role with a
   system claim, contradicting V3.1's positioning that *the merchant is
   the operator, the system is the analyst*.

2. **Compliance**: causal + revenue-denominated outcome statements
   approach marketing claims under FTC substantiation standards in
   CPG/DTC contexts. Directional / review-oriented framing is observation,
   not claim. Loosening this requires legal review, not product review.

Enforcement: the LLM Safety Gateway's outcome-summary gate produces a
`GateRejection` (per ADR-0016 Invariant 3) targeting the specific
forbidden term and the specific section that contains it.

### Contract 6 — Snapshot source resolution (`baseline_snapshot` / `observed_snapshot`)

Two pre-existing data sources can supply baseline metrics, and they are
**not equivalent**:

| Source | Window | Written when | Already exists? |
|--------|--------|--------------|-----------------|
| `wsm_transitions_v3.baseline_snapshot` (JSONB) | 30d rolling at decision time | At decision execution | Yes — see [sql/001_wsm_transition_v3.sql:21](../../sql/001_wsm_transition_v3.sql#L21) |
| `daily_signal_snapshot` (Phase A new table) | Per-metric class (state / daily_aggregate / window) | 00:00 UTC daily | No — Phase A delivery (ADR-0014 Invariant 5) |

The Outcome Review resolver MUST NOT silently choose between them.
Phase A v1 locks the following resolution contract:

```python
class SnapshotPayload(BaseModel, frozen=True):
    metrics: dict[str, MetricValue]    # metric_id → value (typed, not raw dict)
    source: Literal[
        "daily_signal_snapshot",       # primary
        "wsm_transition_baseline",     # fallback for action-time baseline only
    ]
    snapshot_taken_at: datetime        # when the underlying data was captured
    completeness: Literal["complete", "partial", "missing"]
    missing_metrics: list[str]         # explicit; never silent
```

**Resolution rules** (single-sourced; the resolver MUST NOT deviate):

1. **`baseline_snapshot`** is resolved by `review_window.baseline_start`:
   - Primary source: `daily_signal_snapshot` row at `baseline_start`
   - Fallback (only if daily_signal_snapshot is missing or has the
     `data_present=False` sentinel for that day): use
     `wsm_transitions_v3.baseline_snapshot` from the originating
     transition; mark `source="wsm_transition_baseline"` and
     `completeness="partial"`
   - The fallback is **action-time** baseline (30d rolling at decision
     time), not review-window baseline; downstream confidence band
     MUST degrade by one step when fallback is used (per ADR-0016
     Invariant 2 — disagreement-aware degradation)

2. **`observed_snapshot`** is resolved by `review_window.observed_end`:
   - Primary source: `daily_signal_snapshot` row at `observed_end`
   - **No fallback** — observed snapshots have no action-time analog.
     Missing observed snapshot MUST set `completeness="missing"` and the
     resolver MUST mark `direction_signal_clarity="inconclusive"`
     (Contract 4)

3. **Per-metric class semantics** (deferring to ADR-0014 Invariant 5):
   - `state` metrics: read snapshot value at the window endpoint
   - `daily_aggregate` metrics: read the day's aggregate
   - `window` metrics: the snapshot already represents the rolling
     window declared per-metric — no further aggregation by the resolver

4. **Silent zero-substitution is forbidden.** Missing metrics propagate
   to `missing_metrics: list[str]`. The resolver never writes `0.0` for
   "unknown" — that is a known anti-pattern from V0/V2 and is the source
   of multiple silent direction-flip bugs.

The bit-level resolution table (which metric class falls to which
source under which conditions) lives in
`docs/contracts/snapshot_source_contract_v1.md`. ADR-0015 locks the
**principles** above; the spec doc owns the per-metric mapping.

## Alternatives Considered

**Outcome Attribution v1**: Build a causal attribution engine with
counterfactual estimation. Rejected — Phase A has no holdout group, no
peer baseline (deferred to Phase B), and a single-merchant data volume
that does not support reliable causal estimation. Producing causal
numbers anyway is dishonesty.

**Single resolver with metric-delta only**: Force DIAGNOSTIC actions
through `MetricDeltaResolver` with synthetic metrics. Rejected — this
either invents metrics that don't exist (corrupting the snapshot
contract) or marks all diagnostics as `inconclusive` (destroying the
learning signal from diagnostic actions). Two resolvers is the correct
factoring.

**Per-record `expected_direction` (single value)**: Rejected —
direction expectation is per-metric. A single FLOW_CHANGE may expect
CVR up *and* bounce-rate down; collapsing these into one direction
loses information.

**Encode merchant-facing wording in the LLM prompt only**: Rejected —
prompt-based enforcement is bypassable (a future engineer adjusts the
prompt and forbidden terms slip through). The Gate-based enforcement
with explicit forbidden/allowed lists is auditable and version-controlled.

**Defer Outcome Review to Phase B**: Rejected — Phase A produces
decisions that need to be reviewed; without Outcome Review, there is no
input to the learning loop, no calibration of confidence bands, and no
honest "did this work?" signal for the pilot merchant.

**Reuse `wsm_transitions_v3.baseline_snapshot` as the sole baseline
source (skip `daily_signal_snapshot`)**: Rejected — the existing
field is *action-time* 30d rolling, not *review-window* baseline. Using
it as primary baseline would silently change the comparison frame
("we recommended this when X looked like A; how does X look at the end
of the review window?" becomes "how does X look now vs. its 30d rolling
average from action time?"), which is a different question with
different statistical properties. The fallback path in Contract 6
explicitly degrades confidence to flag this when it does happen.

## Consequences

### Positive
- Outcome records are honest about what they measure (direction, not
  causation) — eliminates a class of overclaim risk
- Two-resolver design accommodates DIAGNOSTIC actions without polluting
  the metric-delta frame
- Per-metric direction expectation captures decisions that target
  multiple metrics simultaneously (common in conversion module)
- Merchant-facing wording invariant doubles as compliance posture —
  loosening it now requires legal review, not just product review
- Outcome Review serves as one of five truth sources (ADR-0016
  Invariant 1) — its disagreement with merchant edits / rejections /
  verification becomes a learning signal rather than an aggregation problem

### Negative
- Two resolvers is more code than one; dispatch logic must be tested
  per architecture invariant (no silent fallback)
- `direction_match_by_metric: dict` is heavier in storage than a single
  enum, but the per-metric granularity is load-bearing
- v1 deliberately ships without `hypothesis_correctness` and
  `diagnostic_value`, which limits diagnostic-action learning depth
  until Phase B can establish a peer-baseline ground truth

### Neutral
- This ADR does not specify how Outcome Review interacts with the
  bandit / learning fabric — that is a Phase 3 concern (ADR-0008)
- This ADR does not specify how confidence bands are recalibrated over
  time — recalibration is a separate operational process documented in
  `docs/operations/confidence_calibration_v1.md` (pending)
- DIAGNOSTIC outcomes do not feed the same aggregation pipeline as
  metric-delta outcomes; this is by design (different statistical regimes)

## When to Revisit

- **Pilot merchant requests "how much did this make me?" framing**: This
  is the most likely pressure to loosen Contract 5. The correct response
  is to revisit the Phase B peer-benchmark roadmap, not to soften the
  invariant
- **Phase B onboards Scout Lane**: `skill_class` field activates;
  `OutcomeReviewRecord` v2 may be needed to add Scout-specific outcome
  fields
- **Diagnostic action volume permits causal estimation**: If aggregated
  diagnostic outcomes across many merchants reach a sample size where
  hypothesis_correctness becomes estimable, revisit Contract 3 to add
  `hypothesis_correctness` and `diagnostic_value`
- **Confidence bands consistently too conservative**: If `overall_band`
  is `low` or `inconclusive` more than 50% of the time over a sustained
  window, the decision table in `confidence_band_table_v1.md` needs
  recalibration — this is not a v1 → v2 ADR change; it's an operational
  table update
- **A sixth action_type is proposed**: Adding a Literal value requires
  resolver dispatch coverage; revisit Contract 3's dispatch invariant test

## References
- ADR-0016 (V3.1 Truth Philosophy) — Outcome Review is one of five
  truth sources (Invariant 1); confidence band derivation conforms to
  no-silent-averaging (Invariant 2); rejection emits structured
  `GateRejection` (Invariant 3)
- ADR-0014 (Phase A Scope) — `transition_id` canonicalization (Invariant 1),
  `daily_signal_snapshot` baseline source (Invariant 5)
- ADR-0009 (Evidence Graph Snapshot) — diagnostic outcomes consume the
  snapshot's evidence chain to compute `evidence_gap_delta`
- ADR-0008 (LinUCB Bandit) — Phase 3 learning loop consumes
  `OutcomeReviewRecord`; v1 contract must be stable enough that Phase 3
  doesn't require re-keying
- `V3/CLAUDE.md` — Core Philosophy ("Determinism over Probability"),
  CPG Hard Constraints (attribution windows: Retention 7d / Acquisition
  30d / Promotion 14d / Conversion instant — used by `ReviewWindow`)
- `docs/contracts/confidence_band_table_v1.md` (pending) — decision
  table referenced by Contract 4
- `docs/contracts/snapshot_source_contract_v1.md` (pending) — bit-level
  per-metric source resolution table referenced by Contract 6
- `docs/operations/confidence_calibration_v1.md` (pending) —
  recalibration process for confidence bands
- `tests/architecture/test_resolver_dispatch.py` (pending) — Contract 3
  dispatch invariant
- `tests/architecture/test_snapshot_source_resolution.py` (pending) —
  Contract 6 invariant: no silent zero-substitution, fallback always
  degrades confidence band
