"""Thin database client for WSM, policies, dedup, and bandit state.

Uses raw psycopg (sync) to avoid heavy ORM overhead for this slice.
Falls back to SQLite for tests when POSTGRES_DSN starts with 'sqlite'.

V3 additions over V2:
  - insert_wsm_transition extended with V3 fields
  - update_wsm_execution (idempotent)
  - update_wsm_outcome_delta (idempotent)
  - upsert_merchant_state_vector
  - fetch_latest_merchant_state
  - fetch_wsm_for_billing
  - fetch_baseline_for_merchant
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import text

from .config import settings
from .contracts import MerchantStateVector

log = logging.getLogger(__name__)

_engine: Optional[sa.Engine] = None


def _get_engine() -> sa.Engine:
    global _engine
    if _engine is None:
        _engine = sa.create_engine(
            settings.postgres_dsn,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=2,
        )
    return _engine


def set_engine(engine: sa.Engine) -> None:
    """Allow tests to inject an in-memory engine."""
    global _engine
    _engine = engine


@contextmanager
def _conn():
    engine = _get_engine()
    with engine.connect() as c:
        yield c
        c.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── WSM transitions ────────────────────────────────────────────────

def insert_wsm_transition(
    *,
    merchant_id: str,
    vertical: str,
    decision_mode: str,
    s_json: dict,
    action_id: str,
    action_family: str,
    action_params_json: dict,
    constraints_passed: bool,
    violations_json: list | None = None,
    base_utility_score: float | None = None,
    bandit_ucb_score: float | None = None,
    final_rank_score: float | None = None,
    planner_policy_version: str | None = None,
    bandit_model_version: str | None = None,
    data_quality_flags: dict | None = None,
    # ── V3 new fields (all optional, None default) ───────────────
    was_executed: bool | None = None,
    executed_at: datetime | None = None,
    execution_params: dict | None = None,
    baseline_snapshot: dict | None = None,
    verification_chain: dict | None = None,
    impact_estimate: dict | None = None,
    counterfactual: dict | None = None,
    outcome_delta: dict | None = None,
    urgency_score: float | None = None,
    module: str | None = None,
    msm_dimension: str | None = None,
    msm_state: str | None = None,
) -> int:
    """Insert an (S, A) transition; R and S' are NULL until reward backfill.

    V3 extension: accepts additional fields for verification chain,
    impact estimates, counterfactuals, and MSM context.
    """
    with _conn() as c:
        row = c.execute(
            text("""
                INSERT INTO wsm_transitions_v3
                    (merchant_id, vertical, decision_mode, decision_ts,
                     s_json, action_id, action_family, action_params_json,
                     constraints_passed, violations_json,
                     base_utility_score, bandit_ucb_score, final_rank_score,
                     planner_policy_version, bandit_model_version,
                     was_executed, executed_at, execution_params,
                     baseline_snapshot, verification_chain,
                     impact_estimate, counterfactual, outcome_delta,
                     urgency_score, module, msm_dimension, msm_state)
                VALUES
                    (:mid, :vert, :dm, :ts,
                     :s, :aid, :af, :ap,
                     :cp, :vj,
                     :bus, :buc, :frs,
                     :ppv, :bmv,
                     :we, :ea, :ep,
                     :bs, :vc,
                     :ie, :cf, :od,
                     :us, :mod, :md, :ms)
                RETURNING transition_id
            """),
            dict(
                mid=merchant_id, vert=vertical, dm=decision_mode, ts=_now(),
                s=json.dumps({**s_json, "_dq": data_quality_flags or {}}),
                aid=action_id, af=action_family,
                ap=json.dumps(action_params_json),
                cp=constraints_passed,
                vj=json.dumps(violations_json or []),
                bus=base_utility_score, buc=bandit_ucb_score, frs=final_rank_score,
                ppv=planner_policy_version, bmv=bandit_model_version,
                we=was_executed, ea=executed_at,
                ep=json.dumps(execution_params) if execution_params else None,
                bs=json.dumps(baseline_snapshot) if baseline_snapshot else None,
                vc=json.dumps(verification_chain) if verification_chain else None,
                ie=json.dumps(impact_estimate) if impact_estimate else None,
                cf=json.dumps(counterfactual) if counterfactual else None,
                od=json.dumps(outcome_delta) if outcome_delta else None,
                us=urgency_score, mod=module, md=msm_dimension, ms=msm_state,
            ),
        )
        tid = row.scalar_one()
        log.info("WSM transition %s written for %s/%s", tid, merchant_id, action_id)
        return tid


def fetch_transitions_pending_reward(
    min_age_hours: int = 24,
    max_age_hours: int = 24 * 30,
    reward_type: str = "proxy",
) -> List[Dict[str, Any]]:
    """Return transitions that need reward backfill.

    Uses reward_status column for clean, idempotent selection:
    * proxy  : reward_status='pending'  AND  age >= 24h
    * final  : reward_status='proxy'    AND  age >= 7d
    """
    if reward_type == "proxy":
        status_filter = "reward_status = 'pending'"
        age_hours = min_age_hours
    else:
        status_filter = "reward_status = 'proxy'"
        age_hours = max(min_age_hours, 168)  # 7 days minimum

    cutoff_recent = _now() - timedelta(hours=age_hours)
    cutoff_old = _now() - timedelta(hours=max_age_hours)

    with _conn() as c:
        rows = c.execute(
            text(f"""
                SELECT transition_id, merchant_id, vertical, s_json,
                       action_id, action_family, decision_ts,
                       planner_policy_version, base_utility_score,
                       bandit_ucb_score, final_rank_score,
                       reward_status
                FROM wsm_transitions_v3
                WHERE {status_filter}
                  AND constraints_passed = TRUE
                  AND decision_ts < :cutoff_recent
                  AND decision_ts > :cutoff_old
                ORDER BY decision_ts
                LIMIT 500
            """),
            dict(cutoff_recent=cutoff_recent, cutoff_old=cutoff_old),
        )
        return [dict(r._mapping) for r in rows.fetchall()]


def update_wsm_reward(
    transition_id: int,
    reward_json: dict,
    reward_composite: float,
    sp_json: dict,
    reward_status: str = "proxy",
) -> None:
    """Backfill reward R, next-state S', and reward_status on a transition.

    reward_status must be 'proxy' or 'final'.  The transition is only
    updated if it hasn't already been promoted to a higher status
    (final > proxy > pending), making the call idempotent.
    """
    with _conn() as c:
        c.execute(
            text("""
                UPDATE wsm_transitions_v3
                SET reward_json        = :rj,
                    reward_composite   = :rc,
                    reward_observed_ts = :ts,
                    sp_json            = :sp,
                    reward_status      = :rs
                WHERE transition_id = :tid
                  AND reward_status != 'final'
            """),
            dict(
                rj=json.dumps(reward_json),
                rc=reward_composite,
                ts=_now(),
                sp=json.dumps(sp_json),
                rs=reward_status,
                tid=transition_id,
            ),
        )
        log.info("WSM reward updated for transition %s (status=%s, composite=%.4f)",
                 transition_id, reward_status, reward_composite)


# ── V3 new WSM functions ───────────────────────────────────────────

def update_wsm_execution(transition_id: int, execution_params: dict) -> None:
    """Set was_executed=True, executed_at=now(), execution_params.

    Idempotent: if already executed (was_executed=TRUE), does NOT overwrite.
    """
    with _conn() as c:
        c.execute(
            text("""
                UPDATE wsm_transitions_v3
                SET was_executed     = TRUE,
                    executed_at      = :ts,
                    execution_params = :ep
                WHERE transition_id = :tid
                  AND (was_executed = FALSE OR was_executed IS NULL)
            """),
            dict(
                ts=_now(),
                ep=json.dumps(execution_params),
                tid=transition_id,
            ),
        )


def update_wsm_outcome_delta(transition_id: int, outcome_delta: dict) -> None:
    """Backfill outcome_delta field.

    Only updates if outcome_delta IS NULL (idempotent).
    """
    with _conn() as c:
        c.execute(
            text("""
                UPDATE wsm_transitions_v3
                SET outcome_delta = :od
                WHERE transition_id = :tid
                  AND outcome_delta IS NULL
            """),
            dict(
                od=json.dumps(outcome_delta),
                tid=transition_id,
            ),
        )


def upsert_merchant_state_vector(msv: MerchantStateVector) -> None:
    """Upsert into merchant_state_vector table.

    Uses merchant_id + computed_at as unique key.
    """
    with _conn() as c:
        c.execute(
            text("""
                INSERT INTO merchant_state_vector
                    (merchant_id, computed_at,
                     acquisition_state, conversion_state,
                     retention_state, promotion_state,
                     acquisition_urgency, conversion_urgency,
                     retention_urgency, promotion_urgency,
                     metrics_snapshot)
                VALUES
                    (:mid, :ca,
                     :as_, :cs,
                     :rs, :ps,
                     :au, :cu,
                     :ru, :pu,
                     :ms)
                ON CONFLICT (merchant_id, computed_at) DO UPDATE
                    SET acquisition_state   = EXCLUDED.acquisition_state,
                        conversion_state    = EXCLUDED.conversion_state,
                        retention_state     = EXCLUDED.retention_state,
                        promotion_state     = EXCLUDED.promotion_state,
                        acquisition_urgency = EXCLUDED.acquisition_urgency,
                        conversion_urgency  = EXCLUDED.conversion_urgency,
                        retention_urgency   = EXCLUDED.retention_urgency,
                        promotion_urgency   = EXCLUDED.promotion_urgency,
                        metrics_snapshot    = EXCLUDED.metrics_snapshot
            """),
            dict(
                mid=msv.merchant_id, ca=msv.computed_at,
                as_=msv.acquisition_state, cs=msv.conversion_state,
                rs=msv.retention_state, ps=msv.promotion_state,
                au=msv.acquisition_urgency, cu=msv.conversion_urgency,
                ru=msv.retention_urgency, pu=msv.promotion_urgency,
                ms=json.dumps(msv.metrics_snapshot) if msv.metrics_snapshot else None,
            ),
        )


def fetch_latest_merchant_state(merchant_id: str) -> dict | None:
    """Return the most recent merchant_state_vector row, or None."""
    with _conn() as c:
        row = c.execute(
            text("""
                SELECT merchant_id, computed_at,
                       acquisition_state, conversion_state,
                       retention_state, promotion_state,
                       acquisition_urgency, conversion_urgency,
                       retention_urgency, promotion_urgency,
                       metrics_snapshot
                FROM merchant_state_vector
                WHERE merchant_id = :mid
                ORDER BY computed_at DESC
                LIMIT 1
            """),
            dict(mid=merchant_id),
        ).fetchone()
        if row is None:
            return None
        d = dict(row._mapping)
        if isinstance(d.get("metrics_snapshot"), str):
            d["metrics_snapshot"] = json.loads(d["metrics_snapshot"])
        return d


def _parse_json_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        return json.loads(value) if value else {}
    return dict(value)


def _json_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def fetch_latest_partner_signal_snapshot(user_id: str) -> dict | None:
    """Return latest partner signal data for a frontend user_id.

    Partner schema currently exposes user_id, not merchant_id. Day-1 runtime
    maps user_id directly to merchant_id at the API/adapter boundary.
    """
    with _conn() as c:
        health_row = c.execute(
            text("""
                SELECT user_id, metric_snapshot, calculated_at
                FROM decision_health_score
                WHERE user_id = :uid
                ORDER BY calculated_at DESC
                LIMIT 1
            """),
            dict(uid=user_id),
        ).fetchone()

        signals: dict[str, Any] = {}
        calculated_at = None
        if health_row is not None:
            health = dict(health_row._mapping)
            signals.update(_parse_json_mapping(health.get("metric_snapshot")))
            calculated_at = health.get("calculated_at")

        metric_rows = c.execute(
            text("""
                SELECT metric_name, metric_value, metric_unit, dimension,
                       metric_date, metadata_json
                FROM decision_metric_value
                WHERE user_id = :uid
                ORDER BY metric_date DESC
            """),
            dict(uid=user_id),
        ).fetchall()

        seen_metric_names: set[str] = set()
        for row in metric_rows:
            metric = dict(row._mapping)
            metric_name = metric.get("metric_name")
            if not metric_name or metric_name in seen_metric_names:
                continue
            seen_metric_names.add(metric_name)
            signals[str(metric_name)] = _json_scalar(metric.get("metric_value"))

        if not signals:
            return None

        merchant_id = str(signals.get("merchant_id") or user_id)
        brand_id = str(signals.get("brand_id") or signals.get("brand") or merchant_id)

        return {
            "user_id": user_id,
            "merchant_id": merchant_id,
            "brand_id": brand_id,
            "signals": signals,
            "data_source": "decision_health_score+decision_metric_value",
            "calculated_at": calculated_at,
        }


def fetch_wsm_for_billing(
    merchant_id: str,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Return was_executed=True transitions with outcome_delta populated.

    Used by billing engine in Phase 2 to compute performance fees.
    """
    with _conn() as c:
        rows = c.execute(
            text("""
                SELECT transition_id, merchant_id, decision_ts,
                       action_id, action_family, outcome_delta,
                       impact_estimate, planner_policy_version,
                       was_executed, executed_at, execution_params
                FROM wsm_transitions_v3
                WHERE merchant_id = :mid
                  AND was_executed = TRUE
                  AND outcome_delta IS NOT NULL
                  AND decision_ts >= :sd
                  AND decision_ts <= :ed
                ORDER BY decision_ts
            """),
            dict(mid=merchant_id, sd=start_date, ed=end_date),
        )
        result = []
        for r in rows.fetchall():
            d = dict(r._mapping)
            for json_col in ("outcome_delta", "impact_estimate", "execution_params"):
                if isinstance(d.get(json_col), str):
                    d[json_col] = json.loads(d[json_col])
            result.append(d)
        return result


