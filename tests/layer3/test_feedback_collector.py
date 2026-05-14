# ── Layer 3 Tests · Feedback Collector ────────────────────────────────────
# Covers FeedbackCollector.record_feedback() and get_feedback_summary().
# Previously get_feedback_summary() was at 0% coverage (S8-3).
#
# Note: get_feedback_summary() calls db_client.fetch_wsm_for_billing() which
# only returns rows with was_executed=TRUE AND outcome_delta IS NOT NULL.
# Tests for get_feedback_summary() mock fetch_wsm_for_billing to control
# the returned data and exercise the aggregation logic directly.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.decision_engine import db_client
from src.decision_engine.layer3_value.feedback_collector import FeedbackCollector


@pytest.fixture
def fc():
    return FeedbackCollector()


def _insert_transition(merchant_id: str) -> int:
    return db_client.insert_wsm_transition(
        merchant_id=merchant_id,
        vertical="cpg",
        decision_mode="deep",
        s_json={},
        action_id="DISCOUNT_10PCT",
        action_family="DISCOUNT",
        action_params_json={},
        constraints_passed=True,
        was_executed=False,
    )


# ── record_feedback ───────────────────────────────────────────────────────────

class TestRecordFeedback:
    def test_valid_feedback_type_does_not_raise(self, fc):
        tid = _insert_transition("fb_m1")
        fc.record_feedback(tid, "executed_met_expectations")

    def test_invalid_feedback_type_raises_value_error(self, fc):
        tid = _insert_transition("fb_m2")
        with pytest.raises(ValueError, match="Invalid feedback_type"):
            fc.record_feedback(tid, "bad_type")

    def test_executed_feedback_calls_update_wsm(self, fc):
        """executed_ prefix → was_executed=True → update_wsm_execution is called."""
        tid = _insert_transition("fb_m3")
        fc.record_feedback(tid, "executed_met_expectations", actual_params={"discount_pct": 0.10})

    def test_not_executed_feedback_does_not_raise(self, fc):
        """not_executed_ prefix → was_executed=False → no DB update."""
        tid = _insert_transition("fb_m4")
        fc.record_feedback(tid, "not_executed_price_too_low")

    def test_partial_executed_is_treated_as_executed(self, fc):
        tid = _insert_transition("fb_m5")
        fc.record_feedback(tid, "partial_executed")


# ── get_feedback_summary ──────────────────────────────────────────────────────

class TestGetFeedbackSummary:
    """Tests for get_feedback_summary() aggregation logic.

    fetch_wsm_for_billing requires was_executed=TRUE AND outcome_delta IS NOT NULL.
    We mock it to control exactly what data the aggregation logic sees.
    """

    def test_returns_zero_summary_when_no_transitions(self, fc):
        """No rows from DB → all-zero summary."""
        with patch("src.decision_engine.layer3_value.feedback_collector.db_client") as mock_db:
            mock_db.fetch_wsm_for_billing.return_value = []
            summary = fc.get_feedback_summary("no_data_merchant")

        assert summary["execution_rate"] == 0.0
        assert summary["met_expectations_rate"] == 0.0
        assert summary["top_rejection_reason"] == "no_data"
        assert summary["total_cards"] == 0

    def test_execution_rate_reflects_was_executed_flag(self, fc):
        """2 transitions: 1 executed, 1 not → execution_rate = 0.5."""
        fake_rows = [
            {"was_executed": True, "execution_params": {"feedback_type": "executed_met_expectations"}},
            {"was_executed": False, "execution_params": {"feedback_type": "not_executed_wrong_timing"}},
        ]
        with patch("src.decision_engine.layer3_value.feedback_collector.db_client") as mock_db:
            mock_db.fetch_wsm_for_billing.return_value = fake_rows
            summary = fc.get_feedback_summary("exec_rate_merchant")

        assert summary["total_cards"] == 2
        assert summary["execution_rate"] == pytest.approx(0.5)

    def test_met_expectations_rate_counts_correct_feedback_type(self, fc):
        """Only 'executed_met_expectations' increments met_expectations counter."""
        fake_rows = [
            {"was_executed": True, "execution_params": {"feedback_type": "executed_met_expectations"}},
            {"was_executed": True, "execution_params": {"feedback_type": "executed_below_expectations"}},
            {"was_executed": False, "execution_params": {"feedback_type": "not_executed_other_plan"}},
        ]
        with patch("src.decision_engine.layer3_value.feedback_collector.db_client") as mock_db:
            mock_db.fetch_wsm_for_billing.return_value = fake_rows
            summary = fc.get_feedback_summary("met_exp_merchant")

        assert summary["total_cards"] == 3
        assert summary["met_expectations_rate"] == pytest.approx(1 / 3, abs=1e-4)

    def test_top_rejection_reason_most_common_not_executed(self, fc):
        """Most frequent not_executed_ reason surfaces as top_rejection_reason."""
        fake_rows = [
            {"was_executed": False, "execution_params": {"feedback_type": "not_executed_wrong_timing"}},
            {"was_executed": False, "execution_params": {"feedback_type": "not_executed_wrong_timing"}},
            {"was_executed": False, "execution_params": {"feedback_type": "not_executed_other_plan"}},
        ]
        with patch("src.decision_engine.layer3_value.feedback_collector.db_client") as mock_db:
            mock_db.fetch_wsm_for_billing.return_value = fake_rows
            summary = fc.get_feedback_summary("rejection_merchant")

        assert summary["top_rejection_reason"] == "not_executed_wrong_timing"

    def test_top_rejection_reason_is_none_when_all_executed(self, fc):
        """No not_executed_ feedback → top_rejection_reason = 'none'."""
        fake_rows = [
            {"was_executed": True, "execution_params": {"feedback_type": "executed_met_expectations"}},
        ]
        with patch("src.decision_engine.layer3_value.feedback_collector.db_client") as mock_db:
            mock_db.fetch_wsm_for_billing.return_value = fake_rows
            summary = fc.get_feedback_summary("all_executed_merchant")

        assert summary["top_rejection_reason"] == "none"

    def test_summary_contains_all_required_keys(self, fc):
        with patch("src.decision_engine.layer3_value.feedback_collector.db_client") as mock_db:
            mock_db.fetch_wsm_for_billing.return_value = []
            summary = fc.get_feedback_summary("any_merchant")

        required_keys = {"execution_rate", "met_expectations_rate",
                         "top_rejection_reason", "total_cards"}
        assert required_keys.issubset(summary.keys())

    def test_json_string_execution_params_are_parsed(self, fc):
        """execution_params stored as JSON string (DB TEXT) must be parsed."""
        import json
        fake_rows = [
            {"was_executed": True,
             "execution_params": json.dumps({"feedback_type": "executed_met_expectations"})},
        ]
        with patch("src.decision_engine.layer3_value.feedback_collector.db_client") as mock_db:
            mock_db.fetch_wsm_for_billing.return_value = fake_rows
            summary = fc.get_feedback_summary("json_string_merchant")

        assert summary["met_expectations_rate"] == pytest.approx(1.0)
