"""BrightSkin end-to-end demo fixture.

BrightSkin is a skincare brand with 2 years of Shopline history. Current
state: retention DEGRADING (VIP churn risk + dropping repeat rate),
acquisition WATCH, conversion HEALTHY, promotion HEALTHY.

This is the canonical Phase 1 demo scenario, referenced by:
- V3/tests/e2e/test_brightskin_walkthrough.py
- V3/scripts/demo_brightskin.py
- V3/docs/PHASE_ROADMAP.md Phase 1 / BrightSkin end-to-end fixture

See V3/docs/PHASE_ROADMAP.md
"""

from datetime import datetime, timezone

from src.decision_engine.contracts import MerchantStateVector


def build_brightskin_state() -> MerchantStateVector:
    """BrightSkin's 4D MSM state at decision time.

    Retention DEGRADING: repeat rate has fallen 3 weeks in a row,
    VIP cohort overdue rate crossed 1.5×.
    Acquisition WATCH: CAC creeping up but ROAS still above target.
    Conversion and Promotion remain healthy.
    """
    return MerchantStateVector(
        merchant_id="brightskin_042",
        computed_at=datetime(2026, 4, 8, 9, 0, 0, tzinfo=timezone.utc),
        retention_state="DEGRADING",
        acquisition_state="WATCH",
        conversion_state="HEALTHY",
        promotion_state="HEALTHY",
        retention_urgency=0.75,
        acquisition_urgency=0.35,
        conversion_urgency=0.0,
        promotion_urgency=0.0,
    )


def build_brightskin_signals() -> dict:
    """Raw signals BrightSkin's pipeline would receive.

    Feeds both FeatureBuilder and ConstraintEngine.
    Values represent a real-feeling skincare brand scenario:
    - Healthy inventory (38 days)
    - Good margin (33%) — can absorb a 10–15% discount
    - Dropping repeat rate (18%) — retention alarm trigger
    - Elevated churn score (0.61) — VIP cohort overdue
    - Returning customers (5 orders) — cold_prospect_gate won't fire
    - Previous action was a REMINDER — discount_last_resort can fire
    - Incrementality present (0.45) — incrementality constraint passes
    """
    return {
        # Inventory
        "inventory_days": 38.0,
        "inventory_days_p10": 12.0,
        # Margin
        "margin_pct": 0.33,
        "avg_margin_pct": 0.33,
        # Behavior
        "repeat_rate_7d": 0.18,
        "repeat_purchase_rate": 0.18,
        "cvr_7d": 0.024,
        "cvr_30d": 0.027,
        "checkout_cvr": 0.024,
        "promo_redemption_30d": 0.42,
        "churn_score": 0.61,
        "overdue_ratio": 0.61,
        # Context
        "seasonality_index": 1.0,
        "benchmark_gap_score": -0.23,
        # Customer (returning — cold_prospect_gate must not fire)
        "customer_orders_count": 5,
        "existing_customer_promo_pct": 0.30,
        # Last action (REMINDER sent 5 days ago — discount is now eligible)
        "last_action_type": "REMINDER",
        "days_since_last_action": 5,
        # Incrementality
        "promo_incrementality": 0.45,
        "promo_margin_delta": 0.02,
        # Financial (for ImpactCalculator in full run_once())
        "monthly_gmv": 120_000.0,
        "monthly_ad_spend": 8_000.0,
        "avg_order_value": 62.0,
        "monthly_orders": 1_935,
        # MSM inputs (for run_once() MSM computation path)
        "cac_7d": 11.5,
        "cac_baseline_30d": 10.0,
        "roas_7d": 4.5,
        "roas_baseline_30d": 5.0,
        "mobile_atc_rate": 0.14,
        "desktop_atc_rate": 0.17,
        "mobile_traffic_pct": 0.65,
        "days_since_last_order_p50": 38,
    }


def build_brightskin_policy() -> dict:
    """BrightSkin's policy pack for the demo.

    A retention-focused policy: retention_lift and margin_lift carry
    high weights. Lower beta2 (no bandit data yet in Phase 1).
    """
    return {
        "policy_version": "brightskin_v1",
        "policy_weights": {
            "gmv_lift": 0.30,
            "margin_lift": 0.25,
            "inventory_risk_reduction": 0.20,
            "retention_lift": 0.25,
        },
        "risk_budget": {},
        "beta1": 0.65,
        "beta2": 0.20,
        "beta3": 0.15,
        # Approval gate thresholds
        "discount_threshold": 0.15,
        "budget_threshold_daily": 1000.0,
        "low_risk_auto_actions": False,
        # Constraint settings
        "min_margin_floor": 0.15,
        "incrementality_required": False,
        "attribution_windows": {
            "retention": 7,
            "acquisition": 30,
            "promotion": 14,
            "conversion": 0,
        },
    }
