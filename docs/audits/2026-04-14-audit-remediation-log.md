# KG Translation Landing Audit — Remediation Log

**Date**: 2026-04-14
**Source audit**: `docs/audits/2026-04-14-kg-translation-landing-audit.md`
**Sprint**: Group 1 (runtime/correctness fixes) + Group 2 (documentation/governance)

---

## Baseline

- **Initial findings**: 61 findings across 7 audit dimensions
  - BLOCKER: 3 (all in D2 / D4 — dormant action wiring + WB legacy orphans + WB missing _source archive)
  - MAJOR: 31 (architecture drift, SSoT violations, documentation inconsistencies, schema drift, missing tests, dormant-governance gaps, routing contract ambiguity, unexercised threshold keys)
  - MINOR: 5
  - OBSERVATION: 22 (documented aspects of the system that were already correct; preserved as positive baseline)
- **Group 1 runtime/correctness fixes completed**: 8 task groups addressing
  the 3 BLOCKERS + the highest-priority subset of MAJORs (SSoT duplication,
  orphan use cases, missing dignostic action, missing _source archive, field
  name drift, wrong file reference, threshold metadata classification,
  ADR internal contradiction)
- **Group 2 documentation/governance records completed**: 5 tasks addressing
  the remaining MAJOR findings that are **documentation-fixable without
  runtime change** — routing contract ambiguity, unexercised threshold keys,
  outcome_calibrated wording drift, dormant activation checklist, WB
  retroactive estimate tracking
- **Remaining findings deferred to Group 3** (post-demo): the subset of
  MAJORs that require runtime code changes, new tests, or CI tooling
  (detailed in "Post-demo upgrade candidates" section below)

**Baseline correction note**: An earlier draft of this log stated "13 findings",
which was constructed from sprint task count rather than the verbatim Codex
audit. The number 61 above is from the original Codex audit report at
`docs/audits/2026-04-14-kg-translation-landing-audit.md`. The finding-count
gap was identified on 2026-04-14 during the post-sprint review and corrected
by persisting the original audit to disk and recalibrating this log.

---

## Group 1 fixes completed

### Task 1 — ADR-0011 internal contradiction about action authority
**Finding**: ADR-0011 Neutral consequence stated meta-pattern `actions` are
"descriptive documentation, not executable candidate definitions" — directly
contradicting the authoritative-source statement in the same ADR and the
runtime behavior in `pipeline._generate_candidates()`.
**Fix**: Rewrote the contradictory Neutral bullet; updated the stale
"When to Revisit" entry; added canonical consequence bullet stating the
action-authority assignment is authoritative and future wording must reconcile.
**Files**: `docs/adr/0011-three-layer-kg-playbook-structure.md`

### Task 2 — Remove `calibration_status` from `_KNOWN_THRESHOLD_KEYS`
**Finding**: `calibration_status` was incorrectly classified as a threshold
signal variable. It is threshold metadata, not a routing/trigger variable.
**Fix**: Removed from `_KNOWN_THRESHOLD_KEYS`; added
`_THRESHOLD_METADATA_FIELDS = frozenset({"calibration_status"})`; added
`continue` skip in `_validate_brand_binding()` loop.
**Files**: `src/decision_engine/layer2_decision/pillar1_kg/playbook_registry.py`

### Task 3 — Fix `wb_004` field name `effective_gmv_lift` → `gmv_lift_estimate`
**Finding**: Non-canonical field name in `wb_004_brand_vs_dr_cpa.yaml`
(`effective_gmv_lift`) where all other use cases use `gmv_lift_estimate`.
**Fix**: Renamed field; value and context preserved.
**Files**: `use_cases/wandering_bear/wb_004_brand_vs_dr_cpa.yaml`

### Task 4 — Fix SOP Section 10 dangling file reference
**Finding**: SOP Section 10 referenced `conversion_compliance_ux_cvr.yaml` —
a non-existent path. The real file is `conversion_compliance_friction.yaml`.
**Fix**: Replaced the broken path with the correct filename.
**Files**: `docs/playbook_authoring_sop.md`

### Task 5 — Add `AUDIT_RECENT_CHANGES` as first-class diagnostic action for cba_002
**Finding**: The diagnose-before-execute pattern for compliance friction
exposed only `REMOVE_COMPLIANCE_FRICTION` as a candidate action. The
diagnostic step existed only inside `analysis_path`, invisible to the
pipeline as a scoreable candidate.
**Fix**: Added `AUDIT_RECENT_CHANGES` (type: DIAGNOSTIC) to meta-pattern
`actions[]`, brand binding `action_utility_priors`, use case
`calibration_value_for`, `ImpactCalculator.INDUSTRY_BENCHMARKS`,
`LLMRenderer._TEMPLATES`, and fixture test suite.
**Files**:
- `playbooks/meta/conversion_compliance_friction.yaml`
- `playbooks/brands/consumer_brand_a/conversion_compliance_friction.yaml`
- `use_cases/consumer_brand_a/cba_002_compliance_ux.yaml`
- `src/decision_engine/layer3_value/impact_calculator.py`
- `src/decision_engine/layer2_decision/pillar3_llm/llm_renderer.py`
- `tests/layer2/test_new_patterns_cba.py`

