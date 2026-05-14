# Deterministic Canonicalization Contract v1

**Status**: Proposed
**Date**: 2026-04-28
**Owns**: ADR-0014 Invariant 2 ("Deterministic section canonicalization")
**Versioning**: This contract is versioned independently of ADR-0014.
Any change is **backward-incompatible by default** and requires a new
version (`v2`, `v3`, ...). The Deterministic Section Gate stamps the
contract version into every emitted hash.

---

## Purpose

`DecisionCardV2` partitions fields into `DETERMINISTIC` and
`LLM_RENDERABLE` sections. DETERMINISTIC sections MUST be **byte-identical**
across re-renders given identical inputs. This document defines the
bit-level rules that turn "identical inputs" into a single byte sequence.

Without a single canonicalization spec, three engineers will produce
three different byte sequences for the same logical content, and the
Deterministic Section Gate will reject candidates non-deterministically.

---

## Scope

This contract applies to:

- `DecisionCardV2.observed`
- `DecisionCardV2.missing`
- `DecisionCardV2.first_fix` (when present; absent under abstain)
- Any future field marked with the `DETERMINISTIC` section tag

This contract does **NOT** apply to:

- `DecisionCardV2.suspected` (LLM_RENDERABLE — natural-language hypothesis)
- `DecisionCardV2.why` (LLM_RENDERABLE — natural-language evidence chain)
- Any field marked `LLM_RENDERABLE`

The partition is enforced by an architecture invariant test that walks
the model and asserts every field carries exactly one tag.

---

## Pipeline

The canonicalization pipeline is fixed at five stages, applied in order:

```
Pydantic model
   │
   ▼  (1) Field-level normalization (per-type rules below)
Normalized model
   │
   ▼  (2) Serialize to dict via .model_dump(mode="json")
Dict
   │
   ▼  (3) Recursively walk dict and apply structural rules
Canonical dict
   │
   ▼  (4) JSON-encode with locked encoder settings
Canonical bytes
   │
   ▼  (5) SHA-256
Canonical hash
```

A canonicalizer implementation that skips, reorders, or fuses stages
violates this contract. There is exactly **one** canonicalizer module
in the codebase: `src/decision_engine/canonical/serializer_v1.py` (to be
written). Architecture invariant test
`tests/architecture/test_single_canonicalizer.py` greps for any other
implementation of `json.dumps(... sort_keys=...)` over DETERMINISTIC
section data and fails CI.

---

## Stage 1 — Field-level normalization

### Strings

- Encoding: **UTF-8**, no BOM
- Normalization form: **NFC** (Unicode canonical composition) — applied
  to all user-visible strings before serialization
- No leading/trailing whitespace stripping (whitespace inside strings is
  significant; do NOT auto-trim — operator-entered annotations may rely
  on spacing)
- Empty string `""` and `None` are **distinct** values (see Null handling)

### Numbers — integers
- Plain `int`, no leading zeros, no thousands separators
- No coercion through float

### Numbers — money / margin / discount fractions
- Type: **`decimal.Decimal`**, never float
- Quantization: 4 decimal places (`Decimal('0.0001')`) before serialization
- Rounding: `ROUND_HALF_EVEN` (banker's rounding)
- Serialized form: bare decimal literal, no scientific notation
  (`"1.2300"` not `"1.23e0"`)

**Why Decimal for money**: Float introduces platform-dependent rounding
errors (ARM vs x86 produce different last-digit values for equivalent
arithmetic). Decimal eliminates this class of canonicalization drift.

### Numbers — non-money floats
- Quantization: **6 decimal places** (`round(value, 6)`)
- Special values **rejected**: `NaN`, `+Infinity`, `-Infinity` produce a
  `GateRejection(clause_id="DSG-NUM-001-special-floats")`. They are not
  silently converted to null.
- Negative zero: serialized as `0.0`, not `-0.0`

### Booleans
- JSON `true` / `false`. Not `1` / `0`. Not `"true"` / `"false"`.

### Datetimes
- Type: `datetime` with `tzinfo` set
- Required: timezone-aware (naive datetimes are
  `GateRejection(clause_id="DSG-DT-001-naive")`)
- Format: **ISO 8601 with explicit `Z` suffix for UTC**, microseconds
  always emitted to 6 digits (e.g., `"2026-04-28T14:23:05.123456Z"`)
- Timezones other than UTC are converted to UTC at the canonicalization
  boundary, never serialized in a non-UTC offset
- `+00:00` and `Z` are *literally different bytes*; this contract picks
  `Z` to match Python `datetime.isoformat()` semantics with
  `timezone.utc`. Do NOT use `+00:00`.

### Dates (no time component)
- Format: ISO 8601 `YYYY-MM-DD` (e.g., `"2026-04-28"`)
- No timezone (a date is a date, not midnight)

### UUIDs
- Format: lowercase canonical 36-char string with dashes
  (e.g., `"3f2504e0-4f89-41d3-9a0c-0305e82c3301"`)
- No braces, no uppercase, no compact form

### Enums / Literals
- Serialized as the literal string value (e.g., `"executed"` not
  `"ExecutedStatus.EXECUTED"`)

---

## Stage 2 — Pydantic serialization

- Use `model.model_dump(mode="json", exclude_none=False)`
- `exclude_none=False` is **deliberate**: null vs missing key is
  semantic (see Stage 3); we keep nulls in the dict and let Stage 3
  apply the chosen policy
- Pydantic's `model_dump` already routes through the field-level
  normalization in Stage 1 if the model is constructed from normalized
  values; the canonicalizer asserts this by re-checking each leaf

---

## Stage 3 — Structural rules (recursive dict walk)

### Object (dict) keys
- Keys are **sorted lexicographically** by code-point (Python default
  for `str` comparison, no locale)
- All keys MUST be strings; non-string keys are
  `GateRejection(clause_id="DSG-OBJ-001-non-string-key")`

### Null values
**Policy**: drop null values from the canonical form. Empty string,
empty list, and empty dict are **kept** (they are not null).

```
{"a": null, "b": ""}    → canonical: {"b": ""}
{"a": [], "b": {}}      → canonical: {"a": [], "b": {}}
```

**Why drop nulls**: A field that is `None` is semantically equivalent
to a missing field for the purpose of "what does this card claim?" If a
field's nullness is load-bearing (e.g., `abstain_reason: str | None`
where `None` means "not abstaining"), the *containing* logic must
distinguish `abstain=False` vs `abstain_reason is None`. The reason
field's null is redundant once `abstain` is set.

