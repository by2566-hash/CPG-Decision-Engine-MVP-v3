-- ── Layer 2 · Bandit Model State (Phase 3) ───────────────────────────────
-- Persists LinUCB arm parameters (A matrix, b vector) per merchant.
-- Only populated when Phase 3 data prerequisites are met.
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bandit_model_state_v3 (
    model_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id         VARCHAR(64) NOT NULL,
    arm_id              VARCHAR(128) NOT NULL,      -- action identifier
    context_dim         INTEGER NOT NULL,

    -- LinUCB parameters
    a_matrix            BYTEA,                      -- serialized A matrix (d×d)
    b_vector            BYTEA,                      -- serialized b vector (d×1)
    num_pulls           INTEGER DEFAULT 0,
    total_reward        FLOAT DEFAULT 0.0,

    -- Metadata
    last_updated        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(merchant_id, arm_id)
);

-- TODO: Add index for merchant arm lookup
-- CREATE INDEX idx_bandit_merchant ON bandit_model_state_v3(merchant_id);
