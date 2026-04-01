# ── Layer 3 · Value Intelligence — Feedback Collector ─────────────────────
# Merchant response loop: executed? met expectations? why not?
# Active from Phase 1 — feeds Learning Loop quality in Layer 5.
#
# Called when merchant responds via dashboard.
# Updates wsm_transition_v3 with feedback data via db_client.
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
from collections import Counter

from .. import db_client

log = logging.getLogger(__name__)


class FeedbackCollector:
    """Collects merchant feedback on decision quality and execution outcomes."""

    VALID_FEEDBACK_TYPES: list[str] = [
        "executed_met_expectations",
        "executed_below_expectations",
        "not_executed_price_too_low",
        "not_executed_wrong_timing",
        "not_executed_other_plan",
        "partial_executed",
    ]

    def record_feedback(
        self,
        transition_id: int,
        feedback_type: str,
        actual_params: dict | None = None,
        merchant_note: str | None = None,
    ) -> None:
        """Record merchant feedback for a WSM transition.

        Validates feedback_type, then updates wsm_transition_v3 via db_client.
        """
        if feedback_type not in self.VALID_FEEDBACK_TYPES:
            raise ValueError(
                f"Invalid feedback_type '{feedback_type}'. "
                f"Must be one of: {self.VALID_FEEDBACK_TYPES}"
            )

        was_executed = feedback_type.startswith("executed") or feedback_type == "partial_executed"

        execution_params = {
            "feedback_type": feedback_type,
            "merchant_note": merchant_note,
        }
        if actual_params:
            execution_params["actual_params"] = actual_params

        if was_executed:
            db_client.update_wsm_execution(transition_id, execution_params)

        log.info(
            "Feedback recorded for transition %s: %s",
            transition_id, feedback_type,
        )

    def get_feedback_summary(self, merchant_id: str, days: int = 30) -> dict:
        """Aggregate feedback metrics for a merchant.

        Returns:
        {
          "execution_rate": float,          # % of recommendations executed
          "met_expectations_rate": float,   # % that met expectations
          "top_rejection_reason": str,      # most common not_executed reason
          "total_cards": int
        }
        """
        from datetime import datetime, timedelta, timezone

        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        end_date = datetime.now(timezone.utc)

        transitions = db_client.fetch_wsm_for_billing(
            merchant_id, start_date, end_date,
        )

        total = len(transitions)
        if total == 0:
            return {
                "execution_rate": 0.0,
                "met_expectations_rate": 0.0,
                "top_rejection_reason": "no_data",
                "total_cards": 0,
            }

        executed = sum(1 for t in transitions if t.get("was_executed"))
        execution_rate = executed / total if total > 0 else 0.0

        # Count feedback types from execution_params
        rejection_counter: Counter[str] = Counter()
        met_expectations = 0
        for t in transitions:
            ep = t.get("execution_params") or {}
            if isinstance(ep, str):
                import json
                ep = json.loads(ep)
            ft = ep.get("feedback_type", "")
            if ft == "executed_met_expectations":
                met_expectations += 1
            elif ft.startswith("not_executed_"):
                rejection_counter[ft] += 1

        met_rate = met_expectations / total if total > 0 else 0.0
        top_reason = rejection_counter.most_common(1)[0][0] if rejection_counter else "none"

        return {
            "execution_rate": round(execution_rate, 4),
            "met_expectations_rate": round(met_rate, 4),
            "top_rejection_reason": top_reason,
            "total_cards": total,
        }
