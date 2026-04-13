# Data and License Status

## Purpose
This document records the provenance, usage limitations, and license status of
all data assets used in V3. It exists so that any reviewer — investor, partner,
engineer, or auditor — can answer "where did this data come from?" with a single
document.

---

## Data Assets

### Shopify Data - Sheet1.csv

| Field | Status |
|-------|--------|
| **Location** | `V3/` (or subfolder — confirm exact path) |
| **Provenance** | ⚠️ PENDING CONFIRMATION |
| **Data type** | ⚠️ PENDING CONFIRMATION — real merchant data or synthetic/example? |
| **Usage scope** | ⚠️ PENDING CONFIRMATION |
| **PII present** | ⚠️ PENDING CONFIRMATION |
| **License** | UNKNOWN |

**Action required**: Confirm the following before any external sharing (funding
demo, partner review, open-source):
1. Is this real merchant transaction data from a Shopline/Shopify brand?
2. If yes: what is the data sharing agreement? Is this data covered by an NDA?
   Can it be shown to investors?
3. If it is synthetic/example data: document the generation method and confirm
   no real PII is present.
4. Is there a LICENSE file or data use agreement that should be referenced here?

---

### BrightSkin Fixture (`fixtures/brightskin/scenario.py`)

| Field | Status |
|-------|--------|
| **Provenance** | Synthetic — hand-crafted fixture for architecture validation |
| **Data type** | Deterministic hardcoded values; no real merchant data |
| **PII present** | No — merchant_id "brightskin_042" is fictional |
| **License** | Same as project license |

This fixture is safe for all external sharing (funding demo, investor review,
open-source). Values are representative of a real skincare brand scenario but
contain no actual merchant data.

---

### SQLite Test Database

| Field | Status |
|-------|--------|
| **Provenance** | Generated at test runtime by `db_client.py` in-memory |
| **Data type** | Synthetic — all test data is fabricated |
| **PII present** | No |
| **License** | Same as project license |

Safe for all external sharing.

---

## License Status

| Scope | Status |
|-------|--------|
| **V3 source code** | UNKNOWN — no LICENSE file present |
| **BrightSkin fixture** | Follows project license (once established) |
| **Shopify Data - Sheet1.csv** | UNKNOWN — see action items above |

**Recommendation**: Before any external sharing, establish a LICENSE file at the
V3 root. For an internal prototype under active development with external investors,
a private/proprietary license or a restrictive open-source license (e.g. BUSL-1.1)
is typical. Consult legal before making the repository public.

---

## Audit Trail

| Date | Event | Author |
|------|-------|--------|
| 2026-04-09 | Document created; Shopify Data provenance marked PENDING | Governance session |

---

*This document must be updated whenever a new data asset is added to the project,
or when the status of an existing asset changes (e.g. NDA signed, data replaced
with synthetic version, license file added).*
