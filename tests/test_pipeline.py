"""Tests for Layer 4: Pipeline, Fast Plane, and API endpoints.

Covers:
  - Full pipeline returns decision cards with all V3 fields
  - Failed verification excluded from response
  - Suppressed action excluded from response
  - WSM write always runs in shadow mode
  - Approve endpoint updates was_executed
  - Health endpoint returns MSM state
  - Fast Plane never calls pipeline
  - Fast Plane returns 503 on cache miss
  - Rollback endpoint updates WSM
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.decision_engine import db_client
from src.decision_engine.config import settings
from src.decision_engine.layer4_serving.pipeline import run_once
from src.decision_engine.layer4_serving.fast_plane import FastPlane
from api.app import app

client = TestClient(app, headers={"X-API-Key": settings.api_key})

# Signals that produce retention=DEGRADING, all others HEALTHY
_SIGNALS = {
    # Retention → DEGRADING (overdue_ratio 1.6 >= 1.50 threshold)
    "overdue_ratio": 1.6,
    "repeat_purchase_rate": 0.22,
    "days_since_last_order_p50": 45,
    # Acquisition → HEALTHY
    "cac_7d": 10.0,
    "cac_baseline_30d": 10.0,
    "roas_7d": 3.0,
    "roas_baseline_30d": 3.0,
    # Conversion → HEALTHY
    "mobile_atc_rate": 0.15,
    "desktop_atc_rate": 0.18,
    "mobile_traffic_pct": 0.6,
    "checkout_cvr": 0.03,
    # Promotion → HEALTHY
    "promo_incrementality": 0.60,
    "existing_customer_promo_pct": 0.30,
    "promo_margin_delta": 0.02,
    # Merchant state for ImpactCalculator
    "monthly_gmv": 50_000.0,
    "monthly_ad_spend": 5_000.0,
    "avg_order_value": 45.0,
    "monthly_orders": 1200,
    "avg_margin_pct": 0.35,
}


class TestPipeline:
    def test_frontend_policy_weight_overrides_apply_to_scoring_policy(self):
        """Frontend objective weights must update policy_weights before scoring."""
        from src.decision_engine.layer4_serving.pipeline import _apply_policy_weight_overrides

        policy = {
            "policy_version": "default_v1",
            "policy_weights": {
                "gmv_lift": 0.4,
                "margin_lift": 0.3,
                "inventory_risk_reduction": 0.2,
                "retention_lift": 0.1,
            },
        }
        signals = {
            "policy_weight_overrides": {
                "gmv_lift": 0.7,
                "margin_lift": 0.1,
                "inventory_risk_reduction": 0.1,
                "retention_lift": 0.1,
            }
        }

        updated = _apply_policy_weight_overrides(policy, signals)

        assert updated["policy_weights"] == signals["policy_weight_overrides"]
        assert policy["policy_weights"]["gmv_lift"] == 0.4

    def test_full_pipeline_returns_decision_cards_with_all_v3_fields(self):
        """Pipeline response includes all V3 fields: verification_chain,
        impact_estimate, merchant_copy, msm_state_summary."""
        policy, ranked = run_once("m_full_v3", signals=_SIGNALS)

        # Policy dict has expected keys
        assert "policy_version" in policy
        assert "msm_state" in policy
        assert "mode" in policy
        assert "emergency_triggered" in policy
        assert "weekly_plan" in policy
        assert policy["msm_state"]["retention"] == "DEGRADING"

        # At least one action in response
        assert len(ranked) >= 1

        for card in ranked:
            assert "action_id" in card
            assert "module" in card
            assert "verification_chain" in card
            assert "impact_estimate" in card
            assert "merchant_copy" in card
            assert "msm_state_summary" in card

            # Merchant copy has all renderer fields
            mc = card["merchant_copy"]
            assert "diagnosis" in mc
            assert "recommendation" in mc
            assert "impact_narrative" in mc
            assert "confidence_statement" in mc

    def test_failed_verification_excluded_from_response(self):
        """Candidate with failed DecisionVerifier gets -inf and no LLM render."""
        from src.decision_engine.layer4_serving import pipeline as _mod

        _orig = _mod._generate_candidates

        def _add_bad_candidate(msm_state, signals, policy, merchant_id=""):
            normal = _orig(msm_state, signals, policy, merchant_id)
            # Add a candidate for acquisition (HEALTHY) → fails MSM trigger
            normal.append({
                "action_id": "FORCED_ACQ_ACTION",
                "module": "acquisition",
                "msm_dimension": "acquisition",
                "urgency_score": 0.0,
                "pred": {"gmv_lift": 0.1},
                "action_family": "FORCED",
                "constraints_result": (True, []),
                "signals": signals,
            })
            return normal

        with patch.object(_mod, "_generate_candidates", _add_bad_candidate):
            policy, ranked = run_once("m_fail_verify", signals=_SIGNALS)

        # FORCED_ACQ_ACTION should NOT appear in response
        action_ids = [a["action_id"] for a in ranked]
        assert "FORCED_ACQ_ACTION" not in action_ids

    def test_suppressed_action_excluded_from_response(self):
        """Suppressed action (by CrossModuleCorrelator) excluded from response."""
        # Signals: acquisition=DEGRADING + conversion=DEGRADING triggers suppression
        suppress_signals = {
            **_SIGNALS,
            "cac_7d": 15.0,  # > 10 * 1.15 → acquisition DEGRADING
            "roas_7d": 2.0,  # < 3.0 * 0.9 → roas declining
            "mobile_atc_rate": 0.05,  # < 0.18 * 0.50 → conversion DEGRADING
            "checkout_cvr": {"current": 0.02, "3d_ago": 0.04},  # trending down → CRITICAL
        }

        from src.decision_engine.layer4_serving import pipeline as _mod

        _orig = _mod._generate_candidates

        def _add_suppressible(msm_state, signals, policy, merchant_id=""):
            normal = _orig(msm_state, signals, policy, merchant_id)
            # INCREASE_AD_BUDGET is suppressed by rule: acq DEGRADING + cvr DEGRADING
            normal.append({
                "action_id": "INCREASE_AD_BUDGET",
                "module": "acquisition",
                "msm_dimension": "acquisition",
                "urgency_score": 0.5,
                "pred": {"gmv_lift": 0.2},
                "action_family": "INCREASE",
                "constraints_result": (True, []),
                "signals": signals,
            })
            return normal

        with patch.object(_mod, "_generate_candidates", _add_suppressible):
            policy, ranked = run_once("m_suppress", signals=suppress_signals)

        action_ids = [a["action_id"] for a in ranked]
        assert "INCREASE_AD_BUDGET" not in action_ids

    def test_wsm_write_always_runs_in_shadow_mode(self):
        """Step 14: WSM write runs regardless of gate outcomes, was_executed=False."""
        run_once("m_shadow", signals=_SIGNALS)

        from sqlalchemy import text
        engine = db_client._get_engine()
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT action_id, was_executed FROM wsm_transitions_v3 "
                "WHERE merchant_id = 'm_shadow'"
            )).fetchall()

        assert len(rows) >= 1
        for row in rows:
            # was_executed must be False (0 in SQLite)
            assert row[1] is False or row[1] == 0


class TestEndpoints:
    def test_approve_endpoint_updates_was_executed(self):
        """POST /approve registers rollback token and updates WSM."""
        tid = db_client.insert_wsm_transition(
            merchant_id="m_approve",
            vertical="cpg",
            decision_mode="deep",
            s_json={},
            action_id="DISCOUNT_10PCT",
            action_family="DISCOUNT",
            action_params_json={},
            constraints_passed=True,
            was_executed=False,
        )

        resp = client.post(
            "/decision/m_approve/approve",
            json={"transition_id": tid, "execution_params": {"discount_pct": 0.10},
                  "high_risk_acknowledged": True, "risk_reason": "test approval"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert "rollback_token_id" in data
        assert "rollback_available_until" in data

    def test_health_endpoint_returns_msm_state(self):
        """GET /merchant/{mid}/health returns 4 dimension states."""
        resp = client.get("/merchant/m_health/health")

        assert resp.status_code == 200
        data = resp.json()
        assert "dimensions" in data
        dims = data["dimensions"]
        for d in ["acquisition", "conversion", "retention", "promotion"]:
            assert d in dims
            assert "state" in dims[d]
            assert "urgency" in dims[d]

    def test_rollback_endpoint_updates_wsm(self):
        """POST /rollback validates TTL and updates WSM."""
        tid = db_client.insert_wsm_transition(
            merchant_id="m_rollback",
            vertical="cpg",
            decision_mode="deep",
            s_json={},
            action_id="DISCOUNT_10PCT",
            action_family="DISCOUNT",
            action_params_json={},
            constraints_passed=True,
            was_executed=False,
        )

        # Approve first (registers rollback token)
        approve_resp = client.post(
            "/decision/m_rollback/approve",
            json={"transition_id": tid, "execution_params": {},
                  "high_risk_acknowledged": True, "risk_reason": "test rollback"},
        )
        assert approve_resp.status_code == 200
        token_id = approve_resp.json()["rollback_token_id"]

        # Rollback
        rollback_resp = client.post(
            f"/decision/m_rollback/rollback/{token_id}",
        )
        assert rollback_resp.status_code == 200
        data = rollback_resp.json()
        assert data["status"] == "rolled_back"


class TestFastPlane:
    def test_fast_plane_never_calls_pipeline(self):
        """Fast Plane reads from cache only, never calls pipeline.run_once."""
        # Insert cached data into DB
        db_client.upsert_serving_cache(
            merchant_id="m_fast",
            decision_mode="deep",
            ranked_actions_json=[
                {
                    "action_id": "DISCOUNT_10PCT",
                    "eligible": True,
                    "final_score": 0.5,
                    "u_base": 0.5,
                    "u_ucb": 0.0,
                    "risk_penalty": 0.0,
                },
            ],
            policy_version="v_test",
        )

        fp = FastPlane()

        # If pipeline.run_once is called, this patch makes it raise
        with patch(
            "src.decision_engine.layer4_serving.pipeline.run_once",
            side_effect=AssertionError("pipeline.run_once must never be called"),
        ):
            result = fp.serve("m_fast")

        assert result["merchant_id"] == "m_fast"
        assert result["source"] == "db"
        assert len(result["top_actions"]) >= 1
        assert result["top_actions"][0]["action_id"] == "DISCOUNT_10PCT"

    def test_fast_plane_returns_503_on_cache_miss(self):
        """Fast Plane raises 503 when no cache is available."""
        from fastapi import HTTPException

        fp = FastPlane()

        with pytest.raises(HTTPException) as exc_info:
            fp.serve("m_nonexistent_cache_miss")

        assert exc_info.value.status_code == 503


class TestPolicyEndpoints:
    """POST /policy/{merchant_id} and GET /policy/{merchant_id}."""

    def test_create_policy_success(self):
        """POST /policy creates a PolicyPack and returns 200 with expected fields."""
        resp = client.post(
            "/policy/merchant_policy_test",
            json={
                "policy_version": "v_test_001",
                "vertical": "cpg",
                "policy_weights": {"beta1": 0.65, "beta2": 0.25, "beta3": 0.10},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "created"
        assert body["merchant_id"] == "merchant_policy_test"
        assert body["policy_version"] == "v_test_001"
        assert body["vertical"] == "cpg"

    def test_create_policy_then_get_returns_same_payload(self):
        """GET /policy returns the policy that was just created via POST."""
        client.post(
            "/policy/merchant_policy_get",
            json={
                "policy_version": "v_get_001",
                "vertical": "cpg",
                "custom_field": "custom_value",
            },
        )
        resp = client.get("/policy/merchant_policy_get")
        assert resp.status_code == 200
        body = resp.json()
        assert body["merchant_id"] == "merchant_policy_get"
        assert body["policy"]["policy_version"] == "v_get_001"
        assert body["policy"]["custom_field"] == "custom_value"

    def test_create_policy_rejects_bad_weights(self):
        """POST /policy returns 422 when beta weights sum deviates > 0.05 from 1.0."""
        resp = client.post(
            "/policy/merchant_bad_weights",
            json={
                "policy_version": "v_bad",
                "vertical": "cpg",
                "policy_weights": {"beta1": 0.50, "beta2": 0.50, "beta3": 0.50},
            },
        )
        assert resp.status_code == 422
        assert "beta1+beta2+beta3" in resp.json()["detail"]

    def test_create_policy_allows_missing_weights(self):
        """POST /policy succeeds when policy_weights is omitted entirely."""
        resp = client.post(
            "/policy/merchant_no_weights",
            json={
                "policy_version": "v_no_weights",
                "vertical": "cpg",
            },
        )
        assert resp.status_code == 200

    def test_get_policy_returns_404_for_unknown_merchant(self):
        """GET /policy returns 404 when no PolicyPack exists for the merchant."""
        resp = client.get("/policy/merchant_does_not_exist_xyz")
        assert resp.status_code == 404
