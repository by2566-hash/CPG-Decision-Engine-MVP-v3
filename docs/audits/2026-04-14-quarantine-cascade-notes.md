# Quarantine Cascade Rule — Institutional Notes

**Date:** 2026-04-14
**Trigger:** Task 7 of Group 1 Remediation Sprint (wb_003, wb_006 quarantine)
**Author:** Yubo + Codex audit

---

## What is the quarantine cascade rule

When a use case is quarantined (moved to `_legacy/`), the quarantine action
itself only touches `use_cases/{brand}/_legacy/`. But grep will reveal that
**side documents** — partner comms, translation logs, README files — still
reference the quarantined use cases in active-status language.

Left unaddressed, these stale references create confusion:
- Translation logs show "✓ 已翻译" for cases that are no longer active
- Partner comms ask for threshold values for cases that are not being activated
- Partner README claims N/N cases are active when some are legacy

The **quarantine cascade rule** requires that whenever a use case is
quarantined, three categories of side documents must also be updated in the
same sprint.

---

## The three cascade categories

### Category 1 — Translation logs
**Location:** `partner_drafts/kg_partner/{brand}/TRANSLATION_LOG.md`

**Required action:**
- Change the status cell from `✓ 已翻译` to `⏸ 已翻译 → 已 quarantine（pre-three-layer）`
- Add a dated footnote at the bottom explaining the quarantine and pointing to
  `use_cases/{brand}/_legacy/README.md`

**Why:** The translation log is the operational record of what has been
translated for a partner. If it shows active status for a quarantined case,
a partner reviewer or future engineer will assume the case is active.

### Category 2 — Partner drafts summary README
**Location:** `partner_drafts/README.md`

**Required action:**
- Update the "已翻译" count for the brand to reflect `N active + M legacy`
- Enumerate active and legacy IDs explicitly in the table row

**Why:** The summary README is the first file read when exploring partner
drafts. An inflated active count misleads scope assessment.

### Category 3 — Active partner comms documents
**Location:** `docs/partner_comms/`

**Required action:**
- Do NOT modify historical content (questions, derivation narratives, etc.)
- ADD a dated status note at the top of the document (or most recent status
  section) noting which cases were quarantined, that related questions are
  now non-urgent, and what to do if the partner raises them proactively

**Why:** Partner comms may contain open questions about threshold values for
quarantined cases. Those questions should not be pursued actively, but the
comms doc must not be silently stale either — the next person to open it
needs to know the status without having to cross-reference the legacy dir.

---

## Files that do NOT need updating

The following are correct references and should be left unchanged:

- `use_cases/{brand}/_legacy/README.md` — the legacy README is the canonical
  record; its mentions of wb_003/wb_006 are correct by definition
- `use_cases/{brand}/_legacy/{file}.yaml` — the `use_case_id` field inside
  the quarantined file is correct; do not change it
- `use_cases/{brand}/_source/README.md` — if it correctly describes legacy
  cases as excluded, leave it

---

## Quarantine vs deletion

**Quarantine** means moving a use case to `_legacy/` with a legacy marker
block. The file is preserved in full as an evidence record. It is no longer
part of the active three-layer KG routing system, but its data (observed
numbers, causal chains, gmv_lift_derivation) remains available for:
- future promotion back into active status (if a real meta-pattern is created)
- audit trail (the translation happened; the data was validated)
- cross-brand pattern design (dormant patterns sometimes inform later meta-patterns)

**Deletion** means permanently removing a file. Do not delete use cases.
Use quarantine instead. Deletion removes the evidence record, which cannot
be recovered from runtime artifacts.

The only valid reason to delete a use case file is if it contains incorrect
data that would actively mislead future engineers even in `_legacy/` form —
and that scenario should first be resolved by correcting the data, not deleting.

---

## Cascade checklist template

Copy this checklist for each future quarantine action:

```
Quarantine cascade for: {brand}/{use_case_id}
Date: YYYY-MM-DD

[ ] use_cases/{brand}/_legacy/{file}.yaml — legacy marker block added
[ ] use_cases/{brand}/_legacy/README.md — file listed
[ ] partner_drafts/kg_partner/{brand}/TRANSLATION_LOG.md — status updated, footnote added
[ ] partner_drafts/README.md — active/legacy count updated
[ ] docs/partner_comms/*.md — status note added (original content preserved)
[ ] grep -rn "{use_case_id}" . — no stale active-status references remain
[ ] python -m pytest -q — test count unchanged
[ ] python scripts/kg_dryrun.py — exit=0, playbook count unchanged
```

---

## Instance record: wb_003 and wb_006 (2026-04-14)

The cascade was executed as part of Group 1 Remediation Sprint Task 7 + post-task
cleanup. Files touched:

| File | Change |
|------|--------|
| `use_cases/wandering_bear/_legacy/wb_003_evergreen_naming_test.yaml` | Created (moved + marker added) |
| `use_cases/wandering_bear/_legacy/wb_006_inventory_spend_pullback.yaml` | Created (moved + marker added) |
| `use_cases/wandering_bear/_legacy/README.md` | Created |
| `partner_drafts/kg_partner/wandering_bear/TRANSLATION_LOG.md` | Status updated to quarantine; footnote added |
| `partner_drafts/README.md` | Count updated to 4/6 active + 2/6 legacy |
| `docs/partner_comms/kg_partner_collab_brief.md` | Status note added; original content preserved |

References that were correctly left unchanged:
- `use_cases/wandering_bear/_source/README.md` line 33
- `use_cases/wandering_bear/_legacy/README.md` lines 14–15
- `use_cases/wandering_bear/_legacy/wb_003_*.yaml` line 20
- `use_cases/wandering_bear/_legacy/wb_006_*.yaml` line 20
