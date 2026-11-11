-- Admit at most 100 active research jobs across all staff accounts.
-- A request rejected by the workstation approval gate does not consume the
-- per-user research allowance; the global active-job cap remains unchanged.
create or replace function public.research_enqueue_job(
  p_user_id uuid,
  p_role text,
  p_topic text,
  p_paper_limit integer default 25
)
returns public.research_processing_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  hourly_limit constant integer := 5;
  daily_limit constant integer := 10;
  queue_limit constant integer := 100;
  created public.research_processing_jobs;
begin
  if p_role not in ('faculty', 'librarian', 'administrator')
     or char_length(trim(p_topic)) not between 3 and 200
     or p_paper_limit not between 20 and 30 then
    raise exception 'invalid_research_job';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('research_global_queue', 0));
  perform pg_advisory_xact_lock(hashtextextended(p_user_id::text, 0));
  if (select count(*) from public.research_processing_jobs
      where user_id = p_user_id and created_at >= now() - interval '1 hour'
      and not (status = 'failed' and stage = 'LOCAL_APPROVAL_DECLINED')) >= hourly_limit
     or (select count(*) from public.research_processing_jobs
      where user_id = p_user_id and created_at >= now() - interval '1 day'
      and not (status = 'failed' and stage = 'LOCAL_APPROVAL_DECLINED')) >= daily_limit then
    raise exception 'research_rate_limited';
  end if;
  if exists (select 1 from public.research_processing_jobs
             where user_id = p_user_id and status in ('queued', 'running')) then
    raise exception 'research_job_in_progress';
  end if;
  if (select count(*) from public.research_processing_jobs
      where status in ('queued', 'running')) >= queue_limit then
    raise exception 'research_queue_full';
  end if;
  insert into public.research_processing_jobs(user_id, role, topic, paper_limit)
    values (p_user_id, p_role, trim(p_topic), p_paper_limit)
    returning * into created;
  return created;
end;
$$;
revoke all on function public.research_enqueue_job(uuid, text, text, integer)
  from public, anon, authenticated;
grant execute on function public.research_enqueue_job(uuid, text, text, integer)
  to service_role;