### Array semantics — list vs set
Each array field carries an explicit semantic tag in the Pydantic model
via `Field(json_schema_extra={"array_semantics": "list" | "set"})`.

- `array_semantics="list"`: order is preserved as-is (order is meaningful)
- `array_semantics="set"`: array is sorted lexicographically by
  serialized canonical form of each element before serialization

A field without an `array_semantics` tag is
`GateRejection(clause_id="DSG-ARR-001-untagged")`. There is no default.

**Why explicit**: The single most common canonicalization bug in V0/V2
was "the same set serialized in different orders by different code
paths." Forcing the tag makes the choice visible at model-definition
time.

### Nested objects
Stage 3 rules apply recursively to all nested dicts and arrays.

---

## Stage 4 — JSON encoding

Locked `json.dumps` settings:

```python
json.dumps(
    canonical_dict,
    sort_keys=True,           # belt-and-suspenders; Stage 3 already sorted
    ensure_ascii=False,       # UTF-8 output, do not escape non-ASCII
    separators=(",", ":"),    # no spaces; "compact form"
    allow_nan=False,          # raises on NaN/Inf (caught at Stage 1; this is final guard)
    indent=None,
)
```

**No newlines**, **no indentation**, **no trailing whitespace**, **no BOM**.

The output is bytes via `.encode("utf-8")`. The encoded bytes are the
canonical form.

---

## Stage 5 — Hash

```python
hex_digest = hashlib.sha256(canonical_bytes).hexdigest()
canonical_hash = f"v1:{hex_digest}"
```

**Field name** is fixed: every emitted card carries a `canonical_hash`
field (no version suffix in the field name).

**Value format** is fixed: `f"v{N}:{hex_digest}"` where `N` is this
contract's version. Phase A emits `v1:...`. A future v2 contract emits
`v2:...` under the same field name; consumers parse the prefix to route
to the matching verifier.

This split — versionless field name, version-prefixed value — means a
v2 upgrade does not break the card schema, only the value semantics.
The Deterministic Section Gate refuses any `canonical_hash` whose
prefix does not match its compiled-in contract version.

