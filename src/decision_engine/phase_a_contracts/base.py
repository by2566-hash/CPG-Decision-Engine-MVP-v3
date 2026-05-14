"""Shared building blocks for V3.1 Phase A typed contracts.

Per ADR-0014 Invariant 2 and `docs/contracts/deterministic_canonicalization_v1.md`:
- Phase A contracts inherit StrictFrozenModel (frozen + extra="forbid").
- Datetime fields use AwareDatetime (rejects naive -> DSG-DT-001-naive).
- List/set fields tag themselves via ARRAY_LIST or ARRAY_SET in
  Field(json_schema_extra=...). Untagged arrays raise DSG-ARR-001-untagged
  at canonicalization time.

UTC conversion of aware datetimes is the canonicalizer's job, not the
contract's; the contract enforces only that tzinfo is present.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _require_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("DSG-DT-001-naive: datetime must be timezone-aware")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(_require_aware_datetime)]


ARRAY_LIST: dict[str, Any] = {"array_semantics": "list"}
ARRAY_SET: dict[str, Any] = {"array_semantics": "set"}
