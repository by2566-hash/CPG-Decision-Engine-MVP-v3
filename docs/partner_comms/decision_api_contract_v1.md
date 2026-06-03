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

Day-1 adapter reads partner signal data from:

- `decision_health_score(user_id, metric_snapshot, calculated_at)`
- `decision_metric_value(user_id, metric_name, metric_value, metric_unit, dimension, metric_date, metadata_json)`

The latest `decision_health_score.metric_snapshot` is loaded first, then the latest value per `decision_metric_value.metric_name` overlays that snapshot.

If `metric_snapshot` contains `merchant_id`, Python uses it as the V3 pipeline merchant id. If it contains `brand_id` or `brand`, Python uses that for frontend `Recommendation.brand`. Otherwise both fall back to `user_id`.

Live schema discovery on 2026-06-03 confirmed these partner tables exist in the partner `smart_brain` database, but the relevant signal tables currently had no business rows available for a real smoke test.

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
- `SHOPLINE_APP_SECRET`
- `ALLOW_PLACEHOLDER_SECRETS=1` for local development only

## Unresolved Partner Questions

1. Whether partner will provide a distinct merchant/account id separate from `user_id`.
2. Java route, timeout, retry, and error translation behavior.
3. Required freshness threshold for `calculated_at` / `metric_date`.
4. Whether frontend wants one recommendation or a ranked list.
5. Whether deployment is direct FastAPI process, systemd, Docker, or existing platform.
