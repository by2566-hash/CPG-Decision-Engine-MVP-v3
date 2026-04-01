"""Tests for Layer 3: RollbackRegistry.

Covers:
  - Token creation with correct TTL
  - TTL check before expiry
  - TTL check after expiry
  - Rollback failure after TTL expires
  - Rollback failure for wrong merchant
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.decision_engine.layer3_value.rollback_registry import (
    RollbackRegistry,
    RollbackToken,
)


class TestRollbackRegistry:
    def test_register_creates_token_with_correct_ttl(self):
        """Register creates a token with expires_at = now + rollback_ttl_hours."""
        registry = RollbackRegistry()
        before = datetime.now(timezone.utc)

        token = registry.register(
            merchant_id="m_001",
            action_id="DISCOUNT_10PCT",
            transition_id=42,
            undo_description="Revert 10% discount on SKU-123",
        )

        after = datetime.now(timezone.utc)

        assert token.merchant_id == "m_001"
        assert token.action_id == "DISCOUNT_10PCT"
        assert token.transition_id == 42
        assert token.undo_description == "Revert 10% discount on SKU-123"
        assert before <= token.registered_at <= after
        # TTL = 48 hours by default
        expected_expiry = token.registered_at + timedelta(hours=48)
        assert token.expires_at == expected_expiry

    def test_is_within_ttl_true_before_expiry(self):
        """Token registered just now should be within TTL."""
        registry = RollbackRegistry()
        token = registry.register(
            merchant_id="m_001",
            action_id="DISCOUNT_10PCT",
            transition_id=42,
            undo_description="Revert discount",
        )

        assert registry.is_within_ttl(token) is True

    def test_is_within_ttl_false_after_expiry(self):
        """Token with expires_at in the past should NOT be within TTL."""
        registry = RollbackRegistry()
        token = RollbackToken(
            token_id="expired-token",
            merchant_id="m_001",
            action_id="DISCOUNT_10PCT",
            transition_id=42,
            registered_at=datetime.now(timezone.utc) - timedelta(hours=100),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=52),
            undo_description="Revert discount",
        )

        assert registry.is_within_ttl(token) is False

    def test_execute_rollback_fails_after_ttl(self):
        """Rollback should fail if token has expired."""
        registry = RollbackRegistry()
        # Manually insert an expired token
        expired_token = RollbackToken(
            token_id="expired-001",
            merchant_id="m_001",
            action_id="DISCOUNT_10PCT",
            transition_id=42,
            registered_at=datetime.now(timezone.utc) - timedelta(hours=100),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=52),
            undo_description="Revert discount",
        )
        registry._tokens["expired-001"] = expired_token

        result = registry.execute_rollback("expired-001", "m_001")

        assert result["status"] == "error"
        assert "expired" in result["reason"].lower()

    def test_execute_rollback_fails_wrong_merchant(self):
        """Rollback should fail if merchant_id doesn't match the token."""
        registry = RollbackRegistry()
        token = registry.register(
            merchant_id="m_001",
            action_id="DISCOUNT_10PCT",
            transition_id=42,
            undo_description="Revert discount",
        )

        result = registry.execute_rollback(token.token_id, "m_WRONG")

        assert result["status"] == "error"
        assert "merchant" in result["reason"].lower()
