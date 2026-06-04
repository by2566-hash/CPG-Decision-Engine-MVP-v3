# Decision API Contract v1

## Scope

This contract defines the Day-1 Java backend -> Python FastAPI boundary for generating frontend-demo-compatible Recommendation JSON from a partner `user_id` and four objective weights.

## Endpoint

`POST /partner/decision-cards`

Authentication: `X-API-Key: <API_KEY>`

## Request

The request must include `user_id` plus the four frontend objective weights: `growth`, `margin`, `inventory`, and `retention`.

`brand_id` is optional. If the current frontend keeps the demo `BrandId` union, Java should pass one of the frontend brand ids such as `techhub`, `stylenest`, `homecomfort`, `fitlife`, or `gourmetbite`. If omitted, Python falls back to the resolved `merchant_id`.

Weights may be sent as percentages or normalized values between `0` and `100`. Python normalizes them to a 1.0 sum before applying them to the V3 scoring policy.

```json
{
  "user_id": "user_123",
  "brand_id": "techhub",
  "growth": 40,
  "margin": 30,
  "inventory": 20,
  "retention": 10
}
```

## Response

The response is pure JSON. Python `DecisionCard` objects are never returned directly. The `recommendations` entries are shaped to satisfy the frontend demo `Recommendation` interface.

```json
{
  "user_id": "user_123",
  "merchant_id": "user_123",
  "brand_id": "techhub",
  "mode": "shadow",
  "policy_version": "default_v1",
  "msm_state": {
    "promotion": "DEGRADING"
  },
  "alerts": [],
  "data_source": "decision_health_score+decision_metric_value",
  "applied_objective_weights": {
    "growth": 0.4,
    "margin": 0.3,
    "inventory": 0.2,
    "retention": 0.1
  },
  "recommendations": [
    {
      "id": "dc_test",
      "title": "Low promotion incrementality",
      "module": "Promotion",
      "brand": "techhub",
      "priority": "Best next decision",
      "revenueImpact": "+$500/mo",
      "marginImpact": "Monitor margin impact",
      "confidence": 30,
      "decisionScore": 0.61,
      "recommendation": "Shift discount exposure toward incremental customers.",
      "whyNow": "Expected impact is directionally positive.",
      "actions": ["Shift discount exposure toward incremental customers."],
      "policyGates": [
        {
          "id": "constraints",
          "name": "Decision constraints",
          "status": "pass",
          "detail": "All constraints passed."
        }
      ],
      "trace": {
        "id": "decision-card",
        "label": "Decision card",
        "metric": "0.61",
        "detail": "Expected impact is directionally positive.",
        "type": "score",
        "evidence": ["Low promotion incrementality"],
        "technical": "Mapped from V3 DecisionCard JSON at the partner API boundary.",
        "children": []
      },
      "diagnosis": "Promotion efficiency is below the configured threshold.",
      "primaryBottleneck": {
        "title": "Low promotion incrementality",
        "detail": "Promotion efficiency is below the configured threshold."
      },
      "firstAction": "Shift discount exposure toward incremental customers.",
      "estimatedUpside": "+$500/mo",
      "evidence": [],
      "decisionRisk": {
        "prevented": "Avoid acting outside the ranked V3 decision path.",
        "resourceSaved": "Keeps review focused on the highest-ranked action.",
        "upside": "+$500/mo"
      },
      "funnel": [],
      "funnelInsight": "Promotion efficiency is below the configured threshold.",
      "whatLooksHealthy": [],
      "actionsPlan": [
        {
          "priority": "High",
          "title": "Shift discount exposure toward incremental customers.",
          "detail": "Expected impact is directionally positive.",
          "owner": "Merchant operator"
        }
      ],
      "doNotChangeYet": []
    }
  ]
}
```

## Error Codes

- `401` or `403`: missing or invalid `X-API-Key`.
- `404`: no partner signal snapshot exists for `user_id`.
- `422`: objective weights are missing, negative, non-numeric, or sum to zero.
- `500`: V3 pipeline failure after valid input was accepted.
- `503`: kill switch is active and decision generation is disabled.

