# Partner Source Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the six newly supplied partner DOCX files against the existing Use Case Library FINAL translation, preserve source provenance safely, and identify which cases are eligible for later runtime KG promotion.

**Architecture:** Treat the new DOCX files as pre-runtime source evidence, not runtime KG input. Archive raw files under gitignored `partner_drafts/`, create tracked manifest and reconciliation docs under `docs/kg_translation_*`, then gate any Layer 1/2/3 runtime changes through promotion packets. Decision core and playbook loading must remain unchanged.

**Tech Stack:** Local DOCX XML extraction with Python stdlib, Markdown audit docs, existing V3 KG YAML under `playbooks/` and `use_cases/`, `scripts/kg_dryrun.py`, and targeted pytest suites.

---

## Evaluation Summary

The six DOCX files contain 26 first-party/operator cases. They map to existing
Use Case Library FINAL cases `FP-007` through `FP-032`; they are not a separate
new 26-case library.

| Source DOCX | Case count | Mapped FINAL IDs | Initial disposition |
|-------------|------------|------------------|---------------------|
| `/Users/yubo/Downloads/Bonafide, Spoonful, and Grassroots.docx` | 3 | `FP-007`, `FP-008`, `FP-009` | Supporting/possibly primary source for existing gated packets |
| `/Users/yubo/Downloads/consumer_goods_case_studies_final.docx` | 6 | `FP-010` to `FP-015` | Source reconciliation; `FP-010` and `FP-011` already runtime represented |
| `/Users/yubo/Downloads/r2_consumer_case_studies.docx` | 6 | `FP-016` to `FP-021` | Source reconciliation; several remain action/data/routing gated |
| `/Users/yubo/Downloads/rarebird_use_cases (1).docx` | 4 | `FP-022` to `FP-025` | Source reconciliation; `FP-023` remains the strongest first runtime-promotion candidate |
| `/Users/yubo/Downloads/skincare_use_cases_revised (1).docx` | 3 | `FP-026` to `FP-028` | Measurement/affiliate/search data-contract gated |
| `/Users/yubo/Downloads/wine_pet_use_cases_updated.docx` | 4 | `FP-029` to `FP-032` | Retention/cohort/margin/conversion gated |

Key architectural judgment:

- These files should not be scanned by decision core.
- These files should not directly generate active `playbooks/meta/*.yaml`.
- These files should not directly generate `playbooks/brands/{merchant_id}/*.yaml`.
- Raw observed numbers must not enter brand bindings.
- The next safe step is source reconciliation, not runtime promotion.

## File Structure

Raw source archive, gitignored:

- Create: `partner_drafts/kg_partner/brand_source_batch_2026_06_01/`
- Create: `partner_drafts/kg_partner/brand_source_batch_2026_06_01/<slug>/<original DOCX>`
- Create: `partner_drafts/kg_partner/brand_source_batch_2026_06_01/<slug>/<slug>.md`
- Create: `partner_drafts/kg_partner/brand_source_batch_2026_06_01/<slug>/case_index.json`

Tracked audit/control-plane docs:

- Create: `docs/kg_translation_audits/brand_source_batch_2026_06_01/SOURCE_MANIFEST.md`
- Create: `docs/kg_translation_triage/2026-06-01-brand-source-reconciliation.md`
- Modify: `docs/kg_translation_audits/use_case_library_final/SOURCE_MANIFEST.md`
- Modify: `docs/kg_translation_audits/2026-06-01-use-case-library-final-supervision.md`
- Modify: `docs/kg_intake_log.md`

Runtime files:

- Do not modify in this plan unless a later user-approved promotion task is opened.
- Do not create `playbooks/meta/*.yaml`.
- Do not create `playbooks/brands/{merchant_id}/*.yaml`.
- Do not create new active `use_cases/{merchant_id}/*.yaml`.

## Task 1: Archive And Extract The Six Partner Sources

**Files:**
- Create: `partner_drafts/kg_partner/brand_source_batch_2026_06_01/`
- Create: six slugged subdirectories under that archive
- No tracked files changed in this task

- [ ] **Step 1: Create ignored archive directories**

Run:

