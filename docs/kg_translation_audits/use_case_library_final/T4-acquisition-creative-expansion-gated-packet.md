---
source_group: Use Case Library FINAL - T4 acquisition and creative expansion
status: BLOCKED_FOR_ACTIVE_RUNTIME
created_at: 2026-06-01
scope: Source-only audit packet for acquisition and creative expansion cases from Use Case Library FINAL
runtime_assets_created: false
---

# T4 Acquisition And Creative Expansion Gated Packet

## Final Group Status

Final decision: `BLOCKED_FOR_ACTIVE_RUNTIME`.

The T4 cases are preserved as source-only acquisition and creative evidence. No
active runtime YAML, dormant YAML, brand binding, tests, routing code, action
renderer changes, or generated runtime assets were created by this packet.

The conservative decision is required because the supervised plan says these
cases may become active only after route exclusivity and action-surface checks.
The current evidence does not prove those gates, and several cases require
creative taxonomy, campaign/channel contracts, incrementality or attribution
definitions, partner approval for raw source figures, and action IDs that are
not shown as runtime-ready in the planning docs.

## Count Check

| Check | Value |
|-------|-------|
| Expected T4 count | 9 |
| Observed packet count | 9 |
| Exact IDs | `B-01b`, `B-03`, `FP-007`, `FP-009`, `FP-016`, `FP-018`, `FP-019`, `FP-022`, `FP-025` |
| Runtime assets created | `false` |

## Target Mode Legend

| Target mode | Meaning for T4 |
|-------------|----------------|
| Source-only acquisition evidence | Keep the case as audit evidence for future acquisition logic; do not activate until route exclusivity, data fields, and action surface pass review. |
| Source-only creative evidence | Keep creative format, product-specific, or angle-learning evidence in the packet; do not copy raw metrics into Layer 2 or treat creative tags as executable runtime fields. |
| Future dormant candidate | Plausible future `_deferred/` pattern after partner approval and architecture review, but no dormant asset is created here. |
| Data/action/routing gated source-only | Case needs campaign, channel, action, attribution, or routing contracts before any active or dormant runtime promotion. |

## Group-Level Blockers

1. Acquisition route collisions: T4 cases mostly want acquisition routes and may
   collide with existing acquisition patterns by module, MSM state, and merchant
   unless a route matrix or ADR proves exclusivity.
2. Creative and angle taxonomy: product-specific creative, authority creative,
   Reels-native creative, ABO testing, and ADHD/problem-angle tests need a
   canonical taxonomy before they can be used as stable runtime triggers.
3. Channel/campaign data contract: required fields such as prospecting vs.
   retargeting role, audience overlap, LAL seed definition, channel maturity,
   testing structure, creative tag, placement, and campaign objective are not
   established as runtime contract fields in the reviewed planning docs.
4. Action renderer and action IDs: T4 actions imply exclusion rebuilds, YouTube
   retargeting roles, post-click rebuilds, creative production, ABO testing, and
   angle-specific spend biasing. The reviewed docs do not prove supported
   runtime action IDs or renderer copy for those actions.
5. Incrementality and attribution: YouTube role, LAL seed quality, Reels as a
   top-of-funnel complement, and source-reported acquisition improvements need
   attribution-window and incrementality guardrails before active routing.
6. Raw source governance: observed metrics remain source evidence only. Raw
   numbers from the FINAL source must not be copied into Layer 2 or active YAML
   until partner approval and calibration policy are confirmed.

## Case Audit Table

