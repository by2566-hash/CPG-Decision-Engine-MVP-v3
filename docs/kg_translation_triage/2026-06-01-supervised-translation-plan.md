---
purpose: Supervised multi-agent execution plan for translating Use Case Library FINAL into V3
source_triage: docs/kg_translation_triage/2026-06-01-use-case-library-final.md
status: multi_agent_review_incorporated
created_at: 2026-06-01
branch: codex-kg-translation-supervised-plan
---

# Supervised Translation Plan - Use Case Library FINAL

## Objective

Translate the 55-case Use Case Library FINAL into V3 without losing source
coverage, violating the three-layer KG architecture, or silently changing runtime
behavior. The process must be supervised, independently reviewed, and auditable.

## Current State

- Phase 0 intake is complete: 55/55 cases extracted and triaged.
- Phase 1 source alignment is complete for already-represented cases:
  FP-001, FP-002, FP-003, FP-004, FP-005, FP-006, FP-010, FP-011, FP-013.
- No new active runtime pattern has been promoted from the FINAL source yet.
- Work is isolated on branch `codex-kg-translation-supervised-plan`.
- Three read-only reviewer agents completed architecture, coverage, and
  verification/audit reviews. Their blocking findings are incorporated below.

## Non-Negotiable Architecture Rules

1. Layer 1 meta-patterns under `playbooks/meta/` contain no hardcoded threshold
   numbers. Thresholds must use `${thresholds.*}`.
2. Layer 2 brand bindings under `playbooks/brands/{merchant_id}/` contain no raw
   evidence data. They may contain thresholds, entity bindings, utility priors,
   and `evidence_case` pointers.
3. Layer 3 use cases under `use_cases/{merchant_id}/` are the single source of
   truth for observed numbers.
4. Current routing is MSM-state driven. `triggers.condition` is authoring and
   explanation metadata; it is not executable routing logic.
5. `match_playbook()` returns one `dict | None`. Same merchant + same module +
   same MSM state must be mutually exclusive unless a superseding ADR changes
   the routing contract.
6. `_deferred/` patterns are intentionally dormant and must not be loaded by
   runtime.
7. No routing-code change is allowed without an ADR and architecture test update.
8. Unknown threshold, dormant threshold, invalid calibration, fallback utility,
   or unsupported action-surface warnings are treated as hard gates for this
   translation process even if the current runtime only warns.

## Multi-Agent Operating Model

The controller agent owns integration, sequencing, and final sign-off. Subagents
are used only for bounded work with explicit evidence requirements.

### Per Translation Task

Each case promotion or dormant pattern task follows this loop:

1. Controller prepares the exact case brief and disjoint write scope.
2. Scoped implementer works on that scope only.
3. Spec reviewer checks whether the output satisfies the brief and V3 SOP.
4. Code quality reviewer checks maintainability, schema discipline, and risk.
5. Verification worker runs the required command gates and reports evidence.
6. Controller integrates only after all review issues are resolved.

Implementation subagents are sequential, not parallel, when write scopes could
overlap. Read-only reviewers may run in parallel.

### Required Agent Roles

| Role | Task class | Edit rights | Purpose |
|------|------------|-------------|---------|
| Architecture reviewer | Exploration / review | No | Check ADR-0011/0012/0013 compliance and route risks |
| Coverage reviewer | Exploration / review | No | Check 55-case coverage, mappings, and tranche classification |
| Scoped implementer | Implementation | Yes, assigned files only | Translate one bounded case or dormant group |
| Spec reviewer | Review | No | Verify implementation matches the brief and SOP |
| Code quality reviewer | Review | No | Verify schema quality, naming, duplication, and maintainability |
| Verification worker | Verification | No code edits | Run command gates and report exact outputs |
| Final audit reviewer | Review / handoff | No | Review the full diff before final sign-off |

## Standard Agent Briefs

### Scoped Implementer Brief Template

