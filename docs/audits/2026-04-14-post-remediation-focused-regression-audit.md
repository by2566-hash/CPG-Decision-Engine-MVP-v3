# Post-Remediation Focused Regression Audit

**Date**: 2026-04-14 (audited morning of 2026-04-15)
**Scope**: Group 1 + Group 2 closure verification
**Auditor**: Claude Code (independent regression audit)
**Source audit**: `docs/audits/2026-04-14-kg-translation-landing-audit.md`
**Remediation log**: `docs/audits/2026-04-14-audit-remediation-log.md`
**Cascade governance**: `docs/audits/2026-04-14-quarantine-cascade-notes.md`

---

## Executive summary

- Total findings: 3
- BLOCKER: 0
- MAJOR: 0
- MINOR: 2
- OBSERVATION: 1
- Regression status: **PASS**

---

## Closure table for Group 1 (8 fixes)

| Group 1 fix | Status | Evidence |
|---|---|---|
| Task 1 — ADR-0011 contradiction fixed | CLOSED | `docs/adr/0011-three-layer-kg-playbook-structure.md:74,140,152` — "authoritative" stated three times; "descriptive documentation" wording absent (`grep` returns no matches) |
| Task 2 — calibration_status removed from threshold keys | CLOSED | `playbook_registry.py:243–244` — `_THRESHOLD_METADATA_FIELDS = frozenset({"calibration_status"})`; `calibration_status in active: False`; `calibration_status in metadata: True`; 21 brand binding tests pass including `test_active_brand_binding_cannot_reference_dormant_threshold_key` |
| Task 3 — wb_004 field normalized | CLOSED | `use_cases/wandering_bear/wb_004_brand_vs_dr_cpa.yaml:20` — `gmv_lift_estimate: 0.07`; `effective_gmv_lift` absent from all active YAML files |
| Task 4 — SOP Section 10 path fixed | CLOSED | `docs/playbook_authoring_sop.md` — `conversion_compliance_friction.yaml` filename reference corrected; Section 5 disclosure note and Section 7 canonical phrasing added as part of Group 2 follow-on |
| Task 5 — AUDIT_RECENT_CHANGES landed end-to-end | CLOSED | 6-file wiring verified: meta-pattern action `type: DIAGNOSTIC` at `meta/conversion_compliance_friction.yaml:106`; brand binding `gmv_lift_prior: 0.03` at `cba/conversion_compliance_friction.yaml:24`; use case `method: diagnostic_prevention_value` + `estimated: true` at `cba_002_compliance_ux.yaml:19,27`; `INDUSTRY_BENCHMARKS` entry at `impact_calculator.py:52`; `_TEMPLATES` dict entry at `llm_renderer.py:76–79`; `test_cba_002_audit_recent_changes_action_is_present` PASSED |
| Tasks 6A–6D — brand-binding SSoT cleanup landed | CLOSED | Both precise (`$210.00`, `54.79`, `45.25`, `WB baseline`) and broad pattern greps return zero matches in `playbooks/brands/`; all observed values confirmed present only in corresponding use case SSoT files; all 8 `evidence_case` pointers resolve to real files on disk |
| Task 7 — wb_003 / wb_006 quarantined (incl. cascade) | CLOSED | wb_003 and wb_006 absent from `use_cases/wandering_bear/*.yaml`; both present in `_legacy/` with `legacy_status: pre_three_layer`; TRANSLATION_LOG.md shows `⏸ 已翻译 → 已 quarantine` for both; `partner_drafts/README.md` shows `4/6 active + 2/6 legacy`; `kg_partner_collab_brief.md` has 2026-04-14 quarantine notice; cascade governance notes file present with general rule |
| Task 8 — WB _source archive created | CLOSED | `use_cases/wandering_bear/_source/README.md`, `_source/_RETRIEVAL_NEEDED.md`, and `docs/partner_clarification_queue/2026-04-14-wb-source-archive.md` all exist |

---

## Closure table for Group 2 (5 records)

| Group 2 record | Status | Evidence |
|---|---|---|
| G2 Task 1 — ADR-0013 created | CLOSED | `docs/adr/0013-msm-state-driven-routing-contract.md` exists; all required sections present; runtime code confirmed: `match_playbook()` reads only `pattern.get("msm_state")` and `trigger.get("msm_state")` — no condition expression evaluated; 4 escalation conditions and 4-step escalation process present (see MINOR finding D-1) |
| G2 Task 2 — SOP Section 5 disclosure | CLOSED | `docs/playbook_authoring_sop.md:306–322` — dated note (2026-04-14) explicitly names all three keys, states they are registered in `_KNOWN_THRESHOLD_KEYS` but not exercised by any active pattern, and prescribes cleanup path |
| G2 Task 3 — outcome_calibrated phrasing aligned | CLOSED | Both `docs/adr/0011-three-layer-kg-playbook-structure.md:86–91` and `docs/playbook_authoring_sop.md:379–384` contain identical canonical paragraph stating (a) enum validation is live, (b) auto-promotion is Phase 2 / RewardBackfill-dependent / stubbed, (c) all labels are manually set |
| G2 Task 4 — dormant blocker + adr_ref | CLOSED | `playbooks/meta/_deferred/acquisition_ltv_quality_trap.yaml` — `blocker_count: 4`; all 4 blockers have `adr_ref`; new blocker [3] `runtime_action_surface_wiring` references PAUSE_OFFER_CREATIVE, VALIDATE_BEFORE_SCALE, INDUSTRY_BENCHMARKS, `_TEMPLATES`; Python assert script prints PASS |
| G2 Task 5 — WB retroactive queue | CLOSED | `docs/partner_clarification_queue/2026-04-14-wb-retroactive-estimates.md` exists; all four estimate fields covered across 4 items (prevented_action_cost_est, monthly_new_customers_est, aov_est, monthly_gmv_est); priority label present (see MINOR finding D-2) |

