-- Keep the 35-query rolling daily allowance without blocking every seventh query.
-- Existing cooldown values are ignored and cleared on the next accepted query.
CREATE OR REPLACE FUNCTION public.archipelago_runtime_query(
    p_user_id uuid, p_consume boolean DEFAULT false
)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public AS $$
DECLARE
    state public.archipelago_runtime_quota%ROWTYPE;
    clock_at timestamptz := now();
    start_time timestamptz;
    query_count integer;
    wait_seconds integer := 0;
BEGIN
    IF p_consume THEN
        INSERT INTO public.archipelago_runtime_quota(user_id) VALUES (p_user_id)
        ON CONFLICT (user_id) DO NOTHING;
        SELECT * INTO state FROM public.archipelago_runtime_quota
        WHERE user_id = p_user_id FOR UPDATE;
    ELSE
        SELECT * INTO state FROM public.archipelago_runtime_quota WHERE user_id = p_user_id;
    END IF;
    IF NOT FOUND AND NOT p_consume THEN
        RETURN jsonb_build_object('limited', false, 'used', 0, 'remaining', 35, 'retry_after', 0);
    END IF;

    start_time := state.day_start;
    query_count := state.used;
    IF clock_at >= start_time + interval '24 hours' THEN
        start_time := clock_at;
        query_count := 0;
    END IF;
    IF query_count >= 35 THEN
        wait_seconds := greatest(1, ceil(extract(epoch FROM start_time + interval '24 hours' - clock_at))::integer);
        RETURN jsonb_build_object('limited', true, 'used', query_count,
            'remaining', 0, 'retry_after', wait_seconds);
    END IF;

    IF p_consume THEN
        query_count := query_count + 1;
        UPDATE public.archipelago_runtime_quota
        SET day_start = start_time, used = query_count, cooldown_until = '-infinity'
        WHERE user_id = p_user_id;
    END IF;
    RETURN jsonb_build_object('limited', false, 'used', query_count,
        'remaining', 35 - query_count, 'retry_after', 0,
        'cooldown_after_this_query', false);
END;
$$;

REVOKE ALL ON FUNCTION public.archipelago_runtime_query(uuid, boolean)
FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.archipelago_runtime_query(uuid, boolean)
TO service_role;
