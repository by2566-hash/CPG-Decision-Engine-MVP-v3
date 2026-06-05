# Brand Source Reconciliation - 2026-06-01

## Decision

The six brand-level DOCX files in `brand_source_batch_2026_06_01` are supporting or primary source evidence for existing Use Case Library FINAL first-party cases `FP-007` through `FP-032`. They do not introduce new runtime KG cases by themselves.

Raw source files, extracted markdown, and case indexes remain under `partner_drafts/`. This reconciliation document records titles and dispositions only; it is not a runtime KG input.

## Source-To-FINAL Mapping

| # | Source doc | Local case title | FINAL ID | Current FINAL disposition |
|---|------------|------------------|----------|---------------------------|
| 1 | Bonafide, Spoonful, and Grassroots | Post-signal-loss paid social recovery requires moving the optimization burden from targeting onto creative and post-click experience | FP-007 | Acquisition and creative expansion gated |
| 2 | Bonafide, Spoonful, and Grassroots | A too-long paid social attribution window is a measurement bug that conceals where the incremental new-customer work is happening | FP-008 | Measurement/data-contract/incrementality gated |
| 3 | Bonafide, Spoonful, and Grassroots | When buying cycle is long and YouTube is a new channel, retargeting amplifier is the correct first role, not prospecting | FP-009 | Acquisition and creative expansion gated |
| 4 | consumer_goods_case_studies_final | CAC and CPMs declined following the introduction of a structured UGC creator program on Meta | FP-010 | Already represented and Phase 1 source-aligned |
| 5 | consumer_goods_case_studies_final | Legally required health data consent pop-up caused a sudden CVR collapse across all traffic sources | FP-011 | Already represented and Phase 1 source-aligned |
| 6 | consumer_goods_case_studies_final | Rebuilding the purchase event to isolate new customers improved CAC about 30% | FP-012 | Measurement/data-contract/incrementality gated |
| 7 | consumer_goods_case_studies_final | Offer-led creative reduced CAC but weakened repeat purchase behavior | FP-013 | Already represented and Phase 1 source-aligned |
| 8 | consumer_goods_case_studies_final | Lower-AOV offer outperformed on CAC and CVR despite weaker profit per order | FP-014 | Offer, margin, retention, and conversion gated |
| 9 | consumer_goods_case_studies_final | Restricting DABA to high-margin SKUs improved order profitability without meaningful CAC tradeoff | FP-015 | Offer, margin, retention, and conversion gated |
| 10 | r2_consumer_case_studies | Product-specific creative lowered prospecting CAC and held through the post-launch period | FP-016 | Acquisition and creative expansion gated |
| 11 | r2_consumer_case_studies | High CTR Pinterest creative required a direct offer to improve conversion | FP-017 | Offer, margin, retention, and conversion gated |
| 12 | r2_consumer_case_studies | LAL seeding from top-performing purchase segments improved CAC as an incremental efficiency lever | FP-018 | Acquisition and creative expansion gated |
| 13 | r2_consumer_case_studies | Format-native Reels creative reduced CPMs and improved blended CAC as a complementary top-of-funnel lever | FP-019 | Acquisition and creative expansion gated |
| 14 | r2_consumer_case_studies | Conversion signal loss during Google tracking migration caused a CAC spike and partial recovery after reconnection | FP-020 | Measurement/data-contract/incrementality gated |
| 15 | r2_consumer_case_studies | New welcome offer expanded reach through lower CPMs but underperformed on backend conversion | FP-021 | Offer, margin, retention, and conversion gated |
| 16 | rarebird_use_cases | Dedicated ABO creative testing reduced spend concentration and improved Meta efficiency | FP-022 | Acquisition and creative expansion gated |
| 17 | rarebird_use_cases | Website-only destination outperformed Web + Shop in a head-to-head Meta routing test | FP-023 | Existing-pattern reuse candidate |
| 18 | rarebird_use_cases | Revenue per session was the best decision metric in a landing-page option-architecture test | FP-024 | Offer, margin, retention, and conversion gated |
| 19 | rarebird_use_cases | ADHD messaging materially outperformed broader value-prop and alternative benefit angles | FP-025 | Acquisition and creative expansion gated |
| 20 | skincare_use_cases_revised | Single affiliate bidding on brand terms produced an impossible conversion rate and inflated program metrics | FP-026 | Measurement/data-contract/incrementality gated |
| 21 | skincare_use_cases_revised | Brand keyword bleed into a non-brand paid campaign inflated product performance | FP-027 | Measurement/data-contract/incrementality gated |
| 22 | skincare_use_cases_revised | Affiliate last-click attribution inflated reported paid media CPA | FP-028 | Measurement/data-contract/incrementality gated |
| 23 | wine_pet_use_cases_updated | Gifted subscriptions mixed into retention reporting deflated renewal rate | FP-029 | Offer, margin, retention, and conversion gated |
| 24 | wine_pet_use_cases_updated | Pause feature usage masked true churn and understated subscriber attrition rate | FP-030 | Offer, margin, retention, and conversion gated |
| 25 | wine_pet_use_cases_updated | Autoship discount offered broadly eroded margin without improving retention | FP-031 | Offer, margin, retention, and conversion gated |
| 26 | wine_pet_use_cases_updated | Bundle page received paid traffic but converted at half the rate of individual product pages | FP-032 | Offer, margin, retention, and conversion gated |

## Promotion Implication

This batch strengthens provenance for `FP-007` through `FP-032`, but it does not automatically change runtime readiness.

`FP-023` remains the strongest first runtime-promotion candidate because it can likely reuse `acquisition_cac_channel_mix`. It still needs canonical merchant ID, Layer 2 brand binding, Layer 3 evidence SSoT, route fixture tests, and reviewer approval before any runtime KG promotion.