| Case | Source line | Short title | Source evidence kept in packet | Blocker | Proposed future pattern / note | Target mode |
|------|-------------|-------------|--------------------------------|---------|--------------------------------|-------------|
| `B-01b` | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:64` | Tight existing-customer exclusion reduces nCAC | Lookalike prospecting paid for existing-customer impressions/clicks; comprehensive all-time and recent purchaser exclusion reduced new-customer CAC and grew new-customer order volume. | Needs customer-exclusion freshness fields, Custom Audience match-rate evidence, route exclusivity against existing acquisition CAC patterns, and supported exclusion-audit action. | Candidate note: `acquisition_customer_exclusion_lal_quality`; keep as benchmark/source evidence until anonymized `B-*` governance and route matrix are approved. | Data/action/routing gated source-only |
| `B-03` | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:366` | Audience overlap degrades Meta ROAS as spend scales | Meta ROAS declined during spend scaling; case body attributes recovery to tightened separation between retargeting and prospecting pools and fresher exclusions. | Requires audience-overlap calculation, exclusion-list freshness threshold, Meta route exclusivity, and action support for audience rebuild/overlap controls. | Candidate note: `acquisition_audience_overlap_saturation`; likely future dormant acquisition hygiene pattern after overlap taxonomy exists. | Data/action/routing gated source-only |
| `FP-007` | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1770` | Post-signal-loss recovery via creative and post-click experience | Signal-loss event broke paid social performance; recovery relied on authority creative plus review/information-heavy post-click pages, treating ad engagement and conversion together. | Cross-module collision across acquisition, conversion, and measurement; needs signal-loss event contract, creative authority taxonomy, LP proof fields, attribution handling, and multi-surface action IDs. | Candidate note: `acquisition_signal_loss_creative_postclick_recovery`; may require cross-module architecture rather than a single acquisition route. | Future dormant candidate |
| `FP-009` | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:1911` | Long-cycle YouTube should start as retargeting amplifier | YouTube was introduced as a retargeting amplifier for a long buying cycle while search scaling carried the account-level guardrail. | Needs channel maturity, purchase-cycle length, conversion-lag fields, YouTube role taxonomy, retargeting/prospecting route separation, and attribution-window guardrails. | Candidate note: `acquisition_youtube_retargeting_amplifier`; keep source-only until channel-entry contract exists. | Data/action/routing gated source-only |
| `FP-016` | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2347` | Product-specific creative lowers prospecting CAC | Product-specific attribute-led creative was introduced while audience, offer, landing page, and spend were stable; the source reports lower prospecting CAC and durability across later iterations. | Needs creative taxonomy, stable-test-window contract, creative-level CAC fields, action IDs for product-specific creative expansion, and partner approval before using raw performance figures. | Candidate note: `acquisition_product_specific_creative`; possible future creative evidence bank or dormant pattern. | Source-only creative evidence |
| `FP-018` | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2488` | Top-purchase LAL seed improves CAC | Tighter LAL seed built from highest-performing broad-campaign purchasers improved CAC modestly while creative, LP, offer, bid strategy, and attribution window were held constant. | Needs LAL seed provenance fields, minimum seed threshold policy, comparable order-volume guard, customer-quality readout, and route exclusivity against customer exclusion and CAC mix patterns. | Candidate note: `acquisition_lal_seed_quality`; future dormant candidate only after seed-quality data contract is explicit. | Data/action/routing gated source-only |
| `FP-019` | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2568` | Reels-native creative lowers CPM and blended CAC | Format-native Reels creative improved CPM/CTR and modestly improved blended CAC as a small-spend top-of-funnel complement, not a primary DR scaling lever. | Needs placement/format taxonomy, top-of-funnel role contract, blended-vs-direct-response attribution guard, spend-share guardrail, and supported creative-format action. | Candidate note: `acquisition_reels_format_native_efficiency`; source-only creative/channel evidence until creative-format routing exists. | Source-only creative evidence |
| `FP-022` | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:2796` | Dedicated ABO testing reduces spend concentration | Dedicated ABO testing separated creative testing from CBO performance delivery, reducing spend concentration and improving Meta efficiency/read quality. | Needs testing-structure contract, spend-concentration fields, creative graduation action IDs, route exclusivity, and measurement governance for CPP/CPC/CTR/CPM readouts. | Candidate note: `acquisition_dedicated_abo_creative_testing`; likely testing-ops dormant candidate, not active runtime. | Future dormant candidate |
| `FP-025` | `partner_drafts/kg_partner/use_case_library_final/use_case_library_final.md:3014` | ADHD messaging beats broader benefit angles | Angle-level testing found ADHD/problem-specific messaging more efficient than broader Decaf, Stress, and Weight Loss/Metabolism angles, with downstream purchase metrics checked. | Needs creative-angle taxonomy, ad-set isolation/tagging contract, downstream conversion guard, partner approval for sensitive/health-adjacent message governance, and action support for angle spend biasing. | Candidate note: `acquisition_creative_angle_specificity`; keep as source-only creative-angle evidence until taxonomy and compliance review exist. | Source-only creative evidence |

