# Playbook Authoring SOP
## Partner KG Content → V3 Three-Layer Structure

**Governed by**: ADR-0011
**Last updated**: 2026-04-12
**Status**: Active — v0.1 (threshold namespace will evolve, see Section 4)

---

## Purpose

This SOP defines how to translate partner-delivered KG content (business use cases,
brand analytics narratives) into the V3 three-layer KG structure. Following this
SOP ensures that:

- Every threshold is per-brand configurable and never hardcoded
- Every `gmv_lift_prior` has a traceable evidence source
- Cross-brand patterns are identified and extracted, not duplicated
- The system can calibrate priors as real outcome data accumulates

---

## The Three-Layer Structure

```
Layer 1: playbooks/meta/*.yaml              ← platform-level, partner maintains
              ↓ referenced by meta_pattern_ref
Layer 2: playbooks/brands/{brand}/*.yaml    ← brand-level, you maintain
              ↓ thresholds populate
Layer 3: PolicyPack.alert_thresholds        ← dynamic, calibration updates
```

**Rule: Layer 1 contains ZERO hardcoded threshold numbers.**
**Rule: Layer 2 contains NO raw evidence data (use evidence_case pointer only).**
**Rule: All observed data lives in use_cases/{brand}/*.yaml (Single Source of Truth).**

---

## Section 1: The 10-Step Workflow (Per Partner Delivery Batch)

Each time partner delivers a new batch of brand use cases, execute in this order:

**Step 0: Read the full batch before writing anything**
Read every use case in the batch as a whole. Do not start writing YAML until
you have read all cases in the current delivery.

**Step 1: Cross-brand pattern identification**
Compare new cases against existing meta-patterns in `playbooks/meta/`.
For each case, answer: "Is this a new meta-pattern, or a brand instance of an
existing one?"

- If existing meta-pattern → only write brand binding (Layer 2) + use case
- If new meta-pattern → write meta-pattern first (Layer 1), then brand binding

**Step 2: Magic Number Iron Rule**
Extract every threshold number from the partner's prose. Convert every number
that represents a trigger condition to a `threshold_key` variable.

```yaml
# ❌ NEVER write this in Layer 1 (meta-pattern)
condition: "cac_7d_vs_baseline > 1.15"

# ✅ ALWAYS write this in Layer 1
condition: "cac_7d_vs_baseline > ${thresholds.cac_spike_ratio}"
# And put 1.15 in the brand binding under thresholds.cac_spike_ratio
```

Exception: CPG hard safety floors (margin ≥ 0.15, inventory_days ≥ 5) are
hardcoded in `constraints.py` and must NOT be threshold variables.

**Step 3: Write meta-pattern YAML (if new pattern)**
File: `playbooks/meta/{module}_{theme}.yaml`
Use the schema in Section 2. Focus on logic structure, not numbers.

**Step 4: Write brand binding YAML**
File: `playbooks/brands/{merchant_slug}/{meta_pattern_ref}.yaml`
Use the schema in Section 3. Three mandatory sections: `entity_bindings`,
`thresholds`, `action_utility_priors`.

**Step 5: Calculate gmv_lift_prior from observed outcome**
Every `gmv_lift_prior` must be derived from observed data using the formula
in Section 5. Mark `calibration_status: partner_prior`. Never guess.

**Step 6: Write use case YAML**
File: `use_cases/{merchant_slug}/{brand_prefix}_{NNN}_{slug}.yaml`
This is the Single Source of Truth for all observed numbers. Use schema
in Section 4.

**Step 7: Collect ambiguous questions for partner**
While translating, flag any field where the partner wrote vague language
("several points", "dominant share", "a few weeks"). Collect into a
single list and ask partner in one batch. Do not block translation for these.

**Step 8: Threshold namespace consistency check**
Before finalising, check every `threshold_key` against Section 5 (namespace).
If you need a new key, review whether an existing key can be reused first.
Document new keys with `introduced_at` annotation in the SOP table AND add the
key string to `PlaybookRegistry._KNOWN_THRESHOLD_KEYS` in `playbook_registry.py`.

**Automated enforcement**: `PlaybookRegistry.load_brand_binding()` warns at
load time for any threshold key not in `_KNOWN_THRESHOLD_KEYS`. This warning
appears in `kg_dryrun.py` output and in production logs. Treat it like a
linting error — resolve before the brand binding ships.

**Step 9: Validate with kg_dryrun.py**
```bash
python scripts/kg_dryrun.py
```
Must exit 0. Any WARNING about missing `expected_utility` or wrong `msm_state`
must be resolved before proceeding.

**Step 10: Register triggers in shadow log**
For every new trigger in a brand binding, confirm `calibration_status` is set
and it will appear in the next shadow mode run. The shadow log is L5 evidence
that the trigger is firing.

---

## Section 2: Meta-Pattern YAML Schema

File location: `playbooks/meta/{module}_{theme}.yaml`

```yaml
# ─────────────────────────────────────────────────────────────────────────────
# Meta-Pattern Schema — Layer 1 (platform-level, partner maintains)
# RULE: Zero hardcoded threshold numbers. Use ${thresholds.key_name} only.
# ─────────────────────────────────────────────────────────────────────────────

meta_pattern:
  id: {module}_{theme}                         # e.g. acquisition_cac_channel_mix
  module: {retention|acquisition|conversion|promotion}
  version: "1.0"
  tags: [tag1, tag2]                           # secondary classification
  reusable: true                               # false = brand-specific pattern

triggers:
  - name: {trigger_slug}
    msm_state: {WATCH|DEGRADING|CRITICAL}      # required for PlaybookRegistry routing
    condition: "metric > ${thresholds.key}"    # threshold_key, not number
    metric: {metric_name}                      # structured metric reference

analysis_path:
  - step: {step_slug}
    description: "Human-readable description"
    data_source: {order_table|signals|l0}      # where data comes from
    output_metric: {derived_metric_name}       # what this step produces
    # Optional: decision_gate (condition that confirms the diagnosis)
    decision_gate: "delta > ${thresholds.diagnosis_gate_key}"

root_cause_type: {mix_problem|measurement_artifact|channel_routing|budget_allocation}

actions:
  - id: {ACTION_ID}                            # should match INDUSTRY_BENCHMARKS key
    type: {DIAGNOSTIC|BUDGET_ADJUST|CHANNEL_CONTROL|COPY_TEST|FLOW_CHANGE|MEASUREMENT_FIX}
    description: >
      Plain-language description of what this action does and why.
    expected_utility_basis:
      business_logic: "Why this action creates value"
      gmv_lift_formula: "Formula derivation (no hardcoded numbers)"
    requires_approval: {true|false}
    rollback_available: {true|false}

evidence_refs_template:
  - "Signal: ${metrics.metric_name} observed value"
  - "Outcome: ${metrics.outcome_metric} change"

partner_clarifications_needed:
  - "Question for partner about ambiguous threshold"
```

---

## Section 3: Brand Binding YAML Schema

File location: `playbooks/brands/{merchant_slug}/{meta_pattern_ref}.yaml`

```yaml
# ─────────────────────────────────────────────────────────────────────────────
# Brand Binding Schema — Layer 2 (brand-level, you maintain)
# RULE: No raw evidence data. Use evidence_case pointer to use_cases/ only.
# ─────────────────────────────────────────────────────────────────────────────

brand: {merchant_slug}
meta_pattern_ref: {meta_pattern_id}           # must match Layer 1 id
binding_version: "1.0"

entity_bindings:
  # Brand-specific vocabulary — what does THIS brand call generic concepts?
  # e.g., primary_ad_platform: meta
  #       on_platform_destinations: [ig_shop, fb_shop]

thresholds:
  # Initial values for all ${thresholds.*} variables in the meta-pattern
  # ALL values must have calibration_status
  {threshold_key}: {initial_value}
  calibration_status: partner_prior
  # calibration_status options:
  #   partner_prior         — initial value from partner business judgment
  #   outcome_calibrated    — updated after N ≥ 10 real L5 outcome records
  #   (shadow_data_collected — data completeness only, not calibration quality)

action_utility_priors:
  # Keys must match INDUSTRY_BENCHMARKS action_id vocabulary
  {ACTION_ID}:
    gmv_lift_prior: {float}                   # valid range: [0.0, 0.25]
    confidence: {float}                       # 0.75=high, 0.60=medium, 0.45=low
    calibration_status: partner_prior
    evidence_case: "{brand_prefix}_{NNN}"     # pointer to use_cases/ YAML
```

**gmv_lift_prior confidence guide:**

| Evidence Type | confidence |
|---|---|
| Real observed data, specific numbers, confirmed outcome | 0.75 |
| Real observed data, directionally confirmed | 0.60 |
| Partner judgment, no specific numbers | 0.45 |
| Industry benchmark, no brand data | 0.30 |

---

## Section 4: Use Case YAML Schema

File location: `use_cases/{merchant_slug}/{brand_prefix}_{NNN}_{slug}.yaml`

This file is the **Single Source of Truth** for all observed evidence numbers.
No other file should contain raw CAC values, sub rate deltas, or outcome figures.

```yaml
# ─────────────────────────────────────────────────────────────────────────────
# Use Case Schema — Evidence Layer (brand-level, compiler-ready)
# RULE: This is the only place raw observed numbers should be written.
# ─────────────────────────────────────────────────────────────────────────────

use_case_id: {brand_prefix}_{NNN}             # e.g. wb_005
brand: {merchant_slug}
meta_pattern_ref: {meta_pattern_id}
module: {retention|acquisition|conversion|promotion}
observed_at: "{YYYY-MM or YYYY-QN}"
evidence_quality: {high|medium|low}

calibration_value_for:
  - action_id: {ACTION_ID}                    # INDUSTRY_BENCHMARKS key
    gmv_lift_derivation:
      method: {derivation_method}
      # Include the input numbers and formula used
      gmv_lift_estimate: {float}              # result — this goes into brand binding

data_observed:
  # Structured key-value pairs of observed metrics
  # Before/after structure when applicable
  before:
    {metric_name}: {value}
  after:
    {metric_name}: {value}

action_taken: {ACTION_ID}
root_cause_confirmed: {root_cause_type}

counterfactual: >
  What would have happened if this pattern was not detected.

outcome_value: >
  Quantified outcome and qualitative business value.
```

---

## Section 5: Threshold Key Namespace (v0.1 — will evolve)

**Governance rule**: Before adding a new threshold key, check if an existing
key can be reused. New keys require `introduced_at` annotation. Key renames
must be propagated to all brand bindings that reference them.

| Key | Description | Introduced at |
|---|---|---|
| `cac_spike_ratio` | CAC above baseline × multiplier → WATCH | wandering_bear v0.1 |
| `cac_critical_ratio` | CAC above baseline × multiplier → DEGRADING | wandering_bear v0.1 |
| `sub_rate_alert_pct` | Subscription rate WoW delta (negative) → WATCH trigger | wandering_bear v0.1 |
| `sub_rate_critical_pct` | Subscription rate WoW delta (negative) → DEGRADING trigger | wandering_bear v0.1 |
| `sku_concentration_threshold` | Top SKU order share fraction → mix check | wandering_bear v0.1 |
| `channel_nonsubscribable_share` | Non-subscribable channel order share → denominator fix | wandering_bear v0.1 |
| `brand_dr_split_threshold` | Brand spend fraction → require separate CPA view | wandering_bear v0.1 |
| `destination_cvr_gap_threshold` | On-platform CVR / website CVR ratio → confirm routing | wandering_bear v0.1 |
| `inventory_safety_days` | Inventory days below which spend is reduced | wandering_bear v0.1 |
| `mix_diagnosis_min_delta_pp` | Adjusted vs reported rate delta (pp) to confirm mix | wandering_bear v0.1 |

---

## Section 6: gmv_lift_prior Calculation Guide

`gmv_lift_prior` is the **GMV lift as a fraction of monthly GMV**. Valid range: [0.0, 0.25].
Values above 0.25 are clipped in `PlaybookRegistry.get_base_utility()`.

**Method: cac_improvement_to_gmv_lift**
Use when the observed outcome is a CAC reduction.
```
gmv_lift = cac_improvement_pct × (monthly_new_customers × aov / monthly_gmv)
```
Example (WB Case 5): CAC -17.4%, 2290 new customers, $47 AOV, $150k monthly GMV
= 0.174 × (2290 × 47 / 150000) ≈ 0.174 × 0.717 ≈ 0.12 → `gmv_lift_prior: 0.12`

**Method: rate_lift_to_gmv_lift**
Use when the observed outcome is a conversion rate or subscription rate change.
```
gmv_lift = rate_delta_pct × affected_revenue_fraction
```
Example: sub rate +4pp improvement, subscription revenue = 30% of GMV
= 0.04 × 0.30 ≈ 0.012 → small, but with LTV multiplier may be higher

**Method: diagnostic_prevention_value**
Use when the action is DIAGNOSTIC (prevents a wrong action from being taken).
Estimate the cost of the wrong action that was prevented.
```
gmv_lift = wrong_action_cost / monthly_gmv × probability_of_wrong_action
```
Example: prevented sitewide subscription redesign worth 2-4 weeks engineering
→ conservative estimate: 0.05-0.10

**Hard clip**: all `gmv_lift_prior` values are clipped to [0.0, 0.25] in
`PlaybookRegistry.get_base_utility()` regardless of formula output.

---

## Section 7: Calibration Status State Machine

```
partner_prior
    │
    │  N ≥ 10 real outcome records in L5 WSM
    │  (reward_backfill.py writes outcome_delta)
    │  (future: automatic trigger via reward backfill hook)
    ▼
outcome_calibrated
    │
    │  Phase 3 hook — not implemented
    ▼
(cross_brand_inferred)    ← field reserved, not active
```

`shadow_data_collected` is a data completeness marker only:
- Meaning: shadow mode has run N times and the trigger has fired
- NOT meaning: the threshold is correctly calibrated
- Use for: confirming a trigger is wired correctly before real data arrives

---

## Section 8: Questions to Ask Partner (Standard Checklist)

For every new brand, ask these questions in one batch after initial translation:

1. "For [pattern X], at what [metric] level do you start suspecting this problem?
   Is this different for larger vs smaller brands?"
   → Calibrates initial threshold values

2. "What was the specific outcome / what was prevented by taking this action?
   Can you give me before/after numbers?"
   → Used in `gmv_lift_derivation`

3. "In what situations does this pattern NOT apply (false positive conditions)?"
   → Used in `partner_clarifications_needed` and future conflict checks

4. "Is this pattern specific to [brand category/size/channel mix], or have you
   seen it across brand types?"
   → Determines whether pattern should be `reusable: true` or brand-specific

---

## Section 9: File Naming Conventions

| File Type | Pattern | Example |
|---|---|---|
| Meta-pattern | `playbooks/meta/{module}_{theme}.yaml` | `acquisition_cac_channel_mix.yaml` |
| Brand binding | `playbooks/brands/{slug}/{meta_pattern_ref}.yaml` | `wandering_bear/acquisition_cac_channel_mix.yaml` |
| Use case | `use_cases/{slug}/{prefix}_{NNN}_{slug}.yaml` | `wandering_bear/wb_005_meta_destination_mix.yaml` |
| Brand prefix | 2-4 char brand abbreviation | `wb` = wandering_bear |

Use case numbering: `{prefix}_{NNN}` where NNN is sequential within the brand.
Do not reuse numbers. Deleted use cases leave a gap (no renumbering).

---

## Maintenance

This document is operational guidance, not architecture. Updates do not require
an ADR. Update when:
- A new threshold key is added to Section 5 (update table + `introduced_at`)
- A new `gmv_lift_derivation` method is documented in Section 6
- The partner delivery format changes

Last updated: 2026-04-12