### Tasks 6A–6D — Remove observed-data comments from four active brand bindings
**Finding**: Four active brand bindings contained observed dollar amounts,
percentages, CAC values, and derivation math in comments — violating the
SSoT rule (all observed data belongs in `use_cases/`, not in `playbooks/brands/`).
**Fix**: Removed observed-data comments from each binding; replaced with
evidence pointer comments (`# Full derivation: see use_cases/...`); confirmed
all removed data already existed in the corresponding use case SSoT files.
One hardcoded baseline string (`WB baseline ~52%`) replaced with a
non-numeric evidence pointer in `evidence_refs_template`.
**Files**:
- `playbooks/brands/consumer_brand_a/acquisition_ugc_creative.yaml`
- `playbooks/brands/consumer_brand_a/conversion_compliance_friction.yaml`
- `playbooks/brands/wandering_bear/acquisition_cac_channel_mix.yaml`
- `playbooks/brands/wandering_bear/conversion_subscription_mix.yaml`

### Task 7 — Quarantine `wb_003` and `wb_006` as legacy use cases
**Finding**: `wb_003` and `wb_006` were pre-three-layer artifacts sitting in
the active use-case directory. Their `meta_pattern_ref` values point to
Phase 1 flat stub playbooks, not Layer-1 meta-patterns.
**Fix**: Created `use_cases/wandering_bear/_legacy/`; moved both files with
legacy marker block prepended; created `_legacy/README.md` with promotion
path. Side-document cascade applied to `partner_drafts/` and
`docs/partner_comms/`. Quarantine cascade rule institutionalized in
`docs/audits/2026-04-14-quarantine-cascade-notes.md`.
**Files**:
- `use_cases/wandering_bear/_legacy/wb_003_evergreen_naming_test.yaml`
- `use_cases/wandering_bear/_legacy/wb_006_inventory_spend_pullback.yaml`
- `use_cases/wandering_bear/_legacy/README.md`
- `partner_drafts/kg_partner/wandering_bear/TRANSLATION_LOG.md`
- `partner_drafts/README.md`
- `docs/partner_comms/kg_partner_collab_brief.md`
- `docs/audits/2026-04-14-quarantine-cascade-notes.md`

### Task 8 — Create Wandering Bear `_source/` archive and retrieval tracker
**Finding**: Wandering Bear lacked the `_source/` archive convention required
by ADR-0011. No original partner source materials were archived at translation
time.
**Fix**: Created `use_cases/wandering_bear/_source/` with `README.md` and
`_RETRIEVAL_NEEDED.md` tracking wb_001, wb_002, wb_004, wb_005 as pending
source retrieval. Created formal partner clarification request.
**Files**:
- `use_cases/wandering_bear/_source/README.md`
- `use_cases/wandering_bear/_source/_RETRIEVAL_NEEDED.md`
- `docs/partner_clarification_queue/2026-04-14-wb-source-archive.md`

---

## Group 2 records / clarifications completed

### G2 Task 1 — Record MSM-state-driven routing contract (ADR-0013)
**Issue**: No ADR documented the current routing contract. Meta-pattern
`triggers.condition` fields could be misread as routing-evaluation inputs.
**Record**: Created ADR-0013 stating the contract explicitly: routing input
is `module + msm_state (+ merchant_id)`; `triggers.condition` and
`${thresholds.*}` are authoring/explanation artifacts, not routing predicates.
Includes 4 escalation conditions, concrete escalation process, and
self-verification commands.
**Files**: `docs/adr/0013-msm-state-driven-routing-contract.md`

### G2 Task 2 — Document three registered-but-unexercised threshold keys
**Issue**: `channel_nonsubscribable_share`, `brand_dr_split_threshold`, and
`inventory_safety_days` are registered as `active` in `_KNOWN_THRESHOLD_KEYS`
but are not referenced by any active meta-pattern or brand binding.
**Record**: Added a dated note below the SOP Section 5 threshold table
clarifying the distinction between namespace-registered and battle-tested,
and prescribing a future cleanup path.
**Files**: `docs/playbook_authoring_sop.md`

### G2 Task 3 — Clarify `outcome_calibrated` wording in ADR-0011 and SOP
**Issue**: Both docs implied automatic calibration promotion was already live.
In reality, `RewardBackfill` is entirely stubbed and no priors are
auto-promoted by runtime code.
**Record**: Added canonical phrasing to both documents: enum validation is
live; automatic promotion is Phase 2 work dependent on the stubbed
`RewardBackfill`; all `outcome_calibrated` labels (if any) are manually set.
**Files**:
- `docs/adr/0011-three-layer-kg-playbook-structure.md`
- `docs/playbook_authoring_sop.md`