def fetch_baseline_for_merchant(merchant_id: str, days: int = 30) -> dict:
    """Return rolling N-day average of key metrics from baseline_snapshot.

    Aggregates non-null baseline_snapshot fields across recent transitions.
    Used by ImpactCalculator and billing engine.
    """
    cutoff = _now() - timedelta(days=days)
    with _conn() as c:
        rows = c.execute(
            text("""
                SELECT baseline_snapshot
                FROM wsm_transitions_v3
                WHERE merchant_id = :mid
                  AND baseline_snapshot IS NOT NULL
                  AND decision_ts > :cutoff
                ORDER BY decision_ts DESC
            """),
            dict(mid=merchant_id, cutoff=cutoff),
        )
        snapshots = []
        for r in rows.fetchall():
            raw = r[0]
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if parsed:
                snapshots.append(parsed)

    if not snapshots:
        return {}

    # Average all numeric fields across snapshots
    all_keys: set[str] = set()
    for snap in snapshots:
        all_keys.update(snap.keys())

    averages: dict[str, Any] = {}
    for key in all_keys:
        values = []
        for snap in snapshots:
            v = snap.get(key)
            if isinstance(v, (int, float)):
                values.append(v)
        if values:
            averages[key] = sum(values) / len(values)

    averages["_snapshot_count"] = len(snapshots)
    averages["_days"] = days
    return averages


