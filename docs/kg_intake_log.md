# KG Intake Log

Records every partner KG content intake: cases received, triage results,
translation status, and open questions. Updated at intake start and intake end.

---

## Batch: Use Case Library FINAL — 2026-06-01

**Partner delivery**: `/Users/yubo/Downloads/Use Case Library FINAL.docx`
**Source archive**: `partner_drafts/kg_partner/use_case_library_final/`
**Intake mode**: Mode A (archive + full triage, no runtime promotion yet)
**Intake lead**: Codex source extraction + V3 architecture triage

### Cases received: 55

| Segment | Count | Notes |
|---------|-------|-------|
| Benchmark/research cases | 23 | `B-01a` through `B-19`; mostly measurement, incrementality, channel-role, and attribution cases |
| First-party/operator cases | 32 | `FP-001` through `FP-032`; includes existing WB/CBA/CBB logic plus new brands/patterns |

### Intake result

**Status**: Phase 1 source alignment complete.

**Artifacts**:
- `partner_drafts/kg_partner/use_case_library_final/Use Case Library FINAL.docx`
- `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md`
- `partner_drafts/kg_partner/use_case_library_final/case_index.json`
- `partner_drafts/kg_partner/use_case_library_final/TRANSLATION_TRIAGE.md`
- `docs/kg_translation_triage/2026-06-01-use-case-library-final.md` (tracked,
  non-source triage copy)
- `docs/kg_translation_audits/use_case_library_final/SOURCE_MANIFEST.md`
  (tracked provenance manifest; raw source remains gitignored)

### Classification summary

| Classification | Cases |
|----------------|-------|
| Already active in current V3 | FP-001, FP-002, FP-004, FP-005, FP-010, FP-011 |
| Already legacy evidence | FP-003, FP-006 |
| Already deferred | FP-013 |
| Existing-pattern reuse candidate, promotion blocked pending gates | FP-023 |
| Offer/margin/retention/conversion gated | FP-014, FP-015, FP-017, FP-021, FP-024, FP-029, FP-030, FP-031, FP-032 |
| Acquisition/creative expansion gated | B-01b, B-03, FP-007, FP-009, FP-016, FP-018, FP-019, FP-022, FP-025 |
| Measurement/data-contract/incrementality layer candidate | B-01a, B-01c, B-01d, B-02a, B-02b, B-04, B-05, B-06, B-07, B-08, B-09, B-10, B-11, B-12, B-13, B-14, B-15, B-16, B-17, B-18, B-19, FP-008, FP-012, FP-020, FP-026, FP-027, FP-028 |

### Architecture decision for this intake

No active playbook/use-case promotion in Phase 0. The current registry routes by
`module + msm_state + optional merchant_id`, treats `triggers.condition` as
authoring metadata, and returns one matched pattern. Batch-activating 55 cases
would create route ambiguity, missing data fields, and missing action-surface
wiring. Promotion must be staged through ADR-0011 three-layer assets plus route
and fixture tests.

### Omission check

Fresh verification on 2026-06-01 found no case-level omissions:
- DOCX title extraction, Markdown title extraction, `case_index.json`,
  `TRANSLATION_TRIAGE.md`, and this intake log all resolve to the same 55 case
  IDs with no missing or extra IDs.
- Archived DOCX SHA-256 matches the uploaded source exactly.
- All referenced existing V3 assets in the reuse map exist.
- Runtime dry run passed; targeted KG tests passed with 72 passed and 1 existing
  pytest config warning.

### Phase 1 source alignment

Completed on 2026-06-01. The following already-represented FINAL cases were
aligned to existing V3 assets without changing runtime routing, brand binding
thresholds, utility priors, runtime code, or action IDs:

| Source case | Aligned asset | Result |
|-------------|---------------|--------|
| FP-001 | `use_cases/wandering_bear/wb_001_subscription_mix_dilution.yaml` | Source provenance added; exact match confirmed |
| FP-002 | `use_cases/wandering_bear/wb_002_shopcash_denominator.yaml` | Source provenance added; exact match confirmed |
| FP-003 | `use_cases/wandering_bear/_legacy/wb_003_evergreen_naming_test.yaml` | Source provenance added; remains legacy |
| FP-004 | `use_cases/wandering_bear/wb_004_brand_vs_dr_cpa.yaml` | Source provenance added; exact match confirmed |
| FP-005 | `use_cases/wandering_bear/wb_005_meta_destination_mix.yaml` | Source provenance added; exact match confirmed |
| FP-006 | `use_cases/wandering_bear/_legacy/wb_006_inventory_spend_pullback.yaml` | Source provenance added; remains legacy |
| FP-010 | `use_cases/consumer_brand_a/cba_001_ugc_creative.yaml` | Source provenance added; rollout windows enriched from FINAL source |
| FP-011 | `use_cases/consumer_brand_a/cba_002_compliance_ux.yaml` | Source provenance added; deploy date, remediation window, and CAC movement enriched from FINAL source |
| FP-013 | `playbooks/meta/_deferred/acquisition_ltv_quality_trap.yaml` | Source provenance added; remains deferred |

### Open items

- [ ] Choose long-term private artifact storage for the gitignored raw source
      archive, using `SOURCE_MANIFEST.md` hashes as the tracked verification
      anchor.
- [ ] Confirm whether anonymized `B-*` cases should remain source-only or become
      a dormant pattern bank.
- [ ] Confirm canonical merchant IDs for first-party brands not yet represented
      in V3.