```bash
mkdir -p partner_drafts/kg_partner/brand_source_batch_2026_06_01/{bonafide_spoonful_grassroots,consumer_goods_case_studies,r2_consumer_case_studies,rarebird_use_cases,skincare_use_cases,wine_pet_use_cases}
```

Expected:

```text
directories created under partner_drafts/kg_partner/brand_source_batch_2026_06_01/
```

- [ ] **Step 2: Copy the raw DOCX files into the ignored archive**

Run:

```bash
cp "/Users/yubo/Downloads/Bonafide, Spoonful, and Grassroots.docx" "partner_drafts/kg_partner/brand_source_batch_2026_06_01/bonafide_spoonful_grassroots/Bonafide, Spoonful, and Grassroots.docx"
cp "/Users/yubo/Downloads/consumer_goods_case_studies_final.docx" "partner_drafts/kg_partner/brand_source_batch_2026_06_01/consumer_goods_case_studies/consumer_goods_case_studies_final.docx"
cp "/Users/yubo/Downloads/r2_consumer_case_studies.docx" "partner_drafts/kg_partner/brand_source_batch_2026_06_01/r2_consumer_case_studies/r2_consumer_case_studies.docx"
cp "/Users/yubo/Downloads/rarebird_use_cases (1).docx" "partner_drafts/kg_partner/brand_source_batch_2026_06_01/rarebird_use_cases/rarebird_use_cases (1).docx"
cp "/Users/yubo/Downloads/skincare_use_cases_revised (1).docx" "partner_drafts/kg_partner/brand_source_batch_2026_06_01/skincare_use_cases/skincare_use_cases_revised (1).docx"
cp "/Users/yubo/Downloads/wine_pet_use_cases_updated.docx" "partner_drafts/kg_partner/brand_source_batch_2026_06_01/wine_pet_use_cases/wine_pet_use_cases_updated.docx"
```

Expected:

```text
six DOCX files copied; `git status --ignored --short` shows them ignored under partner_drafts/
```

- [ ] **Step 3: Extract Markdown and case indexes**

Run this exact extraction script from repo root:

```bash
python - <<'PY'
from pathlib import Path
import json
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path("partner_drafts/kg_partner/brand_source_batch_2026_06_01")
DOCS = {
    "bonafide_spoonful_grassroots": "Bonafide, Spoonful, and Grassroots.docx",
    "consumer_goods_case_studies": "consumer_goods_case_studies_final.docx",
    "r2_consumer_case_studies": "r2_consumer_case_studies.docx",
    "rarebird_use_cases": "rarebird_use_cases (1).docx",
    "skincare_use_cases": "skincare_use_cases_revised (1).docx",
    "wine_pet_use_cases": "wine_pet_use_cases_updated.docx",
}
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

for slug, filename in DOCS.items():
    docx = ROOT / slug / filename
    with zipfile.ZipFile(docx) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs = []
    for p in root.findall(".//w:p", NS):
        text = "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()
        if text:
            paragraphs.append(text)

    markdown_lines = []
    case_index = []
    case_no = 0
    for idx, text in enumerate(paragraphs, 1):
        if re.match(r"^\d+\.\s+.{20,}$", text):
            case_no += 1
            markdown_lines.append(f"\n## CASE-{case_no:03d}: {text}\n")
            case_index.append({
                "local_case_id": f"{slug.upper()}-{case_no:03d}",
                "paragraph": idx,
                "title": text,
            })
        else:
            markdown_lines.append(text)

    (ROOT / slug / f"{slug}.md").write_text("\n\n".join(markdown_lines) + "\n", encoding="utf-8")
    (ROOT / slug / "case_index.json").write_text(json.dumps(case_index, indent=2) + "\n", encoding="utf-8")
    print(slug, len(case_index))
PY
```

Expected output:

```text
bonafide_spoonful_grassroots 3
consumer_goods_case_studies 6
r2_consumer_case_studies 6
rarebird_use_cases 4
skincare_use_cases 3
wine_pet_use_cases 4
```

## Task 2: Create Tracked Source Manifest For The Six-File Batch

**Files:**
- Create: `docs/kg_translation_audits/brand_source_batch_2026_06_01/SOURCE_MANIFEST.md`

- [ ] **Step 1: Compute source hashes and generate manifest draft**

Run:

