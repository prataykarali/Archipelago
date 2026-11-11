-- Existing per-account quota, with a UTC calendar reset and a full cooldown
-- after each block of ten accepted AI requests. Only the server service key
-- may call this RPC; callers never choose an account in the browser.
create or replace function public.archipelago_runtime_query(
    p_user_id uuid, p_consume boolean default false
) returns jsonb
language plpgsql
set search_path = public
as $$
declare
    state public.archipelago_runtime_quota%rowtype;
    clock_at timestamptz := now();
    period_at timestamptz := date_trunc('day', now() at time zone 'UTC') at time zone 'UTC';
    day_count integer;
    burst_count integer;
    cooldown_at timestamptz;
    retry_seconds integer;
begin
    if p_consume then
        insert into public.archipelago_runtime_quota(user_id)
        values (p_user_id) on conflict (user_id) do nothing;
        select * into state from public.archipelago_runtime_quota
        where user_id = p_user_id for update;
    else
        select * into state from public.archipelago_runtime_quota
        where user_id = p_user_id;
    end if;

    day_count := case when not found or state.day_start < period_at
        then 0 else state.used end;
    burst_count := case when not found or state.day_start < period_at
        or (state.hour_used >= 10 and state.cooldown_until <= clock_at)
        then 0 else state.hour_used end;
    cooldown_at := case when not found or state.day_start < period_at
        or state.cooldown_until <= clock_at then '-infinity'::timestamptz
        else state.cooldown_until end;

    if day_count >= 40 then
        retry_seconds := greatest(1, ceil(extract(epoch from
            period_at + interval '1 day' - clock_at))::integer);
        return jsonb_build_object('limited', true, 'limit_reason', 'daily',
            'used', day_count, 'remaining', 0, 'burst_count', burst_count,
            'retry_after', retry_seconds);
    end if;
    if cooldown_at > clock_at then
        retry_seconds := greatest(1, ceil(extract(epoch from
            cooldown_at - clock_at))::integer);
        return jsonb_build_object('limited', true, 'limit_reason', 'cooldown',
            'used', day_count, 'remaining', 40 - day_count,
            'burst_count', burst_count, 'retry_after', retry_seconds);
    end if;

    if p_consume then
        day_count := day_count + 1;
        burst_count := burst_count + 1;
        if burst_count = 10 and day_count < 40 then
            cooldown_at := clock_at + interval '1 hour';
        end if;
        update public.archipelago_runtime_quota
        set day_start = period_at, used = day_count,
            hour_start = clock_at, hour_used = burst_count,
            cooldown_until = cooldown_at
        where user_id = p_user_id;
    end if;
    return jsonb_build_object('limited', false, 'used', day_count,
        'remaining', 40 - day_count, 'burst_count', burst_count,
        'retry_after', case when cooldown_at > clock_at
            then greatest(1, ceil(extract(epoch from cooldown_at - clock_at))::integer)
            else 0 end);
end;
$$;
