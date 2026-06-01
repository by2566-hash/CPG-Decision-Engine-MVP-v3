---
source_group: Use Case Library FINAL
status: tracked_manifest_raw_source_gitignored
created_at: 2026-06-01
raw_source_tracked_in_git: false
---

# Source Manifest - Use Case Library FINAL

## Purpose

This manifest is the tracked audit anchor for the Use Case Library FINAL intake.
It preserves provenance, extraction hashes, case IDs, source lines, and current
translation disposition without committing the raw partner document or full
source transcript.

Raw source files remain under:

`partner_drafts/kg_partner/use_case_library_final/`

That directory is intentionally gitignored because the source may contain
partner-sensitive business material. Do not copy raw source text or raw observed
metrics into runtime YAML, Layer 2 brand bindings, or public artifacts without
explicit partner approval.

## Source Files

| File | Size bytes | SHA-256 | Git status |
|------|------------|---------|------------|
| `Use Case Library FINAL.docx` | 53045 | `171a2342a38d2551e04e78fef1ee94906c3f82c69e2b442d36591fe8db01db4d` | gitignored raw source |
| `use_case_library_final.md` | 137670 | `e4ab11775b2730d5c937dc7c5a1a1477702d559a96ddb5405dc9c2df141eb095` | gitignored extracted source |
| `case_index.json` | 13066 | `9f05694d362147316fa3ddd454f24665354fd347c2d33306343f7ad53343dcdf` | gitignored extracted index |

## Extraction Method

- Input: `/Users/yubo/Downloads/Use Case Library FINAL.docx`
- Archive location: `partner_drafts/kg_partner/use_case_library_final/`
- Extracted markdown: `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md`
- Extracted index: `partner_drafts/kg_partner/use_case_library_final/case_index.json`
- Case count verified from `case_index.json`: 55 unique IDs.
- Tracked disposition source:
  `docs/kg_translation_triage/2026-06-01-source-coverage-ledger.md`

## Governance

| Topic | Decision |
|-------|----------|
| Raw source in git | No. Keep under gitignored `partner_drafts/`. |
| Tracked provenance | Yes. Use this manifest plus triage, coverage ledger, and supervision record. |
| Long-term raw-source storage | Pending user-chosen private artifact store, such as private Drive, S3, or internal document storage. |
| Runtime use of raw numbers | Blocked unless partner approval and Layer 3 SSoT decision are recorded. |
| Active runtime promotion | Not authorized by this manifest. |

## Related Tracked Artifacts

| Artifact | Purpose |
|----------|---------|
| `docs/kg_intake_log.md` | Intake status and classification summary |
| `docs/kg_translation_triage/2026-06-01-use-case-library-final.md` | Main triage copy |
| `docs/kg_translation_triage/2026-06-01-source-coverage-ledger.md` | 55-case coverage ledger |
| `docs/kg_translation_triage/2026-06-01-supervised-translation-plan.md` | Supervised execution plan |
| `docs/kg_translation_audits/2026-06-01-use-case-library-final-supervision.md` | Multi-agent supervision and verification record |

## Case Index