# ── Event dedup ─────────────────────────────────────────────────────

def check_and_insert_dedup(dedup_key: str) -> bool:
    """Atomic check-and-insert.  Returns True if key already existed (= duplicate)."""
    with _conn() as c:
        row = c.execute(
            text("""
                INSERT INTO event_dedup (dedup_key, first_seen_at)
                VALUES (:dk, :ts)
                ON CONFLICT (dedup_key) DO NOTHING
                RETURNING dedup_key
            """),
            dict(dk=dedup_key, ts=_now()),
        )
        inserted = row.fetchone() is not None
        return not inserted  # True = duplicate (nothing was inserted)


# ── Planner policy pack ────────────────────────────────────────────

def upsert_policy_pack(
    policy_version: str,
    merchant_id: str,
    payload_json: dict,
    expires_at: datetime | None = None,
) -> None:
    with _conn() as c:
        c.execute(
            text("""
                INSERT INTO planner_policy_pack (merchant_id, policy_version, payload_json, expires_at)
                VALUES (:mid, :pv, :pj, :ea)
                ON CONFLICT (merchant_id, policy_version) DO UPDATE
                    SET payload_json = EXCLUDED.payload_json,
                        expires_at   = EXCLUDED.expires_at
            """),
            dict(pv=policy_version, mid=merchant_id, pj=json.dumps(payload_json), ea=expires_at),
        )


