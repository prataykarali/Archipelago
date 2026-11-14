-- Replace the 40-per-day + 10-query-cooldown student quota model with a
-- rolling 3600-second (60-minute) 10-query window per authenticated student.
-- Additive migration: preserves existing tables and historical rows.

create table if not exists public.archipelago_runtime_quota_events (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

create index if not exists archipelago_runtime_quota_events_user_created_idx
    on public.archipelago_runtime_quota_events (user_id, created_at desc);

alter table public.archipelago_runtime_quota_events enable row level security;
revoke all on public.archipelago_runtime_quota_events from public, anon, authenticated;
grant select, insert, delete on public.archipelago_runtime_quota_events to service_role;

create or replace function public.archipelago_runtime_query(
    p_user_id uuid,
    p_consume boolean default false
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_now timestamptz := now();
    v_window_start timestamptz := v_now - interval '3600 seconds';
    v_used integer := 0;
    v_oldest_at timestamptz;
    v_reset_at timestamptz;
    v_retry_after integer := 0;
    v_limit constant integer := 10;
begin
    if coalesce(current_setting('role', true), '') is distinct from 'service_role'
       and coalesce(current_setting('request.jwt.claim.role', true), '') is distinct from 'service_role'
       and session_user not in ('postgres', 'service_role', 'supabase_admin') then
        raise exception 'insufficient_privilege';
    end if;

    if p_consume then
        perform pg_advisory_xact_lock(hashtext('archipelago_quota:' || p_user_id::text));
    end if;

    select count(*)::integer, min(created_at)
    into v_used, v_oldest_at
    from public.archipelago_runtime_quota_events
    where user_id = p_user_id
      and created_at > v_window_start;

    if v_used >= v_limit then
        v_reset_at := v_oldest_at + interval '3600 seconds';
        v_retry_after := greatest(1, ceil(extract(epoch from (v_reset_at - v_now)))::integer);
        return jsonb_build_object(
            'limited', true,
            'limit_reason', 'hourly_limit',
            'limit', v_limit,
            'window_seconds', 3600,
            'used', v_used,
            'remaining', 0,
            'retry_after', v_retry_after,
            'reset_at', to_jsonb(v_reset_at)
        );
    end if;

    if p_consume then
        insert into public.archipelago_runtime_quota_events (user_id, created_at)
        values (p_user_id, v_now);
        v_used := v_used + 1;
        if v_oldest_at is null then
            v_oldest_at := v_now;
        end if;
    end if;

    if v_oldest_at is not null then
        v_reset_at := v_oldest_at + interval '3600 seconds';
    end if;

    return jsonb_build_object(
        'limited', false,
        'limit', v_limit,
        'window_seconds', 3600,
        'used', v_used,
        'remaining', greatest(0, v_limit - v_used),
        'retry_after', 0,
        'reset_at', case when v_reset_at is not null then to_jsonb(v_reset_at) else 'null'::jsonb end
    );
end;
$$;

create or replace function public.archipelago_runtime_consume(
    p_user_id uuid,
    p_request_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_inserted uuid;
    v_quota jsonb;
begin
    if coalesce(current_setting('role', true), '') is distinct from 'service_role'
       and coalesce(current_setting('request.jwt.claim.role', true), '') is distinct from 'service_role'
       and session_user not in ('postgres', 'service_role', 'supabase_admin') then
        raise exception 'insufficient_privilege';
    end if;

    perform pg_advisory_xact_lock(hashtext('archipelago_quota:' || p_user_id::text));

    insert into public.archipelago_runtime_ai_request (user_id, request_id)
    values (p_user_id, p_request_id)
    on conflict do nothing
    returning request_id into v_inserted;

    if v_inserted is null then
        return public.archipelago_runtime_query(p_user_id, false) ||
            jsonb_build_object('limited', true, 'limit_reason', 'duplicate');
    end if;

    v_quota := public.archipelago_runtime_query(p_user_id, true);
    if (v_quota->>'limited')::boolean then
        delete from public.archipelago_runtime_ai_request
        where user_id = p_user_id and request_id = p_request_id;
    end if;
    return v_quota;
end;
$$;

revoke all on function public.archipelago_runtime_query(uuid, boolean) from public, anon, authenticated;
grant execute on function public.archipelago_runtime_query(uuid, boolean) to service_role;
revoke all on function public.archipelago_runtime_consume(uuid, uuid) from public, anon, authenticated;
grant execute on function public.archipelago_runtime_consume(uuid, uuid) to service_role;
