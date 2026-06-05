from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.decision_engine import db_client


class PartnerSignalNotFound(LookupError):
    """Raised when no Postgres-backed merchant signal snapshot exists."""


CANONICAL_SIGNAL_KEYS: frozenset[str] = frozenset(
    {
        "overdue_ratio",
        "repeat_purchase_rate",
        "days_since_last_order_p50",
        "cac_7d",
        "cac_baseline_30d",
        "roas_7d",
        "roas_baseline_30d",
        "mobile_atc_rate",
        "desktop_atc_rate",
        "mobile_traffic_pct",
        "checkout_cvr",
        "promo_incrementality",
        "existing_customer_promo_pct",
        "promo_margin_delta",
        "monthly_gmv",
        "monthly_ad_spend",
        "avg_order_value",
        "monthly_orders",
        "avg_margin_pct",
        "margin_pct",
        "inventory_days_p10",
        "customer_orders_count",
        "days_since_last_action",
    }
)

OBJECTIVE_WEIGHT_KEYS: tuple[str, str, str, str] = (
    "growth",
    "margin",
    "inventory",
    "retention",
)


@dataclass(frozen=True)
class PartnerSignalSnapshot:
    user_id: str
    merchant_id: str
    brand_id: str | None
    signals: dict[str, Any]
    data_source: str


def load_partner_decision_signals(user_id: str) -> PartnerSignalSnapshot:
    state = db_client.fetch_latest_partner_signal_snapshot(user_id)
    if not state or not state.get("signals"):
        raise PartnerSignalNotFound(
            f"No partner signal snapshot found for user_id={user_id}"
        )

    return PartnerSignalSnapshot(
        user_id=user_id,
        merchant_id=state["merchant_id"],
        brand_id=state.get("brand_id"),
        signals=dict(state["signals"]),
        data_source=state["data_source"],
    )


def _normalize_weight_value(key: str, value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{key} must be numeric")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be numeric") from exc
    if normalized < 0:
        raise ValueError(f"{key} must be non-negative")
    return normalized


def normalize_frontend_objective_weights(
    objective_weights: Mapping[str, Any],
    base_signals: Mapping[str, Any],
) -> dict[str, Any]:
    missing = set(OBJECTIVE_WEIGHT_KEYS) - set(objective_weights)
    extra = set(objective_weights) - set(OBJECTIVE_WEIGHT_KEYS)
    if missing or extra:
        raise ValueError(
            "objective weights must contain exactly growth, margin, inventory, retention"
        )

    raw_weights = {
        key: _normalize_weight_value(key, objective_weights[key])
        for key in OBJECTIVE_WEIGHT_KEYS
    }
    total = sum(raw_weights.values())
    if total <= 0:
        raise ValueError("objective weights must sum to a positive value")

    normalized_weights = {
        key: round(value / total, 6)
        for key, value in raw_weights.items()
    }
    merged = dict(base_signals)
    merged["frontend_objective_weights"] = normalized_weights
    merged["policy_weight_overrides"] = {
        "gmv_lift": normalized_weights["growth"],
        "margin_lift": normalized_weights["margin"],
        "inventory_risk_reduction": normalized_weights["inventory"],
        "retention_lift": normalized_weights["retention"],
    }
    return merged