def fetch_latest_policy(merchant_id: str) -> Optional[Dict]:
    """Return the most recent non-expired policy pack for fallback."""
    now = _now()
    with _conn() as c:
        row = c.execute(
            text("""
                SELECT payload_json FROM planner_policy_pack
                WHERE merchant_id = :mid
                  AND (expires_at IS NULL OR expires_at > :now)
                ORDER BY created_at DESC LIMIT 1
            """),
            dict(mid=merchant_id, now=now),
        )
        r = row.fetchone()
        return json.loads(r[0]) if r else None


# ── Bandit state ────────────────────────────────────────────────────

def upsert_bandit_arm(
    arm_key: str,
    vertical: str,
    action_family: str,
    d: int,
    alpha: float,
    a_matrix_json: list,
    b_vector_json: list,
    num_pulls: int = 0,
    model_version: str | None = None,
) -> None:
    with _conn() as c:
        c.execute(
            text("""
                INSERT INTO bandit_model_state
                    (arm_key, vertical, action_family, d, alpha,
                     a_matrix_json, b_vector_json, num_pulls, model_version, updated_at)
                VALUES
                    (:ak, :v, :af, :d, :a, :am, :bv, :np, :mv, :ts)
                ON CONFLICT (arm_key) DO UPDATE
                    SET a_matrix_json = EXCLUDED.a_matrix_json,
                        b_vector_json = EXCLUDED.b_vector_json,
                        num_pulls     = EXCLUDED.num_pulls,
                        model_version = EXCLUDED.model_version,
                        updated_at    = EXCLUDED.updated_at
            """),
            dict(
                ak=arm_key, v=vertical, af=action_family,
                d=d, a=alpha,
                am=json.dumps(a_matrix_json),
                bv=json.dumps(b_vector_json),
                np=num_pulls, mv=model_version, ts=_now(),
            ),
        )


