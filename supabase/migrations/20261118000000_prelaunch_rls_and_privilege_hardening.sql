-- Pre-launch security audit hardening migration (Check 4.5):
-- 1. Enable RLS on public.retrieval_cache, public.graph_cache,
--    research_intelligence.s6_library_events, and research_intelligence.s6_analytics_audit_log.
-- 2. Ensure schema completeness and RLS on public.archipelago_librarian_records,
--    public.archipelago_runtime_quota, and research_intelligence.okf_paper_records.
-- 3. Revoke over-permissive default PUBLIC / anon / authenticated grants on all
--    server-only tables and views; restrict to service_role.
-- 4. Harden SECURITY DEFINER functions (research_enqueue_job, s5_research_rpc)
--    with explicit pg_catalog search_path and runtime service_role verification,
--    and add owner-scoped delete_user_data support to s5_research_rpc.

CREATE TABLE IF NOT EXISTS public.archipelago_librarian_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_type text NOT NULL CHECK (record_type IN ('catalog', 'circulation', 'orders', 'fines')),
    record_key text NOT NULL CHECK (char_length(record_key) BETWEEN 1 AND 120),
    title text NOT NULL DEFAULT '' CHECK (char_length(title) <= 2000),
    status text NOT NULL DEFAULT '' CHECK (char_length(status) <= 2000),
    shelf text NOT NULL DEFAULT '' CHECK (char_length(shelf) <= 2000),
    note text NOT NULL DEFAULT '' CHECK (char_length(note) <= 2000),
    source_url text NOT NULL DEFAULT '' CHECK (
        source_url = '' OR (char_length(source_url) <= 2000 AND source_url LIKE 'https://%')
    ),
    quantity numeric CHECK (quantity IS NULL OR (quantity >= 0 AND quantity <= 1000000)),
    amount numeric CHECK (amount IS NULL OR (amount >= 0 AND amount <= 10000000)),
    updated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (record_type, record_key)
);

CREATE TABLE IF NOT EXISTS public.archipelago_runtime_quota (
    user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    day_start timestamptz NOT NULL DEFAULT now(),
    used integer NOT NULL DEFAULT 0 CHECK (used >= 0),
    hour_start timestamptz NOT NULL DEFAULT now(),
    hour_used integer NOT NULL DEFAULT 0 CHECK (hour_used >= 0),
    cooldown_until timestamptz NOT NULL DEFAULT '-infinity'::timestamptz
);

CREATE TABLE IF NOT EXISTS research_intelligence.okf_paper_records (
    job_id uuid NOT NULL REFERENCES research_intelligence.jobs(job_id) ON DELETE CASCADE,
    paper_id uuid NOT NULL REFERENCES research_intelligence.papers(paper_id) ON DELETE CASCADE,
    okf_version text NOT NULL,
    record jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, paper_id)
);

-- Enable Row Level Security on every table that lacked it or needed enforcement
ALTER TABLE public.retrieval_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.graph_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_response_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.role_page_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.archipelago_librarian_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.archipelago_runtime_quota ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.okf_paper_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.s6_library_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_intelligence.s6_analytics_audit_log ENABLE ROW LEVEL SECURITY;

-- Service-role-only policies on cache and internal tables in public schema
DROP POLICY IF EXISTS service_role_only_policy ON public.retrieval_cache;
CREATE POLICY service_role_only_policy ON public.retrieval_cache
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_only_policy ON public.graph_cache;
CREATE POLICY service_role_only_policy ON public.graph_cache
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_only_policy ON public.role_page_permissions;
CREATE POLICY service_role_only_policy ON public.role_page_permissions
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_only_policy ON public.archipelago_librarian_records;
CREATE POLICY service_role_only_policy ON public.archipelago_librarian_records
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_only_policy ON public.archipelago_runtime_quota;
CREATE POLICY service_role_only_policy ON public.archipelago_runtime_quota
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Explicit privilege lockdown on public tables
REVOKE ALL ON TABLE
    public.ai_response_cache,
    public.retrieval_cache,
    public.graph_cache,
    public.role_page_permissions,
    public.archipelago_librarian_records,
    public.archipelago_runtime_quota,
    public.archipelago_runtime_ai_request,
    public.archipelago_runtime_quota_events,
    public.research_graph_annotations,
    public.research_intake_records,
    public.research_processing_jobs,
    public.research_processing_papers,
    public.research_worker_heartbeats
