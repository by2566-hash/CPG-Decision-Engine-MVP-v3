# ── Layer 2 · Pillar 1 — Policy Pack ──────────────────────────────────────
# Merchant-level policy configuration — DECOUPLED from KG/Playbooks.
#
# This file has ZERO imports from playbook_registry.py.
# KG and Policy Pack are always decoupled (see CLAUDE.md).
#
# KG/Playbook YAML: platform-level, stable, domain expert manages.
# Policy Pack: merchant-level, changes weekly, operations manages.
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


_REQUIRED_WEIGHT_KEYS = {"gmv_lift", "margin_lift", "inventory_risk_reduction", "retention_lift"}
_REQUIRED_RISK_KEYS = {"max_margin_drop_pct", "max_refund_rate_increase_pct"}


class PolicyPack(BaseModel):
    """Merchant-level policy configuration — decoupled from KG.

    Contains scoring weights (β), risk budgets, exploration budgets,
    module priorities, alert thresholds, and forbidden actions.
    """
    schema_version: str = "planner_policy_v3"
    policy_version: str
    merchant_id: str
    vertical: str
    policy_weights: Dict[str, float]          # sum must equal ~1.0
    risk_budget: Dict[str, float]
    exploration_budget: Dict[str, float]
    module_priorities: List[str]              # ordering of modules (e.g. ["retention", "acquisition", ...])
    alert_thresholds: Dict[str, float]        # per-dimension alert thresholds
    forbidden_actions: List[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _validate_contract(self):
        # policy_version must be non-empty
        if not self.policy_version or not self.policy_version.strip():
            raise ValueError("policy_version must be a non-empty string")

        # policy_weights must contain all required keys
        missing_w = _REQUIRED_WEIGHT_KEYS - set(self.policy_weights.keys())
        if missing_w:
            raise ValueError(f"policy_weights missing required keys: {missing_w}")

        # policy_weights must sum to ~1.0 (tolerance 0.05)
        w_sum = sum(self.policy_weights.values())
        if abs(w_sum - 1.0) > 0.05:
            raise ValueError(f"policy_weights must sum to ~1.0, got {w_sum:.4f}")

        # All weight values must be non-negative
        neg_weights = {k: v for k, v in self.policy_weights.items() if v < 0}
        if neg_weights:
            raise ValueError(f"policy_weights must be non-negative: {neg_weights}")

        # risk_budget must have required keys
        missing_r = _REQUIRED_RISK_KEYS - set(self.risk_budget.keys())
        if missing_r:
            raise ValueError(f"risk_budget missing required keys: {missing_r}")

        # exploration_budget must have bandit_alpha > 0
        if "bandit_alpha" not in self.exploration_budget:
            raise ValueError("exploration_budget must contain 'bandit_alpha'")
        if self.exploration_budget["bandit_alpha"] <= 0:
            raise ValueError("bandit_alpha must be positive")

        return self