```bash
python - <<'PY'
from pathlib import Path
import hashlib
import json

ROOT = Path("partner_drafts/kg_partner/brand_source_batch_2026_06_01")
OUT = Path("docs/kg_translation_audits/brand_source_batch_2026_06_01/SOURCE_MANIFEST.md")
OUT.parent.mkdir(parents=True, exist_ok=True)

DOCS = [
    ("bonafide_spoonful_grassroots", "Bonafide, Spoonful, and Grassroots.docx", ["FP-007", "FP-008", "FP-009"]),
    ("consumer_goods_case_studies", "consumer_goods_case_studies_final.docx", ["FP-010", "FP-011", "FP-012", "FP-013", "FP-014", "FP-015"]),
    ("r2_consumer_case_studies", "r2_consumer_case_studies.docx", ["FP-016", "FP-017", "FP-018", "FP-019", "FP-020", "FP-021"]),
    ("rarebird_use_cases", "rarebird_use_cases (1).docx", ["FP-022", "FP-023", "FP-024", "FP-025"]),
    ("skincare_use_cases", "skincare_use_cases_revised (1).docx", ["FP-026", "FP-027", "FP-028"]),
    ("wine_pet_use_cases", "wine_pet_use_cases_updated.docx", ["FP-029", "FP-030", "FP-031", "FP-032"]),
]

lines = [
    "---",
    "source_group: brand_source_batch_2026_06_01",
    "status: tracked_manifest_raw_source_gitignored",
    "created_at: 2026-06-01",
    "raw_source_tracked_in_git: false",
    "---",
    "",
    "# Source Manifest - Brand Source Batch 2026-06-01",
    "",
    "Raw DOCX, extracted markdown, and per-file case indexes remain under `partner_drafts/` and are intentionally gitignored.",
    "",
    "## Source Files",
    "",
    "| Slug | File | SHA-256 | Mapped FINAL IDs |",
    "|------|------|---------|------------------|",
]
for slug, filename, mapped_ids in DOCS:
    path = ROOT / slug / filename
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    lines.append(f"| `{slug}` | `{filename}` | `{digest}` | {', '.join(mapped_ids)} |")

lines.extend([
    "",
    "## Case Counts",
    "",
    "| Slug | Extracted cases |",
    "|------|-----------------|",
])
for slug, _, _ in DOCS:
    index = json.loads((ROOT / slug / "case_index.json").read_text())
    lines.append(f"| `{slug}` | {len(index)} |")

lines.extend([
    "",
    "## Governance",
    "",
    "- These files are source evidence for existing `FP-007` through `FP-032` cases.",
    "- They are not runtime playbook input.",
    "- Runtime promotion still requires a packet, source reconciliation, data-contract check, action-surface check, route-exclusivity check, tests, and reviewer approval.",
    "",
])
OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT)
PY
```

Expected:

```text
docs/kg_translation_audits/brand_source_batch_2026_06_01/SOURCE_MANIFEST.md
```

- [ ] **Step 2: Verify the manifest**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path("docs/kg_translation_audits/brand_source_batch_2026_06_01/SOURCE_MANIFEST.md").read_text()
for expected in ["FP-007", "FP-032", "raw_source_tracked_in_git: false", "Runtime promotion still requires"]:
    assert expected in text, expected
print("BRAND_SOURCE_MANIFEST_OK")
PY
```

Expected:

```text
BRAND_SOURCE_MANIFEST_OK
```

## Task 3: Create Source Reconciliation Matrix

**Files:**
- Create: `docs/kg_translation_triage/2026-06-01-brand-source-reconciliation.md`

- [ ] **Step 1: Create the reconciliation document**

Create `docs/kg_translation_triage/2026-06-01-brand-source-reconciliation.md`
with this exact case mapping:

```markdown
# Brand Source Reconciliation - 2026-06-01

## Decision

The six brand-level DOCX files are supporting or primary source evidence for
existing Use Case Library FINAL first-party cases `FP-007` through `FP-032`.
They do not introduce new runtime KG cases by themselves.

## Mapping

