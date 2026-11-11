-- Deduplicate one AI action across concurrent Vercel workers and retries.
create table if not exists public.archipelago_runtime_ai_request (
    user_id uuid not null references auth.users(id) on delete cascade,
    request_id uuid not null,
    created_at timestamptz not null default now(),
    primary key (user_id, request_id)
);
alter table public.archipelago_runtime_ai_request enable row level security;
revoke all on public.archipelago_runtime_ai_request from anon, authenticated;
grant select, insert, delete on public.archipelago_runtime_ai_request to service_role;

create or replace function public.archipelago_runtime_consume(
    p_user_id uuid, p_request_id uuid
) returns jsonb
language plpgsql
set search_path = public
as $$
declare
    inserted uuid;
    quota jsonb;
begin
    insert into public.archipelago_runtime_ai_request(user_id, request_id)
    values (p_user_id, p_request_id)
    on conflict do nothing returning request_id into inserted;
    if inserted is null then
        return public.archipelago_runtime_query(p_user_id, false) ||
            jsonb_build_object('limited', true, 'limit_reason', 'duplicate');
    end if;

    quota := public.archipelago_runtime_query(p_user_id, true);
    if (quota->>'limited')::boolean then
        delete from public.archipelago_runtime_ai_request
        where user_id = p_user_id and request_id = p_request_id;
    end if;
    return quota;
end;
$$;
revoke all on function public.archipelago_runtime_consume(uuid, uuid) from public, anon, authenticated;
grant execute on function public.archipelago_runtime_consume(uuid, uuid) to service_role;
