-- Table: ai_response_cache
-- Fields: id, cache_key, normalized_query, query_hash, response (jsonb), sources (jsonb), graph_data (jsonb), roadmap_data (jsonb), model_version, graph_version, prompt_version, library_version, created_at, expires_at, hit_count, last_hit_at
-- Indexes: cache_key (unique), query_hash, expires_at
-- RLS: Service role only (no public access)

CREATE TABLE IF NOT EXISTS ai_response_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT UNIQUE NOT NULL,
    normalized_query TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    response JSONB,
    sources JSONB,
    graph_data JSONB,
    roadmap_data JSONB,
    model_version TEXT,
    graph_version TEXT,
    prompt_version TEXT,
    library_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_hit_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ai_response_cache_query_hash ON ai_response_cache(query_hash);
CREATE INDEX IF NOT EXISTS idx_ai_response_cache_expires_at ON ai_response_cache(expires_at);

ALTER TABLE ai_response_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY service_role_only_policy ON ai_response_cache
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
