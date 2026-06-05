---
source_group: Use Case Library FINAL T2
status: blocked_for_active_runtime
created_at: 2026-06-01
scope: T2 measurement/data-contract/incrementality audit packet only
runtime_assets_created: false
---

# T2 Measurement/Data-Contract Gated Packet

## Decision

T2 is complete as an audit packet only. No active runtime YAML, dormant YAML,
brand binding, use-case YAML, routing code, tests, or source-ledger updates were
created by this packet.

Final group status: `BLOCKED_FOR_ACTIVE_RUNTIME`.

These cases are source-backed evidence and future measurement-pattern candidates,
but they are not active-ready under the current V3 architecture. The current
runtime routes by MSM state, and `triggers.condition` is authoring metadata, not
executable routing logic. Measurement, incrementality, geo-lift, MMM, halo,
affiliate-attribution, and event-quality fields are not proven runtime contract
fields for these cases.

## Count Check

Expected T2 case count: `27`.

Exact T2 IDs:

`B-01a`, `B-01c`, `B-01d`, `B-02a`, `B-02b`, `B-04`, `B-05`, `B-06`, `B-07`,
`B-08`, `B-09`, `B-10`, `B-11`, `B-12`, `B-13`, `B-14`, `B-15`, `B-16`,
`B-17`, `B-18`, `B-19`, `FP-008`, `FP-012`, `FP-020`, `FP-026`, `FP-027`,
`FP-028`

Observed packet count: `27`.

Coverage source:

- `docs/kg_translation_triage/2026-06-01-supervised-translation-plan.md`
- `docs/kg_translation_triage/2026-06-01-source-coverage-ledger.md`
- `partner_drafts/kg_partner/use_case_library_final/case_index.json`
- `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md`

## Target Mode Legend

| Target mode | Meaning |
|-------------|---------|
| Source-only measurement evidence | Keep as source-backed audit evidence. Do not create runtime assets until architecture and data gates are approved. |
| Future dormant measurement candidate | A reusable pattern may be documented later under a dormant measurement guard layer, but only after that layer is explicitly approved. |
| Data-contract gated source-only | First-party or operator case has a plausible operational pattern, but required event, attribution, affiliate, search, or routing fields are absent from the current runtime contract. |

## Group-Level Blockers

| Blocker | Decision impact |
|---------|-----------------|
| Measurement layer missing | V3 has KG playbook routing and evidence traces, but no explicit measurement guard layer for geo holdouts, MMM, synthetic controls, causal ensembles, platform-vs-incrementality calibration, or attribution-window diagnosis. |
| Geo/MMM/halo data absent from current runtime contract | Source cases require market assignment, test/control outcomes, confidence, DTC/retail/marketplace lift, causal MMM calibration, and omnichannel halo data. These are not proven fields in the current `DecisionFeatureVector`, MSM state, or playbook routing contract. |
| Affiliate/search/event-quality data absent from current runtime contract | Source cases require affiliate partner-level CVR/click/order data, brand-query leakage, paid-search term reports, order-level touchpoint sequences, event match quality, event-source connectivity, transaction IDs, revenue, and customer-type event flags. |
| Route/action gates fail | Current routing is MSM-state only. `triggers.condition` cannot make multiple measurement patterns mutually exclusive. Many source actions are measurement setup, event rewiring, affiliate termination, clawback, negative-keyword governance, budget reallocation after a holdout, or reporting-model changes, none of which are proven active runtime action surfaces. |
| Raw evidence cannot enter Layer 2 bindings | Source numbers may be preserved in this packet or future Layer 3 use-case SSoT, but must not be copied into brand bindings or meta-patterns. No Layer 2 YAML was created. |

## Case Audit

### Benchmark And Research Cases

