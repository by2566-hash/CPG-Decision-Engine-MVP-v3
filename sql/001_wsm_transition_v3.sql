-- ── Layer 5 · WSM Transition Table (V3) ──────────────────────────────────
-- S/A/R/S' transition log with V3 schema additions.
-- Reference: V2/sql/wsm_transition_v2 — extended with new fields.
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS wsm_transitions_v3 (
    transition_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id         VARCHAR(64) NOT NULL,
    module              VARCHAR(32) NOT NULL,       -- acquisition/conversion/retention/promotion
    card_id             VARCHAR(128),

    -- State transition (S → S')
    state_before        JSONB NOT NULL,             -- MSM snapshot before action
    action_taken        JSONB NOT NULL,             -- recommended action
    state_after         JSONB,                      -- MSM snapshot after (backfilled)

    -- V3 additions (must exist Day 1)
    was_executed        BOOLEAN DEFAULT FALSE,
    executed_at         TIMESTAMP WITH TIME ZONE,
    execution_params    JSONB,                      -- actual params (may differ from recommendation)
    baseline_snapshot   JSONB,                      -- 30d rolling metrics at time of execution
    outcome_delta       JSONB,                      -- actual results vs baseline (backfilled 30d later)
    verification_chain  JSONB NOT NULL,             -- full DecisionVerifier trace
    impact_estimate     JSONB NOT NULL,             -- { conservative, expected, optimistic, confidence }
    counterfactual      JSONB,                      -- runner-up action and reason not chosen
    reward_status       VARCHAR(16) DEFAULT 'pending', -- pending → proxy → final
    reward_value        FLOAT,
    planner_policy_version VARCHAR(64),
    urgency_score       FLOAT,                        -- 0.0–1.0 from MSM urgency computation
    msm_dimension       VARCHAR(32),                  -- which MSM dimension triggered this action
    msm_state           VARCHAR(16),                  -- dimension state at decision time

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- TODO: Add indexes for common query patterns
-- CREATE INDEX idx_wsm_merchant_module ON wsm_transitions_v3(merchant_id, module);
-- CREATE INDEX idx_wsm_reward_status ON wsm_transitions_v3(reward_status);
