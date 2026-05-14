# ── Layer 4 Tests · Rollout Manager ──────────────────────────────────────
# Tests for shadow mode, kill-switch, and check_readiness() go-live checklist.
# Covers the previously 47%-covered check_readiness() path (S8-2).
#
# Note: check_readiness() lazy-imports db_client inside the function body.
# We must patch 'src.decision_engine.db_client' (the package-level module),
# not 'src.decision_engine.layer4_serving.rollout.db_client' (which doesn't
# exist at module scope in rollout.py).
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.decision_engine.layer4_serving import rollout


class TestRolloutFlags:
    def test_is_shadow_mode_reflects_setting(self):
        with patch("src.decision_engine.layer4_serving.rollout.settings") as mock_s:
            mock_s.shadow_mode = True
            assert rollout.is_shadow_mode() is True
            mock_s.shadow_mode = False
            assert rollout.is_shadow_mode() is False

    def test_is_kill_switch_active_reflects_setting(self):
        with patch("src.decision_engine.layer4_serving.rollout.settings") as mock_s:
            mock_s.kill_switch = True
            assert rollout.is_kill_switch_active() is True
            mock_s.kill_switch = False
            assert rollout.is_kill_switch_active() is False

    def test_can_execute_write_false_in_shadow_mode(self):
        with patch("src.decision_engine.layer4_serving.rollout.settings") as mock_s:
            mock_s.shadow_mode = True
            mock_s.kill_switch = False
            assert rollout.can_execute_write() is False

    def test_can_execute_write_false_with_kill_switch(self):
        with patch("src.decision_engine.layer4_serving.rollout.settings") as mock_s:
            mock_s.shadow_mode = False
            mock_s.kill_switch = True
            assert rollout.can_execute_write() is False

    def test_can_execute_write_true_when_both_off(self):
        with patch("src.decision_engine.layer4_serving.rollout.settings") as mock_s:
            mock_s.shadow_mode = False
            mock_s.kill_switch = False
            assert rollout.can_execute_write() is True


class TestCheckReadiness:
    """Tests for check_readiness() — previously 47% covered.

    db_client is lazy-imported inside check_readiness() via 'from .. import db_client'.
    We patch 'src.decision_engine.db_client' (the package module) so the lazy
    import resolves to our mock.
    """

    def _make_settings(self):
        s = MagicMock()
        s.min_data_freshness_hours = 24
        s.max_constraint_violation_pct = 0.15
        s.kill_switch = False
        return s

    def test_passes_when_data_is_fresh(self):
        fresh_ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        mock_db = MagicMock()
        mock_db.fetch_latest_wsm_timestamp.return_value = fresh_ts
        mock_db.fetch_constraint_violation_rate.return_value = {"violation_rate": 0.05}

        with patch("src.decision_engine.db_client", mock_db), \
             patch("src.decision_engine.layer4_serving.rollout.settings", self._make_settings()):
            checks = rollout.check_readiness("merchant_x")

        by_name = {c.name: c for c in checks}
        assert by_name["data_freshness"].passed is True
        assert by_name["constraint_violations"].passed is True
        assert by_name["kill_switch"].passed is True

    def test_fails_data_freshness_when_stale(self):
        stale_ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
        mock_db = MagicMock()
        mock_db.fetch_latest_wsm_timestamp.return_value = stale_ts
        mock_db.fetch_constraint_violation_rate.return_value = None

        with patch("src.decision_engine.db_client", mock_db), \
             patch("src.decision_engine.layer4_serving.rollout.settings", self._make_settings()):
            checks = rollout.check_readiness("merchant_stale")

        by_name = {c.name: c for c in checks}
        assert by_name["data_freshness"].passed is False
        assert "h ago" in by_name["data_freshness"].detail

    def test_fails_when_no_wsm_data(self):
        mock_db = MagicMock()
        mock_db.fetch_latest_wsm_timestamp.return_value = None
        mock_db.fetch_constraint_violation_rate.return_value = None

        with patch("src.decision_engine.db_client", mock_db), \
             patch("src.decision_engine.layer4_serving.rollout.settings", self._make_settings()):
            checks = rollout.check_readiness("new_merchant")

        by_name = {c.name: c for c in checks}
        assert by_name["data_freshness"].passed is False
        assert "No WSM data" in by_name["data_freshness"].detail

    def test_fails_constraint_violations_above_threshold(self):
        fresh_ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        mock_db = MagicMock()
        mock_db.fetch_latest_wsm_timestamp.return_value = fresh_ts
        mock_db.fetch_constraint_violation_rate.return_value = {"violation_rate": 0.30}

        with patch("src.decision_engine.db_client", mock_db), \
             patch("src.decision_engine.layer4_serving.rollout.settings", self._make_settings()):
            checks = rollout.check_readiness("merchant_violating")

        by_name = {c.name: c for c in checks}
        assert by_name["constraint_violations"].passed is False

    def test_kill_switch_check_fails_when_active(self):
        fresh_ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        mock_db = MagicMock()
        mock_db.fetch_latest_wsm_timestamp.return_value = fresh_ts
        mock_db.fetch_constraint_violation_rate.return_value = {"violation_rate": 0.05}
        mock_s = self._make_settings()
        mock_s.kill_switch = True

        with patch("src.decision_engine.db_client", mock_db), \
             patch("src.decision_engine.layer4_serving.rollout.settings", mock_s):
            checks = rollout.check_readiness("merchant_ks")

        by_name = {c.name: c for c in checks}
        assert by_name["kill_switch"].passed is False
        assert "active" in by_name["kill_switch"].detail.lower()

    def test_readiness_check_to_dict(self):
        check = rollout.ReadinessCheck("test_check", True, "All good")
        d = check.to_dict()
        assert d == {"name": "test_check", "passed": True, "detail": "All good"}
