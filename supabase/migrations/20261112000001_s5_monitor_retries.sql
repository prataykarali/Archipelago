-- S5 monitor retry and success timestamps; no academic or S4 tables are changed.
ALTER TABLE research_intelligence.s5_monitors
    ADD COLUMN IF NOT EXISTS consecutive_failures integer NOT NULL DEFAULT 0
        CHECK (consecutive_failures >= 0),
    ADD COLUMN IF NOT EXISTS lease_started_at timestamptz,
    ADD COLUMN IF NOT EXISTS last_success_at timestamptz;