| Source DOCX | Local case title | FINAL ID | Current FINAL disposition |
|-------------|------------------|----------|---------------------------|
| Bonafide, Spoonful, and Grassroots | Post-signal-loss paid social recovery requires moving the optimization burden from targeting onto creative and post-click experience | FP-007 | Acquisition/creative expansion gated |
| Bonafide, Spoonful, and Grassroots | A too-long paid social attribution window is a measurement bug that conceals where the incremental new-customer work is happening | FP-008 | Measurement/data-contract/incrementality gated |
| Bonafide, Spoonful, and Grassroots | When buying cycle is long and YouTube is a new channel, retargeting amplifier is the correct first role, not prospecting | FP-009 | Acquisition/creative expansion gated |
| consumer_goods_case_studies_final | CAC and CPMs declined following the introduction of a structured UGC creator program on Meta | FP-010 | Already represented and Phase 1 source-aligned |
| consumer_goods_case_studies_final | Legally required health data consent pop-up caused a sudden CVR collapse across all traffic sources | FP-011 | Already represented and Phase 1 source-aligned |
| consumer_goods_case_studies_final | Rebuilding the purchase event to isolate new customers improved CAC about 30% | FP-012 | Measurement/data-contract/incrementality gated |
| consumer_goods_case_studies_final | Offer-led creative reduced CAC but weakened repeat purchase behavior | FP-013 | Already represented and Phase 1 source-aligned |
| consumer_goods_case_studies_final | Lower-AOV offer outperformed on CAC and CVR despite weaker profit per order | FP-014 | Offer/margin/retention/conversion gated |
| consumer_goods_case_studies_final | Restricting DABA to high-margin SKUs improved order profitability without meaningful CAC tradeoff | FP-015 | Offer/margin/retention/conversion gated |
| r2_consumer_case_studies | Product-specific creative lowered prospecting CAC and held through the post-launch period | FP-016 | Acquisition/creative expansion gated |
| r2_consumer_case_studies | High CTR Pinterest creative required a direct offer to improve conversion | FP-017 | Offer/margin/retention/conversion gated |
| r2_consumer_case_studies | LAL seeding from top-performing purchase segments improved CAC as an incremental efficiency lever | FP-018 | Acquisition/creative expansion gated |
| r2_consumer_case_studies | Format-native Reels creative reduced CPMs and improved blended CAC as a complementary top-of-funnel lever | FP-019 | Acquisition/creative expansion gated |
| r2_consumer_case_studies | Conversion signal loss during Google tracking migration caused a CAC spike and partial recovery after reconnection | FP-020 | Measurement/data-contract/incrementality gated |
| r2_consumer_case_studies | New welcome offer expanded reach through lower CPMs but underperformed on backend conversion | FP-021 | Offer/margin/retention/conversion gated |
| rarebird_use_cases | Dedicated ABO creative testing reduced spend concentration and improved Meta efficiency | FP-022 | Acquisition/creative expansion gated |
| rarebird_use_cases | Website-only destination outperformed Web + Shop in a head-to-head Meta routing test | FP-023 | Existing-pattern reuse candidate |
| rarebird_use_cases | Revenue per session was the best decision metric in a landing-page option-architecture test | FP-024 | Offer/margin/retention/conversion gated |
| rarebird_use_cases | ADHD messaging materially outperformed broader value-prop and alternative benefit angles | FP-025 | Acquisition/creative expansion gated |
| skincare_use_cases_revised | Single affiliate bidding on brand terms produced an impossible conversion rate and inflated program metrics | FP-026 | Measurement/data-contract/incrementality gated |
| skincare_use_cases_revised | Brand keyword bleed into a non-brand paid campaign inflated product performance | FP-027 | Measurement/data-contract/incrementality gated |
| skincare_use_cases_revised | Affiliate last-click attribution inflated reported paid media CPA | FP-028 | Measurement/data-contract/incrementality gated |
| wine_pet_use_cases_updated | Gifted subscriptions mixed into retention reporting deflated renewal rate | FP-029 | Offer/margin/retention/conversion gated |
| wine_pet_use_cases_updated | Pause feature usage masked true churn and understated subscriber attrition rate | FP-030 | Offer/margin/retention/conversion gated |
| wine_pet_use_cases_updated | Autoship discount offered broadly eroded margin without improving retention | FP-031 | Offer/margin/retention/conversion gated |
| wine_pet_use_cases_updated | Bundle page received paid traffic but converted at half the rate of individual product pages | FP-032 | Offer/margin/retention/conversion gated |

## Promotion Implication

