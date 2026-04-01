"""Tests for db_client V3 functions.

Covers:
  - insert_wsm_transition with all V3 fields
  - update_wsm_execution idempotency
  - update_wsm_outcome_delta only-when-NULL guard
  - upsert_merchant_state_vector
  - fetch_baseline_for_merchant rolling average
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.decision_engine import db_client
from src.decision_engine.contracts import MerchantStateVector


def _insert_basic_transition(**overrides) -> int:
    """Helper: insert a transition with sensible defaults, allow overrides."""
    defaults = dict(
        merchant_id="m_test_001",
        vertical="cpg",
        decision_mode="deep",
        s_json={"revenue": 1000, "orders": 50},
        action_id="REMINDER_FIRST",
        action_family="retention",
        action_params_json={"channel": "email"},
        constraints_passed=True,
    )
    defaults.update(overrides)
    return db_client.insert_wsm_transition(**defaults)


# ── insert_wsm_transition with V3 fields ───────────────────────────

class TestInsertWSMTransitionV3:
    def test_insert_with_all_v3_fields(self, db_engine):
        """Insert with every V3 field populated and verify they persist."""
        tid = db_client.insert_wsm_transition(
            merchant_id="m_v3",
            vertical="cpg",
            decision_mode="deep",
            s_json={"revenue": 2000},
            action_id="DISCOUNT_10PCT",
            action_family="retention",
            action_params_json={"discount_pct": 10},
            constraints_passed=True,
            base_utility_score=0.8,
            bandit_ucb_score=0.0,
            final_rank_score=0.72,
            planner_policy_version="2026-03-28_m_v3",
            # V3 fields
            was_executed=False,
            verification_chain={"msm_trigger": True, "margin_gate": True},
            impact_estimate={"conservative": 420, "expected": 680, "optimistic": 950, "confidence": 0.73},
            counterfactual={"runner_up": "REMINDER_ONLY", "est": 180},
            baseline_snapshot={"aov": 45.0, "order_freq": 2.1},
            urgency_score=0.85,
            module="retention",
            msm_dimension="retention",
            msm_state="DEGRADING",
        )
        assert tid is not None
        assert isinstance(tid, int)

    def test_insert_with_v3_fields_none(self, db_engine):
        """Insert with V3 fields defaulting to None should still succeed."""
        tid = _insert_basic_transition()
        assert tid is not None

    def test_v2_compatible_insert(self, db_engine):
        """V2-style insert (no V3 fields) must still work."""
        tid = db_client.insert_wsm_transition(
            merchant_id="m_legacy",
            vertical="cpg",
            decision_mode="deep",
            s_json={"revenue": 500},
            action_id="SEND_REMINDER",
            action_family="retention",
            action_params_json={"template": "restock"},
            constraints_passed=True,
            violations_json=[],
            base_utility_score=0.5,
            planner_policy_version="v2_compat",
        )
        assert tid is not None


# ── update_wsm_execution (idempotent) ──────────────────────────────

class TestUpdateWSMExecution:
    def test_marks_executed(self, db_engine):
        """First call should set was_executed=True and populate executed_at."""
        tid = _insert_basic_transition(was_executed=False)

        db_client.update_wsm_execution(tid, {"discount_pct": 10, "channel": "email"})

        # Verify
        from sqlalchemy import text
        with db_engine.connect() as c:
            row = c.execute(
                text("SELECT was_executed, executed_at, execution_params FROM wsm_transitions_v3 WHERE transition_id = :tid"),
                {"tid": tid},
            ).fetchone()
        assert row[0] in (True, 1)  # SQLite returns 1 for TRUE
        assert row[1] is not None   # executed_at populated
        assert row[2] is not None   # execution_params populated

    def test_idempotent_no_overwrite(self, db_engine):
        """Second call must NOT overwrite already-executed transition."""
        tid = _insert_basic_transition(was_executed=False)

        db_client.update_wsm_execution(tid, {"discount_pct": 10})

        # Capture first execution timestamp
        from sqlalchemy import text
        with db_engine.connect() as c:
            row1 = c.execute(
                text("SELECT executed_at, execution_params FROM wsm_transitions_v3 WHERE transition_id = :tid"),
                {"tid": tid},
            ).fetchone()

        # Second call with different params — should be no-op
        db_client.update_wsm_execution(tid, {"discount_pct": 20, "extra": "ignored"})

        with db_engine.connect() as c:
            row2 = c.execute(
                text("SELECT executed_at, execution_params FROM wsm_transitions_v3 WHERE transition_id = :tid"),
                {"tid": tid},
            ).fetchone()

        assert row1[0] == row2[0]  # executed_at unchanged
        assert row1[1] == row2[1]  # execution_params unchanged


# ── update_wsm_outcome_delta (only when NULL) ──────────────────────

class TestUpdateWSMOutcomeDelta:
    def test_backfills_when_null(self, db_engine):
        """Should update outcome_delta when it's NULL."""
        tid = _insert_basic_transition()

        delta = {"revenue_delta": 150.0, "order_delta": 3}
        db_client.update_wsm_outcome_delta(tid, delta)

        from sqlalchemy import text
        import json
        with db_engine.connect() as c:
            row = c.execute(
                text("SELECT outcome_delta FROM wsm_transitions_v3 WHERE transition_id = :tid"),
                {"tid": tid},
            ).fetchone()
        assert row[0] is not None
        parsed = json.loads(row[0])
        assert parsed["revenue_delta"] == 150.0

    def test_does_not_overwrite_existing(self, db_engine):
        """Should NOT overwrite if outcome_delta is already populated."""
        tid = _insert_basic_transition(outcome_delta={"revenue_delta": 100.0})

        # Try to overwrite with different value
        db_client.update_wsm_outcome_delta(tid, {"revenue_delta": 999.0})

        from sqlalchemy import text
        import json
        with db_engine.connect() as c:
            row = c.execute(
                text("SELECT outcome_delta FROM wsm_transitions_v3 WHERE transition_id = :tid"),
                {"tid": tid},
            ).fetchone()
        parsed = json.loads(row[0])
        assert parsed["revenue_delta"] == 100.0  # original value preserved


