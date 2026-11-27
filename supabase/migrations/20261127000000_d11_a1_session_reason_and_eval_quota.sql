-- D11-A.1: Preserve accurate session expiry reasons (idle_expired / absolute_expired vs
-- revoked_credentials), avoid FOR UPDATE lock contention on active passive checks, and add
-- bounded per-account evaluation quota overrides while keeping ordinary students at 10/hour.

alter table public.archipelago_runtime_sessions
    add column if not exists revoked_reason text;

create or replace function public.archipelago_runtime_session_rpc(
    p_operation text,
    p_session_id uuid,
    p_user_id uuid,
    p_idle_seconds integer,
    p_max_age_seconds integer,
    p_passive boolean default false
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_row public.archipelago_runtime_sessions%rowtype;
    v_status text;
begin
    if coalesce(current_setting('role', true), '') is distinct from 'service_role'
       and coalesce(current_setting('request.jwt.claim.role', true), '') is distinct from 'service_role'
       and session_user not in ('postgres', 'service_role', 'supabase_admin') then
        raise exception 'insufficient_privilege';
    end if;
    if p_operation not in ('register', 'check', 'revoke')
       or p_session_id is null or p_user_id is null
       or p_idle_seconds < 1 or p_max_age_seconds < 1 then
        raise exception 'invalid_session_request';
    end if;

    -- A Supabase global sign-out removes auth.sessions. Validate it on every
    -- request so an old access JWT cannot survive a refresh-token revocation.
    if not exists (
        select 1 from auth.sessions
        where id = p_session_id and user_id = p_user_id
    ) then
        update public.archipelago_runtime_sessions
        set revoked_at = coalesce(revoked_at, v_now),
            revoked_reason = coalesce(revoked_reason, 'revoked_credentials')
        where session_id = p_session_id and user_id = p_user_id;
        return jsonb_build_object('status', 'revoked_credentials');
    end if;

    if p_operation in ('register', 'revoke') then
        insert into public.archipelago_runtime_sessions (
            session_id, user_id, started_at, last_activity_at, revoked_at, revoked_reason
        )
        values (
            p_session_id, p_user_id, v_now, v_now,
            case when p_operation = 'revoke' then v_now else null end,
            case when p_operation = 'revoke' then 'revoked_credentials' else null end
        )
        on conflict (session_id) do nothing;
    end if;

    -- Fast lock-free read for active passive polls to eliminate FOR UPDATE contention.
    if p_operation = 'check' and p_passive then
        select * into v_row
        from public.archipelago_runtime_sessions
        where session_id = p_session_id;
        if not found then
            return jsonb_build_object('status', 'missing_session');
        end if;
        if v_row.user_id != p_user_id then
            return jsonb_build_object('status', 'revoked_credentials');
        end if;
        if v_row.revoked_at is not null then
            return jsonb_build_object(
                'status', coalesce(v_row.revoked_reason, 'revoked_credentials')
            );
        end if;
        v_now := clock_timestamp();
        if v_now - v_row.started_at < make_interval(secs => p_max_age_seconds)
           and v_now - v_row.last_activity_at < make_interval(secs => p_idle_seconds) then
            return jsonb_build_object('status', 'active');
        end if;
    end if;

    select * into v_row
    from public.archipelago_runtime_sessions
    where session_id = p_session_id
    for update;
    if not found then
        return jsonb_build_object('status', 'missing_session');
    end if;
    v_now := clock_timestamp();
    if v_row.user_id != p_user_id then
        return jsonb_build_object('status', 'revoked_credentials');
    end if;
    if p_operation = 'revoke' then
        update public.archipelago_runtime_sessions
        set revoked_at = coalesce(revoked_at, v_now),
            revoked_reason = 'revoked_credentials'
        where session_id = p_session_id;
        return jsonb_build_object('status', 'revoked_credentials');
    end if;
    if v_row.revoked_at is not null then
        return jsonb_build_object(
            'status', coalesce(v_row.revoked_reason, 'revoked_credentials')
        );
    end if;
    if v_now - v_row.started_at >= make_interval(secs => p_max_age_seconds) then
        v_status := 'absolute_expired';
    elsif v_now - v_row.last_activity_at >= make_interval(secs => p_idle_seconds) then
        v_status := 'idle_expired';
    else
        v_status := 'active';
    end if;
    if v_status != 'active' then
        update public.archipelago_runtime_sessions
        set revoked_at = v_now,
            revoked_reason = v_status
        where session_id = p_session_id;
    elsif not p_passive then
        update public.archipelago_runtime_sessions
        set last_activity_at = v_now
        where session_id = p_session_id;
    end if;
    return jsonb_build_object('status', v_status);
end;
$$;

-- Bounded per-account evaluation quota overrides (ordinary students remain at 10/hour).
create table if not exists public.archipelago_runtime_quota_overrides (
    user_id uuid primary key references auth.users(id) on delete cascade,
    hourly_limit integer not null check (hourly_limit between 1 and 200),
    note text not null default '',
    updated_at timestamptz not null default now()
);

alter table public.archipelago_runtime_quota_overrides enable row level security;
revoke all on public.archipelago_runtime_quota_overrides from public, anon, authenticated;
grant select, insert, update, delete on public.archipelago_runtime_quota_overrides to service_role;

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
    v_limit integer := 10;
begin
    if coalesce(current_setting('role', true), '') is distinct from 'service_role'
       and coalesce(current_setting('request.jwt.claim.role', true), '') is distinct from 'service_role'
       and session_user not in ('postgres', 'service_role', 'supabase_admin') then
        raise exception 'insufficient_privilege';
    end if;

    select coalesce(o.hourly_limit, 10)
    into v_limit
    from (select 1) as _dummy
    left join public.archipelago_runtime_quota_overrides as o
      on o.user_id = p_user_id;

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

revoke all on function public.archipelago_runtime_session_rpc(text, uuid, uuid, integer, integer, boolean)
    from public, anon, authenticated;
grant execute on function public.archipelago_runtime_session_rpc(text, uuid, uuid, integer, integer, boolean)
    to service_role;
revoke all on function public.archipelago_runtime_query(uuid, boolean) from public, anon, authenticated;
grant execute on function public.archipelago_runtime_query(uuid, boolean) to service_role;
