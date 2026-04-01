"""Tests for PolicyPack validation.

Covers:
  - Valid PolicyPack passes validation
  - Weights not summing to 1.0 raises error
  - Missing required weight key raises error
  - bandit_alpha <= 0 raises error
  - Empty policy_version raises error
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from src.decision_engine.layer2_decision.pillar1_kg.policy_pack import PolicyPack


def _valid_policy_kwargs() -> dict:
    """Return kwargs for a fully valid PolicyPack."""
    return dict(
        policy_version="2026-03-28_m001",
        merchant_id="m_test_001",
        vertical="cpg",
        policy_weights={
            "gmv_lift": 0.40,
            "margin_lift": 0.30,
            "inventory_risk_reduction": 0.15,
            "retention_lift": 0.15,
        },
        risk_budget={
            "max_margin_drop_pct": 0.05,
            "max_refund_rate_increase_pct": 0.02,
        },
        exploration_budget={
            "bandit_alpha": 0.25,
        },
        module_priorities=["retention", "acquisition", "conversion", "promotion"],
        alert_thresholds={
            "acquisition": 1.15,
            "conversion": 0.70,
            "retention": 1.50,
            "promotion": 0.40,
        },
    )


class TestPolicyPackValid:
    def test_valid_policy_pack_passes(self):
        """A well-formed PolicyPack should pass all validators."""
        pp = PolicyPack(**_valid_policy_kwargs())
        assert pp.schema_version == "planner_policy_v3"
        assert pp.merchant_id == "m_test_001"
        assert pp.policy_version == "2026-03-28_m001"

    def test_with_optional_fields(self):
        """PolicyPack with optional fields set should pass."""
        kwargs = _valid_policy_kwargs()
        kwargs["forbidden_actions"] = ["DISCOUNT_30PCT", "PAUSE_ALL_ADS"]
        kwargs["expires_at"] = datetime(2026, 4, 30, tzinfo=timezone.utc)
        pp = PolicyPack(**kwargs)
        assert len(pp.forbidden_actions) == 2
        assert pp.expires_at is not None


class TestPolicyPackWeightSum:
    def test_weights_not_summing_to_1_raises(self):
        """Weights summing to far from 1.0 should raise ValueError."""
        kwargs = _valid_policy_kwargs()
        kwargs["policy_weights"] = {
            "gmv_lift": 0.50,
            "margin_lift": 0.50,
            "inventory_risk_reduction": 0.50,
            "retention_lift": 0.50,
        }  # sum = 2.0
        with pytest.raises(ValueError, match="must sum to"):
            PolicyPack(**kwargs)

    def test_weights_within_tolerance_passes(self):
        """Weights summing to 1.04 (within 0.05 tolerance) should pass."""
        kwargs = _valid_policy_kwargs()
        kwargs["policy_weights"] = {
            "gmv_lift": 0.40,
            "margin_lift": 0.30,
            "inventory_risk_reduction": 0.19,
            "retention_lift": 0.15,
        }  # sum = 1.04
        pp = PolicyPack(**kwargs)
        assert pp is not None


class TestPolicyPackMissingKeys:
    def test_missing_required_weight_key_raises(self):
        """Missing a required weight key should raise ValueError."""
        kwargs = _valid_policy_kwargs()
        kwargs["policy_weights"] = {
            "gmv_lift": 0.50,
            "margin_lift": 0.50,
            # missing: inventory_risk_reduction, retention_lift
        }
        with pytest.raises(ValueError, match="missing required keys"):
            PolicyPack(**kwargs)

    def test_missing_risk_budget_key_raises(self):
        """Missing a required risk_budget key should raise ValueError."""
        kwargs = _valid_policy_kwargs()
        kwargs["risk_budget"] = {
            "max_margin_drop_pct": 0.05,
            # missing: max_refund_rate_increase_pct
        }
        with pytest.raises(ValueError, match="risk_budget missing"):
            PolicyPack(**kwargs)


class TestPolicyPackBanditAlpha:
    def test_bandit_alpha_zero_raises(self):
        """bandit_alpha = 0 should raise ValueError."""
        kwargs = _valid_policy_kwargs()
        kwargs["exploration_budget"] = {"bandit_alpha": 0.0}
        with pytest.raises(ValueError, match="bandit_alpha must be positive"):
            PolicyPack(**kwargs)

    def test_bandit_alpha_negative_raises(self):
        """bandit_alpha < 0 should raise ValueError."""
        kwargs = _valid_policy_kwargs()
        kwargs["exploration_budget"] = {"bandit_alpha": -0.5}
        with pytest.raises(ValueError, match="bandit_alpha must be positive"):
            PolicyPack(**kwargs)

    def test_bandit_alpha_missing_raises(self):
        """Missing bandit_alpha key should raise ValueError."""
        kwargs = _valid_policy_kwargs()
        kwargs["exploration_budget"] = {"some_other_key": 1.0}
        with pytest.raises(ValueError, match="must contain 'bandit_alpha'"):
            PolicyPack(**kwargs)


class TestPolicyPackVersion:
    def test_empty_policy_version_raises(self):
        """Empty string policy_version should raise ValueError."""
        kwargs = _valid_policy_kwargs()
        kwargs["policy_version"] = ""
        with pytest.raises(ValueError, match="policy_version must be a non-empty"):
            PolicyPack(**kwargs)

    def test_whitespace_only_policy_version_raises(self):
        """Whitespace-only policy_version should raise ValueError."""
        kwargs = _valid_policy_kwargs()
        kwargs["policy_version"] = "   "
        with pytest.raises(ValueError, match="policy_version must be a non-empty"):
            PolicyPack(**kwargs)


class TestPolicyPackNegativeWeights:
    def test_negative_weight_raises(self):
        """Negative policy_weight value should raise ValueError."""
        kwargs = _valid_policy_kwargs()
        kwargs["policy_weights"] = {
            "gmv_lift": -0.10,
            "margin_lift": 0.60,
            "inventory_risk_reduction": 0.30,
            "retention_lift": 0.20,
        }
        with pytest.raises(ValueError, match="non-negative"):
            PolicyPack(**kwargs)
