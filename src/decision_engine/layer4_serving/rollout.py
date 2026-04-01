# ── Layer 4 · Rollout — Shadow Mode / Kill-Switch ────────────────────────
# Controls feature rollout: shadow mode (log-only) and kill-switch.
# Shadow mode active from Day 1 — decisions logged but not executed.
#
# Module-level functions (matching V2 interface).
#
# Reference: V2/src/rollout.py (module-level functions — preserved)
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..config import settings

log = logging.getLogger(__name__)


@dataclass
class ReadinessCheck:
    """Single readiness check result."""
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def is_shadow_mode() -> bool:
    """Return True if shadow mode is active (log-only, no execution)."""
    return settings.shadow_mode


def is_kill_switch_active() -> bool:
    """Return True if kill switch is active (all decisions disabled)."""
    return settings.kill_switch


def can_execute_write() -> bool:
    """Return True if the system can execute write actions.

    False when shadow_mode is True or kill_switch is True.
    """
    return not settings.shadow_mode and not settings.kill_switch


def check_readiness(merchant_id: str) -> list[ReadinessCheck]:
    """Run go-live readiness checks for a merchant."""
    from .. import db_client

    checks: list[ReadinessCheck] = []

    # 1. Data freshness
    latest_ts = db_client.fetch_latest_wsm_timestamp(merchant_id)
    if latest_ts is None:
        checks.append(ReadinessCheck("data_freshness", False, "No WSM data found"))
    else:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        age_hours = (now - latest_ts).total_seconds() / 3600
        fresh = age_hours <= settings.min_data_freshness_hours
        checks.append(ReadinessCheck(
            "data_freshness", fresh,
            f"Last data: {age_hours:.1f}h ago (max {settings.min_data_freshness_hours}h)",
        ))

    # 2. Constraint violation rate
    cv = db_client.fetch_constraint_violation_rate(merchant_id)
    if cv is None:
        checks.append(ReadinessCheck("constraint_violations", True, "No decisions yet"))
    else:
        ok = cv["violation_rate"] <= settings.max_constraint_violation_pct
        checks.append(ReadinessCheck(
            "constraint_violations", ok,
            f"Violation rate: {cv['violation_rate']:.1%} (max {settings.max_constraint_violation_pct:.0%})",
        ))

    # 3. Kill switch
    checks.append(ReadinessCheck(
        "kill_switch", not settings.kill_switch,
        "Kill switch active" if settings.kill_switch else "Kill switch inactive",
    ))

    return checks