| Case | Source line | Title | Current disposition |
|------|-------------|-------|---------------------|
| B-01a | 8 | B-01a: Click attribution undercounts YouTube's true new-customer acquisition value | Measurement/data-contract/incrementality gated |
| B-01b | 64 | B-01b: Tight existing-customer exclusion in lookalike prospecting reduces nCAC | Acquisition and creative expansion gated |
| B-01c | 120 | B-01c: Causal MMM with anchored experiments reveals branded search and Meta ASC waste | Measurement/data-contract/incrementality gated |
| B-01d | 184 | B-01d: OOH uniquely drives 100% new-customer lift with zero repeat lift | Measurement/data-contract/incrementality gated |
| B-02a | 247 | B-02a: Geo testing unlocks upper-funnel Meta proven equivalent to performance campaigns | Measurement/data-contract/incrementality gated |
| B-02b | 303 | B-02b: PMax with brand queries dramatically outperforms PMax without brand | Measurement/data-contract/incrementality gated |
| B-03 | 366 | B-03: Audience overlap degrades Meta ROAS as spend scales (mechanism-buried) | Acquisition and creative expansion gated |
| B-04 | 430 | B-04: MTA platform over-credits select channels vs. true incrementality | Measurement/data-contract/incrementality gated |
| B-05 | 491 | B-05: Click MTA inverts top-of-funnel vs. bottom-of-funnel creative performance | Measurement/data-contract/incrementality gated |
| B-06 | 554 | B-06: Longer Meta click optimization window outperforms shorter despite conservative assumption | Measurement/data-contract/incrementality gated |
| B-07 | 616 | B-07: Platform-reported TikTok ROAS overstates true incremental lift; optimization unlocks it | Measurement/data-contract/incrementality gated |
| B-08 | 681 | B-08: Programmatic podcast delivers disproportionate omnichannel iROAS for small spend share | Measurement/data-contract/incrementality gated |
| B-09 | 743 | B-09: DTC-only Meta iROAS understates true value for brands with retail distribution | Measurement/data-contract/incrementality gated |
| B-10 | 809 | B-10: Brand TV halo lands on marketplace, not DTC | Measurement/data-contract/incrementality gated |
| B-11 | 874 | B-11: Snapchat reveals over half of revenue in marketplace halo invisible to DTC attribution | Measurement/data-contract/incrementality gated |
| B-12 | 937 | B-12: Mobile gaming ads halo lands on Amazon, 87% invisible to direct attribution | Measurement/data-contract/incrementality gated |
| B-13 | 1000 | B-13: Meta platform-reported ROAS understates true incremental iROAS by ~35% | Measurement/data-contract/incrementality gated |
| B-14 | 1061 | B-14: Last-touch attribution credits fewer than 20 TikTok conversions; geo lift reveals ~~9,500 incremental orders | Measurement/data-contract/incrementality gated |
| B-15 | 1130 | B-15: Audio underrated by last-click MTA; incrementally positive for new customer demand | Measurement/data-contract/incrementality gated |
| B-16 | 1192 | B-16: Brand search non-incremental across slow season, peak season, and new markets | Measurement/data-contract/incrementality gated |
| B-17 | 1255 | B-17: Promo-code attribution understates podcast iROAS by 2-3X vs. causal modeling | Measurement/data-contract/incrementality gated |
| B-18 | 1321 | B-18: :30s video outperforms :15s in upper-funnel despite higher CPM | Measurement/data-contract/incrementality gated |
| B-19 | 1385 | B-19: Affiliate loyalty/cashback channel zero incremental despite top last-click share | Measurement/data-contract/incrementality gated |
| FP-001 | 1456 | FP-001 / 1. PM flavor mix and ShopCash mix distorted reported subscription rate | Already represented and Phase 1 source-aligned |
| FP-002 | 1510 | FP-002 / 2. ShopCash orders mechanically depressed reported subscription rate | Already represented and Phase 1 source-aligned |
| FP-003 | 1560 | FP-003 / 3. Evergreen flavor naming test should be judged on evergreen ATC mix, not final CVR | Already represented and Phase 1 source-aligned |
| FP-004 | 1615 | FP-004 / 4. Blended CPA worsened after adding brand spend, while DR CPA improved | Already represented and Phase 1 source-aligned |
| FP-005 | 1663 | FP-005 / 5. CAC increase caused by Meta shifting traffic into IG / FB Shop destinations | Already represented and Phase 1 source-aligned |
| FP-006 | 1717 | FP-006 / 6. Inventory-driven spend pullback improved CAC while PM dominated Meta spend | Already represented and Phase 1 source-aligned |
| FP-007 | 1770 | FP-007 / 1. Post-signal-loss paid social recovery requires moving the optimization burden from targeting onto creative and post-click experience | Acquisition and creative expansion gated |
| FP-008 | 1841 | FP-008 / 1. A too-long paid social attribution window is a measurement bug that conceals where the incremental new-customer work is happening | Measurement/data-contract/incrementality gated |
| FP-009 | 1911 | FP-009 / 1. When buying cycle is long and YouTube is a new channel, retargeting amplifier is the correct first role, not prospecting | Acquisition and creative expansion gated |
| FP-010 | 1981 | FP-010 / 1. CAC and CPMs declined following the introduction of a structured UGC creator program on Meta | Already represented and Phase 1 source-aligned |
| FP-011 | 2043 | FP-011 / 2. Legally required health data consent pop-up caused a sudden CVR collapse across all traffic sources | Already represented and Phase 1 source-aligned |
| FP-012 | 2104 | FP-012 / 3. Rebuilding the purchase event to isolate new customers improved CAC about 30% | Measurement/data-contract/incrementality gated |
| FP-013 | 2170 | FP-013 / 4. Offer-led creative reduced CAC but weakened repeat purchase behavior | Already represented and Phase 1 source-aligned |
| FP-014 | 2221 | FP-014 / 5. Lower-AOV offer outperformed on CAC and CVR despite weaker profit per order | Offer, margin, retention, and conversion gated |
| FP-015 | 2272 | FP-015 / 6. Restricting DABA to high-margin SKUs improved order profitability without meaningful CAC tradeoff | Offer, margin, retention, and conversion gated |
| FP-016 | 2347 | FP-016 / 1. Product-specific creative lowered prospecting CAC and held through the post-launch period | Acquisition and creative expansion gated |
| FP-017 | 2418 | FP-017 / 2. High CTR Pinterest creative required a direct offer to improve conversion | Offer, margin, retention, and conversion gated |
| FP-018 | 2488 | FP-018 / 3. LAL seeding from top-performing purchase segments improved CAC as an incremental efficiency lever | Acquisition and creative expansion gated |
| FP-019 | 2568 | FP-019 / 1. Format-native Reels creative reduced CPMs and improved blended CAC as a complementary top-of-funnel lever | Acquisition and creative expansion gated |
| FP-020 | 2643 | FP-020 / 2. Conversion signal loss during Google tracking migration caused a CAC spike and partial recovery after reconnection | Measurement/data-contract/incrementality gated |
| FP-021 | 2717 | FP-021 / 3. New welcome offer expanded reach through lower CPMs but underperformed on backend conversion | Offer, margin, retention, and conversion gated |
| FP-022 | 2796 | FP-022 / 1. Dedicated ABO creative testing reduced spend concentration and improved Meta efficiency | Acquisition and creative expansion gated |
| FP-023 | 2869 | FP-023 / 2. Website-only destination outperformed Web + Shop in a head-to-head Meta routing test | Existing-pattern reuse candidate |
| FP-024 | 2936 | FP-024 / 3. Revenue per session was the best decision metric in a landing-page option-architecture test | Offer, margin, retention, and conversion gated |
| FP-025 | 3014 | FP-025 / 4. ADHD messaging materially outperformed broader value-prop and alternative benefit angles | Acquisition and creative expansion gated |
| FP-026 | 3099 | FP-026 / 1. Single affiliate bidding on brand terms produced an impossible conversion rate and inflated program metrics | Measurement/data-contract/incrementality gated |
| FP-027 | 3190 | FP-027 / 2. Brand keyword bleed into a non-brand paid campaign inflated product performance | Measurement/data-contract/incrementality gated |
| FP-028 | 3275 | FP-028 / 3. Affiliate last-click attribution inflated reported paid media CPA | Measurement/data-contract/incrementality gated |
| FP-029 | 3361 | FP-029 / 1. Gifted subscriptions mixed into retention reporting deflated renewal rate | Offer, margin, retention, and conversion gated |
| FP-030 | 3472 | FP-030 / 2. Pause feature usage masked true churn and understated subscriber attrition rate | Offer, margin, retention, and conversion gated |
| FP-031 | 3572 | FP-031 / 1. Autoship discount offered broadly eroded margin without improving retention | Offer, margin, retention, and conversion gated |
| FP-032 | 3674 | FP-032 / 2. Bundle page received paid traffic but converted at half the rate of individual product pages | Offer, margin, retention, and conversion gated |