```text
Role: Scoped implementation worker
Goal: Translate {case_id} into V3 according to the approved tranche plan.
Task class: Implementation
Delegation fit: Bounded single-case write scope.
Context: Include source case excerpt, current triage row, relevant ADR/SOP rules, existing analogous YAMLs.
Allowed actions: Edit only listed ownership files; run local validation commands.
Ownership: {exact file paths to create/update}
Forbidden actions: Do not edit routing code, CI, dependencies, lockfiles, partner_drafts source files, unrelated cases, or ignored nested apps. Do not commit/push.
Evidence required: List source lines used, thresholds extracted, action IDs, utility derivation, route/MSM-state decision, tests run.
Verification commands: YAML parse, targeted pytest if applicable, python scripts/kg_dryrun.py.
Output format: DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED, then changed files and evidence.
Stop condition: Stop if merchant ID, data field, action surface, route exclusivity, or source evidence is unclear.
Risks / assumptions: State all inferred values explicitly.
```

### Spec Reviewer Brief Template

```text
Role: Spec compliance reviewer
Goal: Check whether the implementer output exactly satisfies the case brief and V3 SOP.
Task class: Review
Allowed actions: Read files and run read-only checks.
Ownership: No writes.
Forbidden actions: No edits, commits, deletes, installs, or network calls.
Evidence required: Findings first, with file/line references. Confirm no overbuild.
Verification commands: rg/sed/python read checks as needed.
Output format: APPROVED or CHANGES_REQUIRED with numbered findings.
Stop condition: Stop after spec verdict.
Risks / assumptions: Distinguish confirmed issue from question.
```

### Code Quality Reviewer Brief Template

```text
Role: Code quality reviewer
Goal: Check schema hygiene, naming, duplication, maintainability, and runtime risk.
Task class: Review
Allowed actions: Read files and run read-only checks.
Ownership: No writes.
Forbidden actions: No edits, commits, deletes, installs, or network calls.
Evidence required: Findings first, with severity and file/line references.
Verification commands: YAML parse, rg checks, optional targeted pytest.
Output format: APPROVED or CHANGES_REQUIRED with findings.
Stop condition: Stop after quality verdict.
Risks / assumptions: Do not re-review product strategy unless it affects code quality.
```

### Verification Worker Brief Template

```text
Role: Verification worker
Goal: Prove whether the translated case is safe to merge.
Task class: Verification
Allowed actions: Run existing local validation commands and inspect outputs.
Ownership: No writes.
Forbidden actions: No edits, installs, commits, deletes, or external calls.
Evidence required: Exact commands, exit codes, pass/fail counts, warnings.
Verification commands: Provided by controller per task.
Output format: PASS / FAIL / BLOCKED, then command evidence.
Stop condition: Stop after command evidence or first blocker.
Risks / assumptions: Existing warnings must be identified as existing, new, or unknown.
```

## Promotion Gates

Every case must pass these gates before it can move from source/triage into an
active three-layer KG asset.

| Gate | Required evidence | Stop condition |
|------|-------------------|----------------|
| Source coverage | Source case ID, line number, title, and source excerpt recorded | Missing or ambiguous source |
| Duplicate check | Existing meta-pattern/use-case comparison completed | Equivalent active pattern already exists |
| Merchant identity | Canonical `merchant_id` selected | Merchant slug unknown |
| Layer decision | Active vs legacy vs deferred vs source-only documented | Runtime suitability unclear |
| Route exclusivity | Module + MSM-state table checked for merchant | Same merchant/module/state overlap without ADR |
| Data contract | Required runtime fields exist or pattern stays dormant | Field missing for active trigger/action |
| Action surface | Action IDs wired or pattern stays dormant | New active action lacks runtime support |
| Threshold discipline | Meta-pattern thresholds use `${thresholds.*}` only | Hardcoded trigger number in Layer 1 |
| Evidence SSoT | Raw observed numbers only in `use_cases/` | Raw evidence duplicated into brand binding |
| Utility derivation | `gmv_lift_prior` has formula and source evidence | Utility guessed without evidence |
| Tests | Fixture/registry tests added or updated for active promotion | No test for active route |
| Dryrun | `python scripts/kg_dryrun.py` exits 0 without new warnings | Dryrun failure or new warning |
| Audit log | Intake/triage/audit docs updated | No traceable audit artifact |
| Threshold namespace | New active keys appear in SOP and `_KNOWN_THRESHOLD_KEYS` | Unknown/dormant key warning |
| Action surface | Active action IDs have impact and renderer support or approved exception | Fallback benchmark/default renderer for active action |
| Data-contract readiness | Required DFV/L0/L5 fields exist | Missing field or event source |
| Reviewer signoff | Spec, quality, and verification verdicts recorded | Any unresolved reviewer finding |

