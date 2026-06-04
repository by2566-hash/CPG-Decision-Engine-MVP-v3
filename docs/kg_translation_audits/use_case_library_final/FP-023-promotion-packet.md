---
source_case_id: FP-023
status: blocked_for_active_promotion
created_at: 2026-06-01
scope: T1 audit packet only
---

# FP-023 Promotion Packet

## Source

| Field | Value |
|-------|-------|
| Source case ID | FP-023 |
| Source line | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2869` |
| Source title | FP-023 \| 2. Website-only destination outperformed Web + Shop in a head-to-head Meta routing test |
| Case index | `partner_drafts/kg_partner/use_case_library_final/case_index.json` line 318 entry confirms line 2869 and title |
| Source excerpt reviewed | Lines 2869-2934 |
| Existing reusable asset | `playbooks/meta/acquisition_cac_channel_mix.yaml` |

## Source Summary

Rarebird tested website-only routing against Web + Shop routing using the
same ads/testing structure. In the head-to-head test, 28-day click cost per
purchase was 171.46 for Web + Shop versus 144.56 for Web only. Cost per add
to cart improved from 9.526 to 7.228 in favor of the website route. The
source says volume was still light, so the case is directional rather than
fully closed-loop.

## Gate Decisions

| Gate | Decision | Evidence |
|------|----------|----------|
| Target mode | Reuse candidate only; do not create active Rarebird binding yet | Existing `acquisition_cac_channel_mix` covers destination routing conceptually, but Rarebird merchant setup is absent. |
| Duplicate check | Reuse existing meta-pattern; no new Layer 1 pattern needed | `playbooks/meta/acquisition_cac_channel_mix.yaml` already models on-platform destination routing and action `FIX_DESTINATION_ROUTING`. Existing active evidence is Wandering Bear FP-005, not Rarebird. |
| Merchant ID | Fail | No canonical Rarebird merchant slug, brand binding directory, or use case directory exists in the repo. `rarebird` appears only in triage/source docs. |
| Route exclusivity | Cannot pass until merchant ID exists | Route exclusivity is checked by same merchant + module + MSM state. Without canonical `merchant_id`, same-merchant overlap cannot be proven. The reusable meta-pattern routes acquisition WATCH and DEGRADING. |
| Data-contract readiness | Partial, not active-ready | Source provides direct website-vs-shop CPP and CPATC comparisons. Active runtime evidence currently expects CAC baseline, on-platform content-view delta, checkout CVR, and `onplatform_cpp_ratio` support. Split destination metrics and same-ad-pool test metadata need explicit L0/L2 fields before active routing. |
| Action-surface readiness | Pass for existing action only | `FIX_DESTINATION_ROUTING` exists in the meta-pattern, benchmark engine, and renderer. `REALLOCATE_BUDGET` also exists as diagnostic support. No new action surface is needed if the case reuses this pattern. |
| Threshold discipline | Pending | `destination_cpp_gap_threshold` is an active key. The source suggests 1.10; Wandering Bear binding uses 1.20. Rarebird needs its own calibrated threshold before an active binding. |

## Asset Manifest

| Layer | File | Decision |
|-------|------|----------|
| Layer 1 meta-pattern | `playbooks/meta/acquisition_cac_channel_mix.yaml` | Reuse candidate; no edit made. |
| Layer 2 brand binding | `playbooks/brands/{canonical_rarebird_id}/acquisition_cac_channel_mix.yaml` | Not created; merchant ID and calibration are pending. |
| Layer 3 use case SSoT | `use_cases/{canonical_rarebird_id}/...yaml` | Not created; source-only evidence until merchant ID is confirmed. |
| Tests | N/A | No active binding created, so no route fixture added. |
| Audit docs | `docs/kg_translation_audits/use_case_library_final/FP-023-promotion-packet.md` | Created by this task. |

## Raw Evidence Location

Raw Rarebird evidence currently exists only in
`partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md`
lines 2869-2934. No Rarebird Layer 3 use case file exists yet, so raw numbers
must not be placed into a future brand binding.

Useful computed ratios from the source:

| Metric | Calculation | Result |
|--------|-------------|--------|
| CPP ratio | 171.46 / 144.56 | 1.186, meaning Web + Shop CPP was about 18.6% higher |
| CPATC ratio | 9.526 / 7.228 | 1.318, meaning Web + Shop CPATC was about 31.8% higher |

## Utility And Evidence Decision

The evidence supports conceptual reuse of `acquisition_cac_channel_mix`, but
it should not set an active `gmv_lift_prior` yet. The existing formula requires
business-volume context such as monthly new customers, AOV, and monthly GMV,
and the source itself marks volume as light. Treat the case as source-backed
directional evidence until a Rarebird Layer 3 use case and utility derivation
exist.

## Partner Questions

1. What is the canonical merchant slug for Rarebird Coffee?
2. Should Rarebird use `destination_cpp_gap_threshold: 1.10`, the existing
   Wandering Bear 1.20 value, or another calibrated threshold?
3. What are Rarebird monthly new customers, AOV, and monthly GMV for the test
   period so `gmv_lift_prior` can be derived?
4. Are website-only and Web + Shop metrics from the same ad pool and same
   campaign logic, with no material creative/audience differences?
5. Should the active recommendation be immediate `FIX_DESTINATION_ROUTING` or
   a diagnostic/test-first action until more volume accumulates?

Final status: `BLOCKED`.
