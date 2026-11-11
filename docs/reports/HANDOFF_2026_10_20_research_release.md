# Research and hosted release handoff — 2026-10-20

## Built

- Restored the standalone hosted app import boundary by moving hosted Research Intelligence permissions into `host_inference/hostapp/research_access.py`; hosted middleware now maps privileged paths to their specific capabilities.
- Added a Vercel Flask entrypoint with a full-corpus guard. Production deployment `dpl_8EskL5946gjjLDTpVXNmJzLDDtQ2` is ready at `https://archipelago-archipelago-6383.vercel.app`.
- Added a deterministic staff research reply endpoint to the local pipeline. It renders stored topic-relevance shortlist reasons and coverage gaps without inventing claims.
- Installed the private research schema in the existing Supabase project `spllaastejfwclllfndp`. All ten tables use RLS; browser roles have no schema usage. Existing users and roles were left intact.
- Saved deployment checks in `docs/validation/research-intelligence-e2e.md` and `artifacts/validation/research-intelligence/vercel-release-2026-10-20.json`.

## Deferred and release gate

The Vercel app is healthy on the full institutional corpus, but its research worker and reply route are not deployed. No research database connection is configured in Vercel. The five required staging jobs and live role tests remain undone. Research Intelligence stays disabled and must not be presented as a released feature. The local five-topic runs remain PARTIAL with source/evidence gaps. The repository-wide strict mypy gate timed out; focused tests and Ruff passed.

## Next pair

Package or separately host the PostgreSQL research worker with durable scheduling and projection persistence, connect it to the existing Supabase project through a server-only pooled connection, then run all five topics and four-role tests on Vercel staging. Promote Research Intelligence only after the report's release gate passes. Keep local run evidence separate from staging evidence.
