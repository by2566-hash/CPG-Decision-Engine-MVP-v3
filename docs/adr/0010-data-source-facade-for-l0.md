# ADR-0010: Data Source Facade for L0 (Concept — Implementation Phase 2 Track A)

## Status
Accepted (concept); implementation deferred to Phase 2 Track A
Date: 2026-04-10

## Context
Phase 2 Track A requires real Shopline data ingestion. Phase 3 adds Meta Ads and
GA4. Without an abstract interface, each new connector would require bespoke
integration into `MerchantStateMachine`, `FeatureBuilder`, and every other
consumer of raw signals — creating coupling and making it impossible to swap or
mock implementations.

The team also evaluated Supermetrics as a third-party data aggregator. Supermetrics
is a black-box attribution source: it ingests ad platform data and re-attributes
conversions using proprietary models. Binding the V3 architecture to Supermetrics
as a required dependency would:
1. Violate "Determinism over Probability" — reward signals from Supermetrics
   attribution models cannot be deterministically reproduced
2. Create a single point of failure for data ingestion
3. Pollute WSM training data with opaque attribution (the bandit would learn
   policies against un-auditable signal sources)

## Decision
Define an abstract `DataSourceConnector` Protocol in
`layer0_data/connector_protocol.py` (to be created in Phase 2 Track A) with
stable method signatures:

```python
class DataSourceConnector(Protocol):
    def get_orders(self, merchant_id: str, since: datetime) -> list[dict]: ...
    def get_customers(self, merchant_id: str) -> list[dict]: ...
    def get_products(self, merchant_id: str) -> list[dict]: ...
    def get_ad_spend(self, merchant_id: str, since: datetime) -> list[dict]: ...
    def get_traffic_signals(self, merchant_id: str, since: datetime) -> list[dict]: ...
```

Committed implementations:
- Phase 2 Track A: `ShoplineConnector` (satisfies Protocol)
- Phase 3: `MetaAdsConnector`, `GA4Connector` (satisfy Protocol)

Optional / non-committed:
- `SupermetricsConnector` may be added as an optional connector if a specific
  customer requires it. It must NOT become a required dependency. If used,
  Supermetrics-sourced signals must be tagged `attribution_source: "supermetrics"`
  in the signals dict so that WSM can track which learning examples used opaque
  attribution.

`MerchantStateMachine.compute()` and `FeatureBuilder.build()` will accept signals
dicts produced by any `DataSourceConnector` implementation without modification —
the Protocol ensures stable field names.

## Alternatives Considered

**Direct connector implementations without Protocol**: Rejected. Each new data
source would require changes to all consumers (MSM, FeatureBuilder, pipeline).
With a Protocol, the consumers are stable and only the connectors change.

**Use Supermetrics as primary aggregator**: Rejected. See Context section. The
determinism and auditability concerns are not resolvable within Supermetrics'
architecture. Supermetrics is permitted as an optional tagged connector only.

**Use a third-party data orchestration tool (Airbyte, Fivetran)**: Deferred for
evaluation. These tools provide managed connectors and schema normalization.
If evaluated in Phase 2/3, they would implement the `DataSourceConnector` Protocol
at the adapter layer — the V3 architecture is compatible with either approach.

## Consequences

### Positive
- Clean abstraction: MSM and FeatureBuilder are stable regardless of how many
  connectors are added
- Supermetrics is explicitly "optional and tagged," not required
- Protocol enables mock connectors for testing (no live API calls in tests)
- Future connector adds require only: write new class implementing Protocol,
  register in connector factory (to be defined in Phase 2 Track A)

### Negative
- Extra abstraction layer to maintain
- Protocol compliance is structural (duck typing), not enforced at import time —
  violations only surface at runtime unless explicitly tested

### Neutral
- No implementation in this ADR — design commitment only
- The connector factory pattern (which concrete connector to use per merchant)
  is a Phase 2 Track A design decision, not governed by this ADR

## When to Revisit
When Phase 2 Track A begins Shopline connector work. At that point, define the
connector factory and registration pattern, and write a Phase 2-specific ADR
covering the Shopline connector implementation details.

## References
- `V3/docs/PHASE_ROADMAP.md` — Phase 2 Track A (Shopline connector productionization)
- `V3/docs/PHASE_ROADMAP.md` — Phase 3 (Meta Ads connector, GA4 connector)
- `V3/src/decision_engine/layer0_data/connectors/` — current stub connectors
- `V3/src/decision_engine/layer1_msm/merchant_state_machine.py` — primary consumer
- `V3/src/decision_engine/feature_plane/builder.py` — secondary consumer
- ADR-0006 (Phase 2 dual-track structure — Track A entry conditions)
