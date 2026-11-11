-- Private, server-owned Research Intelligence records. Never expose this schema
-- through PostgREST or grant browser roles direct table access.
CREATE SCHEMA IF NOT EXISTS research_intelligence;
REVOKE ALL ON SCHEMA research_intelligence FROM PUBLIC;

CREATE TABLE IF NOT EXISTS research_intelligence.jobs (
    job_id uuid PRIMARY KEY,
    user_id text NOT NULL,
    role text NOT NULL,
    topic text NOT NULL,
    idempotency_key text NOT NULL,
    pipeline_version text NOT NULL,
    status text NOT NULL,
    stage text NOT NULL,
    counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    shortlist jsonb NOT NULL DEFAULT '[]'::jsonb,
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS research_intelligence.source_snapshots (
    job_id uuid NOT NULL REFERENCES research_intelligence.jobs(job_id),
    source text NOT NULL,
    requested_at timestamptz NOT NULL,
    status text NOT NULL,
    response_sha256 text,
    response_body bytea,
    request_id text,
    http_status integer,
    record_count integer NOT NULL,
    error text,
    PRIMARY KEY (job_id, source)
);

CREATE TABLE IF NOT EXISTS research_intelligence.papers (
    paper_id uuid PRIMARY KEY,
    paper jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research_intelligence.paper_identifiers (
    kind text NOT NULL,
    value text NOT NULL,
    paper_id uuid NOT NULL REFERENCES research_intelligence.papers(paper_id),
    PRIMARY KEY (kind, value)
);

CREATE TABLE IF NOT EXISTS research_intelligence.job_papers (
    job_id uuid NOT NULL REFERENCES research_intelligence.jobs(job_id),
    paper_id uuid NOT NULL REFERENCES research_intelligence.papers(paper_id),
    pipeline_state text NOT NULL,
    access_state text NOT NULL,
    identity_review jsonb NOT NULL DEFAULT '[]'::jsonb,
    merge_history jsonb NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (job_id, paper_id)
);

CREATE TABLE IF NOT EXISTS research_intelligence.paper_evidence (
    paper_id uuid NOT NULL REFERENCES research_intelligence.papers(paper_id),
    artifact_sha256 text NOT NULL,
    evidence jsonb NOT NULL,
    verification_state text NOT NULL,
    PRIMARY KEY (paper_id, artifact_sha256)
);

CREATE TABLE IF NOT EXISTS research_intelligence.feature_observations (
    job_id uuid NOT NULL REFERENCES research_intelligence.jobs(job_id),
    paper_id uuid NOT NULL REFERENCES research_intelligence.papers(paper_id),
    feature_name text NOT NULL,
    observation jsonb NOT NULL,
    PRIMARY KEY (job_id, paper_id, feature_name)
);

CREATE TABLE IF NOT EXISTS research_intelligence.audit (
    audit_id bigserial PRIMARY KEY,
    user_id text,
    role text,
    action text NOT NULL,
    research_job_id uuid,
    topic text,
    timestamp timestamptz NOT NULL DEFAULT now(),
    result text NOT NULL
);

CREATE TABLE IF NOT EXISTS research_intelligence.projection_events (
    event_key text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    output_path text,
    error text
);

CREATE TABLE IF NOT EXISTS research_intelligence.tracked_topics (
    topic_id uuid PRIMARY KEY,
    user_id text NOT NULL,
    role text NOT NULL,
    topic text NOT NULL,
    normalized_topic text NOT NULL,
    pinned boolean NOT NULL DEFAULT false,
    refresh_hours integer,
    last_searched_at timestamptz NOT NULL DEFAULT now(),
    next_refresh_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, normalized_topic)
);

ALTER TABLE research_intelligence.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.source_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.paper_identifiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.job_papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.paper_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.feature_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.projection_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.tracked_topics ENABLE ROW LEVEL SECURITY;
