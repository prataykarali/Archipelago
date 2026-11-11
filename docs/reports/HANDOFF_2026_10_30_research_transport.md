# Handoff — research transport and Koha metadata, 30 October 2026

## Built

- `archipelago-librarian` is the second Vercel project on the `shinaura`
  account. Its production source is branch `codex/research-transport-20261029`,
  commit `8c84758`.
- Moved the original five Research pages, hero artwork, progress view, topic
  graph, paper OKF, and topic dossier to the new project. Staff sign in to the
  same Supabase Auth project. The new app verifies their `profiles.role`.
- The Research API forwards verified staff requests to the existing hosted
  backend. This keeps its queue and local workstation approval, Indra paper
  extraction, automatic OKF, HF publication, and progress APIs intact. No
  research job was started during deployment. The original hosted backend must
  remain reachable until a later backend migration.
- Copied the Academic graph into the new project and added Koha metadata under
  Academic → Library details. The original library page was not edited.
- Validated and published four dated Koha ODS exports to a separate private
  Supabase Storage object. Counts: 109 holdings, 1,212 journal issues, 952
  subject counts, 2,882 subject titles. The exports were last modified on
  3 October 2026 and are clearly marked stale.
- Enabled `archipelago-koha-sync.timer` for 09:00 Asia/Kolkata daily on the
  local workstation. A manual service run succeeded and correctly skipped an
  unchanged snapshot. Vercel has separate daily scheduled research discovery
  and Koha freshness checks.
- The new Vercel project's encrypted production variables now include the
  shared Supabase URL, publishable key, and secret key. Values were never
  printed. Focused Ruff and five tests passed.

## Deferred or limited

- Daily Koha data changes require a new **authorized** export in `data/koha`.
  The public OPAC disallows crawling; its checked OAI path was absent and the
  public MARCXML export was denied. The timer checks and uploads new exports,
  but it cannot create fresh source data on its own.
- The first Vercel deployment still serves its old `/research` URL and the
  original `/graph` page because that Vercel account is not connected here.
  The new Research and Academic graph URLs are on the second project. The
  existing `/library` page was deliberately left alone.
- Candidate discovery makes review proposals. It does not auto-ingest papers.
  The user will choose later whether to start ingestion requests.
- The full repo quality gate has substantial pre-existing failures outside
  these changes; focused Ruff and tests passed. A strict mypy run also lacks
  installed stubs for Flask and requests in this environment.

## Next pair

1. Verify the new production Research dashboard with a real staff account,
   including one saved OKF and local worker status. Do not enqueue a job merely
   to test it.
2. Connect the original Vercel account if the original `/research` link should
   redirect to the new site.
3. Arrange an authorized scheduled Koha export to `data/koha` so daily updates
   contain current OPAC changes.
4. Plan the later paper ingestion request flow and real-time inference/graph
   references as separate sessions.
