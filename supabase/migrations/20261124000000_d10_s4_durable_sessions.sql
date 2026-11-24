-- D10-S4: shared session lifetime and revocation for hosted Vercel instances.
-- Only the server-side service_role may execute the RPC. No bearer token is stored.

create table if not exists public.archipelago_runtime_sessions (
    session_id uuid primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    started_at timestamptz not null default now(),
    last_activity_at timestamptz not null default now(),
    revoked_at timestamptz
);

create index if not exists archipelago_runtime_sessions_user_idx
    on public.archipelago_runtime_sessions (user_id, started_at desc);

alter table public.archipelago_runtime_sessions enable row level security;
revoke all on public.archipelago_runtime_sessions from public, anon, authenticated;
grant select, insert, update on public.archipelago_runtime_sessions to service_role;

create or replace function public.archipelago_runtime_session(
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
        set revoked_at = coalesce(revoked_at, v_now)
        where session_id = p_session_id and user_id = p_user_id;
        return jsonb_build_object('status', 'revoked_credentials');
    end if;

    if p_operation in ('register', 'revoke') then
        insert into public.archipelago_runtime_sessions (session_id, user_id, started_at, last_activity_at, revoked_at)
        values (
            p_session_id, p_user_id, v_now, v_now,
            case when p_operation = 'revoke' then v_now else null end
        )
        on conflict (session_id) do nothing;
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
        set revoked_at = coalesce(revoked_at, v_now)
        where session_id = p_session_id;
        return jsonb_build_object('status', 'revoked_credentials');
    end if;
    if v_row.revoked_at is not null then
        return jsonb_build_object('status', 'revoked_credentials');
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
        set revoked_at = v_now
        where session_id = p_session_id;
    elsif not p_passive then
        update public.archipelago_runtime_sessions
        set last_activity_at = v_now
        where session_id = p_session_id;
    end if;
    return jsonb_build_object('status', v_status);
end;
$$;

revoke all on function public.archipelago_runtime_session(text, uuid, uuid, integer, integer, boolean)
    from public, anon, authenticated;
grant execute on function public.archipelago_runtime_session(text, uuid, uuid, integer, integer, boolean)
    to service_role;
