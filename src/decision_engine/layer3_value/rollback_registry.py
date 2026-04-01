# ── Layer 3 · Action Safety — Rollback Registry ──────────────────────────
# Every write action has an undo endpoint with TTL (settings.rollback_ttl_hours).
# Operator trust foundation — ensures all actions are reversible.
#
# Every write action MUST register here before execution.
# Phase 1: in-memory storage, no external API calls.
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from ..config import settings

log = logging.getLogger(__name__)


class RollbackToken(BaseModel):
    """Token proving an action is registered for rollback."""
    token_id: str
    merchant_id: str
    action_id: str
    transition_id: int
    registered_at: datetime
    expires_at: datetime  # registered_at + settings.rollback_ttl_hours
    undo_description: str


class RollbackRegistry:
    """Manages undo endpoints for every executed write action.

    Phase 1: in-memory store. Phase 2+: persisted to DB.
    """

    def __init__(self) -> None:
        self._tokens: dict[str, RollbackToken] = {}

    def register(
        self,
        merchant_id: str,
        action_id: str,
        transition_id: int,
        undo_description: str,
    ) -> RollbackToken:
        """Create and store a RollbackToken.

        expires_at = now() + timedelta(hours=settings.rollback_ttl_hours)
        """
        now = datetime.now(timezone.utc)
        token = RollbackToken(
            token_id=str(uuid.uuid4()),
            merchant_id=merchant_id,
            action_id=action_id,
            transition_id=transition_id,
            registered_at=now,
            expires_at=now + timedelta(hours=settings.rollback_ttl_hours),
            undo_description=undo_description,
        )
        self._tokens[token.token_id] = token
        log.info(
            "Rollback token %s registered for %s/%s (expires %s)",
            token.token_id, merchant_id, action_id, token.expires_at,
        )
        return token

    def is_within_ttl(self, token: RollbackToken) -> bool:
        """Returns True if now() < token.expires_at."""
        return datetime.now(timezone.utc) < token.expires_at

    def execute_rollback(self, token_id: str, merchant_id: str) -> dict:
        """Execute rollback for a previously registered action.

        Validates:
          1. Token exists
          2. Token belongs to merchant_id
          3. is_within_ttl()

        Phase 1: no external API call, just mark as rolled back.
        """
        token = self._tokens.get(token_id)
        if token is None:
            return {"status": "error", "reason": "Token not found"}

        if token.merchant_id != merchant_id:
            return {"status": "error", "reason": "Token does not belong to this merchant"}

        if not self.is_within_ttl(token):
            return {
                "status": "error",
                "reason": f"Rollback window expired at {token.expires_at.isoformat()}",
            }

        # Phase 1: mark as rolled back in-memory (no external API call)
        del self._tokens[token_id]

        log.info(
            "Rollback executed for token %s (%s/%s)",
            token_id, merchant_id, token.action_id,
        )

        return {
            "status": "rolled_back",
            "action_id": token.action_id,
            "note": token.undo_description,
        }

    def get_token(self, token_id: str, merchant_id: str) -> RollbackToken | None:
        """Retrieve a token by ID, verifying ownership.

        Returns the token if it exists and belongs to merchant_id.
        Returns None if not found or ownership mismatch.
        Does NOT delete the token.
        """
        token = self._tokens.get(token_id)
        if token is None:
            return None
        if token.merchant_id != merchant_id:
            return None
        return token
