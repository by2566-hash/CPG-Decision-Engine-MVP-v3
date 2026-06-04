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
        for table_name in (
            "decision_silver_google_ads",
            "decision_silver_meta_ads",
        ):
            conn.execute(
                sa.text(
                    f"""
                    CREATE TABLE {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id VARCHAR(64) NOT NULL,
                        data_source_id INTEGER,
                        batch_id VARCHAR(128),
                        date DATE NOT NULL,
                        campaign_id VARCHAR(128),
                        campaign_name VARCHAR(256),
                        spend NUMERIC,
                        impressions INTEGER,
                        clicks INTEGER,
                        ctr NUMERIC,
                        cpc NUMERIC,
                        cpm NUMERIC,
                        conversions INTEGER,
                        conversion_value NUMERIC,
                        raw_json TEXT,
                        raw_data_id INTEGER,
                        created_at TIMESTAMP,
                        tenant_id INTEGER
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


def test_load_partner_decision_signals_falls_back_to_silver_ads(db_engine):
    _create_partner_signal_tables(db_engine)
    now = datetime.now(timezone.utc)
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO decision_silver_meta_ads
                    (user_id, date, campaign_name, spend, impressions, clicks,
                     conversions, conversion_value, created_at, tenant_id)
                VALUES
                    (:uid, '2026-06-03', 'Meta Prospecting', 100, 1000, 50,
                     10, 400, :created_at, 1),
                    (:uid, '2026-06-02', 'Meta Prospecting', 60, 600, 30,
                     6, 240, :created_at, 1),
                    (:uid, '2026-05-10', 'Meta Prospecting', 300, 3000, 150,
                     15, 600, :created_at, 1)
                """
            ),
            {"uid": "100", "created_at": now},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO decision_silver_google_ads
                    (user_id, date, campaign_name, spend, impressions, clicks,
                     conversions, conversion_value, created_at, tenant_id)
                VALUES
                    (:uid, '2026-06-03', 'Google Brand', 40, 400, 20,
                     4, 160, :created_at, 1)
                """
            ),
            {"uid": "100", "created_at": now},
        )

    loaded = load_partner_decision_signals("100")

    assert loaded.user_id == "100"
    assert loaded.merchant_id == "100"
    assert loaded.brand_id == "100"
    assert loaded.data_source == (
        "decision_silver_google_ads+decision_silver_meta_ads"
    )
    assert loaded.signals["paid_spend_7d"] == pytest.approx(200.0)
    assert loaded.signals["monthly_ad_spend"] == pytest.approx(500.0)
    assert loaded.signals["paid_clicks_7d"] == 100
    assert loaded.signals["paid_impressions_7d"] == 2000
    assert loaded.signals["paid_conversions_7d"] == 20
    assert loaded.signals["cac_7d"] == pytest.approx(10.0)
    assert loaded.signals["cac_baseline_30d"] == pytest.approx(500.0 / 35.0)
    assert loaded.signals["roas_7d"] == pytest.approx(4.0)
    assert loaded.signals["roas_baseline_30d"] == pytest.approx(2.8)
    assert loaded.signals["cac_vs_baseline_ratio"] == pytest.approx(0.7)
    assert loaded.signals["partner_ads_latest_date"] == "2026-06-03"


def test_load_partner_decision_signals_marks_unavailable_roas_for_meta_only(db_engine):
    _create_partner_signal_tables(db_engine)
    now = datetime.now(timezone.utc)
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO decision_silver_meta_ads
                    (user_id, date, campaign_name, spend, impressions, clicks,
                     conversions, conversion_value, created_at, tenant_id)
                VALUES
                    (:uid, '2026-06-03', 'Chafolio_Prospecting', 229.02, 5809, 245,
                     7, 0, :created_at, 1),
                    (:uid, '2026-06-02', 'Chafolio_Prospecting', 296.32, 7237, 299,
                     12, 0, :created_at, 1)
                """
            ),
            {"uid": "100", "created_at": now},
        )

    loaded = load_partner_decision_signals("100")

    assert loaded.data_source == "decision_silver_meta_ads"
    assert loaded.signals["cac_7d"] == pytest.approx((229.02 + 296.32) / 19)
    assert loaded.signals["roas_7d"] == 0.0
    assert loaded.signals["roas_baseline_30d"] == 0.0
    assert loaded.signals["partner_signal_quality"]["roas"] == (
        "unavailable_zero_conversion_value"
    )


def test_load_partner_decision_signals_marks_window_level_roas_quality(db_engine):
    _create_partner_signal_tables(db_engine)
    now = datetime.now(timezone.utc)
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO decision_silver_meta_ads
                    (user_id, date, campaign_name, spend, impressions, clicks,
                     conversions, conversion_value, created_at, tenant_id)
                VALUES
                    (:uid, '2026-06-03', 'Recent Zero Revenue', 100, 1000, 50,
                     10, 0, :created_at, 1),
                    (:uid, '2026-05-15', 'Older Revenue', 300, 3000, 150,
                     15, 600, :created_at, 1)
                """
            ),
            {"uid": "100", "created_at": now},
        )

    loaded = load_partner_decision_signals("100")

    assert loaded.signals["roas_7d"] == 0.0
    assert loaded.signals["roas_baseline_30d"] == pytest.approx(1.5)
    assert loaded.signals["partner_signal_quality"]["roas_7d"] == (
        "unavailable_zero_conversion_value"
    )
    assert "roas_baseline_30d" not in loaded.signals["partner_signal_quality"]


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
