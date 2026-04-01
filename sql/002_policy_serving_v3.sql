-- ── Layer 2 · Policy Pack Serving Table ──────────────────────────────────
-- Merchant-level policy configurations (β weights, risk budget, etc.).
-- Versioned — every update creates a new version row.
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS policy_packs_v3 (
    policy_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id         VARCHAR(64) NOT NULL,
    policy_version      VARCHAR(64) NOT NULL,       -- e.g., '2026-03-24_m001'
    is_active           BOOLEAN DEFAULT TRUE,

    -- Scoring weights (β formula)
    beta1_kg_weight     FLOAT NOT NULL DEFAULT 1.0,
    beta2_bandit_weight FLOAT NOT NULL DEFAULT 0.0, -- 0 until Phase 3
    beta3_risk_weight   FLOAT NOT NULL DEFAULT 1.0,

    -- Budgets
    risk_budget         FLOAT DEFAULT 0.5,
    exploration_budget  FLOAT DEFAULT 0.0,          -- 0 until Phase 3

    -- Full config
    config_json         JSONB,

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(merchant_id, policy_version)
);

-- TODO: Add index for active policy lookup
-- CREATE INDEX idx_policy_active ON policy_packs_v3(merchant_id, is_active) WHERE is_active = TRUE;