---

## Findings by severity

### BLOCKER

None.

### MAJOR

None.

### MINOR

**[MINOR-D-1]** ADR-0013 Escalation Process has 4 numbered steps; audit spec requires ≥ 5
File(s): `docs/adr/0013-msm-state-driven-routing-contract.md:131–158`
Evidence: Steps 1–4 present under `### Escalation Process`; no step 5 or 6. Reference spec states "at least 5 numbered steps (should have ~6 based on Group 2 spec)."
Impact: None at runtime; reduces procedural completeness of the escalation protocol. The 4-step reduction was an intentional architectural choice made during the ADR-0013 review session (author chose design-first escalation over code-cascade escalation), but the chosen step count falls below the spec floor.
Recommendation: Add at least one step covering post-merge validation or a cross-reference to ADR-0012 interaction check confirmation. Not demo-blocking.

**[MINOR-D-2]** `2026-04-14-wb-retroactive-estimates.md` uses a single file-level priority label rather than per-item H/M/L section structure
File(s): `docs/partner_clarification_queue/2026-04-14-wb-retroactive-estimates.md:6`
Evidence: File carries `**Priority:** Medium — not blocking demo; needed before outcome calibration upgrades` as a single top-level label for all 4 items. Reference format (`2026-04-13-cba-active-translation.md`) uses `## Priority: High / Medium / Low` section headers with per-item summary table.
Impact: None at runtime; cosmetic consistency gap between the two partner clarification queue files.
Recommendation: Restructure into H/M/L priority sections with per-item summary table in a future cleanup sprint. Not demo-blocking.

### OBSERVATIONS

**[OBS-B-1]** Confidence comments in two brand bindings characterize evidence quality using the phrase "specific CAC numbers" / "specific before/after numbers confirmed" without reproducing the numbers themselves
File(s): `playbooks/brands/consumer_brand_a/acquisition_ugc_creative.yaml:33`, `playbooks/brands/wandering_bear/acquisition_cac_channel_mix.yaml:26`
Evidence: `# real observed data, directionally confirmed (specific CAC numbers)` and `# high: specific before/after numbers confirmed`
Impact: None — comments are governance notes about evidence quality, not reproductions of observed data. Fully compliant with SSoT rule.
Recommendation: Acceptable as-is. If a future sprint enforces a strict no-observation-reference policy at the comment level, these would be candidates for rewording to remove any allusion to raw numbers.

---

## Findings by focus area

### A — Meta-pattern / action-surface closure

No findings. All 6-file AUDIT_RECENT_CHANGES wiring verified. Proxy-trigger discipline (timeline_correlation as `must_run_first`, ≥2 required keywords in rationale) confirmed. All 10 CBA fixture tests pass including both new and pre-existing timeline-first tests.

### B — Brand-binding SSoT enforcement

No BLOCKER or MAJOR findings. One OBSERVATION (OBS-B-1) recorded for borderline confidence comments; classified as acceptable governance notes, not SSoT violations. All 8 `evidence_case` pointers resolve. Dormant key isolation confirmed: `calibration_status in active: False`, `calibration_status in metadata: True`.

### C — Use-case / legacy / source-archive integrity + Task 7 cascade

No findings. wb_003 and wb_006 quarantine complete with `legacy_status: pre_three_layer` on both files. `_source/` archive structure fully in place. Full Task 7 cascade verified: TRANSLATION_LOG.md, partner_drafts/README.md, and kg_partner_collab_brief.md all updated; quarantine cascade notes file present with general institutionalized rule and "Quarantine vs deletion" section.

### D — Documentation / contract alignment

2 MINOR findings (MINOR-D-1, MINOR-D-2). No BLOCKER or MAJOR. All substantive content checks pass: ADR-0013 contract accurate against runtime code; SOP Section 5 disclosure complete with all 3 required conditions; outcome_calibrated phrasing identical across ADR-0011 and SOP; dormant blocker count and adr_ref completeness verified via Python assert.

### E — Runtime and SSoT round-trip