- [ ] Decide whether FINAL doc numbers can be copied into active YAML evidence
      records immediately or need partner review first.
- [ ] Pick the first promotion tranche and add meta-pattern + brand binding +
      use-case YAML + targeted tests.

## Batch: Consumer Brand A + Consumer Brand B — 2026-04-13

**Partner delivery**: `partner_drafts/kg_partner/Consumer Goods Company/`
**Source archive**: `use_cases/consumer_brand_a/_source/`, `use_cases/consumer_brand_b/_source/`
**Intake mode**: Mode B (synchronous translate + activate)
**Intake lead**: Step 0–8 execution per Execution Prompt 2026-04-13

### Cases received: 3

| Case | Brand | Title | Module | MSM State | Classification | Phase | Status |
|------|-------|-------|--------|-----------|----------------|-------|--------|
| cba_001 | Consumer Brand A | UGC Creator Program | acquisition | DEGRADING | NOVEL | P1 | Active translation — Step 3 pending |
| cba_002 | Consumer Brand A | Compliance UX + CVR Collapse | conversion | CRITICAL | NOVEL | P1 | Active translation — Step 3 pending, proxy-trigger discipline required |
| cbb_001 | Consumer Brand B | Offer-Heavy Creative / LTV Quality Trap | acquisition | WATCH | NOVEL + cross-module | P2 | Dormant — `playbooks/meta/_deferred/acquisition_ltv_quality_trap.yaml` |

### Classification notes

**cba_001 — NOVEL** (not VARIANT):
Conceptually related to `acquisition_cac_channel_mix` ("audit upstream compositional
variable on CAC rise"). Both detect CAC degradation from a mix problem, but the
upstream variable differs: destination routing (channel_mix) vs creative format
(ugc_creative). V3 has no meta-pattern inheritance mechanism — VARIANT would
imply shared YAML logic, which does not exist. Relationship documented in
description field only. When Phase 3+ introduces meta-pattern composition,
reclassification to VARIANT becomes meaningful.

**cba_002 — NOVEL with proxy-trigger discipline**:
MSM CRITICAL fires via `mobile_below_degrading AND cvr_trending_down`. Root cause
(compliance popup) is site-wide, not mobile-specific. `analysis_path[0]` MUST be
`timeline_correlation` with `must_run_first: true`. See SOP Section 10.

**cbb_001 — P2 DEFERRED**:
Trigger condition requires `second_order_rate_delta` (creative-level cohort metric).
Field does not exist in `DecisionFeatureVector`. Population-level `repeat_rate_7d`
is NOT a valid proxy — would cause false positives on all acquisition WATCH events.
Three Phase 2 dependencies block activation. See dormant YAML `blocked_by` section.

### Mutual exclusivity check (acquisition module — cba_001 vs cbb_001)

cba_001 (DEGRADING) and cbb_001 (WATCH) share the acquisition module.
MSM-State Separation Corollary applies (ADR-0012): different MSM states
on the same dimension are mutually exclusive by system invariant.
No trigger-level analysis required. Option 1 (dict | None) confirmed correct.

### Architecture changes this intake

| Change | File | ADR |
|--------|------|-----|
| `match_playbook()` gains `merchant_id` param | `playbook_registry.py` | ADR-0012 |
| `_deferred/` directory skipped by loader | `playbook_registry.py` | ADR-0012 |
| ADR-0012 written | `docs/adr/0012-...md` | ADR-0012 |
| SOP Section 10 (Proxy Trigger Discipline) | `docs/playbook_authoring_sop.md` | — |
| Architecture invariant Test 10 | `tests/architecture/test_architecture_invariants.py` | ADR-0012 |
| 5 router tests + 1 deferred loader test | `tests/layer2/test_playbook_registry.py` | ADR-0012 |

### Open items (resolve before intake end)

- [ ] Step 3: translate cba_001 meta-pattern + brand binding + use case YAML
- [ ] Step 3: translate cba_002 meta-pattern + brand binding + use case YAML
- [ ] Confirm cba_001 threshold keys with partner (see partner_clarification_queue/)
- [ ] Confirm cba_002 threshold keys with partner
- [ ] Run fixture tests for cba_001 and cba_002 before shipping

### Intake end update (2026-04-13)

**Status**: Active translation complete — fixture tests green, dryrun exit 0.

**Final stats**:
- New meta-patterns (active): 2 (acquisition_ugc_creative, conversion_compliance_friction)
- New meta-patterns (dormant): 1 (acquisition_ltv_quality_trap in _deferred/)
- New brand bindings: 2 (both under consumer_brand_a/)
- New use cases: 2 (cba_001_ugc_creative, cba_002_compliance_ux)
- New threshold keys (active): 4 (cpm_spike_ratio, creative_ugc_share_floor, cvr_collapse_threshold, recent_change_window_days)
- New threshold keys (dormant): 2 (cac_improvement_floor, offer_creative_share_threshold — for cbb_001)
- New action_ids: 3 (AUDIT_CREATIVE_MIX, SCALE_TOP_CREATIVE, REMOVE_COMPLIANCE_FRICTION)
- Test count: 402 passing (up from 391 pre-intake)
- ADRs: ADR-0012 (match_playbook contract) accepted

**Open items carried forward** (to partner sync):
- cba_001 monthly_gmv, aov, and observation timeframe all estimated — partner confirmation needed
- cba_002 session count and paid/organic split estimated — partner confirmation needed
- cbb_001 4 clarification questions — collected in partner_clarification_queue/