## Partner And Data Questions

1. Are anonymized benchmark cases `B-01b` and `B-03` approved for a dormant
   pattern bank, or must all `B-*` cases remain source-only?
2. Are raw FINAL source metrics approved for runtime YAML calibration, or must
   they remain audit-only evidence inside `partner_drafts/` and packet docs?
3. What canonical creative taxonomy should V3 use for product-specific,
   authority/whitecoat, format-native, ABO testing, and angle-specific creative
   decisions?
4. Which campaign fields are available and reliable: prospecting/retargeting
   role, audience overlap, exclusion-list freshness, LAL seed provenance, channel
   maturity, conversion lag, testing structure, creative tag, placement, and
   spend concentration?
5. Which action IDs and renderer surfaces can support exclusion rebuilds,
   YouTube retargeting amplifier setup, post-click proof-page rebuilds,
   product-specific creative production, seeded LAL tests, Reels-native creative,
   dedicated ABO testing, and angle-specific budget biasing?
6. What attribution and incrementality policy should govern top-of-funnel
   YouTube, Reels, LAL, and creative-angle cases before they are promoted?
7. For health-adjacent or sensitive-message cases, especially `FP-007` and
   `FP-025`, what compliance review is required before creative or angle
   recommendations can appear in active runtime output?

## Final Status

`BLOCKED_FOR_ACTIVE_RUNTIME`.

The packet preserves all 9 expected T4 cases as audit evidence only. It does
not create active runtime assets, dormant runtime assets, tests, route changes,
action renderer changes, or brand bindings. Future promotion requires route
exclusivity, data-contract readiness, action-surface support, source-governance
approval, and case-specific attribution or creative-taxonomy review.

## Verification Evidence

Commands run:

```bash
git diff --check
python - <<'PY'
from pathlib import Path

path = Path('docs/kg_translation_audits/use_case_library_final/T4-acquisition-creative-expansion-gated-packet.md')
issues = []
for lineno, line in enumerate(path.read_text().splitlines(), 1):
    if line.rstrip(' \t') != line:
        issues.append(lineno)
assert not issues, issues
print('packet whitespace check: no trailing spaces')
PY
python - <<'PY'
from pathlib import Path
import re

path = Path('docs/kg_translation_audits/use_case_library_final/T4-acquisition-creative-expansion-gated-packet.md')
text = path.read_text()
expected = ['B-01b', 'B-03', 'FP-007', 'FP-009', 'FP-016', 'FP-018', 'FP-019', 'FP-022', 'FP-025']

rows = re.findall(r'^\| `([^`]+)` \|', text, flags=re.M)
assert rows == expected, rows

all_case_ids = sorted(set(re.findall(r'\b(?:B-\d{2}[a-z]?|FP-\d{3})\b', text)))
unexpected_rows = [case for case in rows if case not in expected]
assert not unexpected_rows, unexpected_rows

print(f'case rows: {len(rows)}')
print('case rows exact:', ', '.join(rows))
print('all case ids mentioned:', ', '.join(all_case_ids))
PY
python - <<'PY'
import json
from pathlib import Path

expected = ['B-01b', 'B-03', 'FP-007', 'FP-009', 'FP-016', 'FP-018', 'FP-019', 'FP-022', 'FP-025']
index = json.loads(Path('partner_drafts/kg_partner/use_case_library_final/case_index.json').read_text())
found = {row['id']: row['line'] for row in index if row['id'] in expected}
assert list(found) == expected, found
print('source lines:', ', '.join(f'{case}:{found[case]}' for case in expected))
PY
```

Observed results:

- `git diff --check`: passed with no output.
- Direct packet whitespace check: `packet whitespace check: no trailing spaces`.
- Case-row count check: `case rows: 9`.
- Case-row exact IDs: `B-01b`, `B-03`, `FP-007`, `FP-009`, `FP-016`,
  `FP-018`, `FP-019`, `FP-022`, `FP-025`.
- Source-line plausibility check: `B-01b:64`, `B-03:366`, `FP-007:1770`,
  `FP-009:1911`, `FP-016:2347`, `FP-018:2488`, `FP-019:2568`,
  `FP-022:2796`, `FP-025:3014`.
