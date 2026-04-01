"""Shared test fixtures: in-memory SQLite engine with V3 schema applied.

Includes all V2 tables (backward compatibility) plus V3 extensions:
  - wsm_transitions_v3: V2 columns + V3 new fields (was_executed, verification_chain, etc.)
  - merchant_state_vector: MSM 4-dimension state snapshots
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

# Ensure project root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.decision_engine import db_client


# ── SQL DDL (SQLite-compatible) ─────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS wsm_transitions_v3 (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id VARCHAR(64) NOT NULL,
    vertical VARCHAR(32) NOT NULL,
    decision_mode VARCHAR(16) NOT NULL,
    decision_ts TIMESTAMP NOT NULL,
    s_json TEXT NOT NULL,
    action_id VARCHAR(128) NOT NULL,
    action_family VARCHAR(64) NOT NULL,
    action_params_json TEXT NOT NULL,
    constraints_passed BOOLEAN NOT NULL,
    violations_json TEXT,
    reward_json TEXT,
    reward_composite DOUBLE PRECISION,
    reward_observed_ts TIMESTAMP,
    reward_status VARCHAR(16) NOT NULL DEFAULT 'pending',
    sp_json TEXT,
    base_utility_score DOUBLE PRECISION,
    bandit_ucb_score DOUBLE PRECISION,
    final_rank_score DOUBLE PRECISION,
    planner_policy_version VARCHAR(64),
    bandit_model_version VARCHAR(64),
    -- V3 new fields (from 001_wsm_transition_v3.sql + CLAUDE.md WSM required fields)
    was_executed BOOLEAN DEFAULT FALSE,
    executed_at TIMESTAMP,
    execution_params TEXT,
    baseline_snapshot TEXT,
    outcome_delta TEXT,
    verification_chain TEXT,
    impact_estimate TEXT,
    counterfactual TEXT,
    reward_value DOUBLE PRECISION,
    urgency_score DOUBLE PRECISION,
    module VARCHAR(32),
    msm_dimension VARCHAR(32),
    msm_state VARCHAR(16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_dedup (
    dedup_key VARCHAR(256) PRIMARY KEY,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS planner_policy_pack (
    policy_version VARCHAR(64) PRIMARY KEY,
    merchant_id VARCHAR(64) NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS serving_rank_cache (
    merchant_id VARCHAR(64) NOT NULL,
    decision_mode VARCHAR(16) NOT NULL,
    ranked_actions_json TEXT NOT NULL,
    policy_version VARCHAR(64) NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (merchant_id, decision_mode)
);

CREATE TABLE IF NOT EXISTS bandit_model_state (
    arm_key VARCHAR(128) PRIMARY KEY,
    vertical VARCHAR(32) NOT NULL,
    action_family VARCHAR(64) NOT NULL,
    d INTEGER NOT NULL,
    alpha DOUBLE PRECISION NOT NULL,
    a_matrix_json TEXT NOT NULL,
    b_vector_json TEXT NOT NULL,
    num_pulls INTEGER DEFAULT 0,
    model_version VARCHAR(64),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS merchant_state_vector (
    merchant_id VARCHAR(64) NOT NULL,
    computed_at TIMESTAMP NOT NULL,
    acquisition_state VARCHAR(16),
    conversion_state VARCHAR(16),
    retention_state VARCHAR(16),
    promotion_state VARCHAR(16),
    acquisition_urgency DOUBLE PRECISION DEFAULT 0.0,
    conversion_urgency DOUBLE PRECISION DEFAULT 0.0,
    retention_urgency DOUBLE PRECISION DEFAULT 0.0,
    promotion_urgency DOUBLE PRECISION DEFAULT 0.0,
    metrics_snapshot TEXT,
    PRIMARY KEY (merchant_id, computed_at)
);
"""


@pytest.fixture(autouse=True)
def db_engine():
    """Create a fresh in-memory SQLite DB for every test.

    Uses StaticPool so all connections share the same in-memory database.
    """
    from sqlalchemy.pool import StaticPool

    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(sa.text(stmt))
        conn.commit()
    db_client.set_engine(engine)
    yield engine
    db_client.set_engine(None)