FROM PUBLIC, anon, authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    public.ai_response_cache,
    public.retrieval_cache,
    public.graph_cache,
    public.role_page_permissions,
    public.archipelago_librarian_records,
    public.archipelago_runtime_quota,
    public.archipelago_runtime_ai_request,
    public.archipelago_runtime_quota_events,
    public.research_graph_annotations,
    public.research_intake_records,
    public.research_processing_jobs,
    public.research_processing_papers,
    public.research_worker_heartbeats
TO service_role;

-- Ensure anon has no access and authenticated has read-only access on RLS-protected user tables
REVOKE ALL ON TABLE
    public.profiles,
    public.credential_import_permissions,
    public.credential_import_audits
FROM PUBLIC, anon;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE
    public.profiles,
    public.credential_import_permissions,
    public.credential_import_audits
FROM authenticated;

GRANT SELECT ON TABLE
    public.profiles,
    public.credential_import_permissions,
    public.credential_import_audits
TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    public.profiles,
    public.credential_import_permissions,
    public.credential_import_audits
TO service_role;

-- Lock down private research_intelligence schema
REVOKE ALL ON SCHEMA research_intelligence FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA research_intelligence FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA research_intelligence FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA research_intelligence TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA research_intelligence TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA research_intelligence TO service_role;

-- Harden research_enqueue_job with explicit pg_catalog search_path and service_role runtime check
CREATE OR REPLACE FUNCTION public.research_enqueue_job(
    p_user_id uuid,
    p_role text,
    p_topic text,
    p_paper_limit integer DEFAULT 25
)
RETURNS public.research_processing_jobs
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    hourly_limit constant integer := 5;
    daily_limit constant integer := 10;
    queue_limit constant integer := 100;
    created public.research_processing_jobs;
BEGIN
    IF coalesce(current_setting('role', true), '') IS DISTINCT FROM 'service_role'
       AND coalesce(current_setting('request.jwt.claim.role', true), '') IS DISTINCT FROM 'service_role'
       AND session_user NOT IN ('postgres', 'service_role', 'supabase_admin') THEN
        RAISE EXCEPTION 'insufficient_privilege';
    END IF;

    IF p_role NOT IN ('faculty', 'librarian', 'administrator')
       OR char_length(trim(p_topic)) NOT BETWEEN 3 AND 200
       OR p_paper_limit NOT BETWEEN 20 AND 30 THEN
        RAISE EXCEPTION 'invalid_research_job';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('research_global_queue', 0));
    PERFORM pg_advisory_xact_lock(hashtextextended(p_user_id::text, 0));

    IF (SELECT count(*) FROM public.research_processing_jobs
        WHERE user_id = p_user_id AND created_at >= now() - interval '1 hour'
        AND NOT (status = 'failed' AND stage = 'LOCAL_APPROVAL_DECLINED')) >= hourly_limit
       OR (SELECT count(*) FROM public.research_processing_jobs
        WHERE user_id = p_user_id AND created_at >= now() - interval '1 day'
        AND NOT (status = 'failed' AND stage = 'LOCAL_APPROVAL_DECLINED')) >= daily_limit THEN
        RAISE EXCEPTION 'research_rate_limited';
    END IF;

    IF EXISTS (SELECT 1 FROM public.research_processing_jobs
               WHERE user_id = p_user_id AND status IN ('queued', 'running')) THEN
        RAISE EXCEPTION 'research_job_in_progress';
    END IF;

    IF (SELECT count(*) FROM public.research_processing_jobs
        WHERE status IN ('queued', 'running')) >= queue_limit THEN
        RAISE EXCEPTION 'research_queue_full';
    END IF;

    INSERT INTO public.research_processing_jobs(user_id, role, topic, paper_limit)
    VALUES (p_user_id, p_role, trim(p_topic), p_paper_limit)
    RETURNING * INTO created;

    RETURN created;