This batch strengthens source provenance for `FP-007` through `FP-032`. It does
not automatically change runtime readiness. `FP-023` remains the strongest first
runtime-promotion candidate because it can likely reuse the existing
`acquisition_cac_channel_mix` meta-pattern, but it still needs canonical
merchant ID, Layer 2 brand binding, Layer 3 evidence SSoT, route fixture tests,
and reviewer approval.
```

- [ ] **Step 2: Verify mapping count**

Run:

```bash
python - <<'PY'
from pathlib import Path
import re
text = Path("docs/kg_translation_triage/2026-06-01-brand-source-reconciliation.md").read_text()
ids = re.findall(r"\bFP-\d{3}\b", text)
unique = sorted(set(ids))
expected = [f"FP-{i:03d}" for i in range(7, 33)]
assert unique == expected, (unique, expected)
print("BRAND_SOURCE_RECONCILIATION_OK", len(unique))
PY
```

Expected:

```text
BRAND_SOURCE_RECONCILIATION_OK 26
```

## Task 4: Update Existing Audit References Without Changing Runtime

**Files:**
- Modify: `docs/kg_translation_audits/use_case_library_final/SOURCE_MANIFEST.md`
- Modify: `docs/kg_translation_audits/2026-06-01-use-case-library-final-supervision.md`
- Modify: `docs/kg_intake_log.md`

- [ ] **Step 1: Add supporting-source reference to existing source manifest**

Add a short section to
`docs/kg_translation_audits/use_case_library_final/SOURCE_MANIFEST.md`:

```markdown
## Supporting Brand Source Batch

The six-file brand source batch archived under
`partner_drafts/kg_partner/brand_source_batch_2026_06_01/` provides supporting
or primary source evidence for `FP-007` through `FP-032`. The tracked manifest is
`docs/kg_translation_audits/brand_source_batch_2026_06_01/SOURCE_MANIFEST.md`.
This does not change runtime readiness.
```

- [ ] **Step 2: Add supervision-record reference**

Add one row to the Control Artifacts table in
`docs/kg_translation_audits/2026-06-01-use-case-library-final-supervision.md`:

```markdown
| `docs/kg_translation_triage/2026-06-01-brand-source-reconciliation.md` | Maps six brand-level DOCX files to existing `FP-007` through `FP-032` cases |
```

- [ ] **Step 3: Add intake-log reference**

Add one bullet under the Use Case Library FINAL artifact list in
`docs/kg_intake_log.md`:

```markdown
- `docs/kg_translation_triage/2026-06-01-brand-source-reconciliation.md`
  (tracked reconciliation of six brand-level source files to `FP-007` through
  `FP-032`)
```

## Task 5: Re-score Runtime Promotion Candidates

**Files:**
- Create: `docs/kg_translation_triage/2026-06-01-brand-source-promotion-candidates.md`

- [ ] **Step 1: Create candidate scoring doc**

Create `docs/kg_translation_triage/2026-06-01-brand-source-promotion-candidates.md`
with this initial decision:

```markdown
# Brand Source Promotion Candidates - 2026-06-01

## Decision

No case from the six-file brand source batch is promoted directly to active
runtime KG in this reconciliation step.

## Candidate Ranking

| Rank | Case | Decision | Reason |
|------|------|----------|--------|
| 1 | FP-023 | Best first runtime-promotion candidate after confirmation | Can likely reuse existing `playbooks/meta/acquisition_cac_channel_mix.yaml`; action surface `FIX_DESTINATION_ROUTING` exists; still needs canonical `rarebird` merchant ID, Layer 2 brand binding, Layer 3 use case SSoT, and route tests. |
| 2 | FP-010 / FP-011 | Already represented | Use new brand source batch only to strengthen provenance if needed; runtime assets already exist. |
| 3 | FP-016 / FP-018 / FP-019 / FP-022 / FP-025 | Future acquisition/creative candidates | Need creative taxonomy, campaign data contract, route exclusivity, and supported action surfaces. |
| 4 | FP-014 / FP-015 / FP-017 / FP-021 / FP-024 / FP-029 / FP-030 / FP-031 / FP-032 | Future offer/retention/conversion candidates | Need margin, offer, retention/cohort, landing-page, and action contracts. |
| 5 | FP-008 / FP-012 / FP-020 / FP-026 / FP-027 / FP-028 | Measurement/data-contract candidates | Need measurement, event-quality, affiliate, search-query, and attribution contracts before runtime. |

