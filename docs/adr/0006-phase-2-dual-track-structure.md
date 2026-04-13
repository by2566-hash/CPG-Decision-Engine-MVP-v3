# ADR-0006: Phase 2 Dual-Track Structure

## Status
Accepted
Date: 2026-04-09

## Context
Initial Phase 2 planning in the V3 README combined two fundamentally different types of work:

**Commercial activation work** (blocking first paying customer):
- Real Shopline data ingestion
- LLM API for merchant copy rendering
- Web Dashboard + approval workflow
- First paying customer onboarding
- Performance billing

**Architectural deepening work** (improving system quality):
- KG content translation from partner documents
- L3 physical submodule split
- Document compiler
- Multi-brand fixtures

The problem: these items have incompatible blocking conditions and dependency chains.

Commercial activation is blocked on **Shopline integration** — no real data means no real MSM
signals, no real DecisionCards, no paying customer. Once Shopline is live, the rest of Track A
can proceed quickly.

KG content work is blocked on **partner delivery cadence** — a human team must translate domain
expertise into typed YAML. This cannot be parallelised with Shopline integration because it
depends on a different external party. It also cannot block the first paying customer.

A dependency analysis in session 2026-04-09 further revealed that the original Phase 2 had
a dependency inversion: it attempted to defer Shopline data ingestion to Phase 3 (treating
it as a "learning layer" concern), while Phase 2 commercial activation assumed real signals
existed. This was incoherent — the connector is a prerequisite for commercial activation,
not an optimisation.

## Decision
Phase 2 splits into two parallel tracks with independent progress and blocking conditions.

**Track A — Commercial Activation** (blocks first paying customer):
1. Shopline connector productionization (orders, inventory, catalog → real MSM signals)
2. Real LLM API integration (replace DeterministicRenderer)
3. External write APIs (Shopline action execution for approved recommendations)
4. Web Dashboard + one-click merchant approval workflow
5. First paying customer onboarding
6. ImpactCalculator upgrade (confidence scales above 30% as `was_executed=True` data accumulates)
7. Performance billing infrastructure (built in Track A; first charge deferred to first complete
   30-day reward cycle)

**Track B — Architecture & KG Deepening** (partner-dependent, independent of Track A):
1. KG Protocol interface + YAML loader implementation
2. Partner KG content translation workflow establishment
3. L3 physical submodule split (ADR-0003 execution)
4. LLM Renderer migration from `layer2_decision/` to `layer4_serving/`
5. `CorrelatedCandidate` Pydantic typing
6. Second real brand fixture for regression testing

**Dependency between tracks**: None in Phase 2 — Track A is not blocked by Track B and
vice versa. They reinforce each other (Track A produces real execution data that Phase 3
learning needs; Track B improves DecisionCard quality that Track A delivers to customers)
but do not block each other.

**Phase 3 entry condition**: Track A complete AND 6+ months of real action_log with outcomes.
Track B items not completed in Phase 2 continue into Phase 3 alongside learning work.

## Alternatives Considered

**Single Phase 2 with all items mixed**: One phase list combining commercial activation,
KG work, and architecture split. Rejected — combining items with different blocking conditions
makes it impossible to report progress clearly. "Phase 2 is 70% done" is meaningless when
some items are 100% done (Shopline connector) and others are 0% (KG content) due to external
dependencies.

**Three separate phases (commercial / architecture / KG)**: Treat KG content translation as
a fully independent Phase 2b. Rejected — architecture work (L3 split, Renderer migration)
and KG content translation are tightly coupled; the split becomes most useful when new
KG content is actively being added, making them natural companions.

**Defer Shopline connector to Phase 3**: Treat data ingestion as a "learning infrastructure"
concern alongside the bandit. Rejected explicitly — this is a dependency inversion. Real
Shopline signals are a prerequisite for the first paying customer (Phase 2), not an
optimisation for the learning layer (Phase 3). Deferring it would make Phase 2 commercial
activation impossible.

## Consequences
### Positive
- Clear blocking conditions per track: Track A blocked on Shopline integration, Track B
  blocked on partner delivery — these are tracked separately
- First paying customer is not blocked by partner KG delivery cadence
- Architecture work proceeds at its own pace without blocking commercial timeline
- Phase 3 entry condition is unambiguous

### Negative
- Requires coordinating two concurrent tracks — more project management overhead than a
  single linear phase
- Phase 3 entry condition (both tracks complete + 6 months data) is more complex than
  a single-track Phase 2 would have been
- Risk of one track completing much faster than the other, creating pressure to begin
  Phase 3 before all Phase 2 items are done

### Neutral
- Multi-merchant BenchmarkEngine moved from Phase 2 (original README) to Phase 2 Track A
  milestone (activated once 2+ merchants are in production) — correction of original error
  where it was listed before data existed

## When to Revisit
If Track A completes and Track B is substantially incomplete, evaluate:
1. Can Phase 3 Signal Completeness (Meta Ads, GA4) begin before Track B finishes?
   Answer: yes, these are independent.
2. Can bandit training begin before Track B's CorrelatedCandidate typing is done?
   Answer: yes, but bandit feature contract should reference `DecisionFeatureVector` which
   is already defined (ADR-0005).
If Track B stalls due to prolonged partner delay, consider splitting it further.

## References
- V3/README.md — Phase Roadmap section
- V3/CLAUDE.md — Phase definition section
- ADR-0003 (L3 split — Track B execution)
- ADR-0005 (Feature Plane — Track B execution)
- V3/docs/AUDIT_2026_04_09.md — dependency analysis basis
