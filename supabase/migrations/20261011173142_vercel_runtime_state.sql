-- Durable per-user limits and session activity for stateless Vercel Functions.
-- Only the server-side service role can access these tables or RPCs.
CREATE TABLE IF NOT EXISTS public.archipelago_runtime_quota (
    user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    day_start timestamptz NOT NULL DEFAULT now(),
    used integer NOT NULL DEFAULT 0 CHECK (used >= 0),
    cooldown_until timestamptz NOT NULL DEFAULT '-infinity'
);
CREATE TABLE IF NOT EXISTS public.archipelago_runtime_quiz (
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    target text NOT NULL,
    result jsonb NOT NULL,
    PRIMARY KEY (user_id, target)
);
CREATE TABLE IF NOT EXISTS public.archipelago_runtime_session (
    token_id text PRIMARY KEY,
    last_activity timestamptz NOT NULL DEFAULT now(),
    expired boolean NOT NULL DEFAULT false
);
ALTER TABLE public.archipelago_runtime_quota ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.archipelago_runtime_quiz ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.archipelago_runtime_session ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.archipelago_runtime_quota FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.archipelago_runtime_quiz FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.archipelago_runtime_session FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.archipelago_runtime_quota TO service_role;
GRANT SELECT, INSERT ON public.archipelago_runtime_quiz TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.archipelago_runtime_session TO service_role;

CREATE OR REPLACE FUNCTION public.archipelago_runtime_query(p_user_id uuid, p_consume boolean DEFAULT false)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public AS $$
DECLARE
    state public.archipelago_runtime_quota%ROWTYPE;
    clock_at timestamptz := now();
    wait_seconds integer := 0;
    start_time timestamptz;
    query_count integer;
    cooldown_time timestamptz;
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
    cooldown_time := state.cooldown_until;
    IF clock_at >= start_time + interval '24 hours' THEN
        start_time := clock_at;
        query_count := 0;
        cooldown_time := '-infinity';
    END IF;
    IF query_count >= 35 THEN
        wait_seconds := greatest(1, ceil(extract(epoch FROM start_time + interval '24 hours' - clock_at))::integer);
    ELSIF cooldown_time > clock_at THEN
        wait_seconds := greatest(1, ceil(extract(epoch FROM cooldown_time - clock_at))::integer);
    END IF;
    IF wait_seconds > 0 THEN
        RETURN jsonb_build_object('limited', true, 'used', query_count,
            'remaining', 35 - query_count, 'retry_after', wait_seconds);
    END IF;
    IF p_consume THEN
        query_count := query_count + 1;
        IF mod(query_count, 7) = 0 THEN
            cooldown_time := clock_at + interval '1 hour';
        ELSE
            cooldown_time := '-infinity';
        END IF;
        UPDATE public.archipelago_runtime_quota
        SET day_start = start_time, used = query_count, cooldown_until = cooldown_time
        WHERE user_id = p_user_id;
    END IF;
    RETURN jsonb_build_object('limited', false, 'used', query_count,
        'remaining', 35 - query_count, 'retry_after', 0,
        'cooldown_after_this_query', p_consume AND cooldown_time > clock_at);
END;
$$;

CREATE OR REPLACE FUNCTION public.archipelago_runtime_quiz_result(
    p_user_id uuid, p_target text, p_result jsonb DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public AS $$
DECLARE saved jsonb;
BEGIN
    IF p_result IS NOT NULL THEN
        INSERT INTO public.archipelago_runtime_quiz(user_id, target, result)
        VALUES (p_user_id, p_target, p_result) ON CONFLICT DO NOTHING;
    END IF;
    SELECT result INTO saved FROM public.archipelago_runtime_quiz
    WHERE user_id = p_user_id AND target = p_target;
    RETURN saved;
END;
$$;

CREATE OR REPLACE FUNCTION public.archipelago_runtime_touch_session(
    p_token_id text, p_end boolean DEFAULT false)
RETURNS boolean LANGUAGE plpgsql SECURITY INVOKER SET search_path = public AS $$
DECLARE state public.archipelago_runtime_session%ROWTYPE;
BEGIN
    INSERT INTO public.archipelago_runtime_session(token_id, expired)
    VALUES (p_token_id, p_end) ON CONFLICT (token_id) DO NOTHING;
    SELECT * INTO state FROM public.archipelago_runtime_session
    WHERE token_id = p_token_id FOR UPDATE;
    IF p_end OR state.expired OR state.last_activity < now() - interval '5 minutes' THEN
        UPDATE public.archipelago_runtime_session SET expired = true WHERE token_id = p_token_id;
        RETURN false;
    END IF;
    UPDATE public.archipelago_runtime_session SET last_activity = now()
    WHERE token_id = p_token_id;
    RETURN true;
END;
$$;
REVOKE ALL ON FUNCTION public.archipelago_runtime_query(uuid, boolean) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.archipelago_runtime_quiz_result(uuid, text, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.archipelago_runtime_touch_session(text, boolean) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.archipelago_runtime_query(uuid, boolean) TO service_role;
GRANT EXECUTE ON FUNCTION public.archipelago_runtime_quiz_result(uuid, text, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.archipelago_runtime_touch_session(text, boolean) TO service_role;