def fetch_all_bandit_arms() -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(text("SELECT * FROM bandit_model_state"))
        out = []
        for r in rows.fetchall():
            d = dict(r._mapping)
            if isinstance(d["a_matrix_json"], str):
                d["a_matrix_json"] = json.loads(d["a_matrix_json"])
            if isinstance(d["b_vector_json"], str):
                d["b_vector_json"] = json.loads(d["b_vector_json"])
            out.append(d)
        return out


# ── Serving rank cache ──────────────────────────────────────────────

def upsert_serving_cache(
    merchant_id: str,
    decision_mode: str,
    ranked_actions_json: list,
    policy_version: str,
) -> None:
    with _conn() as c:
        c.execute(
            text("""
                INSERT INTO serving_rank_cache
                    (merchant_id, decision_mode, ranked_actions_json, policy_version, generated_at)
                VALUES (:mid, :dm, :raj, :pv, :ts)
                ON CONFLICT (merchant_id, decision_mode) DO UPDATE
                    SET ranked_actions_json = EXCLUDED.ranked_actions_json,
                        policy_version      = EXCLUDED.policy_version,
                        generated_at        = EXCLUDED.generated_at
            """),
            dict(
                mid=merchant_id, dm=decision_mode,
                raj=json.dumps(ranked_actions_json),
                pv=policy_version, ts=_now(),
            ),
        )


def fetch_serving_cache(merchant_id: str, decision_mode: str = "deep") -> Optional[list]:
    with _conn() as c:
        row = c.execute(
            text("""
                SELECT ranked_actions_json FROM serving_rank_cache
                WHERE merchant_id = :mid AND decision_mode = :dm
            """),
            dict(mid=merchant_id, dm=decision_mode),
        )
        r = row.fetchone()
        if r is None:
            return None
        v = r[0]
        return json.loads(v) if isinstance(v, str) else v