| Case | Source line | Short title | Source evidence kept in packet | Measurement/data-contract blocker | Proposed future pattern/note | Target mode |
|------|-------------|-------------|--------------------------------|-----------------------------------|------------------------------|-------------|
| B-01a | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:8` | YouTube click attribution undercounts new-customer value | Matched-market geo holdout; YouTube drove `1.8X` the click-attributed orders at baseline and `2.3X` at doubled spend. | Needs geo holdout market assignment, treated/control new-customer orders, click-attribution baseline, and validated iROAS. Current runtime cannot scale YouTube from non-executable trigger conditions. | Future guard for view-heavy channel under-credit after geo validation. | Source-only measurement evidence; future dormant measurement candidate. |
| B-01c | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:120` | Causal MMM reveals branded search and Meta ASC waste | Causal MMM plus targeted geo experiments; branded search cut from about `$3K/day` to `$0/day`; Meta ASC pulled back. | Needs anchored MMM, spend-level experiment points, new-vs-returning split, and marginal incrementality data. No active MMM evidence contract exists. | Future MMM/anchored-experiment guard for branded search and auto-bidding waste. | Source-only measurement evidence; future dormant measurement candidate. |
| B-01d | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:184` | OOH drives new-customer lift with zero repeat lift | Fixed geo test with synthetic control; about `+9%` new orders, `0%` repeat orders, and `100%` of lift from new customers. | Needs OOH geo-test data, synthetic control output, new/repeat lift decomposition, and CPIA profitability threshold. Current runtime has no OOH measurement/action surface. | Future channel-role guard for acquisition-only OOH lift. | Source-only measurement evidence; future dormant measurement candidate. |
| B-02a | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:247` | Geo testing unlocks upper-funnel Meta | 50/50 US geo holdout; upper-funnel Meta generated about `4%` of new-customer revenue and comparable iROAS to performance campaigns. | Needs geo-lift ingestion and upper-funnel incremental revenue fields. Existing acquisition routing cannot treat measurement-gap diagnosis as executable route proof. | Future geo-lift test guard for upper-funnel channel activation. | Source-only measurement evidence; future dormant measurement candidate. |
| B-02b | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:303` | PMax with brand queries outperforms without brand | 3-cell geo lift; brand-inclusive PMax drove about `2.0X` total revenue and `1.75X` new-customer revenue vs brand-excluded; Google overstated by about `33%`. | Needs PMax brand-query segmentation, no-PMax holdout cell, geo lift outcomes, and platform-discount logic. Current runtime does not support brand-query inclusion as a safe active action. | Future `measurement_pmax_brand_query_dependency` candidate after geo/query data contract. | Source-only measurement evidence; future dormant measurement candidate. |
| B-04 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:430` | MTA over-credits channels vs true incrementality | Channel-level incrementality tests calibrated against MTA; CAC and MER improved directionally after reallocation. | Needs MTA-vs-iROAS calibration by channel and budget-reallocation evidence. Source lacks accessible channel-level percentages, and runtime lacks MTA calibration fields. | Future attribution-integrity guard for periodic MTA calibration. | Source-only measurement evidence; future dormant measurement candidate. |
| B-05 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:491` | Click MTA inverts ToF vs BoF creative performance | 2-cell geo holdout; BoF CPIA was about `250%` higher than MTA reported, ToF was about `20%` lower, and ToF was about `13X` more incremental. | Needs creative funnel role, MTA CPIA, geo CPIA, and Meta ASC test-cell fields. Current action surface cannot safely reallocate creative budget from measurement-only evidence. | Future creative readout attribution guard for ToF/BoF inversion. | Source-only measurement evidence; future dormant measurement candidate. |
| B-06 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:554` | Longer Meta click window outperforms shorter | 80/20 US geo A/B; 7-day click produced `+6.5%` incremental new revenue vs 1-day click. | Needs attribution-window configuration, incrementality test result, and Meta outcome fields. Runtime has no active attribution-window action or test contract. | Future attribution-window experiment guard; not active until config/action surface exists. | Source-only measurement evidence; future dormant measurement candidate. |
| B-07 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:616` | TikTok platform ROAS overstates true lift | First geo test showed `0%` incremental subscription lift; after optimization, second test showed `+8%` lift; platform overstatement about `10%`. | Needs sequential geo holdouts, platform-vs-incremental ROAS, optimization-setting changes, and campaign timing/creative fields. Current runtime cannot distinguish measurement verdict from routing. | Future platform-vs-incrementality guard for TikTok/new channels. | Source-only measurement evidence; future dormant measurement candidate. |
| B-08 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:681` | Programmatic podcast omnichannel iROAS | 2-cell geo holdout across Shopify, Amazon, Ulta, and Nordstrom; Shopify iROAS exceeded goal by about `55%`; omnichannel iROAS about `4X` goal. | Needs omnichannel sales ingestion, retailer/marketplace lift, and geo-test evidence. Current runtime does not see retail halo surfaces. | Future omnichannel iROAS guard for small-spend channel measurement. | Source-only measurement evidence; future dormant measurement candidate. |
| B-09 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:743` | DTC-only Meta iROAS misses retail value | Vendor geo holdout across about `10` DMAs for about `6` weeks; DTC iROAS about `0.5`, omnichannel iROAS about `4-5X`, statistically significant `+10%` lift. | Needs DTC vs omnichannel revenue, retail distribution share, confidence intervals, and iCPA fields. Current runtime cannot reason over retail halo. | Future retail-distribution halo guard for Meta evaluation. | Source-only measurement evidence; future dormant measurement candidate. |
| B-10 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:809` | Brand TV halo lands on marketplace | Synthetic-control geo test; double-digit Amazon lift while DTC and retail changes were modest. | Needs TV spend, synthetic-control geo output, Amazon/marketplace lift, and marketplace share fields. Current runtime lacks brand-TV halo contract. | Future marketplace-halo guard for brand TV. | Source-only measurement evidence; future dormant measurement candidate. |
| B-11 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:874` | Snapchat marketplace halo invisible to DTC attribution | 2-cell geo holdout; DTC new-customer revenue about `+5%`, mass-retailer about `+11%`, marketplace about `+5%`, holistic iROAS about `+125%`, about `55%` invisible to DTC attribution. | Needs DTC, Walmart, Amazon, and holistic iROAS fields by geo cell. Current runtime has no marketplace-halo measurement data. | Future marketplace-halo guard for upper-funnel social channels. | Source-only measurement evidence; future dormant measurement candidate. |
| B-12 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:937` | Mobile gaming ads halo lands on Amazon | State-level geo holdout plus causal MMM; DTC lift about `+5%`, marketplace gross sales about `+2%`, combined iROAS about `4X`, about `87%` marketplace impact invisible to direct attribution. | Needs combined DTC/marketplace lift, MMM output, Amazon halo, and channel platform fields. Current runtime cannot evaluate marketplace-skewed halo. | Future Amazon-halo guard for upper-funnel digital channels. | Source-only measurement evidence; future dormant measurement candidate. |
| B-13 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1000` | Meta platform ROAS understates incremental iROAS | Geo holdout; Meta platform ROAS about `1.6`, geo iROAS about `2.4`, platform understatement about `35%`. | Needs geo iROAS, platform ROAS, lifecycle-stage context, and holdout validation. Runtime lacks platform-vs-geo calibration fields. | Future Meta platform under-credit guard before cut decisions. | Source-only measurement evidence; future dormant measurement candidate. |
| B-14 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1061` | TikTok geo lift reveals incremental orders | 3-cell geo lift; fewer than `20` last-touch conversions vs about `9,500` incremental orders, including about `3,500` DTC and `6,000` marketplace halo; combined iROAS about `$2.30`. | Needs last-touch vs geo-lift orders, DTC/marketplace decomposition, TikTok cell assignment, and Shop Ads surface fields. Current runtime lacks these action/data gates. | Future last-touch incompatibility guard for awareness formats. | Source-only measurement evidence; future dormant measurement candidate. |
| B-15 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1130` | Audio underrated by last-click MTA | Matched-market geo holdout; audio had near-zero last-click conversions but drove net-new customers and incremental ROAS above breakeven. | Needs audio spend, MTA conversions, geo holdout lift, and breakeven iROAS threshold. Current runtime lacks passive-channel incrementality fields. | Future audio incrementality guard before channel cuts. | Source-only measurement evidence; future dormant measurement candidate. |
| B-16 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1192` | Brand search non-incremental across seasons and markets | Three sequential geo holdouts; slow season `1%` lift at inefficient CPA, peak season `0%`, new markets `0%`; brand search eliminated. | Needs repeat holdout history by season/market, paid-search spend, lift, and CPA fields. Active elimination action requires explicit route/action gate. | Future brand-search incrementality guard with multi-test requirement. | Source-only measurement evidence; future dormant measurement candidate. |
| B-17 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1255` | Promo-code attribution understates podcast iROAS | Causal ensemble over 6 months; promo-code ROAS `1.0X-1.5X`; modeled iROAS about `2.9X`, `2.65X`, then `1.2X`. | Needs promo-code attribution, podcast show spend, causal-model outputs, and modeled iROAS by window. Current runtime lacks podcast causal attribution contract. | Future promo-code-vs-causal-model guard for podcast. | Source-only measurement evidence; future dormant measurement candidate. |
| B-18 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1321` | 30s video beats 15s despite higher CPM | 3-cell geo holdout across about `50` DMAs; `:30s` iROAS about `2.85`, `:15s` about `2.45`, about `+15%` revenue per dollar despite `28%` CPM premium. | Needs creative-length cell assignment, passive-video channel type, incremental revenue per dollar, and CPM fields. Current runtime lacks creative-length test and action surface. | Future passive-video creative-length measurement guard. | Source-only measurement evidence; future dormant measurement candidate. |
| B-19 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1385` | Affiliate loyalty/cashback zero incremental | Hybrid time-series plus geo synthetic control; 7-week US affiliate loyalty pause; zero US revenue change and no SKU-level decrease. | Needs affiliate partner data, pause-test or synthetic-control output, SKU-level revenue, and budget redirection action support. Current runtime cannot terminate/reduce affiliates from last-click evidence alone. | Future affiliate incrementality guard for loyalty/cashback partners. | Source-only measurement evidence; future dormant measurement candidate. |

### First-Party And Operator Cases

| Case | Source line | Short title | Source evidence kept in packet | Measurement/data-contract blocker | Proposed future pattern/note | Target mode |
|------|-------------|-------------|--------------------------------|-----------------------------------|------------------------------|-------------|
| FP-008 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1841` | Long paid-social attribution window hides incremental work | 180-day attribution window with no funnel separation; Facebook revenue `+800%` on `+500%` spend at sustained `3x` ROAS; new customers `+300%`; email Q1 revenue `+231%`; SMS active subscribers `90K+`. | Needs attribution-window history, funnel segmentation, paid-social/email/SMS coordination fields, and reporting model changes. Current runtime has no attribution-window/funnel-separation contract. | Future `measurement_attribution_window_funnel_separation` guard. | Data-contract gated source-only. |
| FP-012 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2104` | First-time purchaser event improved CAC | Custom first-time purchaser event launched on `9/6`; CAPI event match quality improved from below `7` to `9`; CAC improved about `30%`. | Needs optimization-event schema, first-time vs repeat purchaser flags, CAPI event match quality, validation event, and event-deployment action support. Current runtime does not expose event-quality fields or a safe event-rebuild action. | Future `acquisition_new_customer_event_signal_quality` guard after event-quality contract. | Data-contract gated source-only. |
| FP-020 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2643` | Google tracking migration caused CAC spike | Google Ads CAC rose from `$43` to `$52` after `7/21` tracking migration and recovered to `$45` after correct event source reconnection. | Needs tracking-migration calendar, primary event-source status, transaction ID/revenue/identifier completeness, relearning window, and connector validation action. Runtime lacks conversion-signal integrity contract. | Future `measurement_google_tracking_migration_signal_loss` guard. | Data-contract gated source-only. |
| FP-026 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:3099` | Affiliate brand-term bidding inflated metrics | Flagged affiliate CVR `28.7%` vs site-wide `3.2%`; credited with `44.8%` of affiliate conversions from `11.4%` of clicks; no material revenue loss after removal. | Needs partner-level affiliate clicks/orders/CVR, paid-search source breakdown, UTM redirect audit, agreement restrictions, and clawback/termination action support. Current runtime lacks affiliate audit contract and action surface. | Future `measurement_affiliate_brand_term_anomaly` guard. | Data-contract gated source-only. |
| FP-027 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:3190` | Brand keyword bleed inflated non-brand campaign | Reported CPA `$29.60` and ROAS `3.06x` normalized to CPA `$38.20` and ROAS `2.38x` after brand traffic exclusion; clean 30-day follow-up held near benchmark. | Needs Google/Bing search term reports, brand-vs-non-brand query split, match type, negative keyword state, landing-page relevance, and spend-hold action support. Runtime lacks search-query leakage contract. | Future `measurement_brand_keyword_bleed` guard. | Data-contract gated source-only. |
| FP-028 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:3275` | Affiliate last-click inflated paid media CPA | Paid CPA appeared to rise from `$38.40` to `$41.50`, but adjusted first-touch paid CPA was `$37.20`; blended CPA improved to `$35.60` and held near `$35.40`. | Needs order-level touchpoint sequence, affiliate-assisted order share, first-touch vs last-click reporting, blended CPA, and attribution-model action support. Runtime lacks order-level attribution path contract. | Future `measurement_affiliate_last_click_inflation` guard. | Data-contract gated source-only. |

## Partner And Data Questions

### Measurement And Experiment Design

1. For each geo or synthetic-control case, can the partner provide treated and
   control market IDs, assignment rules, test dates, spend by cell, outcome
   metric definitions, confidence intervals, and statistical method?
2. Which tests are one-off case-study evidence versus repeatable measurements
   the runtime should expect to receive on an ongoing cadence?
3. Should future recommendations be "run measurement", "change budget after
   measurement", or both? These are different action surfaces.

### Omnichannel, Retail, And Marketplace Halo

1. Which retailers and marketplaces are available in the merchant data contract
   by brand: Amazon, Walmart, Ulta, Nordstrom, other retail, or DTC only?
2. Can marketplace and retail lift be tied to geo, channel, campaign, and
   time-window dimensions in a way that is auditable?
3. What lag and data-quality flags should be expected for marketplace halo
   reporting?

### Attribution, MMM, And Incrementality

1. Which external measurement outputs are allowed as runtime evidence: MMM,
   geo lift, synthetic control, Bayesian structural time series, temporal
   regression, MTA calibration, or platform experiment output?
2. What fields prove causal confidence, and what minimum confidence level is
   required before a budget or channel recommendation is allowed?
3. Are platform-reported metrics retained only as diagnostic baselines, or can
   they ever drive a recommendation without incrementality validation?

### Event Quality And Tracking Integrity

1. What is the canonical event schema for first-time purchaser, repeat purchase,
   transaction ID, revenue, identifiers, event source, and event match quality?
2. Which systems own event deployment and validation: Meta CAPI, Google Enhanced
   Conversions, a tag manager, a server-side event bus, or partner tooling?
3. What action surface exists for event rebuilds, reconnection, or migration
   rollback, and what human approval is required?

### Affiliate, Paid Search, And Query Governance

1. Can the runtime receive affiliate partner-level clicks, orders, conversion
   rate, traffic-source breakdown, UTM/redirect data, and commission terms?
2. Can the runtime receive paid-search query reports split by brand/non-brand,
   match type, CPC, conversion, and negative-keyword status?
3. Are affiliate termination, commission clawback, brand-bidding enforcement,
   negative-keyword insertion, and reporting-model changes supported actions or
   only audit recommendations?

### Runtime Routing And Action Gates

1. Should V3 add a separate measurement guard layer, executable
   trigger-condition routing, or multi-pattern returns before any T2 pattern is
   activated?
2. What MSM state should route measurement recommendations without colliding
   with existing acquisition, conversion, retention, or promotion playbooks?
3. Which actions are safe to render today, and which require new impact
   calculator, renderer, rollback, approval, or connector support?

### Source Governance

1. Should anonymized `B-*` benchmark cases remain source-only indefinitely, or
   can their raw evidence be copied into future Layer 3 use-case SSoT after
   partner approval?
2. For first-party cases, what canonical merchant IDs should be used if future
   dormant or active assets are approved?
3. Which raw observed numbers may be reused in runtime-facing assets, and which
   must remain only in source/audit packets?

## Final Status

The group is not active-ready. The correct current disposition is:

- Preserve all 27 cases as source-backed audit evidence.
- Do not create active runtime YAML.
- Do not create dormant YAML in this task because ownership is audit-packet docs
  only.
- Revisit only after measurement-layer, data-contract, routing, action-surface,
  and raw-evidence governance questions are answered.

Final status: `BLOCKED_FOR_ACTIVE_RUNTIME`.
