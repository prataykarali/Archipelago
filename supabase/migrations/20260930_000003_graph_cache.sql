-- Table: graph_cache
-- Fields: id, concept_id, graph_version, nodes (jsonb), edges (jsonb), roadmap (jsonb), created_at, expires_at
-- Index: (concept_id, graph_version) unique, expires_at

CREATE TABLE IF NOT EXISTS graph_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id TEXT NOT NULL,
    graph_version TEXT NOT NULL,
    nodes JSONB,
    edges JSONB,
    roadmap JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE(concept_id, graph_version)
);

CREATE INDEX IF NOT EXISTS idx_graph_cache_expires_at ON graph_cache(expires_at);