The Deterministic Section Gate compares:
- `expected_hash` = canonicalize(input data)
- `actual_hash` = canonicalize(rendered card's DETERMINISTIC sections)

Mismatch → `GateRejection(clause_id="DSG-001-section-hash-mismatch")`
with target_section identifying which DETERMINISTIC section produced
the diverging bytes.

---

## Reference Implementation Sketch

```python
# src/decision_engine/canonical/serializer_v1.py

from __future__ import annotations
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any
from uuid import UUID

CONTRACT_VERSION = "v1"


def _normalize_leaf(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):  # before int — bool is subclass of int
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        q = value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
        return f"{q:f}"  # bare decimal literal, no scientific
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("DSG-NUM-001-special-floats")
        rounded = round(value, 6)
        return 0.0 if rounded == 0.0 else rounded  # collapse -0.0
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("DSG-DT-001-naive")
        utc = value.astimezone(timezone.utc)
        # Force microseconds to 6 digits, force Z suffix
        return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond:06d}Z"
    if isinstance(value, UUID):
        return str(value).lower()
    raise ValueError(f"DSG-LEAF-001-unknown-type: {type(value).__name__}")


def _walk(node: Any, schema_hint: dict | None = None) -> Any:
    if isinstance(node, dict):
        out = {}
        for k in sorted(node.keys()):
            if not isinstance(k, str):
                raise ValueError("DSG-OBJ-001-non-string-key")
            v = node[k]
            if v is None:
                continue  # drop nulls
            walked = _walk(v, schema_hint=(schema_hint or {}).get(k))
            out[k] = walked
        return out
    if isinstance(node, list):
        if schema_hint is None or "array_semantics" not in schema_hint:
            raise ValueError("DSG-ARR-001-untagged")
        elements = [_walk(e) for e in node]
        if schema_hint["array_semantics"] == "set":
            elements = sorted(elements, key=lambda e: json.dumps(e, sort_keys=True))
        return elements
    return _normalize_leaf(node)


def canonicalize(model: Any, *, schema: dict) -> tuple[bytes, str]:
    raw = model.model_dump(mode="json", exclude_none=False)
    canonical = _walk(raw, schema_hint=schema)
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
        indent=None,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return encoded, f"{CONTRACT_VERSION}:{digest}"
```

This sketch is **non-normative**; the normative content is the rules in
Stages 1–5. Any conforming implementation is acceptable.

---

## Testing Requirements

The canonicalizer ships with a frozen test corpus:
`tests/canonical/test_canonicalization_v1_corpus.py` containing at least:

1. **Round-trip stability**: same input → same hash across 1000 invocations
2. **Cross-platform stability**: same input → same hash on macOS / Linux / CI runners (CI matrix asserts this)
3. **Decimal vs float divergence**: a corpus pair where `Decimal("0.1") + Decimal("0.2") != float(0.1) + float(0.2)`; both must canonicalize, and the test asserts the contract chose Decimal
4. **Datetime canonicalization**: `+00:00` input and `Z` input produce the same hash (after normalization) — but ensure the canonical bytes contain `Z`
5. **NFC normalization**: `"é"` (U+00E9) and `"é"` (U+0065 + U+0301) produce the same hash
6. **Null vs empty**: `{"a": None}`, `{}`, `{"a": ""}`, `{"a": []}` all produce **distinct** hashes (drop-null is for `None` only)
7. **Set semantics**: `[3, 1, 2]` with `array_semantics="set"` produces the same hash as `[1, 2, 3]`; with `array_semantics="list"`, they produce different hashes
8. **Special-float rejection**: `float("nan")` raises `ValueError("DSG-NUM-001-special-floats")`
9. **Naive datetime rejection**: `datetime.utcnow()` (naive) raises `ValueError("DSG-DT-001-naive")`
10. **Untagged array rejection**: an array field without `array_semantics` raises `ValueError("DSG-ARR-001-untagged")`

Any new canonicalization rule → new corpus entry. Corpus is append-only.

---

## Versioning Discipline

- This contract is **v1**. Every emitted hash carries the `v1:` prefix.
- A v2 is needed if any rule changes (new type, different
  precision, different normalization). v2 is **not backward-compatible**;
  hashes from v1 and v2 are not comparable.
- A v2 contract MUST be introduced via a new ADR (or amendment to
  ADR-0014) explaining what rule changed and why.
- Both contracts coexist in code only during a migration window
  (e.g., re-canonicalizing historical cards). Outside that window,
  exactly one version is active.

---

## Failure Mode Catalog

All `clause_id` values used in `GateRejection.clause_id` originating
from this contract:

| clause_id | Stage | Trigger |
|-----------|-------|---------|
| `DSG-001-section-hash-mismatch` | post-pipeline | Re-rendered DETERMINISTIC section produces different hash than input |
| `DSG-NUM-001-special-floats` | Stage 1 | NaN, ±Infinity in a float field |
| `DSG-DT-001-naive` | Stage 1 | Naive datetime (no tzinfo) |
| `DSG-LEAF-001-unknown-type` | Stage 1 | Field has a type not covered by Stage 1 rules |
| `DSG-OBJ-001-non-string-key` | Stage 3 | Dict key is not a string |
| `DSG-ARR-001-untagged` | Stage 3 | Array field missing `array_semantics` tag |

Adding a new clause_id requires a corpus test entry (Testing
Requirements §). No silent additions.

---

## References

- ADR-0014 (V3.1 Phase A Scope), Invariant 2 — locks the principle this
  doc fills in
- ADR-0016 (V3.1 Truth Philosophy), Invariant 3 — `GateRejection`
  schema this doc emits
- `src/decision_engine/canonical/serializer_v1.py` (pending) — the
  single canonicalizer implementation
- `tests/canonical/test_canonicalization_v1_corpus.py` (pending) —
  frozen test corpus
- `tests/architecture/test_single_canonicalizer.py` (pending) —
  asserts no second canonicalizer exists in the codebase
