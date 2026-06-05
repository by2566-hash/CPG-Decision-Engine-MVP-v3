---
source_case_id: FP-006
status: blocked_for_active_promotion
created_at: 2026-06-01
scope: T1 audit packet only
---

# FP-006 Promotion Packet

## Source

| Field | Value |
|-------|-------|
| Source case ID | FP-006 |
| Source line | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1717` |
| Source title | FP-006 \| 6. Inventory-driven spend pullback improved CAC while PM dominated Meta spend |
| Case index | `partner_drafts/kg_partner/use_case_library_final/case_index.json` line 199 entry confirms line 1717 and title |
| Source excerpt reviewed | Lines 1717-1766 |
| Existing source-aligned asset | `use_cases/wandering_bear/_legacy/wb_006_inventory_spend_pullback.yaml` |

## Source Summary

Wandering Bear reduced spend when PM represented 71% of Meta spend and PM
inventory was tightening. The action happened on Jan 9, 2023. Spend was cut
by $350 total across FB, TikTok, and Google, and 7-day CAC improved from
$46.97 to $43.23 while spend fell 5.89%. The source frames this as
ops-aware acquisition budgeting: reduce paid spend before inventory pressure
fully breaks efficiency.

## Gate Decisions

| Gate | Decision | Evidence |
|------|----------|----------|
| Target mode | Keep as legacy evidence; do not promote active | Existing file is `legacy_status: pre_three_layer` and still references flat stub `acquisition_efficiency_v1`. |
| Duplicate check | No equivalent active inventory-aware pattern found, but active acquisition route overlap exists | No `acquisition_inventory_aware_spend_pullback` meta-pattern exists. Wandering Bear already has active `acquisition_cac_channel_mix` on acquisition WATCH and DEGRADING. |
| Merchant ID | Pass | Existing canonical merchant slug is `wandering_bear`. |
| Route exclusivity | Fail for active promotion | Current route matrix has `wandering_bear / acquisition / WATCH,DEGRADING` bound to `acquisition_cac_channel_mix`. FP-006 would need acquisition WATCH or DEGRADING routing, so it overlaps unless ADR-0012 is superseded or a new routing dimension exists. |
| Data-contract readiness | Fail | The pattern needs constrained SKU/flavor share of paid spend, platform-level budget allocation, inventory runway, and ops freshness/delay signals. `DecisionFeatureVector` has inventory days and stock pressure, but no SKU spend concentration or ad-platform-to-inventory join. `inventory_safety_days` is a dormant threshold key. |
| Action-surface readiness | Fail | Legacy action `PAUSE_CHANNEL` is explicitly marked wrong in the use case. The resolved clarification says the action should be SKU-level spend reduction, suggested `REDUCE_SKU_SPEND`, which is not present in benchmarks, renderer templates, or active meta-pattern action vocabularies. |
| Threshold discipline | Fail for active promotion | `inventory_safety_days` is registered as dormant. Any active binding that references it would emit a dormant-threshold warning, which this translation plan treats as a hard gate. |

## Asset Manifest

| Layer | File | Decision |
|-------|------|----------|
| Layer 1 meta-pattern | `playbooks/meta/acquisition_inventory_aware_spend_pullback.yaml` | Not created; route, data, threshold, and action gates failed. |
| Layer 2 brand binding | `playbooks/brands/wandering_bear/acquisition_inventory_aware_spend_pullback.yaml` | Not created; active gates failed. |
| Layer 3 use case SSoT | `use_cases/wandering_bear/_legacy/wb_006_inventory_spend_pullback.yaml` | Reviewed only; remains legacy. |
| Existing flat stub | `playbooks/acquisition_efficiency_v1.yaml` | Reviewed as non-promotable stub. |
| Tests | N/A | No active runtime asset created, so no fixture test added. |
| Audit docs | `docs/kg_translation_audits/use_case_library_final/FP-006-promotion-packet.md` | Created by this task. |

## Raw Evidence Location

Raw observed numbers are in
`use_cases/wandering_bear/_legacy/wb_006_inventory_spend_pullback.yaml`,
especially `calibration_value_for`, `data_observed`, and
`analysis_executed`. No raw evidence was moved into Layer 2.

## Utility And Evidence Decision

The legacy file derives `gmv_lift_estimate: 0.04` from CAC improvement and
modest spend reduction. This evidence is directionally useful but cannot be
bound to the current legacy action ID because `PAUSE_CHANNEL` is known wrong.
Future utility should attach to a supported SKU-level budget action after the
action surface exists.

## Partner Questions

1. Confirm the canonical active action ID and semantics for SKU-specific paid
   spend reduction. Is `REDUCE_SKU_SPEND` acceptable?
2. What PM or constrained-SKU spend share should trigger review: 71%, a lower
   value, or a category-specific threshold?
3. What inventory runway threshold defines "limited inventory"?
4. Which source system provides the join between ad spend by SKU/flavor and
   live inventory runway?
5. Should this ever route through the same acquisition MSM states as
   `acquisition_cac_channel_mix`, or does it require a new routing contract?

Final status: `BLOCKED`.