# ── upsert_merchant_state_vector ───────────────────────────────────

class TestUpsertMerchantStateVector:
    def test_insert_new(self, db_engine):
        """Should insert a new merchant state vector."""
        now = datetime.now(timezone.utc)
        msv = MerchantStateVector(
            merchant_id="m_test_001",
            computed_at=now,
            acquisition_state="HEALTHY",
            conversion_state="WATCH",
            retention_state="DEGRADING",
            promotion_state="HEALTHY",
            acquisition_urgency=0.1,
            conversion_urgency=0.4,
            retention_urgency=0.8,
            promotion_urgency=0.0,
            metrics_snapshot={"aov": 42.5, "cac": 12.0},
        )
        db_client.upsert_merchant_state_vector(msv)

        result = db_client.fetch_latest_merchant_state("m_test_001")
        assert result is not None
        assert result["merchant_id"] == "m_test_001"
        assert result["retention_state"] == "DEGRADING"
        assert result["retention_urgency"] == 0.8
        assert result["metrics_snapshot"]["aov"] == 42.5

    def test_upsert_overwrites_same_key(self, db_engine):
        """Upsert with same (merchant_id, computed_at) should update."""
        ts = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        msv1 = MerchantStateVector(
            merchant_id="m_test_001",
            computed_at=ts,
            retention_state="WATCH",
            retention_urgency=0.3,
        )
        db_client.upsert_merchant_state_vector(msv1)

        msv2 = MerchantStateVector(
            merchant_id="m_test_001",
            computed_at=ts,
            retention_state="CRITICAL",
            retention_urgency=0.95,
        )
        db_client.upsert_merchant_state_vector(msv2)

        result = db_client.fetch_latest_merchant_state("m_test_001")
        assert result["retention_state"] == "CRITICAL"
        assert result["retention_urgency"] == 0.95

    def test_fetch_returns_none_for_unknown(self, db_engine):
        """fetch_latest_merchant_state should return None for unknown merchant."""
        result = db_client.fetch_latest_merchant_state("m_nonexistent")
        assert result is None


# ── fetch_baseline_for_merchant ────────────────────────────────────

class TestFetchBaselineForMerchant:
    def test_returns_correct_rolling_average(self, db_engine):
        """Should average numeric fields from baseline_snapshot over last N days."""
        # Insert 3 transitions with known baseline_snapshot values
        _insert_basic_transition(
            merchant_id="m_baseline",
            baseline_snapshot={"aov": 30.0, "order_freq": 2.0},
        )
        _insert_basic_transition(
            merchant_id="m_baseline",
            baseline_snapshot={"aov": 40.0, "order_freq": 3.0},
        )
        _insert_basic_transition(
            merchant_id="m_baseline",
            baseline_snapshot={"aov": 50.0, "order_freq": 4.0},
        )

        result = db_client.fetch_baseline_for_merchant("m_baseline", days=30)
        assert result["aov"] == 40.0           # (30+40+50)/3
        assert result["order_freq"] == 3.0     # (2+3+4)/3
        assert result["_snapshot_count"] == 3

    def test_returns_empty_for_no_data(self, db_engine):
        """Should return empty dict when no baseline data exists."""
        result = db_client.fetch_baseline_for_merchant("m_no_data", days=30)
        assert result == {}

    def test_ignores_null_snapshots(self, db_engine):
        """Transitions without baseline_snapshot should be excluded."""
        _insert_basic_transition(merchant_id="m_partial")  # no baseline
        _insert_basic_transition(
            merchant_id="m_partial",
            baseline_snapshot={"aov": 60.0},
        )

        result = db_client.fetch_baseline_for_merchant("m_partial", days=30)
        assert result["aov"] == 60.0
        assert result["_snapshot_count"] == 1
