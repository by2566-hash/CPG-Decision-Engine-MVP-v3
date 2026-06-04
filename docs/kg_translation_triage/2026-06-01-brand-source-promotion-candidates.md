# Brand Source Promotion Candidates - 2026-06-01

## Decision

No case from the six-file brand source batch is promoted directly to active runtime KG in this reconciliation step.

The ranking below is candidate scoring only. It uses the six-file brand source batch as provenance for existing Use Case Library FINAL cases `FP-007` through `FP-032`; it is not approval to create or modify runtime KG assets.

## Candidate Ranking

| Rank | Case IDs | Promotion posture | Notes |
| --- | --- | --- | --- |
| 1 | FP-023 | Best first runtime-promotion candidate after confirmation | Can likely reuse existing `playbooks/meta/acquisition_cac_channel_mix.yaml`; action surface `FIX_DESTINATION_ROUTING` exists; still needs canonical `rarebird` merchant ID, Layer 2 brand binding, Layer 3 use case SSoT, and route tests. |
| 2 | FP-010 / FP-011 | Already represented | Use new brand source batch only to strengthen provenance if needed; runtime assets already exist. |
| 3 | FP-016 / FP-018 / FP-019 / FP-022 / FP-025 | Future acquisition/creative candidates | Need creative taxonomy, campaign data contract, route exclusivity, and supported action surfaces. |
| 4 | FP-014 / FP-015 / FP-017 / FP-021 / FP-024 / FP-029 / FP-030 / FP-031 / FP-032 | Future offer/retention/conversion candidates | Need margin, offer, retention/cohort, landing-page, and action contracts. |
| 5 | FP-008 / FP-012 / FP-020 / FP-026 / FP-027 / FP-028 | Measurement/data-contract candidates | Need measurement, event-quality, affiliate, search-query, and attribution contracts before runtime. |

## Coverage Notes

The ranking table covers the cases with the clearest promotion posture in the current reconciliation step. The remaining cases are still covered by prior gates and are not active-ready:

- `FP-007` and `FP-009` remain acquisition/creative expansion gated source-only cases.
- `FP-013` remains already represented and Phase 1 source-aligned; this batch can strengthen provenance if needed.

Together, the table plus these coverage notes account for `FP-007` through `FP-032` from the six-file brand source batch.

## Recommended Next Promotion

Start with `FP-023` only after the user confirms the canonical merchant slug and approves creation of:

- `playbooks/brands/rarebird/acquisition_cac_channel_mix.yaml`
- `use_cases/rarebird/rb_001_website_vs_shop_destination.yaml`
- route and brand-binding tests for `merchant_id=rarebird`

Runtime promotion should remain a separate user-approved implementation step with source reconciliation, Layer 2 brand binding, Layer 3 use case SSoT, route tests, and reviewer approval.

## Boundary

No runtime file was created in this reconciliation step.

This document is not runtime input. It is a tracked triage artifact for promotion candidate ranking only.
