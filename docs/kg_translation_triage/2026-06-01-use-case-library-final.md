---
purpose: Initial V3 translation triage for Use Case Library FINAL
source_doc: partner_drafts/kg_partner/use_case_library_final/Use Case Library FINAL.docx
extracted_markdown: partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md
case_index: partner_drafts/kg_partner/use_case_library_final/case_index.json
status: phase_1_source_alignment_complete
last_updated: 2026-06-01
---

# Use Case Library FINAL - V3 Translation Triage

## Executive Decision

Do not batch-promote all 55 cases into active `playbooks/` and `use_cases/`.
The correct V3 path is:

1. Archive the full source library.
2. Classify every case against the current three-layer KG design.
3. Reuse existing active patterns where the business logic already exists.
4. Promote only cases whose runtime route, data fields, action surface, and
   brand binding are safe under ADR-0011 through ADR-0013.
5. Keep measurement/incrementality and cross-channel attribution cases as
   source-backed candidates until V3 has the needed measurement layer fields
   and routing contract.

Reason: current runtime routing is `module + msm_state + optional merchant_id`.
`triggers.condition` is authoring metadata, not executable routing logic. The
registry returns one matched pattern. Multiple new cases with the same module,
MSM state, and merchant cannot safely be activated without either stronger
mutual exclusion, executable condition routing, or a multi-pattern return
contract.

## Extraction Facts

