# ── Layer 4 · Fast Plane ──────────────────────────────────────────────────
# Serves every API request: Read Redis Cache → Apply Emergency Features → Return.
# Latency target: < 50ms (p99).
# NEVER recomputes. Fallback chain: Redis → DB Cache → 503.
# This guarantees latency SLA regardless of ML pipeline state.
#
# CRITICAL RULE: Fast Plane NEVER calls pipeline.run_once().
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
import time

from fastapi import HTTPException

from .. import db_client
from . import redis_cache

log = logging.getLogger(__name__)


class FastPlane:
    """Low-latency serving plane — reads pre-computed results from cache.

    CRITICAL RULE: Fast Plane NEVER recomputes decisions.
    NEVER calls pipeline.run_once() from this path.
    """

    def serve(
        self,
        merchant_id: str,
        emergency_features: dict | None = None,
    ) -> dict:
        """Serve pre-computed decisions via fallback chain.

        Fallback chain (strict order):
          1. Try Redis: read_serving_cache(merchant_id, "deep")
          2. If Redis miss: try DB: fetch_serving_cache(merchant_id, "deep")
          3. If DB miss: raise HTTPException(503, "No cached decisions available")

        NEVER calls pipeline.run_once() from this path.

        If emergency_features provided: apply deterministic reweighting.
        Reweighting uses only explicit numeric fields (u_base, u_ucb, risk_penalty).
        NEVER parses trace text fields for numeric scoring.

        Returns only eligible actions (filters out -inf scored actions).
        Adds latency measurement and logs it.
        """
        t0 = time.perf_counter()
        source = "redis"

        # 1. Try Redis
        cached_data = redis_cache.read_serving_cache(merchant_id, "deep")
        actions = None
        policy_version = "unknown"

        if cached_data:
            actions = cached_data.get("ranked_actions", [])
            policy_version = cached_data.get("policy_version", "unknown")
        else:
            # 2. Try DB
            source = "db"
            db_cached = db_client.fetch_serving_cache(merchant_id, "deep")
            if db_cached:
                actions = db_cached
                policy_version = "db_fallback"

        # 3. No cache → 503
        if not actions:
            raise HTTPException(
                status_code=503,
                detail="No cached decisions available",
            )

        # Filter out -inf scored actions
        eligible = [
            a for a in actions
            if a.get("eligible", True)
            and a.get("final_score", 0) != float("-inf")
        ]

        # Apply emergency reweighting if features provided
        if emergency_features:
            eligible = self._emergency_reweight(eligible, emergency_features)

        latency_ms = (time.perf_counter() - t0) * 1000
        log.info(
            "[fast_plane] %s served from %s in %.1fms policy=%s",
            merchant_id, source, latency_ms, policy_version,
        )

        return {
            "merchant_id": merchant_id,
            "mode": "emergency" if emergency_features else "fast",
            "source": source,
            "policy_version": policy_version,
            "latency_ms": round(latency_ms, 2),
            "top_actions": eligible[:3],
        }

    def _emergency_reweight(
        self,
        actions: list[dict],
        features: dict,
    ) -> list[dict]:
        """Lightweight deterministic reweighting.

        Features (all optional, float -1 to 1):
          margin_bias: positive = prefer higher base utility
          risk_bias: positive = penalize risk more heavily
          urgency_bias: positive = prefer exploitation over exploration

        emergency_score = 0.65 * adjusted_base + 0.25 * adjusted_ucb - 0.10 * adjusted_risk

        Clamp all biases to [-1, 1].
        Uses ONLY explicit numeric fields (u_base, u_ucb, risk_penalty).
        NEVER parses trace text fields for numeric scoring.
        """
        margin_bias = max(-1.0, min(1.0, float(features.get("margin_bias", 0.0))))
        risk_bias = max(-1.0, min(1.0, float(features.get("risk_bias", 0.0))))
        urgency_bias = max(-1.0, min(1.0, float(features.get("urgency_bias", 0.0))))

        reweighted = []
        for a in actions:
            u_base = float(a.get("u_base", 0.0))
            u_ucb = float(a.get("u_ucb", 0.0))
            risk_p = float(a.get("risk_penalty", 0.0))
            original = float(a.get("final_score", 0.0))

            adjusted_base = u_base * (1.0 + 0.3 * margin_bias)
            adjusted_ucb = u_ucb * (1.0 - 0.5 * urgency_bias)
            adjusted_risk = risk_p * (1.0 + 0.5 * risk_bias)

            emergency_score = (
                0.65 * adjusted_base
                + 0.25 * adjusted_ucb
                - 0.10 * adjusted_risk
            )

            entry = dict(a)
            entry["emergency_score"] = round(emergency_score, 6)
            entry["original_score"] = original
            reweighted.append(entry)

        reweighted.sort(
            key=lambda z: z.get("emergency_score", 0), reverse=True,
        )
        return reweighted
