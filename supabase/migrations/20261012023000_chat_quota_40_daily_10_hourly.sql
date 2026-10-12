-- Student and faculty AI allowance: 40 per rolling 24 hours, 10 per rolling hour.
ALTER TABLE public.archipelago_runtime_quota
ADD COLUMN IF NOT EXISTS hour_start timestamptz NOT NULL DEFAULT now(),
ADD COLUMN IF NOT EXISTS hour_used integer NOT NULL DEFAULT 0;

CREATE OR REPLACE FUNCTION public.archipelago_runtime_query(
    p_user_id uuid, p_consume boolean DEFAULT false
)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public AS $$
DECLARE
    state public.archipelago_runtime_quota%ROWTYPE;
    clock_at timestamptz := now();
    day_at timestamptz;
    hour_at timestamptz;
    day_count integer;
    hour_count integer;
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
        RETURN jsonb_build_object('limited', false, 'used', 0, 'remaining', 40,
            'hourly_used', 0, 'hourly_remaining', 10, 'retry_after', 0);
    END IF;

    day_at := state.day_start;
    day_count := state.used;
    hour_at := state.hour_start;
    hour_count := state.hour_used;
    IF clock_at >= day_at + interval '24 hours' THEN
        day_at := clock_at;
        day_count := 0;
    END IF;
    IF clock_at >= hour_at + interval '1 hour' THEN
        hour_at := clock_at;
        hour_count := 0;
    END IF;

    IF day_count >= 40 THEN
        wait_seconds := greatest(1, ceil(extract(epoch FROM day_at + interval '24 hours' - clock_at))::integer);
        RETURN jsonb_build_object('limited', true, 'limit_reason', 'daily',
            'used', day_count, 'remaining', 0, 'hourly_used', hour_count,
            'hourly_remaining', 10 - hour_count, 'retry_after', wait_seconds);
    END IF;
    IF hour_count >= 10 THEN
        wait_seconds := greatest(1, ceil(extract(epoch FROM hour_at + interval '1 hour' - clock_at))::integer);
        RETURN jsonb_build_object('limited', true, 'limit_reason', 'hourly',
            'used', day_count, 'remaining', 40 - day_count, 'hourly_used', hour_count,
            'hourly_remaining', 0, 'retry_after', wait_seconds);
    END IF;

    IF p_consume THEN
        day_count := day_count + 1;
        hour_count := hour_count + 1;
        UPDATE public.archipelago_runtime_quota
        SET day_start = day_at, used = day_count, hour_start = hour_at,
            hour_used = hour_count, cooldown_until = '-infinity'
        WHERE user_id = p_user_id;
    END IF;
    RETURN jsonb_build_object('limited', false, 'used', day_count,
        'remaining', 40 - day_count, 'hourly_used', hour_count,
        'hourly_remaining', 10 - hour_count, 'retry_after', 0);
END;
$$;

REVOKE ALL ON FUNCTION public.archipelago_runtime_query(uuid, boolean)
FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.archipelago_runtime_query(uuid, boolean)
TO service_role;