## Recommended Next Promotion

Start with `FP-023` only after user confirms the canonical merchant slug and
approval to create:

- `playbooks/brands/rarebird/acquisition_cac_channel_mix.yaml`
- `use_cases/rarebird/rb_001_website_vs_shop_destination.yaml`
- route and brand-binding tests for `merchant_id=rarebird`
```

- [ ] **Step 2: Verify that no runtime file changed**

Run:

```bash
git diff -- playbooks use_cases src tests
```

Expected:

```text
no output
```

## Task 6: Verification Bundle

**Files:**
- No new files

- [ ] **Step 1: Verify source counts**

Run:

```bash
python - <<'PY'
from pathlib import Path
import json

root = Path("partner_drafts/kg_partner/brand_source_batch_2026_06_01")
expected = {
    "bonafide_spoonful_grassroots": 3,
    "consumer_goods_case_studies": 6,
    "r2_consumer_case_studies": 6,
    "rarebird_use_cases": 4,
    "skincare_use_cases": 3,
    "wine_pet_use_cases": 4,
}
for slug, count in expected.items():
    rows = json.loads((root / slug / "case_index.json").read_text())
    assert len(rows) == count, (slug, len(rows), count)
print("BRAND_SOURCE_COUNTS_OK", sum(expected.values()))
PY
```

Expected:

```text
BRAND_SOURCE_COUNTS_OK 26
```

- [ ] **Step 2: Verify docs whitespace and Git diff**

Run:

```bash
git diff --check
```

Expected:

```text
no output
```

- [ ] **Step 3: Verify runtime still runs unchanged**

Run:

```bash
python scripts/kg_dryrun.py
```

Expected:

```text
KG Dry-Run — 8 playbooks loaded
All checks passed
```

- [ ] **Step 4: Verify targeted tests**

Run:

```bash
python -m pytest tests/layer2/test_playbook_registry.py tests/layer2/test_brand_binding.py tests/layer2/test_new_patterns_cba.py tests/architecture/test_architecture_invariants.py -q
```

Expected:

```text
72 passed, 1 warning
```

## Task 7: Commit Reconciliation Docs Only

**Files:**
- Stage tracked docs created or modified in Tasks 2 to 5
- Do not stage `partner_drafts/`

- [ ] **Step 1: Confirm ignored raw source is not staged**

Run:

```bash
git status --short --ignored | grep partner_drafts || true
```

Expected:

```text
only ignored partner_drafts entries, no staged partner_drafts paths
```

- [ ] **Step 2: Stage tracked docs explicitly**

Run:

```bash
git add docs/superpowers/plans/2026-06-01-partner-source-reconciliation.md docs/kg_translation_audits/brand_source_batch_2026_06_01/SOURCE_MANIFEST.md docs/kg_translation_triage/2026-06-01-brand-source-reconciliation.md docs/kg_translation_triage/2026-06-01-brand-source-promotion-candidates.md docs/kg_translation_audits/use_case_library_final/SOURCE_MANIFEST.md docs/kg_translation_audits/2026-06-01-use-case-library-final-supervision.md docs/kg_intake_log.md
```

Expected:

```text
tracked reconciliation docs and execution plan staged; raw source remains ignored
```

- [ ] **Step 3: Commit**

Run:

```bash
git commit -m "Add partner brand source reconciliation"
```

Expected:

```text
commit created with only tracked reconciliation docs
```

## Execution Boundary

This plan stops after source reconciliation and promotion candidate scoring. It
does not create runtime KG assets. If the user approves runtime promotion next,
write a separate focused plan for `FP-023` with Layer 2 brand binding, Layer 3
use case SSoT, tests, and reviewer gates.

## Self-Review

- Spec coverage: The plan reads all six DOCX files, archives raw source safely,
  maps all 26 cases to `FP-007` through `FP-032`, updates tracked audit docs,
  and preserves decision-core isolation.
- Placeholder scan: No unresolved placeholder markers or unspecified
  implementation steps are present.
- Type consistency: Paths, IDs, and file names are consistent across tasks.
