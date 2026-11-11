-- A live topic index derived from active papers, without a separate sync job.
create or replace view public.research_topic_inventory
with (security_invoker = true)
as
select
  topic,
  count(*)::integer as paper_count,
  max(updated_at) as last_ingested_at
from public.research_intake_records
where kind = 'paper'
  and nullif(trim(topic), '') is not null
  and (metadata->>'active') is distinct from 'false'
group by topic;

revoke all on public.research_topic_inventory from anon, authenticated;
grant select on public.research_topic_inventory to service_role;
