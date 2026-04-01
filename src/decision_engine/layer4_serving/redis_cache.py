"""Redis-backed serving cache for the Fast Plane.

Provides write/read for ranked action lists keyed by merchant+mode.
Falls back gracefully on Redis connection errors (returns None, doesn't crash).

Design: thin wrapper around redis-py with JSON serialisation and TTL.
Written by Deep Plane, read by Fast Plane.

Reference: V2/src/decision_engine/redis_cache.py (verified and adapted)
"""
from __future__ import annotations

import json
import logging

from ..config import settings

log = logging.getLogger(__name__)

# Default TTL: 7 hours (covers 6h Deep Engine cycle + 1h grace)
_DEFAULT_TTL_SECONDS = 7 * 3600

# Lazy singleton — only connect when first used
_redis_client = None


def _key(merchant_id: str, decision_mode: str) -> str:
    return f"serving:{merchant_id}:{decision_mode}"


def _get_redis():
    """Lazy-init Redis connection."""
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=1,
        )
    return _redis_client


def set_redis(client) -> None:
    """Allow tests to inject a mock/stub Redis client."""
    global _redis_client
    _redis_client = client


# ── Write ───────────────────────────────────────────────────────────

def write_serving_cache(
    merchant_id: str,
    decision_mode: str,
    ranked_actions: list,
    policy_version: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> None:
    """Write ranked actions to Redis with TTL."""
    key = _key(merchant_id, decision_mode)
    payload = json.dumps({
        "ranked_actions": ranked_actions,
        "policy_version": policy_version,
    })
    try:
        _get_redis().setex(key, ttl_seconds, payload)
        log.info(
            "[redis] Cached %d actions for %s (ttl=%ds, pv=%s)",
            len(ranked_actions), key, ttl_seconds, policy_version,
        )
    except Exception:
        log.exception("[redis] Failed to write serving cache for %s", key)


# ── Read ────────────────────────────────────────────────────────────

def read_serving_cache(
    merchant_id: str,
    decision_mode: str = "deep",
) -> dict | None:
    """Read cached ranked actions from Redis.

    Returns dict with keys: ranked_actions, policy_version.
    Returns None on cache miss or error (caller should fallback to DB).
    Graceful fallback: Redis connection error → return None (don't crash).
    """
    key = _key(merchant_id, decision_mode)
    try:
        raw = _get_redis().get(key)
        if raw is None:
            log.debug("[redis] Cache miss for %s", key)
            return None
        data = json.loads(raw)
        log.debug(
            "[redis] Cache hit for %s (%d actions)",
            key, len(data.get("ranked_actions", [])),
        )
        return data
    except Exception:
        log.exception("[redis] Failed to read serving cache for %s", key)
        return None
