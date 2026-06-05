---
source_group: Use Case Library FINAL T3
status: blocked_for_active_runtime
created_at: 2026-06-01
scope: T3 offer/margin/retention/conversion gated audit packet only
runtime_assets_created: false
---

# T3 Offer/Margin/Retention/Conversion Gated Packet

## Decision

T3 is complete as an audit packet only. No active runtime YAML, dormant YAML,
brand binding, use-case YAML, routing code, tests, generated files, or source
ledger updates were created by this packet.

Final group status: `BLOCKED_FOR_ACTIVE_RUNTIME`.

These cases remain source-backed offer, margin, retention, lifecycle, and
conversion evidence. They are not active-ready under the current V3 architecture
because the required contribution-margin, offer objective, subscriber cohort,
retention, attribution-window, and action-surface contracts are not proven
runtime fields. Current routing is MSM-state driven, and `triggers.condition`
is authoring metadata, not executable route logic.

Source evidence is preserved here for audit review only. Raw observed numbers
from these cases must not be copied into Layer 2 brand bindings or treated as
active runtime calibration without partner approval and a Layer 3 SSoT decision.

## Count Check

Expected T3 case count: `9`.

Exact T3 IDs:

`FP-014`, `FP-015`, `FP-017`, `FP-021`, `FP-024`, `FP-029`, `FP-030`,
`FP-031`, `FP-032`

Observed packet count: `9`.

Coverage source:

- `docs/kg_translation_triage/2026-06-01-supervised-translation-plan.md`
- `docs/kg_translation_triage/2026-06-01-source-coverage-ledger.md`
- `docs/kg_translation_triage/2026-06-01-use-case-library-final.md`
- `partner_drafts/kg_partner/use_case_library_final/case_index.json`
- `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md`

## Target Mode Legend

| Target mode | Meaning |
|-------------|---------|
| Source-only offer/retention evidence | Keep the source facts in audit context only. Do not create runtime assets until partner approval, data contracts, and action gates exist. |
| Future dormant candidate | A reusable pattern may be documented later as dormant if architecture review approves the target module, route, data fields, and action surface. |
| Margin/action-surface gated source-only | The case has plausible operational value, but contribution-margin fields, offer actions, promo/discount controls, or renderer support are not proven. |
| Retention/cohort gated source-only | The case depends on subscriber state, cohort definitions, lifecycle events, or retention denominators that are not proven runtime contract fields. |
| Conversion merchandising gated source-only | The case depends on landing-page, creative, offer, or merchandising diagnostics that could collide with existing conversion routes unless executable route conditions or route ranking are approved. |

## Group-Level Blockers

| Blocker | Decision impact |
|---------|-----------------|
| Margin/profit guard missing | Offer and discount cases require AOP, AOV, gross margin, contribution margin, downstream revenue, and objective-aware tradeoff logic. Current runtime readiness for these fields and profit guardrails is unproven. |
| Discount/promo action surface missing | Source actions include scaling, rolling back, restricting offers, changing welcome offers, moving discounts to at-risk segments, and reallocating paid traffic. These require supported action IDs, impact calculators, renderer copy, rollback/approval behavior, and partner-side execution authority. |
| Retention/cohort data contract missing | Retention cases require self-purchased vs gifted subscriber flags, pause duration, true active-base logic, resume rate, churn state, gift-to-paid conversion, at-risk segmentation, and retention value. These are not proven runtime contract fields. |
| Attribution/window and test-context gaps | Several cases rely on controlled test windows, consistent attribution windows, landing-page structure, creative format, catalog scope, and pre/post windows. These must be modeled as data contracts before promotion. |
| Route collisions under current MSM routing | `triggers.condition` cannot make these cases mutually exclusive. Multiple conversion, acquisition, retention, and margin patterns could overlap under merchant/module/MSM state without executable conditions, route ranking, or an ADR-backed routing contract change. |
| Raw source governance unresolved | The source archive is ignored by git and contains raw observed evidence. Numbers may remain in this audit packet, but cannot become runtime-facing Layer 2 calibration or active use-case SSoT without approval. |

## Case Audit

