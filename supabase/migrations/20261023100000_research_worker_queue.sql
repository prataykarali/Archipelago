-- A private-to-service-role bridge between Vercel and the local research worker.
create table if not exists public.research_processing_jobs (
  job_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('faculty', 'librarian', 'administrator')),
  topic text not null check (char_length(topic) between 3 and 200),
  paper_limit integer not null default 25 check (paper_limit between 20 and 30),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'completed', 'partial', 'failed')),
  stage text not null default 'QUEUED',
  fetched_count integer not null default 0,
  processed_count integer not null default 0,
  fulltext_count integer not null default 0,
  result_summary jsonb not null default '{}'::jsonb,
  error text,
  worker_id text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists research_one_active_job_per_user
  on public.research_processing_jobs(user_id)
  where status in ('queued', 'running');
create index if not exists research_jobs_queue_order
  on public.research_processing_jobs(status, created_at);
create index if not exists research_jobs_user_recent
  on public.research_processing_jobs(user_id, created_at desc);

create table if not exists public.research_processing_papers (
  job_id uuid not null references public.research_processing_jobs(job_id) on delete cascade,
  paper_id uuid not null,
  title text not null,
  source_url text,
  source_name text,
  access_state text not null,
  okf jsonb not null,
  created_at timestamptz not null default now(),
  primary key (job_id, paper_id)
);
create index if not exists research_papers_job_order
  on public.research_processing_papers(job_id, created_at);

create table if not exists public.research_worker_heartbeats (
  worker_id text primary key,
  last_seen_at timestamptz not null,
  model_status text not null default 'unknown',
  processed_jobs integer not null default 0
);

alter table public.research_processing_jobs enable row level security;
alter table public.research_processing_papers enable row level security;
alter table public.research_worker_heartbeats enable row level security;
revoke all on public.research_processing_jobs from anon, authenticated;
revoke all on public.research_processing_papers from anon, authenticated;
revoke all on public.research_worker_heartbeats from anon, authenticated;
grant select, insert, update on public.research_processing_jobs to service_role;
grant select, insert, update on public.research_processing_papers to service_role;
grant select, insert, update on public.research_worker_heartbeats to service_role;

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
  hourly_limit constant integer := 3;
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
      where user_id = p_user_id and created_at >= now() - interval '1 hour') >= hourly_limit
     or (select count(*) from public.research_processing_jobs
      where user_id = p_user_id and created_at >= now() - interval '1 day') >= daily_limit then
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
