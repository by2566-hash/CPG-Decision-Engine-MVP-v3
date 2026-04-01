# ── Layer 3 · Action Safety — CPG Hard Constraints ────────────────────────
# Non-negotiable constraints. CANNOT be overridden by LLM or ML outputs.
# CANNOT be relaxed by any Policy Pack configuration.
#
# 6 CPG Hard Constraints:
#   1. Margin floor          — post-discount margin >= 0.15 always
#   2. Discount = last resort — REMINDER must precede DISCOUNT
#   3. Incrementality required — no discount without uplift attribution
#   4. Cold prospect gate    — no discount to first-time visitors
#   5. Attribution windows   — Retention 7d / Acquisition 30d / Promotion 14d / Conversion 0d
#   6. Inventory gate        — no discount when inventory_days_p10 < 5
#
# compute_risk_score() feeds the β3·Risk(Constraints) term in:
#   Score = β1·U_base + β2·U_ucb − β3·Risk(Constraints)
# This cross-layer dependency is intentional and documented in CLAUDE.md.
#
# Phase 1 behaviour for missing signals:
#   All constraints: missing required signal → PASS with logged warning.
#   Reason: Phase 1 has incomplete signals; missing data must not block all recommendations.
#   Log format: "WARNING: constraint {name} skipped — signal {signal_name} not available"
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# Post-discount margin floor — CPG absolute minimum (CLAUDE.md)
_MARGIN_FLOOR = 0.15

# Incrementality threshold — minimum promo uplift required for discount
_INCREMENTALITY_THRESHOLD = 0.30

# Inventory minimum — discount blocked below this many days of supply (p10)
_INVENTORY_DAYS_MIN = 5

# Attribution windows in days per module (CLAUDE.md Hard Constraints table)
_ATTRIBUTION_WINDOWS: dict[str, int] = {
    "retention": 7,
    "acquisition": 30,
    "promotion": 14,
    "conversion": 0,  # instant
}


def _is_discount(candidate: dict) -> bool:
    """Return True if the candidate is a discount-type action."""
    action_id = candidate.get("action_id", "")
    action_family = candidate.get("action_family", "")
    return (
        "DISCOUNT" in action_id.upper()
        or action_family.upper() == "DISCOUNT"
        or action_id in {
            "FLASH_SALE", "BUNDLE_DISCOUNT", "HIGH_DISCOUNT", "DISCOUNT_LAST_RESORT",
        }
    )


def _infer_discount_pct(candidate: dict) -> float:
    """Infer discount fraction from candidate.  DISCOUNT_10PCT → 0.10."""
    explicit = candidate.get("discount_pct")
    if explicit is not None:
        return float(explicit)
    action_id = candidate.get("action_id", "")
    try:
        # e.g. "DISCOUNT_10PCT" → "10" → 0.10
        pct_str = action_id.upper().split("DISCOUNT_")[-1].replace("PCT", "")
        return float(pct_str) / 100.0
    except (ValueError, IndexError):
        return 0.0