## Postgres Input Boundary

Day-1 adapter first reads normalized partner signal data from:

- `decision_health_score(user_id, metric_snapshot, calculated_at)`
- `decision_metric_value(user_id, metric_name, metric_value, metric_unit, dimension, metric_date, metadata_json)`

The latest `decision_health_score.metric_snapshot` is loaded first, then the latest value per `decision_metric_value.metric_name` overlays that snapshot.

If those normalized signal tables are empty for the requested `user_id`, Python falls back to partner silver ads tables:

- `decision_silver_google_ads`
- `decision_silver_meta_ads`

The fallback aggregates rows for the requested `user_id` over the latest available 7-day and 30-day windows and emits acquisition/growth signals into the same V3 `signals` dict:

```json
{
  "cac_7d": 25.78,
  "cac_baseline_30d": 38.08,
  "cac_vs_baseline_ratio": 0.68,
  "roas_7d": 0,
  "roas_baseline_30d": 0,
  "monthly_ad_spend": 11081.44,
  "paid_spend_7d": 2139.9,
  "paid_clicks_7d": 1758,
  "paid_impressions_7d": 45880,
  "paid_conversions_7d": 83,
  "partner_signal_quality": {
    "source_layer": "silver_ads",
    "source_tables": ["decision_silver_meta_ads"],
    "roas_7d": "unavailable_zero_conversion_value",
    "roas_baseline_30d": "unavailable_zero_conversion_value",
    "roas": "unavailable_zero_conversion_value"
  }
}
```

The fallback does not fabricate retention, inventory, margin, conversion, or promotion facts. Missing non-ads dimensions use the existing V3 missing-signal fallback path.

If `metric_snapshot` contains `merchant_id`, Python uses it as the V3 pipeline merchant id. If it contains `brand_id` or `brand`, Python uses that for frontend `Recommendation.brand`. Otherwise both fall back to `user_id`.

Live schema discovery on 2026-06-04 confirmed:

- `decision_silver_meta_ads` has 101 rows for `user_id=100`, date range `2026-03-06` to `2026-06-03`.
- `decision_silver_google_ads` currently has 0 rows.
- `decision_health_score` and `decision_metric_value` currently have 0 rows.
- Current Meta Ads `conversion_value` is 0, so ROAS is marked as unavailable instead of treated as validated revenue.

There is no separate partner mapping table in the current schema. Day-1 fallback mapping is `merchant_id = user_id`, so the existing V3 pipeline can run with the partner `user_id` as its merchant id. If partner data later supplies a distinct merchant/account id, place it in `metric_snapshot.merchant_id` or move the mapping into the adapter before changing the pipeline.

Frontend objective weights are normalized and added to the signal context:

```json
{
  "frontend_objective_weights": {
    "growth": 0.4,
    "margin": 0.3,
    "inventory": 0.2,
    "retention": 0.1
  },
  "policy_weight_overrides": {
    "gmv_lift": 0.4,
    "margin_lift": 0.3,
    "inventory_risk_reduction": 0.2,
    "retention_lift": 0.1
  }
}
```

The partner endpoint passes these overrides into `run_once()` through `signals`. The pipeline applies `policy_weight_overrides` to the active `policy_weights` before candidate scoring, so frontend changes affect decision ranking without changing the `run_once()` signature.

## Environment Variables

- `POSTGRES_DSN`
- `REDIS_URL`
- `API_KEY`
- Optional only if Shopline webhook is enabled: `ENABLE_SHOPLINE_WEBHOOK=true`, `SHOPLINE_APP_SECRET`
- `ALLOW_PLACEHOLDER_SECRETS=1` for local development only

## Unresolved Partner Questions

1. Whether partner will provide a distinct merchant/account id separate from `user_id`.
2. Java route, timeout, retry, and error translation behavior.
3. Required freshness threshold for `calculated_at` / `metric_date`.
4. Whether frontend wants one recommendation or a ranked list.
5. Whether deployment is direct FastAPI process, systemd, Docker, or existing platform.
