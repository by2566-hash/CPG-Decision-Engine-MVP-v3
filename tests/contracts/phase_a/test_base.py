"""Contract tests for phase_a_contracts.base.

Guards the shared building blocks used by every Phase A typed contract:
StrictFrozenModel, AwareDatetime, ARRAY_LIST/ARRAY_SET.

Every test docstring names the invariant it guards. Failure of any test
means a Phase A contract surface invariant has been broken; do not
"fix" by relaxing the test — write an ADR superseding ADR-0014 first.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import Field, ValidationError

from src.decision_engine.phase_a_contracts.base import (
    ARRAY_LIST,
    ARRAY_SET,
    AwareDatetime,
    StrictFrozenModel,
)


# ── StrictFrozenModel ────────────────────────────────────────────────────────


class _Sample(StrictFrozenModel):
    value: int


def test_strict_frozen_model_happy_path():
    """Basic construction works for valid input."""
    sample = _Sample(value=42)
    assert sample.value == 42


def test_strict_frozen_model_is_frozen():
    """Mutation after construction raises.

    Invariant: frozen=True. Required for canonicalization — post-construction
    mutation would invalidate the canonical hash.
    """
    sample = _Sample(value=1)
    with pytest.raises(ValidationError):
        sample.value = 2  # type: ignore[misc]


def test_strict_frozen_model_forbids_extra_fields():
    """Unknown fields raise at construction.

    Invariant: extra="forbid". Required for byte-identical canonicalization —
    extra fields would silently enter the canonical form and produce
    divergent hashes across producers.
    """
    with pytest.raises(ValidationError):
        _Sample(value=1, surprise="extra")  # type: ignore[call-arg]


# ── AwareDatetime ────────────────────────────────────────────────────────────


class _DTSample(StrictFrozenModel):
    when: AwareDatetime


def test_aware_datetime_accepts_aware():
    """An aware datetime passes validation."""
    aware = datetime(2026, 4, 28, 14, 23, 5, tzinfo=timezone.utc)
    sample = _DTSample(when=aware)
    assert sample.when == aware


def test_aware_datetime_rejects_naive_with_clause_id():
    """Naive datetime raises with DSG-DT-001-naive in the error message.

    Invariant: canonicalization spec §Stage 1. The clause_id MUST surface
    in the error so the GateRejection emitter can attach it without
    string-matching on a generic "missing tzinfo" message.
    """
    naive = datetime(2026, 4, 28, 14, 23, 5)
    with pytest.raises(ValidationError) as exc_info:
        _DTSample(when=naive)
    assert "DSG-DT-001-naive" in str(exc_info.value)


def test_aware_datetime_rejects_naive_iso_string():
    """Naive ISO 8601 string also rejected (string parsing path).

    Pydantic's default str->datetime path produces a naive datetime when
    the ISO string carries no offset; AfterValidator must catch this too.
    """
    with pytest.raises(ValidationError) as exc_info:
        _DTSample(when="2026-04-28T14:23:05")  # type: ignore[arg-type]
    assert "DSG-DT-001-naive" in str(exc_info.value)


# ── Array semantics tags ─────────────────────────────────────────────────────


def test_array_list_shape():
    """ARRAY_LIST carries array_semantics='list'.

    Used as Field(json_schema_extra=ARRAY_LIST) to opt list fields out of
    DSG-ARR-001-untagged. Shape is part of the contract.
    """
    assert ARRAY_LIST == {"array_semantics": "list"}


def test_array_set_shape():
    """ARRAY_SET carries array_semantics='set'."""
    assert ARRAY_SET == {"array_semantics": "set"}


def test_array_tag_surfaces_in_json_schema():
    """ARRAY_LIST applied via Field exposes array_semantics in model schema.

    The canonicalizer reads json_schema_extra to dispatch list-vs-set
    ordering. If Pydantic ever stops surfacing this metadata, every
    Phase A contract that ships a list field is silently miscanonicalized.
    """
    class _ListSample(StrictFrozenModel):
        items: list[int] = Field(default_factory=list, json_schema_extra=ARRAY_LIST)

    schema = _ListSample.model_json_schema()
    items_schema = schema["properties"]["items"]
    assert items_schema.get("array_semantics") == "list"
