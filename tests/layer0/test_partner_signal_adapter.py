from datetime import datetime, timezone
import json

import pytest
import sqlalchemy as sa

from src.decision_engine.layer0_data.partner_signal_adapter import (
    PartnerSignalNotFound,
    load_partner_decision_signals,
    normalize_frontend_objective_weights,
)


def _signals() -> dict:
    return {
        "overdue_ratio": 1.6,
        "repeat_purchase_rate": 0.22,
        "days_since_last_order_p50": 45,
        "cac_7d": 10.0,
        "cac_baseline_30d": 10.0,
        "roas_7d": 3.0,
        "roas_baseline_30d": 3.0,
        "mobile_atc_rate": 0.15,
        "desktop_atc_rate": 0.18,
        "mobile_traffic_pct": 0.6,
        "checkout_cvr": 0.03,
        "promo_incrementality": 0.60,
        "existing_customer_promo_pct": 0.30,
        "promo_margin_delta": 0.02,
        "monthly_gmv": 50000.0,
        "monthly_ad_spend": 5000.0,
        "avg_order_value": 45.0,
        "monthly_orders": 1200,
        "avg_margin_pct": 0.35,
        "brand_id": "techhub",
    }


def _create_partner_signal_tables(db_engine):
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE decision_health_score (
                    user_id VARCHAR(64) NOT NULL,
                    metric_snapshot TEXT,
                    calculated_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE decision_metric_value (
                    user_id VARCHAR(64) NOT NULL,
                    metric_name VARCHAR(128) NOT NULL,
                    metric_value DOUBLE PRECISION,
                    metric_unit VARCHAR(32),
                    dimension VARCHAR(32),
                    metric_date TIMESTAMP NOT NULL,
                    metadata_json TEXT
                )
                """
            )
        )


def test_load_partner_decision_signals_reads_partner_tables_by_user_id(db_engine):
    _create_partner_signal_tables(db_engine)
    now = datetime.now(timezone.utc)
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO decision_health_score
                    (user_id, metric_snapshot, calculated_at)
                VALUES (:uid, :snapshot, :calculated_at)
                """
            ),
            {
                "uid": "u_partner",
                "snapshot": json.dumps(_signals()),
                "calculated_at": now,
            },
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO decision_metric_value
                    (user_id, metric_name, metric_value, metric_unit, dimension,
                     metric_date, metadata_json)
                VALUES
                    (:uid, 'inventory_days_p10', 11.0, 'days', 'inventory',
                     :metric_date, :metadata),
                    (:uid, 'margin_pct', 0.32, 'ratio', 'margin',
                     :metric_date, :metadata)
                """
            ),
            {
                "uid": "u_partner",
                "metric_date": now,
                "metadata": json.dumps({"source": "fixture"}),
            },
        )

    loaded = load_partner_decision_signals("u_partner")

    assert loaded.user_id == "u_partner"
    assert loaded.merchant_id == "u_partner"
    assert loaded.brand_id == "techhub"
    assert loaded.data_source == "decision_health_score+decision_metric_value"
    assert loaded.signals["overdue_ratio"] == 1.6
    assert loaded.signals["inventory_days_p10"] == 11.0
    assert loaded.signals["margin_pct"] == 0.32


def test_load_partner_decision_signals_raises_when_missing(db_engine):
    _create_partner_signal_tables(db_engine)

    with pytest.raises(PartnerSignalNotFound):
        load_partner_decision_signals("missing_user")


def test_normalize_frontend_objective_weights_requires_four_objectives():
    with pytest.raises(ValueError):
        normalize_frontend_objective_weights(
            {"growth": 40, "margin": 30, "inventory": 20},
            _signals(),
        )


def test_normalize_frontend_objective_weights_adds_policy_context():
    base = _signals()
    merged = normalize_frontend_objective_weights(
        {
            "growth": 40,
            "margin": 30,
            "inventory": 20,
            "retention": 10,
        },
        base,
    )

    assert merged["promo_incrementality"] == 0.60
    assert merged["frontend_objective_weights"] == {
        "growth": 0.4,
        "margin": 0.3,
        "inventory": 0.2,
        "retention": 0.1,
    }
    assert merged["policy_weight_overrides"] == {
        "gmv_lift": 0.4,
        "margin_lift": 0.3,
        "inventory_risk_reduction": 0.2,
        "retention_lift": 0.1,
    }