## Multi-Agent Review Findings Incorporated

| Reviewer | Finding | Plan change |
|----------|---------|-------------|
| Architecture reviewer | Batch activation and same merchant/module/MSM overlap are P0 risks; `condition` cannot prove route safety | Route-conflict and ADR escalation gates made hard stop conditions |
| Architecture reviewer | Unknown threshold/calibration warnings are runtime warnings but SOP treats them as lint errors | Threshold namespace gate added as hard gate |
| Verification reviewer | Automated tests are necessary but insufficient for semantic translation | Per-case promotion packet and reviewer signoff gates added |
| Verification reviewer | Measurement-heavy and FP-013-style cases must remain blocked until fields/action surfaces exist | Data-contract readiness and action-surface gates added |
| Coverage reviewer | Original promotion order did not explicitly tranche 13 cases | Case tranche ledger below now covers all 55 cases |
| Coverage reviewer | FP-012 is not low-risk because event-quality and CAPI fields/action surfaces are not visible | FP-012 moved to data-contract gated measurement tranche |
| Coverage reviewer | B-02b, B-06, and B-18 depend on geo/incrementality evidence | They are measurement-gated, not near-term active promotion items |

## Case Tranche Ledger

This ledger is the controller's source of truth for next-step ownership. It
covers all 55 source cases exactly once for current disposition.

| Current disposition | Cases | Count |
|---------------------|-------|-------|
| Already represented and Phase 1 source-aligned | FP-001, FP-002, FP-003, FP-004, FP-005, FP-006, FP-010, FP-011, FP-013 | 9 |
| Existing-pattern reuse candidate | FP-023 | 1 |
| Measurement/data-contract/incrementality gated | B-01a, B-01c, B-01d, B-02a, B-02b, B-04, B-05, B-06, B-07, B-08, B-09, B-10, B-11, B-12, B-13, B-14, B-15, B-16, B-17, B-18, B-19, FP-008, FP-012, FP-020, FP-026, FP-027, FP-028 | 27 |
| Offer, margin, retention, and conversion gated | FP-014, FP-015, FP-017, FP-021, FP-024, FP-029, FP-030, FP-031, FP-032 | 9 |
| Acquisition and creative expansion gated | B-01b, B-03, FP-007, FP-009, FP-016, FP-018, FP-019, FP-022, FP-025 | 9 |

## Translation Tranches

### T0 - Completed Intake and Source Alignment

Status: complete.

Artifacts:
- `docs/kg_translation_triage/2026-06-01-use-case-library-final.md`
- `docs/kg_intake_log.md`
- `source_alignment` metadata in the 9 already-represented assets

### T1 - Low-Risk Promotion Candidates

These are closest to the current V3 architecture and should be implemented one
case at a time with full review gates:

