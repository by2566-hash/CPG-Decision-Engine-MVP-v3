# ADR-0005: Feature Plane as Logical Concept, No Infrastructure in Phase 1

## Status
Accepted
Date: 2026-04-09

## Context
V3.5 identified a "Feature Plane" problem: the continuous numeric features consumed by the
LinUCB scoring formula and (eventually) the bandit were scattered across three different
representations in V3:

1. `signals` dict — raw signals from MSM computation, passed freely between pipeline stages
2. `ImpactCalculator` inputs — merchant state dict with `monthly_gmv`, `avg_margin_pct`, etc.
3. `scoring.py` candidate dicts — `pred` sub-dict with `gmv_lift`, `margin_lift`, etc.

No unified contract existed for "the set of continuous numbers the scoring model and bandit
consume." This creates training/serving skew risk: when the LinUCB bandit is trained in
Phase 3, there is no guarantee that the training feature vector matches what `scoring.py`
passes at inference time.

SageMaker Feature Store (or equivalent) would solve this with an online/offline feature
serving layer. However, Phase 1 has no real data (all stubs), no bandit training, and no
offline evaluation — making feature store infrastructure pure overhead.

The V3.5 proposal also defined two objects:
- `DecisionState` — discrete MSM routing states (HEALTHY/WATCH/DEGRADING/CRITICAL per dimension)
- `DecisionFeatureVector` — continuous numeric features for model consumption

These solve different problems: `DecisionState` is for routing and explainability;
`DecisionFeatureVector` is the model's context input. Both needed to exist as types even if
infrastructure was not built.

## Decision
Introduce `DecisionFeatureVector` and `DecisionState` as Pydantic contracts in `contracts.py`.
Create a `feature_plane/` module with a `FeatureBuilder` class that produces both objects from
raw signals (Phase 2 task). No persistent storage, no online/offline sync, no feature store
infrastructure in Phase 1.

Phase 1 deliverable: typed contracts and `from_signals()` classmethods.
Phase 2 Track B deliverable: `FeatureBuilder` wired into `pipeline.py`, replacing raw `signals` dict
  as the bandit context contract.
Phase 3 deliverable: historical feature snapshots for offline policy evaluation.

`DecisionFeatureVector` fields (all `Optional[float]`, missing = None in Phase 1):
`inventory_days`, `margin_pct`, `repeat_rate_7d`, `cvr_7d`, `cvr_30d`,
`promo_redemption_30d`, `stock_pressure_score`, `churn_score`, `seasonality_index`,
`benchmark_gap_score`

`DecisionState` fields (all `str = "HEALTHY"`):
`acquisition_state`, `conversion_state`, `retention_state`, `promotion_state`,
`active_alerts: list[str]`

## Alternatives Considered

**Introduce SageMaker Feature Store now**: Build the full online/offline feature pipeline
immediately. Rejected — Phase 1 has no real data and no model training. SageMaker Feature
Store adds AWS infrastructure cost and integration complexity to a system that will not use
it until Phase 3. The cost/benefit ratio at Phase 1 is deeply negative.

**Custom lightweight feature store (DynamoDB or Redis-backed)**: Simpler than SageMaker,
still provides online/offline split. Rejected — same reasoning: no real data, no model,
infrastructure investment cannot be validated until Phase 3.

**Keep features in scattered dicts permanently**: Accepted training/serving skew as a known
risk. Rejected — Phase 3 bandit activation requires feature consistency; fixing this later
means refactoring the bandit training pipeline after it already exists, which is harder than
defining the contract now.

## Consequences
### Positive
- Bandit (`pillar2_ml/bandit.py`) and scoring engine have stable, testable contracts for
  numeric inputs — Phase 3 implementation knows exactly what fields to expect
- Training/serving skew risk acknowledged and addressed at the contract level
- `DecisionState` explicitly separates routing state (MSM) from model inputs (FeatureVector),
  clarifying that MSM's 4×4 state is for explainability, not the bandit's context vector
- `feature_plane/` is a clean extension point — adding Feature Store infrastructure in
  Phase 3 means adding a storage backend, not redesigning the type system

### Negative
- No persistent feature history in Phase 1 — historical replay and offline evaluation not
  possible until Phase 3
- `DecisionFeatureVector` is defined but not wired into `pipeline.py` in Phase 1 —
  the gap between definition and use creates a TODO that must be tracked

### Neutral
- `from_signals()` classmethod provides migration path: pipeline can switch from raw dicts
  to `DecisionFeatureVector` without changing the scoring formula, just the input type

## When to Revisit
When LinUCB bandit training begins (Phase 3). The `DecisionFeatureVector` contract should
be validated against real signal availability before training starts. If required fields
are consistently None due to missing connectors, the bandit context vector must be revised.

## References
- V3/CLAUDE.md — Feature Plane section
- V3/src/decision_engine/contracts.py — `DecisionFeatureVector` and `DecisionState`
- ADR-0003 (L3 split — FeatureBuilder wiring is part of the same Phase 2 Track B work)
