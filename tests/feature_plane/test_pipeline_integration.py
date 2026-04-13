# ── Feature Plane Tests — Pipeline Integration ───────────────────────────────
# Verifies that _generate_candidates() attaches a DecisionFeatureVector
# to every candidate under key "feature_vector".
#
# Reference: V3/docs/PHASE_ROADMAP.md Phase 1 / Feature Plane implementation
# V3/docs/adr/0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md
# ─────────────────────────────────────────────────────────────────────────────
from datetime import datetime, timezone

from src.decision_engine.contracts import DecisionFeatureVector, MerchantStateVector


# ── Helpers ───────────────────────────────────────────────────────────────────

def _signals() -> dict:
    """Minimal signal set that produces at least one candidate."""
    return {
        "overdue_ratio": 1.6,
        "repeat_purchase_rate": 0.18,
        "days_since_last_order_p50": 45,
        "cac_7d": 10.0, "cac_baseline_30d": 10.0,
        "roas_7d": 3.5, "roas_baseline_30d": 3.0,
        "mobile_atc_rate": 0.15, "desktop_atc_rate": 0.18,
        "mobile_traffic_pct": 0.6, "checkout_cvr": 0.03,
        "promo_incrementality": 0.60, "existing_customer_promo_pct": 0.30,
        "promo_margin_delta": 0.02,
        "monthly_gmv": 50_000.0, "monthly_ad_spend": 5_000.0,
        "avg_order_value": 45.0, "monthly_orders": 1200, "avg_margin_pct": 0.35,
        "inventory_days": 12.0, "margin_pct": 0.35,
        "repeat_rate_7d": 0.18, "cvr_7d": 0.03, "cvr_30d": 0.027,
    }


def _degrading_msv() -> MerchantStateVector:
    """MerchantStateVector with retention DEGRADING to guarantee candidate generation."""
    return MerchantStateVector(
        merchant_id="test_fp_integration",
        computed_at=datetime.now(timezone.utc),
        retention_state="DEGRADING",
        retention_urgency=0.70,
        acquisition_state="HEALTHY",
        conversion_state="HEALTHY",
        promotion_state="HEALTHY",
    )


# ── Integration tests ─────────────────────────────────────────────────────────

def test_each_candidate_has_feature_vector_key():
    """Every candidate produced by _generate_candidates() must have 'feature_vector'.

    Enforces: ADR-0005 — DecisionFeatureVector is attached by the pipeline
    so downstream stages (scoring engine, bandit) can consume it without
    re-computing from raw signals.

    If this test fails: the FeatureBuilder call in _generate_candidates()
    was removed or the key name was changed.
    """
    from src.decision_engine.layer4_serving.pipeline import _generate_candidates

    signals = _signals()
    msv = _degrading_msv()
    policy = {
        "policy_version": "test_v1",
        "policy_weights": {"gmv_lift": 0.4, "margin_lift": 0.3,
                           "inventory_risk_reduction": 0.2, "retention_lift": 0.1},
        "risk_budget": {},
        "beta1": 0.6, "beta2": 0.1, "beta3": 0.3,
        "min_margin_floor": 0.15,
        "discount_threshold": 0.10,
        "budget_threshold_daily": 1000.0,
        "low_risk_auto_actions": False,
        "incrementality_required": False,
        "attribution_windows": {
            "retention": 7, "acquisition": 30, "promotion": 14, "conversion": 0
        },
    }

    candidates = _generate_candidates(msv, signals, policy)

    assert len(candidates) > 0, (
        "No candidates generated — check that retention_state=DEGRADING "
        "triggers candidate generation."
    )

    for c in candidates:
        assert "feature_vector" in c, (
            f"Candidate {c.get('action_id')!r} missing 'feature_vector' key. "
            "FeatureBuilder must be called in _generate_candidates()."
        )


def test_feature_vector_is_decision_feature_vector_instance():
    """'feature_vector' in each candidate must be a DecisionFeatureVector instance."""
    from src.decision_engine.layer4_serving.pipeline import _generate_candidates

    signals = _signals()
    msv = _degrading_msv()
    policy = {
        "policy_version": "test_v1",
        "policy_weights": {"gmv_lift": 0.4, "margin_lift": 0.3,
                           "inventory_risk_reduction": 0.2, "retention_lift": 0.1},
        "risk_budget": {},
        "beta1": 0.6, "beta2": 0.1, "beta3": 0.3,
        "min_margin_floor": 0.15,
        "discount_threshold": 0.10,
        "budget_threshold_daily": 1000.0,
        "low_risk_auto_actions": False,
        "incrementality_required": False,
        "attribution_windows": {
            "retention": 7, "acquisition": 30, "promotion": 14, "conversion": 0
        },
    }

    candidates = _generate_candidates(msv, signals, policy)

    for c in candidates:
        fv = c["feature_vector"]
        assert isinstance(fv, DecisionFeatureVector), (
            f"Expected DecisionFeatureVector, got {type(fv).__name__!r} "
            f"for candidate {c.get('action_id')!r}."
        )


def test_all_candidates_share_same_feature_vector():
    """All candidates in one pipeline run must share the same DecisionFeatureVector.

    FeatureBuilder is called once per _generate_candidates() invocation
    (signals are constant within a single run). All candidates reference
    the same immutable instance.
    """
    from src.decision_engine.layer4_serving.pipeline import _generate_candidates

    signals = _signals()
    msv = _degrading_msv()
    policy = {
        "policy_version": "test_v1",
        "policy_weights": {"gmv_lift": 0.4, "margin_lift": 0.3,
                           "inventory_risk_reduction": 0.2, "retention_lift": 0.1},
        "risk_budget": {},
        "beta1": 0.6, "beta2": 0.1, "beta3": 0.3,
        "min_margin_floor": 0.15,
        "discount_threshold": 0.10,
        "budget_threshold_daily": 1000.0,
        "low_risk_auto_actions": False,
        "incrementality_required": False,
        "attribution_windows": {
            "retention": 7, "acquisition": 30, "promotion": 14, "conversion": 0
        },
    }

    candidates = _generate_candidates(msv, signals, policy)

    if len(candidates) >= 2:
        fv0 = candidates[0]["feature_vector"]
        for c in candidates[1:]:
            assert c["feature_vector"] is fv0, (
                "All candidates should reference the same DecisionFeatureVector "
                "instance (computed once per run, not once per candidate)."
            )


def test_feature_vector_reflects_input_signals():
    """feature_vector fields must reflect the input signals values."""
    from src.decision_engine.layer4_serving.pipeline import _generate_candidates

    signals = _signals()
    msv = _degrading_msv()
    policy = {
        "policy_version": "test_v1",
        "policy_weights": {"gmv_lift": 0.4, "margin_lift": 0.3,
                           "inventory_risk_reduction": 0.2, "retention_lift": 0.1},
        "risk_budget": {},
        "beta1": 0.6, "beta2": 0.1, "beta3": 0.3,
        "min_margin_floor": 0.15,
        "discount_threshold": 0.10,
        "budget_threshold_daily": 1000.0,
        "low_risk_auto_actions": False,
        "incrementality_required": False,
        "attribution_windows": {
            "retention": 7, "acquisition": 30, "promotion": 14, "conversion": 0
        },
    }

    candidates = _generate_candidates(msv, signals, policy)
    assert candidates

    fv = candidates[0]["feature_vector"]
    assert fv.inventory_days == signals["inventory_days"]
    assert fv.margin_pct == signals["margin_pct"]
    assert fv.cvr_7d == signals["cvr_7d"]
