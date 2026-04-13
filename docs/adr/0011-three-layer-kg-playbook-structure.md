# ADR-0011: Three-Layer KG Playbook Structure for Multi-Brand Content

## Status
Accepted
Date: 2026-04-12

## Context

Phase 2 Track B requires a partner-driven KG content workflow that scales
across 10+ brands, ~50 use cases, and multiple CPG verticals. The current
playbook structure is a flat directory of four module-level YAML stubs with
hardcoded `expected_utility` floats. This creates three compounding problems:

1. **No per-brand thresholds**: A flat playbook cannot express that WB's
   CAC spike threshold (1.15×) differs from a larger brand's (1.25×). Any
   threshold written into the YAML becomes a magic number that cannot be
   calibrated without touching the platform file.

2. **No cross-brand pattern reuse**: When two brands exhibit the same root
   cause (e.g., channel destination mix diluting CAC), the pattern logic is
   duplicated verbatim. The 50 use cases should yield N meta-patterns, not
   50 isolated rules.

3. **`expected_utility` is a static float with no derivation trace**: Values
   like `expected_utility: 0.35` cannot be audited, calibrated, or updated as
   real outcome data accumulates. There is no link back to the observed evidence
   that justifies the number.

Partner delivery cadence is incremental (2 brands now, ~10 brands over 12
weeks). Every translation decision made now will be repeated 8 more times.
Getting the structure right at brand 2 prevents full rewrites at brand 6.

## Decision

Adopt a three-layer KG playbook structure:

**Layer 1 — Meta-Pattern YAML** (`playbooks/meta/*.yaml`)
- Platform-level, partner-maintained, one file per distinct CPG pattern
- Contains: pattern identity, trigger structure (threshold *keys*, not values),
  analysis path (steps), root cause type, action type vocabulary
- Zero hardcoded threshold numbers — all threshold references use
  `${thresholds.key_name}` template variables
- Cross-brand reusable: one meta-pattern serves all brands that exhibit it

**Layer 2 — Brand Binding YAML** (`playbooks/brands/{merchant_id}/*.yaml`)
- Brand-level, per-brand instance of a meta-pattern
- Contains: `meta_pattern_ref`, `entity_bindings` (brand vocabulary),
  `thresholds` (initial values, `calibration_status: partner_prior`),
  `action_utility_priors` (gmv_lift_prior + evidence_case pointer)
- Extremely lightweight — no raw evidence numbers. All observed outcomes
  live exclusively in `use_cases/{brand}/`, referenced by pointer only
  (Single Source of Truth)

**Layer 3 — Brand Config** (`PolicyPack.alert_thresholds`)
- Merchant-level, dynamically computed from `MerchantBaseline` on onboarding
- Populated initially from Brand Binding `thresholds` values
- Updated by Calibration Tool as real outcome data accumulates in L5

`PlaybookRegistry` is extended with:
- `load_brand_binding(merchant_id)`: loads Layer 2 YAMLs into memory cache
- `_render_with_thresholds(raw_yaml, brand_binding)`: interpolates
  `${thresholds.*}` and `${entity_bindings.*}` using `string.Template`
- Updated `get_base_utility()`: reads `gmv_lift_prior` from brand binding
  (priority 1), falls back to meta-pattern `expected_utility` (priority 2),
  falls back to INDUSTRY_BENCHMARKS (priority 3). Hard clips output to
  `[0.0, 0.25]` to prevent bandit exploration weight explosion on small
  merchants with high AOV.

Calibration status is a **two-state machine**:
- `partner_prior`: initial value from partner's business judgment
- `outcome_calibrated`: updated after N ≥ 10 real outcome records in L5
  (triggered by `reward_backfill.py`)

The intermediate state `shadow_data_collected` is reserved as a data
completeness marker only (not a calibration quality state) and is not
implemented in Phase 2.

## Alternatives Considered

**Alternative 1: LLM Document Compiler**
Parse partner's natural-language prose directly into YAML via LLM. Rejected
because: 50 use cases is below the amortization threshold for compiler
engineering; hand-translation forces the architect to internalize the business
logic that drives scoring decisions; compiler errors would be silent and
difficult to audit.

**Alternative 2: Single flat YAML per brand**
One large YAML per brand containing all patterns, thresholds, and evidence.
Rejected because: cross-brand pattern reuse requires duplicating pattern logic
into every brand file; changes to a shared pattern require touching N files;
no clear separation between platform-level logic and brand-level parameters.

**Alternative 3: Keep current flat structure, extend with per-brand overrides**
Add a `brand_overrides/` directory that patches values in existing module YAMLs.
Rejected because: patch semantics are error-prone at scale; the two-file model
(original + patch) is harder to audit than a three-layer model where each
layer has a single, well-defined responsibility.

## Consequences

### Positive
- Pattern reuse: WB's Meta destination routing pattern can be applied to any
  brand without copying trigger logic
- Threshold safety: zero magic numbers in meta-patterns; all values per-brand
  configurable and marked with `calibration_status`
- Audit trail: every `gmv_lift_prior` has an `evidence_case` pointer to the
  use case that justifies the number
- Additive to existing code: old flat playbooks in `playbooks/` root continue
  to work; three-layer structure is opt-in per brand
- Calibration path: `partner_prior` → `outcome_calibrated` is explicit,
  with N ≥ 10 outcome gate enforced in code

### Negative
- Three files instead of one for each brand × pattern combination; more files
  to maintain
- `PlaybookRegistry` complexity increases (new methods, lazy brand loading)
- Template rendering introduces `string.Template` dependency (stdlib, low risk)

### Neutral
- Existing `INDUSTRY_BENCHMARKS` action IDs remain the candidate generation
  vocabulary in Phase 2; meta-pattern `actions` are descriptive documentation,
  not executable candidate definitions. Full candidate vocabulary extension is
  Phase 3 work.
- Threshold namespace (`cac_spike_ratio`, `sub_rate_alert_pct`, etc.) starts
  at v0.1 with explicit governance process for additions. Not frozen.

## When to Revisit
- When Phase 3 Document Compiler is designed: compiler output should populate
  Layer 1 meta-patterns programmatically; schema must remain compatible
- When `INDUSTRY_BENCHMARKS` action IDs are extended: meta-pattern `actions`
  may become the authoritative vocabulary at that point
- When a brand requires a pattern not expressible in the three-layer structure

## References
- ADR-0006: Phase 2 dual-track structure (Track B owns KG content workflow)
- ADR-0009: Evidence Graph Snapshot (evidence_refs flow into EvidenceTraceEntry)
- PHASE_ROADMAP.md: Phase 2 Track B — "Partner KG content translation workflow"
- `playbooks/` directory for existing stub playbooks (unaffected by this ADR)
- `docs/playbook_authoring_sop.md`: operational SOP for partner content translation
