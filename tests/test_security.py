# ── Security Tests — Ownership Validation + Rollback Race Fix ─────────────
# Tests for BUG 1 (/approve ownership) and BUG 2 (rollback WSM update).
# ───────────────────────────────────────────────────────────────────────────
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.app import app
from src.decision_engine import db_client
from src.decision_engine.layer3_value.rollback_registry import RollbackRegistry

client = TestClient(app)


def _insert_transition(merchant_id: str, was_executed: bool = False) -> int:
    """Helper: insert a WSM transition and return its transition_id."""
    return db_client.insert_wsm_transition(
        merchant_id=merchant_id,
        vertical="cpg",
        decision_mode="deep",
        s_json={},
        action_id="DISCOUNT_10PCT",
        action_family="DISCOUNT",
        action_params_json={},
        constraints_passed=True,
        was_executed=was_executed,
    )


# ── BUG 1: /approve ownership validation ─────────────────────────────────


def test_approve_rejects_wrong_merchant_ownership():
    """Merchant B cannot approve Merchant A's transition — must return 403."""
    tid = _insert_transition("merchant_A")

    resp = client.post(
        "/decision/merchant_B/approve",
        json={"transition_id": tid, "execution_params": {}},
    )

    assert resp.status_code == 403
    assert "does not belong to this merchant" in resp.json()["detail"]


def test_approve_rejects_nonexistent_transition():
    """POST /approve with a transition_id that does not exist — must return 404."""
    resp = client.post(
        "/decision/merchant_A/approve",
        json={"transition_id": 99999, "execution_params": {}},
    )

    assert resp.status_code == 404
    assert "99999" in resp.json()["detail"]


def test_approve_accepts_correct_owner():
    """Merchant can approve their own transition — must return 200."""
    tid = _insert_transition("merchant_owner")

    resp = client.post(
        "/decision/merchant_owner/approve",
        json={"transition_id": tid, "execution_params": {},
              "high_risk_acknowledged": True, "risk_reason": "test ownership"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert "rollback_token_id" in data


# ── BUG 2: Rollback WSM update after token deletion ───────────────────────


def test_rollback_updates_wsm_after_execution():
    """WSM must show was_executed=False after successful rollback.

    Verifies the fix for the post-delete race: token is fetched before
    execute_rollback() deletes it, so the WSM update always runs.
    """
    from sqlalchemy import text

    tid = _insert_transition("m_rb_wsm", was_executed=False)

    # Step 1: approve (sets was_executed=True, registers rollback token)
    approve_resp = client.post(
        "/decision/m_rb_wsm/approve",
        json={"transition_id": tid, "execution_params": {},
              "high_risk_acknowledged": True, "risk_reason": "test rollback wsm"},
    )
    assert approve_resp.status_code == 200
    token_id = approve_resp.json()["rollback_token_id"]

    # Step 2: rollback
    rollback_resp = client.post(f"/decision/m_rb_wsm/rollback/{token_id}")
    assert rollback_resp.status_code == 200
    assert rollback_resp.json()["status"] == "rolled_back"

    # Step 3: verify WSM shows was_executed=False
    engine = db_client._get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT was_executed FROM wsm_transitions_v3 WHERE transition_id = :tid"),
            {"tid": tid},
        ).fetchone()

    assert row is not None
    assert row[0] is False or row[0] == 0, (
        "WSM was_executed must be False after rollback, "
        f"but got: {row[0]!r}"
    )


def test_rollback_rejects_expired_token():
    """Rollback with an expired token must return HTTP 400, not 200."""
    from api.app import _rollback_registry

    tid = _insert_transition("m_rb_expired")

    # Register a token that is already expired (expires_at in the past)
    from src.decision_engine.layer3_value.rollback_registry import RollbackToken
    import uuid

    expired_token = RollbackToken(
        token_id=str(uuid.uuid4()),
        merchant_id="m_rb_expired",
        action_id="DISCOUNT_10PCT",
        transition_id=tid,
        registered_at=datetime.now(timezone.utc) - timedelta(hours=50),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=2),  # already expired
        undo_description="test expired token",
    )
    # Inject directly into the registry's store
    _rollback_registry._tokens[expired_token.token_id] = expired_token

    resp = client.post(f"/decision/m_rb_expired/rollback/{expired_token.token_id}")

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "expired" in detail.lower() or "Rollback window expired" in detail


def test_rollback_rejects_unknown_token():
    """Rollback with a token that does not exist must return 404."""
    resp = client.post("/decision/any_merchant/rollback/nonexistent-token-id")
    assert resp.status_code == 404


def test_rollback_rejects_wrong_merchant_token():
    """Merchant B cannot use Merchant A's rollback token — must return 404."""
    from api.app import _rollback_registry
    import uuid
    from src.decision_engine.layer3_value.rollback_registry import RollbackToken

    tid = _insert_transition("merchant_token_owner")
    token = RollbackToken(
        token_id=str(uuid.uuid4()),
        merchant_id="merchant_token_owner",
        action_id="DISCOUNT_10PCT",
        transition_id=tid,
        registered_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        undo_description="test ownership",
    )
    _rollback_registry._tokens[token.token_id] = token

    # Merchant B tries to use Merchant A's token
    resp = client.post(f"/decision/merchant_B_thief/rollback/{token.token_id}")
    assert resp.status_code == 404


# ── get_token() public API ────────────────────────────────────────────────


def test_get_token_returns_none_for_wrong_merchant():
    """RollbackRegistry.get_token() enforces ownership — returns None on mismatch."""
    registry = RollbackRegistry()
    token = registry.register(
        merchant_id="owner",
        action_id="DISCOUNT_10PCT",
        transition_id=1,
        undo_description="test",
    )

    # Correct owner: returns token
    assert registry.get_token(token.token_id, "owner") is token

    # Wrong owner: returns None
    assert registry.get_token(token.token_id, "attacker") is None

    # Unknown token_id: returns None
    assert registry.get_token("nonexistent", "owner") is None