class ConstraintEngine:
    """Enforces CPG hard constraints — non-negotiable safety rules.

    All 6 constraints are checked via check_all().
    compute_risk_score() returns a continuous penalty for the scoring formula.
    Hard violations (check_all returning False) block the action in scoring.
    """

    def check_all(
        self,
        candidate: dict,
        signals: dict,
        policy: dict,
    ) -> tuple[bool, list[str]]:
        """Run all 6 CPG hard constraints in order.

        Returns (all_passed: bool, violations: list[str]).
        Violation format: "constraint_name:detail".

        For all constraints: if required signal is missing, PASS with logged warning.
        Phase 1: incomplete signals must not block all recommendations.

        Constraint 5 (attribution_window) is metadata-only — always passes but
        sets candidate["attribution_window_days"] as a side effect.
        Constraint 6 (rollback TTL) is enforced by RollbackRegistry, not here.
        """
        violations: list[str] = []

        # 1. Margin floor
        v = self._check_margin_floor(candidate, signals)
        if v:
            violations.append(v)

        # 2. Discount last resort
        v = self._check_discount_last_resort(candidate, signals)
        if v:
            violations.append(v)

        # 3. Incrementality required
        v = self._check_incrementality(candidate, signals)
        if v:
            violations.append(v)

        # 4. Cold prospect gate
        v = self._check_cold_prospect_gate(candidate, signals)
        if v:
            violations.append(v)

        # 5. Attribution window (metadata — always passes, sets field on candidate)
        self._set_attribution_window(candidate)

        # 6. Inventory gate
        v = self._check_inventory_gate(candidate, signals)
        if v:
            violations.append(v)

        return (len(violations) == 0, violations)

    # ── Individual constraint checks ─────────────────────────────────────

    def _check_margin_floor(self, candidate: dict, signals: dict) -> str | None:
        """Constraint 1: post-discount margin must stay >= 0.15.

        post_discount_margin = signals["margin_pct"] - inferred discount_pct.
        Returns violation string or None.
        """
        if not _is_discount(candidate):
            return None

        margin_pct = signals.get("margin_pct")
        if margin_pct is None:
            log.warning(
                "WARNING: constraint margin_floor skipped — signal margin_pct not available"
            )
            return None

        margin_pct = float(margin_pct)
        discount_pct = _infer_discount_pct(candidate)
        post_margin = margin_pct - discount_pct

        if post_margin < _MARGIN_FLOOR:
            log.warning(
                "[constraints] Margin floor violated: post_discount_margin=%.2f < %.2f",
                post_margin, _MARGIN_FLOOR,
            )
            return f"margin_floor:post_discount_margin_{post_margin:.2f}_below_0.15"

        return None

    def _check_discount_last_resort(self, candidate: dict, signals: dict) -> str | None:
        """Constraint 2: REMINDER must precede DISCOUNT within 7 days.

        Checks signals["last_action_type"] and signals["days_since_last_action"].
        Missing signal → PASS with warning (Phase 1 data gap).
        """
        if not _is_discount(candidate):
            return None

        last_action_type = signals.get("last_action_type")
        if last_action_type is None:
            log.warning(
                "WARNING: constraint discount_last_resort skipped"
                " — signal last_action_type not available"
            )
            return None

        if last_action_type.upper() == "REMINDER":
            days = signals.get("days_since_last_action")
            # If days is missing or within window, pass
            if days is None or float(days) < 7:
                return None

        log.warning(
            "[constraints] Discount last-resort violated: last_action_type=%s,"
            " days_since_last_action=%s",
            last_action_type,
            signals.get("days_since_last_action"),
        )
        return "discount_last_resort:no_prior_reminder"

    def _check_incrementality(self, candidate: dict, signals: dict) -> str | None:
        """Constraint 3: no discount without promo uplift attribution.

        promo_incrementality < 0.30 → fail.
        Missing signal → PASS with warning (Phase 1 data gap).
        """
        if not _is_discount(candidate):
            return None

        promo_inc = signals.get("promo_incrementality")
        if promo_inc is None:
            log.warning(
                "WARNING: constraint incrementality_required skipped"
                " — signal promo_incrementality not available"
            )
            return None

        promo_inc = float(promo_inc)
        if promo_inc < _INCREMENTALITY_THRESHOLD:
            log.warning(
                "[constraints] Incrementality violated: promo_incrementality=%.3f < %.2f",
                promo_inc, _INCREMENTALITY_THRESHOLD,
            )
            return (
                f"incrementality:promo_incrementality_{promo_inc:.3f}"
                f"_below_{_INCREMENTALITY_THRESHOLD}"
            )

        return None

    def _check_cold_prospect_gate(self, candidate: dict, signals: dict) -> str | None:
        """Constraint 4: no discount to first-time visitors (0 prior orders).

        Phase 1 — if customer_orders_count not available: pass (default 999).
        Fails when customer_orders_count == 0.
        """
        if not _is_discount(candidate):
            return None

        orders_count = signals.get("customer_orders_count", 999)
        if int(orders_count) == 0:
            log.warning(
                "[constraints] Cold prospect gate: customer_orders_count=0, discount blocked"
            )
            return "cold_prospect_gate:first_time_visitor_no_discount"

        return None

    def _set_attribution_window(self, candidate: dict) -> None:
        """Constraint 5: set attribution_window_days on candidate (metadata, never blocks)."""
        module = candidate.get("module", "retention")
        candidate["attribution_window_days"] = _ATTRIBUTION_WINDOWS.get(module, 7)

    def _check_inventory_gate(self, candidate: dict, signals: dict) -> str | None:
        """Constraint 6: no discount when inventory is critically low.

        inventory_days_p10 < 5 → fail.
        Missing signal → PASS with warning (Phase 1 data gap).
        """
        if not _is_discount(candidate):
            return None

        inv_days = signals.get("inventory_days_p10")
        if inv_days is None:
            log.warning(
                "WARNING: constraint inventory_gate skipped"
                " — signal inventory_days_p10 not available"
            )
            return None

        inv_days = float(inv_days)
        if inv_days < _INVENTORY_DAYS_MIN:
            log.warning(
                "[constraints] Inventory gate violated: inventory_days_p10=%.1f < %d",
                inv_days, _INVENTORY_DAYS_MIN,
            )
            return f"inventory_gate:inventory_days_p10_{inv_days:.1f}_below_5"

        return None

    # ── Public helpers ────────────────────────────────────────────────────

    def get_attribution_window(self, module: str) -> int:
        """Return attribution window in days for a module.

        Retention 7d / Acquisition 30d / Promotion 14d / Conversion 0d (instant).
        """
        return _ATTRIBUTION_WINDOWS.get(module, 7)

    def compute_risk_score(
        self,
        candidate: dict,
        signals: dict,
        policy: dict,
    ) -> float:
        """Compute Risk(Constraints) for the β3·Risk scoring term.

        Each hard constraint violation contributes 1.0 to the risk score.
        Returns 0.0 when all constraints pass (most common case in Phase 1).

        Used as the authoritative source for Risk(Constraints) in:
          Score = β1·U_base + β2·U_ucb − β3·Risk(Constraints)
        """
        _, violations = self.check_all(candidate, signals, policy)
        return float(len(violations))