| Case | Source line | Short title | Source evidence kept in packet | Blocker | Proposed future pattern/note | Target mode |
|------|-------------|-------------|--------------------------------|---------|------------------------------|-------------|
| FP-014 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2221` | Lower-AOV offer wins on CAC/CVR despite margin tradeoff | One-month 50/50 offer test with equal CPMs and similar spend; higher-value offer had stronger AOP/AOV, while lower-value offer had lower CAC and higher CVR. | Needs objective-aware margin guard, offer-test fields, AOP/AOV/CAC/CVR comparison contract, and a safe scale-vs-profit action. | Future offer objective pattern that selects scale or profit mode before recommendation; keep raw offer economics source-only until Layer 3 approval. | Margin/action-surface gated source-only; future dormant candidate. |
| FP-015 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2272` | High-margin DABA improves profitability without meaningful CAC tradeoff | High-margin DABA was compared with full-catalog DABA while audience, budget, bid strategy, attribution window, timing, and creative format were held constant; high-margin catalog improved CAC, AOP, AOV, and two-month revenue but plateaued on reach/spend. | Needs SKU-level margin contract, catalog-scope action support, plateau/reach guard, and proof that DABA catalog restriction can be rendered safely. | Future `acquisition_high_margin_catalog_daba` or margin-aware catalog-scope candidate after SKU economics and action gates are explicit. | Margin/action-surface gated source-only; future dormant candidate. |
| FP-017 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2418` | High-CTR Pinterest creative needs direct offer | Organic-style Pinterest creative greatly exceeded CTR baseline but converted below baseline; adding a direct offer improved CVR while reducing CTR, and spend was insufficient for reliable CAC/RPS read. | Needs creative/offer variant fields, CTR-vs-CVR diagnostic contract, audience-quality validation, and unsupported offer-add action surface. | Future conversion diagnostic for high-click/low-conversion creative; do not route active until CTR-only false positives and offer actions are modeled. | Conversion merchandising gated source-only; future dormant candidate. |
| FP-021 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2717` | Welcome offer lowers CPM but hurts backend CVR | July-September test: new welcome offer lowered CPMs versus core offer, but backend CVR weakened and slight AOV gain did not create favorable revenue per session; offer was rolled back before Q4. | Needs offer objective, backend CVR/RPS fields, consistent attribution-window evidence, seasonal context, rollback action, and route exclusivity against other acquisition/conversion offer patterns. | Future reach-vs-backend-conversion tradeoff pattern; active use requires supported rollback and peak-season confidence gates. | Margin/action-surface gated source-only; future dormant candidate. |
| FP-024 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2936` | Revenue per session is best LP option metric | Multi-variant landing-page option architecture test changed roast, bag count, bag size, and purchase configuration; RPS was used as strongest payback proxy because subscription data was hard to read, and a purchase-configuration bug was found. | Needs LP variant data contract, RPS/LTV proxy governance, purchase-configuration bug detection, and action surface for merchandising architecture changes. | Future `conversion_option_architecture_rps_metric` candidate after LP test schema and bug-check contract exist. | Conversion merchandising gated source-only; future dormant candidate. |
| FP-029 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:3361` | Gifted subscriptions deflate renewal rate | Holiday gift promotion mixed gifted subscriptions into retention reporting; blended renewal declined, but segmented self-purchased renewal stayed stable; win-back spend against gifted subscribers performed poorly and gift-to-paid became a separate lifecycle opportunity. | Needs subscriber acquisition-source flags, gifted vs self-purchased cohort contract, gift-to-paid lifecycle event, retention-denominator governance, and retention spend action surface. | Future `retention_gifted_subscription_denominator` candidate after cohort reporting and win-back guardrails are explicit. | Retention/cohort gated source-only; future dormant candidate. |
| FP-030 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:3472` | Pause feature masks true churn | Pause-inclusive reporting understated churn; applying a 60-day pause-adjusted active-base rule corrected churn, identified paused-past-60-day subscribers, and supported a 45-day reactivation sequence. | Needs pause-state and pause-duration contract, adjusted active-base definition, resume-rate history, churn denominator governance, and reactivation action support. | Future `retention_pause_masked_churn` candidate after subscriber lifecycle state machine and reactivation action gates exist. | Retention/cohort gated source-only; future dormant candidate. |
| FP-031 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:3572` | Autoship discount erodes margin without retention lift | Site-wide autoship discount raised enrollment but materially reduced margin with minimal retention lift; moving discount to at-risk segment restored margin directionally and improved at-risk retention. | Needs gross-margin-per-order, autoship enrollment, retention value, discount sensitivity, at-risk segmentation, and targeted discount action support. | Future `retention_autoship_discount_margin_erosion` candidate after margin guard and promo segmentation actions are approved. | Margin/action-surface gated source-only; retention/cohort gated source-only; future dormant candidate. |
| FP-032 | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:3674` | Bundle page paid traffic converts at half product pages | Bundle page received large cold paid allocation and had much worse CPA/CVR than individual product pages, despite longer sessions and lower bounce; reallocation retained bundle only for retargeting where performance was stronger. | Needs landing-page destination performance fields, cold-vs-retargeting segment contract, paid allocation action support, relearning-window handling, and route exclusivity against existing conversion/acquisition destination mix patterns. | Future `conversion_bundle_page_paid_traffic_mismatch` candidate after LP destination schema and budget reallocation action gates are explicit. | Conversion merchandising gated source-only; future dormant candidate. |

## Partner And Data Questions

### Offer, Margin, And Discount Governance

1. Which source numbers from offer, DABA, welcome-offer, and autoship-discount
   cases are approved for future Layer 3 use-case SSoT, and which must remain
   source-only?
2. What is the canonical contribution-margin contract: AOP, gross margin,
   discount cost, COGS, shipping, return rate, downstream revenue, LTV proxy,
   or another partner-approved measure?
3. Which objective should the runtime optimize when metrics conflict: new-order
   volume, CAC, CVR, AOV, AOP, revenue per session, contribution margin, or
   retention value?
4. Are offer scale, offer rollback, catalog restriction, discount removal,
   targeted discount deployment, and paid-budget reallocation supported actions
   with human approval and rollback behavior?

### Retention, Lifecycle, And Cohort Contracts

1. Can the runtime receive durable subscriber state fields for gifted,
   self-purchased, paused, lapsed, reactivated, autoship, at-risk, and
   gift-to-paid cohorts?
2. Who owns denominator definitions for renewal, churn, active subscribers,
   pause-adjusted active base, and gift-to-paid conversion?
3. What window lengths are canonical for retention analysis: 30 days, 45 days,
   60 days, 90 days, billing cycle, or merchant-specific cadence?
4. Which lifecycle actions can be rendered today: pause cap, reactivation
   sequence, win-back suppression, gift renewal reminder, curated preview, or
   targeted discount?

### Conversion Merchandising And Landing-Page Data

1. Can landing-page test data be ingested by variant, URL, session source,
   audience segment, product option architecture, CVR, CPA, AOV, RPS, and bug
   status?
2. Can creative and offer variants be linked to downstream page metrics without
   relying only on CTR or platform CAC?
3. How should V3 separate cold acquisition routing from retargeting routing when
   the same page or offer performs differently by audience state?
4. What validation is required before changing a merchandising architecture or
   paid landing-page allocation?

### Runtime Routing And Source Governance

1. Should T3 cases wait for executable trigger-condition routing, route ranking,
   or a separate lifecycle/margin guard layer before any active promotion?
2. What MSM states should own offer/margin/retention/conversion diagnostics
   without colliding with existing acquisition, conversion, retention, or
   promotion playbooks?
3. For named first-party brands in these cases, what canonical merchant IDs are
   approved for any future dormant or active assets?
4. Should raw source evidence from the ignored partner archive ever be copied
   into runtime-facing YAML, or should it remain audit-only unless separately
   approved by the partner?

## Final Status

The group is not active-ready. The correct current disposition is:

- Preserve all 9 cases as source-backed audit evidence.
- Do not create active runtime YAML.
- Do not create dormant YAML in this task because ownership is audit-packet docs
  only.
- Do not copy raw observed numbers into Layer 2 brand bindings.
- Revisit only after margin/profit, offer/discount action, retention/cohort,
  attribution/window, route-collision, and raw-source governance questions are
  answered.

Final status: `BLOCKED_FOR_ACTIVE_RUNTIME`.