END;
$$;

REVOKE ALL ON FUNCTION public.research_enqueue_job(uuid, text, text, integer)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.research_enqueue_job(uuid, text, text, integer)
    TO service_role;

-- Extend s5_research_rpc with owner-scoped delete_user_data for privacy compliance (Check 12.2)
CREATE OR REPLACE FUNCTION public.s5_research_rpc(
    p_op text,
    p_args jsonb DEFAULT '{}'::jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, research_intelligence, public
AS $$
DECLARE
    v_ready boolean;
    v_payload jsonb;
    v_audit jsonb;
    v_count integer;
    v_id uuid;
    v_owner_id uuid;
    v_options jsonb;
    v_last_run_id uuid;
    v_lease_started_at timestamptz;
    v_run_id uuid;
    v_error text;
    v_status text;
BEGIN
    IF coalesce(current_setting('role', true), '') IS DISTINCT FROM 'service_role'
       AND coalesce(current_setting('request.jwt.claim.role', true), '') IS DISTINCT FROM 'service_role'
       AND session_user NOT IN ('postgres', 'service_role', 'supabase_admin') THEN
        RAISE EXCEPTION 'insufficient_privilege';
    END IF;

    IF p_op = 'check_ready' THEN
        SELECT to_regclass('research_intelligence.s5_runs') IS NOT NULL
           AND to_regclass('research_intelligence.s5_monitors') IS NOT NULL
           AND to_regclass('research_intelligence.s5_monitor_history') IS NOT NULL
           AND to_regclass('research_intelligence.s5_events') IS NOT NULL
           AND to_regclass('research_intelligence.s6_library_events') IS NOT NULL
           AND EXISTS (
               SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'research_intelligence'
                 AND table_name = 's5_monitors'
                 AND column_name = 'consecutive_failures'
           )
           AND EXISTS (
               SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'research_intelligence'
                 AND table_name = 's5_monitors'
                 AND column_name = 'last_success_at'
           )
        INTO v_ready;
        RETURN jsonb_build_object('ready', coalesce(v_ready, false));

    ELSIF p_op = 'save_run' THEN
        INSERT INTO research_intelligence.s5_runs (id, owner_id, schema_version, topic, payload)
        VALUES (
            (p_args->>'id')::uuid,
            (p_args->>'owner_id')::uuid,
            p_args->>'schema_version',
            p_args->>'topic',
            p_args->'payload'
        );
        RETURN jsonb_build_object('run_id', p_args->>'id');

    ELSIF p_op = 'get_run' THEN
        SELECT payload INTO v_payload
        FROM research_intelligence.s5_runs
        WHERE id = (p_args->>'id')::uuid
          AND owner_id = (p_args->>'owner_id')::uuid;
        IF NOT FOUND THEN
            RETURN jsonb_build_object('found', false);
        END IF;
        RETURN jsonb_build_object('found', true, 'payload', v_payload);

    ELSIF p_op = 'list_runs' THEN
        SELECT coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'run_id', id::text,
                    'created_at', created_at,
                    'topic', topic
                ) ORDER BY created_at DESC
            ),
            '[]'::jsonb
        ) INTO v_payload
        FROM (
            SELECT id, created_at, topic
            FROM research_intelligence.s5_runs
            WHERE owner_id = (p_args->>'owner_id')::uuid
            ORDER BY created_at DESC
            LIMIT 30
        ) sub;
        RETURN jsonb_build_object('runs', v_payload);

    ELSIF p_op = 'save_monitor' THEN
        INSERT INTO research_intelligence.s5_monitors (id, owner_id, options, cadence_hours)
        VALUES (
            (p_args->>'id')::uuid,
            (p_args->>'owner_id')::uuid,
            p_args->'options',
            (p_args->>'cadence_hours')::integer
        );
        RETURN jsonb_build_object('monitor_id', p_args->>'id');

    ELSIF p_op = 'list_monitors' THEN
        SELECT coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'id', id::text,
                    'options', options,
                    'enabled', enabled,
                    'cadence_hours', cadence_hours,
                    'next_run_at', next_run_at,
                    'last_run', last_run_id::text,
                    'last_error', last_error,
                    'last_success_at', last_success_at,
                    'consecutive_failures', consecutive_failures
                ) ORDER BY created_at DESC
            ),
            '[]'::jsonb
        ) INTO v_payload
        FROM (
            SELECT id, options, enabled, cadence_hours, next_run_at, last_run_id,
                   last_error, last_success_at, consecutive_failures, created_at
            FROM research_intelligence.s5_monitors
            WHERE owner_id = (p_args->>'owner_id')::uuid
            ORDER BY created_at DESC
            LIMIT 30
        ) sub;
        RETURN jsonb_build_object('monitors', v_payload);

    ELSIF p_op = 'set_monitor_enabled' THEN
        UPDATE research_intelligence.s5_monitors
        SET enabled = (p_args->>'enabled')::boolean,
            next_run_at = CASE WHEN (p_args->>'enabled')::boolean THEN now() ELSE NULL END,
            lease_until = NULL,
            updated_at = now()
        WHERE id = (p_args->>'id')::uuid
          AND owner_id = (p_args->>'owner_id')::uuid;
        GET DIAGNOSTICS v_count = ROW_COUNT;
        RETURN jsonb_build_object('ok', v_count = 1);

    ELSIF p_op = 'set_monitor_cadence' THEN
        UPDATE research_intelligence.s5_monitors
        SET cadence_hours = (p_args->>'cadence_hours')::integer,
            next_run_at = CASE
                WHEN enabled THEN now() + ((p_args->>'cadence_hours')::integer * interval '1 hour')
                ELSE NULL
            END,
            updated_at = now()
        WHERE id = (p_args->>'id')::uuid
          AND owner_id = (p_args->>'owner_id')::uuid;
        GET DIAGNOSTICS v_count = ROW_COUNT;
        RETURN jsonb_build_object('ok', v_count = 1);

    ELSIF p_op = 'delete_monitor' THEN
        DELETE FROM research_intelligence.s5_monitors
        WHERE id = (p_args->>'id')::uuid
          AND owner_id = (p_args->>'owner_id')::uuid;
        GET DIAGNOSTICS v_count = ROW_COUNT;
        RETURN jsonb_build_object('ok', v_count = 1);

    ELSIF p_op = 'make_monitor_due' THEN
        UPDATE research_intelligence.s5_monitors
        SET next_run_at = now()
        WHERE id = (p_args->>'id')::uuid
          AND owner_id = (p_args->>'owner_id')::uuid
          AND enabled;
        GET DIAGNOSTICS v_count = ROW_COUNT;
        RETURN jsonb_build_object('ok', v_count = 1);

    ELSIF p_op = 'claim_monitor' THEN
        UPDATE research_intelligence.s5_monitors
        SET lease_until = (p_args->>'lease_until')::timestamptz,
            lease_started_at = now()
        WHERE id = (p_args->>'id')::uuid
          AND enabled
          AND next_run_at <= GREATEST((p_args->>'now')::timestamptz, now())
          AND (lease_until IS NULL OR lease_until < (p_args->>'now')::timestamptz)
        RETURNING id, owner_id, options, last_run_id
        INTO v_id, v_owner_id, v_options, v_last_run_id;
        IF NOT FOUND THEN
            RETURN jsonb_build_object('claimed', null);
        END IF;
        RETURN jsonb_build_object(
            'claimed',
            jsonb_build_object(
                'id', v_id::text,
                'owner', v_owner_id::text,
                'options', v_options::text,
                'last_run', v_last_run_id::text
            )
        );

    ELSIF p_op = 'due_monitor_ids' THEN
        SELECT coalesce(jsonb_agg(id::text ORDER BY next_run_at), '[]'::jsonb)
        INTO v_payload
        FROM (
            SELECT id, next_run_at
            FROM research_intelligence.s5_monitors
            WHERE enabled
              AND next_run_at <= now()
              AND (lease_until IS NULL OR lease_until < now())
            ORDER BY next_run_at
            LIMIT least(coalesce((p_args->>'limit')::integer, 30), 30)
        ) sub;
        RETURN jsonb_build_object('ids', v_payload);

    ELSIF p_op = 'finish_monitor' THEN
        v_run_id := NULLIF(p_args->>'run_id', '')::uuid;
        v_error := NULLIF(p_args->>'error', '');
        v_status := CASE
            WHEN v_error IS NOT NULL THEN 'failed'
            WHEN v_run_id IS NOT NULL THEN 'updated'
            ELSE 'unchanged'
        END;
        UPDATE research_intelligence.s5_monitors
        SET last_run_id = COALESCE(v_run_id, last_run_id),
            last_error = v_error,
            consecutive_failures = CASE WHEN v_error IS NULL THEN 0 ELSE consecutive_failures + 1 END,
            last_success_at = CASE WHEN v_error IS NULL THEN now() ELSE last_success_at END,
            lease_until = NULL,
            next_run_at = CASE
                WHEN NOT enabled THEN NULL
                WHEN v_error IS NULL THEN now() + cadence_hours * interval '1 hour'
                ELSE now() + LEAST(60, 5 * power(2, LEAST(consecutive_failures, 4))) * interval '1 minute'
            END,
            updated_at = now()
        WHERE id = (p_args->>'id')::uuid
        RETURNING owner_id, lease_started_at
        INTO v_owner_id, v_lease_started_at;
        IF FOUND THEN
            INSERT INTO research_intelligence.s5_monitor_history
                (id, monitor_id, owner_id, run_id, status, error_code, started_at)
            VALUES (
                (p_args->>'history_id')::uuid,
                (p_args->>'id')::uuid,
                v_owner_id,
                v_run_id,
                v_status,
                v_error,
                coalesce(v_lease_started_at, now())
            );
        END IF;
        RETURN jsonb_build_object('ok', true);

    ELSIF p_op = 'list_history' THEN
        SELECT coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'id', id::text,
                    'run_id', run_id::text,
                    'status', status,
                    'error', error_code,
                    'finished_at', finished_at
                ) ORDER BY finished_at DESC
            ),
            '[]'::jsonb
        ) INTO v_payload
        FROM (
            SELECT h.id, h.run_id, h.status, h.error_code, h.finished_at
            FROM research_intelligence.s5_monitor_history h
            JOIN research_intelligence.s5_monitors m ON m.id = h.monitor_id
            WHERE h.monitor_id = (p_args->>'monitor_id')::uuid
              AND m.owner_id = (p_args->>'owner_id')::uuid
            ORDER BY h.finished_at DESC
            LIMIT 30
        ) sub;
        RETURN jsonb_build_object('history', v_payload);

    ELSIF p_op = 'add_event' THEN
        INSERT INTO research_intelligence.s5_events
            (id, owner_id, monitor_id, run_id, kind, subject_id, payload)
        SELECT
            (p_args->>'id')::uuid,
            (p_args->>'owner_id')::uuid,
            (p_args->>'monitor_id')::uuid,
            NULLIF(p_args->>'run_id', '')::uuid,
            p_args->>'kind',
            p_args->>'subject_id',
            p_args->'payload'
        WHERE EXISTS (
            SELECT 1 FROM research_intelligence.s5_monitors m
            WHERE m.id = (p_args->>'monitor_id')::uuid
              AND m.owner_id = (p_args->>'owner_id')::uuid
        )
        ON CONFLICT (monitor_id, kind, subject_id, run_id) DO NOTHING;
        RETURN jsonb_build_object('ok', true);

    ELSIF p_op = 'list_events' THEN
        SELECT coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'id', id::text,
                    'monitor_id', monitor_id::text,
                    'run_id', run_id::text,
                    'kind', kind,
                    'subject_id', subject_id,
                    'payload', payload,
                    'created_at', created_at
                ) ORDER BY created_at DESC
            ),
            '[]'::jsonb
        ) INTO v_payload
        FROM (
            SELECT id, monitor_id, run_id, kind, subject_id, payload, created_at
            FROM research_intelligence.s5_events
            WHERE owner_id = (p_args->>'owner_id')::uuid
            ORDER BY created_at DESC
            LIMIT 30
        ) sub;
        RETURN jsonb_build_object('events', v_payload);

    ELSIF p_op = 'record_library_event' THEN
        v_id := (p_args->>'id')::uuid;
        INSERT INTO research_intelligence.s6_library_events (
            id, idempotency_key, source_id, event_type, subject_category,
            quantity, occurred_at, recorded_by, is_demo, metadata
        )
        VALUES (
            v_id,
            p_args->>'idempotency_key',
            p_args->>'source_id',
            p_args->>'event_type',
            NULLIF(p_args->>'subject_category', ''),
            (p_args->>'quantity')::integer,
            (p_args->>'occurred_at')::timestamptz,
            (p_args->>'recorded_by')::uuid,
            coalesce((p_args->>'is_demo')::boolean, false),
            coalesce(p_args->'metadata', '{}'::jsonb)
        )
        ON CONFLICT (idempotency_key) DO NOTHING;
        GET DIAGNOSTICS v_count = ROW_COUNT;
        IF v_count = 1 THEN
            INSERT INTO research_intelligence.s6_analytics_audit_log (
                actor_id, action, source_id, event_id
            )
            VALUES (
                (p_args->>'recorded_by')::uuid,
                'record_' || (p_args->>'event_type'),
                p_args->>'source_id',
                v_id
            );
        END IF;
        RETURN jsonb_build_object(
            'inserted', v_count = 1,
            'deduplicated', v_count = 0,
            'event_id', v_id::text
        );

    ELSIF p_op = 'list_library_events' THEN
        SELECT coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'id', id::text,
                    'idempotency_key', idempotency_key,
                    'source_id', source_id,
                    'event_type', event_type,
                    'subject_category', subject_category,
                    'quantity', quantity,
                    'occurred_at', occurred_at,
                    'is_demo', is_demo,
                    'created_at', created_at
                ) ORDER BY occurred_at DESC
            ),
            '[]'::jsonb
        ) INTO v_payload
        FROM (
            SELECT id, idempotency_key, source_id, event_type, subject_category,
                   quantity, occurred_at, is_demo, created_at
            FROM research_intelligence.s6_library_events
            WHERE is_demo = coalesce((p_args->>'is_demo')::boolean, false)
              AND (
                  NULLIF(p_args->>'source_id', '') IS NULL
                  OR source_id = (p_args->>'source_id')
              )
              AND (
                  NULLIF(p_args->>'from_ts', '') IS NULL
                  OR occurred_at >= (p_args->>'from_ts')::timestamptz
              )
              AND (
                  NULLIF(p_args->>'to_ts', '') IS NULL
                  OR occurred_at <= (p_args->>'to_ts')::timestamptz
              )
            ORDER BY occurred_at DESC
            LIMIT 500
        ) sub;

        SELECT coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'id', id::text,
                    'action', action,
                    'source_id', source_id,
                    'event_id', event_id::text,
                    'created_at', created_at
                ) ORDER BY created_at DESC
            ),
            '[]'::jsonb
        ) INTO v_audit
        FROM (
            SELECT id, action, source_id, event_id, created_at
            FROM research_intelligence.s6_analytics_audit_log
            ORDER BY created_at DESC
            LIMIT 50
        ) aud;

        RETURN jsonb_build_object('events', v_payload, 'audit', v_audit);

    ELSIF p_op = 'delete_user_data' THEN
        v_owner_id := (p_args->>'owner_id')::uuid;
        DELETE FROM research_intelligence.s5_events WHERE owner_id = v_owner_id;
        DELETE FROM research_intelligence.s5_monitor_history WHERE owner_id = v_owner_id;
        DELETE FROM research_intelligence.s5_monitors WHERE owner_id = v_owner_id;
        DELETE FROM research_intelligence.s5_runs WHERE owner_id = v_owner_id;
        DELETE FROM research_intelligence.tracked_topics WHERE user_id = v_owner_id::text;
        RETURN jsonb_build_object('ok', true);

    ELSE
        RAISE EXCEPTION 'unsupported_s5_op';
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.s5_research_rpc(text, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.s5_research_rpc(text, jsonb) TO service_role;
