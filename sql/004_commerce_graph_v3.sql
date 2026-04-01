-- ── Layer 0 · Commerce Graph Tables ──────────────────────────────────────
-- DynamoDB adjacency list fallback in PostgreSQL.
-- Nodes: Merchant · Product · Category · CustomerSegment · Action · Outcome
-- MVP storage — Neptune migration is NOT in V3 scope.
-- ──────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS commerce_graph_nodes_v3 (
    node_id             VARCHAR(128) PRIMARY KEY,
    node_type           VARCHAR(32) NOT NULL,       -- merchant/product/category/customer_segment/action/outcome
    merchant_id         VARCHAR(64) NOT NULL,
    attributes          JSONB DEFAULT '{}',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS commerce_graph_edges_v3 (
    edge_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           VARCHAR(128) NOT NULL REFERENCES commerce_graph_nodes_v3(node_id),
    target_id           VARCHAR(128) NOT NULL REFERENCES commerce_graph_nodes_v3(node_id),
    edge_type           VARCHAR(64) NOT NULL,
    attributes          JSONB DEFAULT '{}',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(source_id, target_id, edge_type)
);

-- TODO: Add indexes for graph traversal queries
-- CREATE INDEX idx_graph_edges_source ON commerce_graph_edges_v3(source_id);
-- CREATE INDEX idx_graph_edges_target ON commerce_graph_edges_v3(target_id);
-- CREATE INDEX idx_graph_nodes_type ON commerce_graph_nodes_v3(node_type, merchant_id);