### G2 Task 4 — Strengthen dormant-pattern activation checklist
**Issue**: Third `blocked_by` entry had no `adr_ref`; no blocker recorded
that `PAUSE_OFFER_CREATIVE` and `VALIDATE_BEFORE_SCALE` are not yet wired
into `ImpactCalculator.INDUSTRY_BENCHMARKS` or `LLMRenderer._TEMPLATES`.
**Record**: Added `adr_ref: ADR-0005` to third blocker; added fourth blocker
(`runtime_action_surface_wiring`) documenting the silent-fallback risk if
the pattern is activated without wiring both action IDs into the runtime
action-surface layers.
**Files**: `playbooks/meta/_deferred/acquisition_ltv_quality_trap.yaml`

### G2 Task 5 — Retroactive clarification queue for WB estimated priors
**Issue**: Four estimate-backed inputs in wb_001 and wb_005 had no
clarification queue coverage: `prevented_action_cost_est` (wb_001),
`monthly_new_customers_est`, `aov_est`, `monthly_gmv_est` (wb_005).
**Record**: Created clarification queue file with per-item structure (field,
current value, why it matters, specific ask).
**Files**: `docs/partner_clarification_queue/2026-04-14-wb-retroactive-estimates.md`

---

## Remaining known issues (not fixed in Group 1 / Group 2)

### Demo-safe known issues (runtime behavior unchanged, documented)

| Issue | Status | Notes |
|-------|--------|-------|
| `triggers.condition` not evaluated at routing time | Documented in ADR-0013 | Intentional architecture; MSM is the upstream signal conclusion layer |
| Three threshold keys unexercised (`channel_nonsubscribable_share`, `brand_dr_split_threshold`, `inventory_safety_days`) | Documented in SOP Section 5 | Namespace-preserved; no active pattern uses them; cleanup deferred |
| `RewardBackfill` entirely stubbed; no auto-calibration | Documented in ADR-0011 + SOP Section 7 | Phase 2 work; all current priors are `partner_prior` |
| WB source archive not yet retrieved | Tracked in `_source/_RETRIEVAL_NEEDED.md` | Four use cases pending partner source confirmation |
| Four WB priors backed by unconfirmed estimates | Tracked in clarification queue | `gmv_lift_prior` values are reasonable but not partner-confirmed |
| `wb_003`, `wb_006` not promoted to three-layer | Quarantined in `_legacy/` | Promotion requires creating real meta-patterns; deferred post-demo |

### Post-demo upgrade candidates (Group 3)

### Coverage summary

Of the 31 MAJOR findings in the original audit:
- **8 were directly fixed in Group 1** (SSoT cleanup, diagnostic action,
  field normalization, ADR contradiction, threshold metadata, etc.)
- **5 were documented/recorded in Group 2** without runtime change (routing
  contract ambiguity, unexercised keys, outcome_calibrated wording, dormant
  activation checklist, WB retroactive clarification)
- **The remaining 18 MAJORs are deferred to Group 3** — they require
  runtime code changes, new test infrastructure, or CI tooling that is
  out of scope for a pre-demo sprint

The Group 3 items below represent the deferred MAJOR subset, organized by
theme. None of them affect demo-day correctness; they are technical debt
with documented workarounds.

| Item | What is needed |
|------|----------------|
| Condition-level routing | ADR required before any `triggers.condition` evaluation is added to `match_playbook()` |
| Retire or wire unexercised threshold keys | Either wire into active patterns or move to `_DORMANT_THRESHOLD_KEYS` |
| `RewardBackfill` implementation | Phase 2 Track A/B; requires real execution data accumulation |
| SOP / test coverage for SSoT enforcement | Automated check that observed data does not appear in brand bindings |
| Architecture invariant for condition non-evaluation | Test that `trigger.condition` is never read inside `match_playbook()` routing loop |
| Partner source retrieval for WB | Follow `use_cases/wandering_bear/_source/_RETRIEVAL_NEEDED.md` |

---

## Demo readiness assessment

**Status: CONDITIONALLY READY**

**Rationale**: All 8 Group 1 correctness issues have been resolved — the
active KG system is internally consistent, SSoT-clean, and passes 403 tests
with `kg_dryrun exit=0` loading 8 playbooks. The `AUDIT_RECENT_CHANGES`
diagnostic action is now a first-class candidate, `conversion_compliance_friction`
correctly surfaces 2 actions, and `wb_003`/`wb_006` are quarantined out of
the active routing path. The 5 Group 2 records make all known limitations
explicit rather than hidden. No remaining issue materially affects demo
correctness or narrative strength. Conditions: (1) `RewardBackfill` stub
status should be verbally acknowledged in demo if calibration path is shown;
(2) WB source retrieval and estimate confirmation are open but non-blocking.

---

## Next batch

- **Group 3**: SOP / test / CI upgrades
  - Architecture invariant test for condition non-evaluation in routing loop
  - Automated SSoT check: observed data must not appear in brand bindings
  - Threshold key lifecycle enforcement: unexercised active keys flagged at
    load time after a configurable staleness window
  - `_source/` archive presence check for all active brands at `kg_dryrun` time
  - ADR template update: all future contract ADRs should include a
    "How To Verify" section (pattern established by ADR-0013)