| Item | Result |
|------|--------|
| Source received | `/Users/yubo/Downloads/Use Case Library FINAL.docx` |
| Archived source | `partner_drafts/kg_partner/use_case_library_final/Use Case Library FINAL.docx` |
| Extracted markdown | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md` |
| Parsed case index | `partner_drafts/kg_partner/use_case_library_final/case_index.json` |
| Total cases | 55 |
| Benchmark/research cases | 23 |
| First-party/operator cases | 32 |
| DOCX comments | 0 detected |
| Visual render QA | Blocked: `soffice` unavailable |

## Omission Check

Fresh verification on 2026-06-01 found no case-level omissions:

| Check | Result |
|-------|--------|
| Original DOCX title extraction | 55 rows, 55 unique IDs, order matches `case_index.json` |
| Extracted Markdown title extraction | 55 rows, 55 unique IDs, order matches `case_index.json` |
| `case_index.json` | 55 rows, 55 unique IDs, first `B-01a`, last `FP-032` |
| Initial disposition table | 55 rows, 55 unique IDs, order matches `case_index.json` |
| `docs/kg_intake_log.md` classification summary | 55 unique IDs, no missing/extra vs `case_index.json` |
| Archived DOCX integrity | SHA-256 matches uploaded source exactly |
| Reuse-map file existence | 19/19 referenced V3 assets exist |
| Runtime dry run | `python scripts/kg_dryrun.py` passed |
| Targeted tests | 72 passed, 1 existing pytest config warning |

Known limitation: visual DOCX render QA was not available because this
environment does not have LibreOffice `soffice`. This does not affect the
case-ID extraction check above, which was performed directly against
`word/document.xml` inside the DOCX.

## Current V3 Reuse Map

| Source case | V3 disposition | Existing asset / next action |
|-------------|----------------|------------------------------|
| FP-001 | Already active | Covered by `conversion_subscription_mix` and `wb_001`; source confirms PM + ShopCash mix logic |
| FP-002 | Already active | Covered by `conversion_subscription_mix` and `wb_002`; source confirms ShopCash denominator logic |
| FP-003 | Legacy evidence | Maps to `use_cases/wandering_bear/_legacy/wb_003_evergreen_naming_test.yaml`; needs real meta-pattern + brand binding before promotion |
| FP-004 | Already active | Covered by `acquisition_cac_channel_mix` brand binding utility prior `REALLOCATE_BUDGET` and `wb_004` evidence |
| FP-005 | Already active | Covered by `acquisition_cac_channel_mix` and `wb_005`; source confirms Meta destination mix diagnosis |
| FP-006 | Legacy evidence | Maps to `use_cases/wandering_bear/_legacy/wb_006_inventory_spend_pullback.yaml`; needs ops-aware acquisition meta-pattern before promotion |
| FP-010 | Already active | Covered by `acquisition_ugc_creative` and `cba_001`; FINAL source has richer observed numbers |
| FP-011 | Already active | Covered by `conversion_compliance_friction` and `cba_002`; FINAL source has richer date/CAC details |
| FP-013 | Already deferred | Maps to dormant `playbooks/meta/_deferred/acquisition_ltv_quality_trap.yaml`; activation still blocked by cohort attribution/reward-gate dependencies |
| FP-023 | Reuse candidate | Likely new brand binding for existing `acquisition_cac_channel_mix`, not necessarily a new meta-pattern |

## Phase 1 Source Alignment

Completed on 2026-06-01. This phase added provenance and source-alignment
metadata only, plus FINAL-source factual enrichment where the source had more
precise evidence. No active routing, brand binding thresholds, utility priors,
runtime code, or action IDs were changed.

| Source case | Aligned V3 asset | Phase 1 result |
|-------------|------------------|----------------|
| FP-001 | `use_cases/wandering_bear/wb_001_subscription_mix_dilution.yaml` | Added `source_alignment`; existing evidence exact-match confirmed |
| FP-002 | `use_cases/wandering_bear/wb_002_shopcash_denominator.yaml` | Added `source_alignment`; existing evidence exact-match confirmed |
| FP-003 | `use_cases/wandering_bear/_legacy/wb_003_evergreen_naming_test.yaml` | Added `source_alignment`; legacy status unchanged |
| FP-004 | `use_cases/wandering_bear/wb_004_brand_vs_dr_cpa.yaml` | Added `source_alignment`; existing evidence exact-match confirmed |
| FP-005 | `use_cases/wandering_bear/wb_005_meta_destination_mix.yaml` | Added `source_alignment`; existing evidence exact-match confirmed |
| FP-006 | `use_cases/wandering_bear/_legacy/wb_006_inventory_spend_pullback.yaml` | Added `source_alignment`; legacy status unchanged |
| FP-010 | `use_cases/consumer_brand_a/cba_001_ugc_creative.yaml` | Added `source_alignment`; enriched rollout windows from FINAL source |
| FP-011 | `use_cases/consumer_brand_a/cba_002_compliance_ux.yaml` | Added `source_alignment`; enriched deploy date, 5-day remediation window, and CAC movement from FINAL source |
| FP-013 | `playbooks/meta/_deferred/acquisition_ltv_quality_trap.yaml` | Added `source_alignment`; deferred activation blockers unchanged |

## Initial Case Disposition

| Case | Short title | Initial V3 disposition | Candidate pattern / note |
|------|-------------|------------------------|--------------------------|
| B-01a | YouTube click attribution undercounts new-customer value | Measurement-layer candidate | Needs incrementality/attribution layer before runtime actioning |
| B-01b | Tight existing-customer exclusion reduces nCAC | New acquisition candidate | `acquisition_customer_exclusion_lal_quality` |
| B-01c | Causal MMM reveals branded search and Meta ASC waste | Measurement-layer candidate | Needs MMM/experiment evidence contract |
| B-01d | OOH drives new-customer lift with zero repeat lift | Measurement/channel-role candidate | Cross-channel incrementality + retention evidence |
| B-02a | Geo testing unlocks upper-funnel Meta | Measurement/channel-role candidate | Needs geo-lift test ingestion |
| B-02b | PMax with brand queries outperforms without brand | Measurement-layer candidate | `measurement_pmax_brand_query_dependency`; geo-lift methodology blocks near-term active routing |
| B-03 | Audience overlap degrades Meta ROAS as spend scales | New acquisition candidate | `acquisition_audience_overlap_saturation` |
| B-04 | MTA over-credits select channels | Measurement-layer candidate | Attribution integrity guard |
| B-05 | Click MTA inverts ToF vs BoF creative performance | Measurement-layer candidate | Creative readout attribution guard |
| B-06 | Longer Meta click window outperforms shorter | Measurement/channel-strategy candidate | Needs geo/incrementality evidence and attribution-window config surface |
| B-07 | TikTok platform ROAS overstates true lift | Measurement-layer candidate | Platform-vs-incrementality guard |
| B-08 | Programmatic podcast omnichannel iROAS | Measurement-layer candidate | Omnichannel iROAS evidence needed |
| B-09 | DTC-only Meta iROAS misses retail distribution value | Measurement-layer candidate | Retail halo evidence needed |
| B-10 | Brand TV halo lands on marketplace | Measurement-layer candidate | Marketplace halo evidence needed |
| B-11 | Snapchat marketplace halo invisible to DTC attribution | Measurement-layer candidate | Marketplace halo evidence needed |
| B-12 | Mobile gaming ads halo lands on Amazon | Measurement-layer candidate | Marketplace/Amazon halo evidence needed |
| B-13 | Meta platform ROAS understates incremental iROAS | Measurement-layer candidate | Platform under-credit guard |
| B-14 | TikTok geo lift reveals incremental orders | Measurement-layer candidate | Geo-lift ingestion needed |
| B-15 | Audio underrated by last-click MTA | Measurement-layer candidate | Incremental audio demand guard |
| B-16 | Brand search non-incremental across seasons/markets | Measurement-layer candidate | Brand-search incrementality guard |
| B-17 | Promo-code attribution understates podcast iROAS | Measurement-layer candidate | Promo-code vs causal model guard |
| B-18 | 30s video beats 15s upper-funnel despite CPM | Measurement/channel-creative candidate | Needs creative-length test fields plus incrementality/geo evidence |
| B-19 | Affiliate loyalty/cashback zero incremental | Measurement/partner-channel candidate | Affiliate incrementality guard |
| FP-001 | PM + ShopCash mix distorts subscription rate | Already active | `conversion_subscription_mix`, `wb_001` / `wb_002` |
| FP-002 | ShopCash depresses subscription rate denominator | Already active | `conversion_subscription_mix`, `wb_002` |
| FP-003 | Evergreen naming should be judged on ATC mix | Legacy promotion candidate | `conversion_merchandising_primary_metric` |
| FP-004 | Brand spend worsens blended CPA while DR improves | Already active | `acquisition_cac_channel_mix`, `wb_004` |
| FP-005 | Meta IG/FB Shop routing raises CAC | Already active | `acquisition_cac_channel_mix`, `wb_005` |
| FP-006 | Inventory pullback improves CAC | Legacy promotion candidate | `acquisition_inventory_aware_spend_pullback` |
| FP-007 | Post-signal-loss recovery via creative + post-click | New cross-module candidate | `acquisition_signal_loss_creative_postclick_recovery` |
| FP-008 | Too-long attribution window hides incremental work | Measurement-layer candidate | `measurement_attribution_window_funnel_separation` |
| FP-009 | Long-cycle YouTube should start as retargeting amplifier | New acquisition candidate | `acquisition_youtube_retargeting_amplifier` |
| FP-010 | Structured UGC lowers CAC/CPM | Already active | `acquisition_ugc_creative`, `cba_001` |
| FP-011 | Compliance consent popup collapses CVR | Already active | `conversion_compliance_friction`, `cba_002` |
| FP-012 | First-time purchaser event improves CAC | Data-contract-gated acquisition/measurement candidate | `acquisition_new_customer_event_signal_quality`; active promotion blocked until event-quality fields and action surface exist |
| FP-013 | Offer-led creative lowers CAC but weakens repeat | Already deferred | `acquisition_ltv_quality_trap` |
| FP-014 | Lower-AOV offer wins on CAC/CVR despite margin tradeoff | New offer/margin candidate | Needs objective-aware margin guard |
| FP-015 | High-margin DABA improves profitability | New acquisition/margin candidate | `acquisition_high_margin_catalog_daba` |
| FP-016 | Product-specific creative lowers prospecting CAC | New creative candidate | `acquisition_product_specific_creative` |
| FP-017 | High-CTR Pinterest creative needs direct offer | New conversion/creative candidate | `conversion_high_ctr_low_cvr_offer_bridge` |
| FP-018 | Top-purchase LAL seed improves CAC | New acquisition candidate | `acquisition_lal_seed_quality` |
| FP-019 | Reels-native creative lowers CPM/blended CAC | New creative/channel candidate | `acquisition_reels_format_native_efficiency` |
| FP-020 | Google tracking migration causes signal-loss CAC spike | Measurement/data-quality candidate | `measurement_google_tracking_migration_signal_loss` |
| FP-021 | Welcome offer lowers CPM but hurts backend CVR | New offer/conversion candidate | `acquisition_reach_offer_backend_cvr_tradeoff` |
| FP-022 | Dedicated ABO testing reduces spend concentration | New testing-ops candidate | `acquisition_dedicated_abo_creative_testing` |
| FP-023 | Website-only beats Web + Shop routing | Existing-pattern reuse candidate | New brand binding for `acquisition_cac_channel_mix` after merchant setup |
| FP-024 | Revenue per session is best LP option metric | New conversion candidate | `conversion_option_architecture_rps_metric` |
| FP-025 | ADHD messaging beats broader benefit angles | New creative-angle candidate | `acquisition_creative_angle_specificity` |
| FP-026 | Affiliate brand-term bidding inflates metrics | Measurement/partner-channel candidate | `measurement_affiliate_brand_term_anomaly` |
| FP-027 | Brand keyword bleed inflates non-brand campaign | Measurement/search candidate | `measurement_brand_keyword_bleed` |
| FP-028 | Affiliate last-click inflates paid media CPA | Measurement/attribution candidate | `measurement_affiliate_last_click_inflation` |
| FP-029 | Gifted subscriptions deflate renewal rate | New retention-measurement candidate | `retention_gifted_subscription_denominator` |
| FP-030 | Pause feature masks true churn | New retention-lifecycle candidate | `retention_pause_masked_churn` |
| FP-031 | Autoship discount erodes margin without retention lift | New margin/retention candidate | `retention_autoship_discount_margin_erosion` |
| FP-032 | Bundle page paid traffic converts at half product pages | New conversion candidate | `conversion_bundle_page_paid_traffic_mismatch` |

## Proposed Promotion Order

### Phase 1 - Safe Source Alignment

Status: complete as of 2026-06-01. No runtime change. The FINAL doc has been
used to align source references for existing assets:

- `wb_001`, `wb_002`, `wb_004`, `wb_005`
- `cba_001`, `cba_002`
- dormant `acquisition_ltv_quality_trap`
- legacy `wb_003`, `wb_006`

This phase updated evidence provenance and FINAL-source facts only. Existing
pattern behavior was preserved.

### Phase 2 - Low-Risk Runtime Candidates

Promote only after explicit meta-pattern, brand binding, use-case YAML, and
fixture test are written:

- FP-003: `conversion_merchandising_primary_metric`
- FP-006: `acquisition_inventory_aware_spend_pullback`
- FP-023: Rarebird binding reuse for `acquisition_cac_channel_mix`

These are closer to V3's current data model than the incrementality cases, but
still require route-conflict checks. FP-012 was removed from this low-risk
tranche after coverage review because the source case depends on first-time
purchaser event quality, CAPI event match quality, and optimization-event
deployment fields that are not currently exposed as runtime contract fields.

### Phase 3 - Pattern Bank, Initially Dormant

Create dormant meta-pattern candidates under `playbooks/meta/_deferred/` for
measurement-heavy and cross-module cases. Do not load them until data contracts
exist:

- incrementality and halo measurement cases (`B-01a`, `B-01c`, `B-01d`,
  `B-02a`, `B-02b`, `B-04` through `B-19`, `FP-008`, `FP-012`, `FP-020`,
  `FP-026` through `FP-028`)
- retention/margin cases requiring lifecycle or contribution-margin fields
  (`FP-029` through `FP-031`)
- offer/margin objective tradeoffs (`FP-014`, `FP-015`, `FP-021`)

### Phase 4 - ADR / Runtime Contract Extension

Before activating a large library, decide whether V3 needs one of:

- executable trigger-condition routing,
- multi-pattern route return with ranking,
- a separate measurement guard layer,
- or stricter module/MSM-state allocation so cases remain mutually exclusive.

### Phase 5 - Explicit Non-Measurement Candidate Backlog

The following cases are not covered by Phase 2 or Phase 3 above and must be
handled through supervised promotion packets before any active YAML is written:

- acquisition/creative expansion: `B-01b`, `B-03`, `FP-007`, `FP-009`,
  `FP-016`, `FP-018`, `FP-019`, `FP-022`, `FP-025`
- offer, margin, retention, and conversion candidates: `FP-014`, `FP-015`,
  `FP-017`, `FP-021`, `FP-024`, `FP-029`, `FP-030`, `FP-031`, `FP-032`

Default mode for this backlog is dormant/source-backed candidate until the
promotion packet proves route exclusivity, data-contract readiness, action
surface support, and test coverage.

## Open Decisions

1. Confirm whether anonymized benchmark cases (`B-*`) should remain source-only
   or become a dormant pattern bank.
2. Confirm canonical merchant IDs for named first-party brands not currently in
   V3: Bonafide Health, Spoonful of Comfort, Grass Roots Farmers Cooperative,
   Consumer Brand C, Consumer Brand D, Rarebird Coffee, Skincare Brand, Wine
   Subscription Brand, and Pet CPG Brand.
3. Decide whether FINAL doc numbers may be copied into active use-case YAMLs or
   should remain in `partner_drafts/` until partner approval.
4. Decide whether to extend the runtime routing contract before activating more
   than one pattern per merchant/module/MSM state.