No findings. 403 tests pass. kg_dryrun exit=0, 8 playbooks loaded. 14 architecture invariants pass. All 8 active action utilities resolve in `[0.0, 0.25]`. Known-bad observed values (`$210`, `$54.79/$45.25`, `WB baseline ~52`) confirmed absent from brand bindings and present only in use case SSoT files. Dormant pattern `acquisition_ltv_quality_trap` confirmed absent from active registry (`False`).

---

## Attachments

### Utility resolution matrix (from E2)

```
OK   consumer_brand_a     acquisition_ugc_creative            AUDIT_CREATIVE_MIX             util=0.04
OK   consumer_brand_a     acquisition_ugc_creative            SCALE_TOP_CREATIVE             util=0.08
OK   consumer_brand_a     conversion_compliance_friction      AUDIT_RECENT_CHANGES           util=0.03
OK   consumer_brand_a     conversion_compliance_friction      REMOVE_COMPLIANCE_FRICTION     util=0.12
OK   wandering_bear       acquisition_cac_channel_mix         PAUSE_CHANNEL                  util=0.12
OK   wandering_bear       acquisition_cac_channel_mix         REALLOCATE_BUDGET              util=0.07
OK   wandering_bear       conversion_subscription_mix         DIAGNOSE_MIX                   util=0.08
OK   wandering_bear       conversion_subscription_mix         FIX_DENOMINATOR                util=0.05
```

### SSoT round-trip grep outputs (from E3)

```
# Step 1: known-bad strings in brand bindings
grep -rn "210\.00|149\.00|54\.79|45\.25|WB baseline" playbooks/brands --include="*.yaml"
→ (no output)

# Step 2: 210.00 / cac_before: 210 — use cases only
use_cases/consumer_brand_a/cba_001_ugc_creative.yaml:32:      cac_before: 210.00
use_cases/consumer_brand_a/cba_001_ugc_creative.yaml:65:    meta_cac: 210.00

# Step 3: 54.79 / 45.25 — use cases only
use_cases/wandering_bear/wb_005_meta_destination_mix.yaml:17:      cac_before: 54.79
use_cases/wandering_bear/wb_005_meta_destination_mix.yaml:18:      cac_after: 45.25
use_cases/wandering_bear/wb_005_meta_destination_mix.yaml:19:      cac_improvement_pct: 0.174
use_cases/wandering_bear/wb_005_meta_destination_mix.yaml:47:    cac_sitewide: 54.79
use_cases/wandering_bear/wb_005_meta_destination_mix.yaml:53:    cac_sitewide: 45.25
use_cases/wandering_bear/wb_005_meta_destination_mix.yaml:57:  cac_recovery: 9.54
use_cases/wandering_bear/wb_005_meta_destination_mix.yaml:73:  to $45.25 in April vs $54.79 in March

# Step 4: WB baseline ~52 in brand bindings
→ (no output)
```

All observed values confirmed in use case SSoT files only. Zero brand-binding violations.

### Pre-flight baseline outputs

```
python -m pytest -q | tail -3:
    403 passed, 66 warnings in 0.70s

python scripts/kg_dryrun.py; echo "exit=$?":
    KG Dry-Run — 8 playbooks loaded
    acquisition_cac_channel_mix.yaml       [meta-pattern]  (2 actions)  ✓
    acquisition_efficiency_v1.yaml                         (1 actions)  ✓
    acquisition_ugc_creative.yaml          [meta-pattern]  (2 actions)  ✓
    conversion_compliance_friction.yaml    [meta-pattern]  (2 actions)  ✓
    conversion_merchandising_v1.yaml                       (1 actions)  ✓
    conversion_subscription_mix.yaml       [meta-pattern]  (2 actions)  ✓
    promotion_offer_strategy_v1.yaml                       (1 actions)  ✓
    retention_replenishment_v1.yaml                        (2 actions)  ✓
    Route simulation: retention/acquisition/conversion/promotion × HEA/WAT/DEG/CRI — all ✓
    All checks passed — KG is ready for pipeline use
    exit=0

git diff -- scoring.py:
    (empty)

docs/audits/ contents:
    2026-04-14-audit-remediation-log.md
    2026-04-14-kg-translation-landing-audit.md
    2026-04-14-quarantine-cascade-notes.md
```

---

## Final assessment

The V3 KG translation system is in materially better shape than its pre-remediation state. All three original BLOCKERs are closed, all 8 Group 1 runtime fixes verified end-to-end, all 5 Group 2 governance records confirmed present and substantively correct. The two MINOR findings (ADR-0013 step count and WB queue format) are both documentation-cosmetic and neither blocks a demo nor introduces drift risk. There are no MAJOR findings and no BLOCKER findings — meaning no remediation-claimed closure turned out to be a false close, and no regression was introduced during the sprint. **Regression status: PASS.** The system remains CONDITIONALLY READY for demo, with the same deferred conditions as documented in the remediation log: (1) WB retroactive estimate confirmation from partner still open, (2) `_source/` archive population pending retrieval, (3) three unexercised threshold keys requiring future wiring or reclassification.