| Case | Proposed asset | Initial mode | Notes |
|------|----------------|--------------|-------|
| FP-003 | `conversion_merchandising_primary_metric` | Active candidate | Promote legacy WB naming test only if route exclusivity holds |
| FP-006 | `acquisition_inventory_aware_spend_pullback` | Active or dormant candidate | Requires SKU/inventory-aware action naming; current legacy action ID is known wrong |
| FP-023 | Rarebird binding for `acquisition_cac_channel_mix` | Existing-pattern reuse candidate | Requires canonical merchant ID and route check |

FP-012 was removed from T1 after review. It remains a valid pattern candidate,
but only after the data-contract reviewer confirms event-quality and CAPI fields
plus action-surface support.

### T2 - Dormant Pattern Bank

Measurement-heavy cases should become dormant pattern candidates or architecture
notes until V3 has an explicit measurement/incrementality layer:

- `B-01a`, `B-01c`, `B-01d`, `B-02a`, `B-02b`, `B-04` through `B-19`
- `FP-008`, `FP-012`, `FP-020`, `FP-026`, `FP-027`, `FP-028`

Expected output is not active runtime YAML unless the architecture gate approves
a measurement guard layer.

### T3 - Offer, Margin, Retention, and Lifecycle Candidates

These require contribution-margin, lifecycle, cohort, or retention-specific data
contracts before active promotion:

- Offer/margin: `FP-014`, `FP-015`, `FP-021`
- Retention/lifecycle: `FP-029`, `FP-030`, `FP-031`
- Conversion merchandising: `FP-017`, `FP-024`, `FP-032`

Default mode is dormant or source-backed pattern candidate until fields and
action gates are explicit.

### T4 - Acquisition and Creative Expansion

These may become active only after route exclusivity and action-surface checks:

- `B-01b`, `B-03`
- `FP-007`, `FP-009`, `FP-016`, `FP-018`, `FP-019`, `FP-022`, `FP-025`

## Required Verification Commands

Run at minimum after each active promotion:

```bash
python -c "from pathlib import Path; import yaml; [yaml.safe_load(p.read_text()) for p in Path('playbooks').rglob('*.yaml')]; [yaml.safe_load(p.read_text()) for p in Path('use_cases').rglob('*.yaml')]"
python scripts/kg_dryrun.py
python -m pytest tests/layer2/test_playbook_registry.py tests/layer2/test_brand_binding.py tests/architecture/test_architecture_invariants.py -q
git diff --check
```

Run additionally when adding a new active pattern:

```bash
python -m pytest tests/layer2/test_new_patterns_cba.py tests/layer2/test_multi_merchant_isolation.py -q
```

Run broader validation before final handoff:

```bash
python -m pytest -q
python scripts/kg_dryrun.py
git status --short --untracked-files=all
```

## Audit Artifacts

Each promoted case or dormant group must leave an audit trail:

1. Update `docs/kg_translation_triage/2026-06-01-source-coverage-ledger.md`.
2. Update `docs/kg_translation_triage/2026-06-01-use-case-library-final.md`.
3. Update `docs/kg_intake_log.md`.
4. Create or update a promotion packet under `docs/kg_translation_audits/`.
5. If partner clarification is needed, add/update a file under
   `docs/partner_clarification_queue/`.

## Stop Conditions

Stop before writing active YAML if any of these occur:

- canonical merchant ID is unknown,
- source case cannot be mapped unambiguously,
- action ID is not supported by runtime surfaces,
- required feature field is absent from `DecisionFeatureVector`,
- new pattern overlaps an existing same merchant + same module + same MSM state,
- meta-pattern needs executable trigger conditions to route correctly,
- `kg_dryrun.py` emits a new warning or failure,
- targeted tests fail,
- source data appears sensitive beyond existing repository policy.

## Current Multi-Agent Review

Three read-only subagents have been dispatched to review this plan area:

1. Architecture reviewer: ADR/routing constraints and promotion gates.
2. Coverage reviewer: 55-case coverage and tranche taxonomy.
3. Verification reviewer: command gates and audit process.

Their findings must be incorporated before T1 implementation begins.