# ── WSM observed rewards for bandit ────────────────────────────────

def fetch_wsm_with_rewards(since_hours: int = 24) -> List[Dict[str, Any]]:
    """Return recently-rewarded transitions for bandit training."""
    cutoff = _now() - timedelta(hours=since_hours)
    with _conn() as c:
        rows = c.execute(
            text("""
                SELECT transition_id, merchant_id, vertical,
                       action_id, action_family,
                       s_json, reward_composite,
                       base_utility_score, bandit_ucb_score
                FROM wsm_transitions_v3
                WHERE reward_observed_ts IS NOT NULL
                  AND reward_observed_ts > :cutoff
                  AND reward_composite IS NOT NULL
                ORDER BY reward_observed_ts
                LIMIT 1000
            """),
            dict(cutoff=cutoff),
        )
        return [dict(r._mapping) for r in rows.fetchall()]


# ── Transition lookup ──────────────────────────────────────────────

def fetch_transition_by_id(transition_id: int) -> dict | None:
    """Fetch a single WSM transition row by primary key.

    Returns dict with keys: transition_id, merchant_id, action_id, was_executed,
    action_params (parsed from action_params_json).
    Returns None if not found.
    Used by /approve endpoint for ownership validation and discount_pct mismatch check.
    """
    with _conn() as c:
        row = c.execute(
            text("""
                SELECT transition_id, merchant_id, action_id, was_executed,
                       action_params_json
                FROM wsm_transitions_v3
                WHERE transition_id = :tid
            """),
            dict(tid=transition_id),
        ).fetchone()
        if row is None:
            return None
        d = dict(row._mapping)
        raw = d.pop("action_params_json", None)
        d["action_params"] = json.loads(raw) if isinstance(raw, str) else (raw or {})
        return d


def rollback_wsm_execution(transition_id: int, execution_params: dict) -> None:
    """Set was_executed=False after a rollback.

    Unconditional update — rolls back regardless of current was_executed state.
    Called only by the rollback endpoint after TTL + ownership validation passes.
    """
    with _conn() as c:
        c.execute(
            text("""
                UPDATE wsm_transitions_v3
                SET was_executed     = FALSE,
                    executed_at      = NULL,
                    execution_params = :ep
                WHERE transition_id = :tid
            """),
            dict(
                ep=json.dumps(execution_params),
                tid=transition_id,
            ),
        )
        log.info("WSM rollback written for transition %s", transition_id)


# ── Readiness check helpers ────────────────────────────────────────

def fetch_latest_wsm_timestamp(merchant_id: str) -> datetime | None:
    """Return the most recent decision_ts for a merchant, or None."""
    with _conn() as c:
        row = c.execute(
            text("""
                SELECT MAX(decision_ts) AS latest
                FROM wsm_transitions_v3
                WHERE merchant_id = :mid
                  AND decision_mode != 'webhook_observation'
            """),
            dict(mid=merchant_id),
        ).fetchone()
        if row and row[0]:
            v = row[0]
            dt = datetime.fromisoformat(v) if isinstance(v, str) else v
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        return None


def fetch_latest_bandit_timestamp() -> datetime | None:
    """Return the most recent bandit model update timestamp, or None."""
    with _conn() as c:
        row = c.execute(
            text("SELECT MAX(updated_at) AS latest FROM bandit_model_state")
        ).fetchone()
        if row and row[0]:
            v = row[0]
            return datetime.fromisoformat(v) if isinstance(v, str) else v
        return None


def fetch_constraint_violation_rate(merchant_id: str) -> dict | None:
    """Return {total, violated, violation_rate} for recent decisions."""
    with _conn() as c:
        row = c.execute(
            text("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN constraints_passed = 0 THEN 1 ELSE 0 END) AS violated
                FROM wsm_transitions_v3
                WHERE merchant_id = :mid
                  AND decision_mode = 'deep'
            """),
            dict(mid=merchant_id),
        ).fetchone()
        if row and row[0] and row[0] > 0:
            total, violated = int(row[0]), int(row[1] or 0)
            return {"total": total, "violated": violated,
                    "violation_rate": violated / total}
        return None
