-- Table: retrieval_cache  
-- Fields: id, query_hash, concept_ids (jsonb), document_ids (jsonb), graph_nodes (jsonb), graph_edges (jsonb), retrieval_version, graph_version, created_at, expires_at
-- Indexes: query_hash (unique), expires_at

CREATE TABLE IF NOT EXISTS retrieval_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash TEXT UNIQUE NOT NULL,
    concept_ids JSONB,
    document_ids JSONB,
    graph_nodes JSONB,
    graph_edges JSONB,
    retrieval_version TEXT,
    graph_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_retrieval_cache_expires_at ON retrieval_cache(expires_at);
