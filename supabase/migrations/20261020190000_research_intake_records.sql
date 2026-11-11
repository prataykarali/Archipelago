-- Staff research intake. The hosted service writes through its server-only key.
create table if not exists public.research_intake_records (
  id uuid primary key default gen_random_uuid(),
  record_key text not null unique,
  kind text not null check (kind in ('paper', 'institutional_page')),
  title text not null,
  source_url text not null,
  source_name text not null,
  topic text not null default '',
  content text not null default '',
  published_at date,
  metadata jsonb not null default '{}'::jsonb,
  updated_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists research_intake_kind_updated_idx
  on public.research_intake_records (kind, updated_at desc);
create index if not exists research_intake_topic_idx
  on public.research_intake_records (topic);
alter table public.research_intake_records enable row level security;
revoke all on public.research_intake_records from anon, authenticated;
grant select, insert, update on public.research_intake_records to service_role;
