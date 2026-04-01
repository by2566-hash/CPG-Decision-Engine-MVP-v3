# ── Layer 1 · State Definitions ────────────────────────────────────────────
# Enums and helpers for the 4 MSM dimensions.
# Each dimension has 4 ordered states: HEALTHY < WATCH < DEGRADING < CRITICAL.
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from enum import Enum


class DimensionState(str, Enum):
    """Possible states for each MSM dimension, ordered by severity."""

    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    DEGRADING = "DEGRADING"
    CRITICAL = "CRITICAL"

    # ── Ordering: HEALTHY < WATCH < DEGRADING < CRITICAL ──────────

    _severity_map: dict  # declared for type checker; populated below

    def severity_score(self) -> int:
        """Return numeric severity: 0=HEALTHY, 1=WATCH, 2=DEGRADING, 3=CRITICAL."""
        return _SEVERITY[self]

    def is_at_risk(self) -> bool:
        """Return True if DEGRADING or CRITICAL."""
        return self.severity_score() >= 2

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, DimensionState):
            return NotImplemented
        return self.severity_score() < other.severity_score()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, DimensionState):
            return NotImplemented
        return self.severity_score() <= other.severity_score()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, DimensionState):
            return NotImplemented
        return self.severity_score() > other.severity_score()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, DimensionState):
            return NotImplemented
        return self.severity_score() >= other.severity_score()


# Severity lookup — outside the enum to avoid member pollution
_SEVERITY: dict[DimensionState, int] = {
    DimensionState.HEALTHY: 0,
    DimensionState.WATCH: 1,
    DimensionState.DEGRADING: 2,
    DimensionState.CRITICAL: 3,
}
