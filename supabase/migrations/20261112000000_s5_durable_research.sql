-- S5 private snapshots. This schema is not exposed through PostgREST.
-- Apply only to the Archipelago Supabase project after its identity is verified.
CREATE SCHEMA IF NOT EXISTS research_intelligence;
REVOKE ALL ON SCHEMA research_intelligence FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS research_intelligence.s5_runs (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    schema_version text NOT NULL,
    topic text NOT NULL,
    payload jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS s5_runs_owner_created_idx
    ON research_intelligence.s5_runs (owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS research_intelligence.s5_monitors (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL,
    options jsonb NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    cadence_hours integer NOT NULL DEFAULT 24 CHECK (cadence_hours BETWEEN 1 AND 720),
    next_run_at timestamptz,
    last_run_id uuid REFERENCES research_intelligence.s5_runs(id),
    last_error text,
    lease_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS s5_monitors_due_idx
    ON research_intelligence.s5_monitors (next_run_at)
    WHERE enabled;
CREATE INDEX IF NOT EXISTS s5_monitors_owner_idx
    ON research_intelligence.s5_monitors (owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS research_intelligence.s5_monitor_history (
    id uuid PRIMARY KEY,
    monitor_id uuid NOT NULL REFERENCES research_intelligence.s5_monitors(id) ON DELETE CASCADE,
    owner_id uuid NOT NULL,
    run_id uuid REFERENCES research_intelligence.s5_runs(id),
    status text NOT NULL CHECK (status IN ('updated', 'unchanged', 'failed')),
    error_code text,
    started_at timestamptz NOT NULL,
    finished_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS s5_history_monitor_finished_idx
    ON research_intelligence.s5_monitor_history (monitor_id, finished_at DESC);

CREATE TABLE IF NOT EXISTS research_intelligence.s5_events (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL,
    monitor_id uuid NOT NULL REFERENCES research_intelligence.s5_monitors(id) ON DELETE CASCADE,
    run_id uuid REFERENCES research_intelligence.s5_runs(id),
    kind text NOT NULL,
    subject_id text NOT NULL,
    payload jsonb NOT NULL,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (monitor_id, kind, subject_id, run_id)
);
CREATE INDEX IF NOT EXISTS s5_events_owner_created_idx
    ON research_intelligence.s5_events (owner_id, created_at DESC);

ALTER TABLE research_intelligence.s5_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.s5_monitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.s5_monitor_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.s5_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA research_intelligence FROM PUBLIC, anon, authenticated;
