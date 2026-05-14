# Partner Clarification: Wandering Bear Retroactive Estimate Confirmation

**Date:** 2026-04-14
**Brand:** Wandering Bear
**Type:** gmv_lift_prior estimate confirmation
**Priority:** Medium — not blocking demo; needed before outcome calibration upgrades

## Background

During Group 1 / Group 2 audit remediation (2026-04-14), four estimate-backed
inputs were identified in active Wandering Bear use cases that have not yet
been confirmed by the partner. These inputs were used to derive `gmv_lift_prior`
values currently loaded into the active brand bindings.

The estimates are reasonable (derived from available data or industry-typical
values), but they are marked `estimated: true` or sourced from Globalink
internal assumptions rather than confirmed WB actuals. Until confirmed, the
`gmv_lift_prior` values they underpin are `calibration_status: partner_prior`
— not `outcome_calibrated`.

This file tracks the four open confirmation requests.

---

## Item 1 — wb_001: `prevented_action_cost_est` (DIAGNOSE_MIX)

**Use case:** `use_cases/wandering_bear/wb_001_subscription_mix_dilution.yaml`
**Field:** `gmv_lift_derivation.prevented_action_cost_est`
**Current value:** `"2-4 weeks engineering (misallocated)"`
**Derived prior:** `DIAGNOSE_MIX gmv_lift_prior: 0.08`

**Why it matters:**
The `gmv_lift_prior` for `DIAGNOSE_MIX` is computed using
`diagnostic_prevention_value` method — the value of correctly diagnosing
mix dilution is quantified as the cost of the wrong action prevented
(sitewide subscription redesign). The 2-4 week engineering estimate is
the anchor for this prevention value. If the actual avoided cost was
substantially smaller or larger, the prior should be recalibrated.

**Ask:**
When the incorrect diagnosis (sitewide subscription redesign) was considered,
what was the actual scope of work being planned? Was it truly in the 2-4 week
engineering range, or more/less? Any specifics on team size or sprint scope
would help refine the prevented-cost basis.

---

## Item 2 — wb_005: `monthly_new_customers_est` (FIX_DESTINATION_ROUTING)

**Use case:** `use_cases/wandering_bear/wb_005_meta_destination_mix.yaml`
**Field:** `gmv_lift_derivation.monthly_new_customers_est`
**Current value:** `2290`
**Source:** Derived as `$58K weekly Meta spend / $141 UGC CAC × 4 weeks`
  (cross-referenced from WB acquisition data; marked as estimate)
**Derived prior:** contributes to `FIX_DESTINATION_ROUTING gmv_lift_prior: 0.12`

**Why it matters:**
The `cac_improvement_to_gmv_lift` formula multiplies `cac_improvement_pct ×
(monthly_new_customers × aov / monthly_gmv)`. Monthly new customers is the
scaling factor that converts the CAC improvement percentage into a GMV lift
fraction. If the actual WB monthly new customer count during March–April 2023
was materially different from 2290, the 0.12 prior will need recalibration.

**Ask:**
What was the approximate number of new customers acquired per month via Meta
during March–April 2023? An order-of-magnitude confirmation (e.g. "roughly
2000–2500" or "closer to 1500") is sufficient.

---

## Item 3 — wb_005: `aov_est` (FIX_DESTINATION_ROUTING)

**Use case:** `use_cases/wandering_bear/wb_005_meta_destination_mix.yaml`
**Field:** `gmv_lift_derivation.aov_est`
**Current value:** `47.0`
**Source:** Used as a typical WB order value; not explicitly confirmed for
  the March–April 2023 observation period
**Derived prior:** contributes to `FIX_DESTINATION_ROUTING gmv_lift_prior: 0.12`

**Why it matters:**
AOV directly scales the GMV lift formula. A $47 AOV yields the current 0.12
prior. If WB's actual AOV during this period was materially higher (e.g. $60+)
or lower (e.g. $35), the prior denominator changes accordingly.

**Ask:**
What was WB's average order value during Q1–Q2 2023 (the March–April
observation window)? A confirmed figure from the Shopify/Shopline data export
would replace this estimate.

---

## Item 4 — wb_005: `monthly_gmv_est` (FIX_DESTINATION_ROUTING)

**Use case:** `use_cases/wandering_bear/wb_005_meta_destination_mix.yaml`
**Field:** `gmv_lift_derivation.monthly_gmv_est`
**Current value:** `150000` (i.e. $150k/month)
**Source:** Internal estimate; `derivation_note` in the use case flags it as
  conservative ("actual monthly_gmv may be higher → lift fraction lower")
**Derived prior:** denominator in `FIX_DESTINATION_ROUTING gmv_lift_prior: 0.12`

**Why it matters:**
Monthly GMV is the denominator of the lift formula. The current $150k estimate
is conservative. If WB's actual monthly GMV was $250k–$300k+, the 0.12 prior
would recalibrate downward (smaller fraction). If it was closer to $100k, the
prior recalibrates upward. This is the highest-leverage single input to the
`FIX_DESTINATION_ROUTING` prior.

**Ask:**
What was WB's approximate total monthly GMV (across all channels) during
March–April 2023? Even a range (e.g. "$200k–$300k/month") would materially
improve the prior quality. This figure is typically available from
Shopify/Shopline monthly revenue reports.

---

## Resolution

This file can be closed when all four items have been confirmed (or explicitly
waived as "estimate acceptable at this stage"). Update the corresponding
`use_cases/wandering_bear/` YAML files with confirmed values and mark
`estimated: false` where applicable. Set `calibration_status:
outcome_calibrated` only after N ≥ 10 real outcome records, per ADR-0011.
