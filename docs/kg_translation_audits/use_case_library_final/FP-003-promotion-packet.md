---
source_case_id: FP-003
status: blocked_for_active_promotion
created_at: 2026-06-01
scope: T1 audit packet only
---

# FP-003 Promotion Packet

## Source

| Field | Value |
|-------|-------|
| Source case ID | FP-003 |
| Source line | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1560` |
| Source title | FP-003 \| 3. Evergreen flavor naming test should be judged on evergreen ATC mix, not final CVR |
| Case index | `partner_drafts/kg_partner/use_case_library_final/case_index.json` line 178 entry confirms line 1560 and title |
| Source excerpt reviewed | Lines 1560-1613 |
| Existing source-aligned asset | `use_cases/wandering_bear/_legacy/wb_003_evergreen_naming_test.yaml` |

## Source Summary

Wandering Bear ran a landing-page naming test intended to shift add-to-cart
mix toward evergreen flavors with better downstream economics. The source says
the correct readout is evergreen ATC share, not final checkout CVR. Observed
evidence: evergreen ATC share increased from 42.74% to 49.00% (+6.26pp, about
14.6% relative), while CPA/CVR/AOV were roughly neutral to positive. Some
individual renames underperformed and need iteration or rollback.

## Gate Decisions

| Gate | Decision | Evidence |
|------|----------|----------|
| Target mode | Keep as legacy evidence; do not promote active | Existing file is explicitly `legacy_status: pre_three_layer` and points to flat stub `conversion_merchandising_v1`, not a Layer 1 meta-pattern. |
| Duplicate check | No equivalent active meta-pattern found, but active conversion route overlap exists | Current active Wandering Bear conversion binding is `conversion_subscription_mix` with WATCH and DEGRADING triggers. Existing `conversion_merchandising_v1` is a flat stub, not a valid three-layer pattern. |
| Merchant ID | Pass | Existing canonical merchant slug is `wandering_bear` in the legacy use case and active brand bindings. |
| Route exclusivity | Fail for active promotion | Current routing is module + MSM state + merchant_id. The route matrix has `wandering_bear / conversion / WATCH,DEGRADING` already bound to `conversion_subscription_mix`. The FP-003 source does not justify a distinct MSM state; `triggers.condition` cannot make routing exclusive. |
| Data-contract readiness | Fail | The needed primary signal is evergreen vs LTO ATC share by test group plus naming-test objective and variant outcomes. Current `DecisionFeatureVector` has generic CVR/inventory/margin/repeat/promo/churn fields, not product-framing test mix fields. Current conversion MSM uses mobile-vs-desktop ATC and checkout CVR, not evergreen mix. |
| Action-surface readiness | Fail | Legacy action `REORDER_SHELF` exists in benchmarks and renderer, but current renderer text is mobile shelf layout, not naming-framework evaluation or variant rollback. Using it would produce a semantically wrong recommendation. |
| Threshold discipline | Blocked pending design | A future active pattern would need an explicit, registered threshold or non-threshold decision rule for primary-metric selection. No active key for evergreen ATC mix/test objective exists today. |

## Asset Manifest

| Layer | File | Decision |
|-------|------|----------|
| Layer 1 meta-pattern | `playbooks/meta/conversion_merchandising_primary_metric.yaml` | Not created; active gates failed. |
| Layer 2 brand binding | `playbooks/brands/wandering_bear/conversion_merchandising_primary_metric.yaml` | Not created; route and action gates failed. |
| Layer 3 use case SSoT | `use_cases/wandering_bear/_legacy/wb_003_evergreen_naming_test.yaml` | Reviewed only; remains legacy. |
| Existing flat stub | `playbooks/conversion_merchandising_v1.yaml` | Reviewed as non-promotable stub. |
| Tests | N/A | No active runtime asset created, so no fixture test added. |
| Audit docs | `docs/kg_translation_audits/use_case_library_final/FP-003-promotion-packet.md` | Created by this task. |

## Raw Evidence Location

Raw observed numbers are already in the legacy SSoT under
`use_cases/wandering_bear/_legacy/wb_003_evergreen_naming_test.yaml`,
especially `calibration_value_for` and `data_observed`. No raw numbers were
copied into a brand binding.

## Utility And Evidence Decision

The legacy use case contains a future-use utility derivation
(`gmv_lift_estimate: 0.09`) based on evergreen ATC share lift and PLTV ROAS
improvement. Treat this as usable Layer 3 evidence only. It is not sufficient
to create an active brand binding until routing, data contract, and action
surface are fixed.

## Partner Questions

1. Should the action be a test-readout action such as "set primary test metric"
   rather than `REORDER_SHELF`?
2. What minimum evergreen ATC mix lift or confidence level should justify
   keeping a naming framework?
3. How should weaker individual names be represented: rollback action, variant
   iteration, or only diagnostic guidance?
4. Which MSM state should route this pattern without colliding with
   `conversion_subscription_mix`?

Final status: `BLOCKED`.
