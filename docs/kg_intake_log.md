# KG Intake Log

Records every partner KG content intake: cases received, triage results,
translation status, and open questions. Updated at intake start and intake end.

---

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
