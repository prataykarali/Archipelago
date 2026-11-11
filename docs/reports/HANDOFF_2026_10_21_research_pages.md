# Hosted Research pages and source graph handoff — 2026-10-21

## Built

- Split Research into seven independent routes: `/research/overview`, `/domains`, `/pipeline`, `/papers`, `/college`, `/evidence`, and `/graph`. The nav changes pages; each route has its own content and loader. `/research` opens Overview.
- Expanded one topic intake to at most 50 deduplicated papers per request, round-robin selected across OpenAlex, Crossref, arXiv, Europe PMC, and optional Semantic Scholar. The button performs fetch and save; the Papers page shows per-provider counts and downloadable normalized intake JSON.
- Added `/api/research/graph/ingested` and `/api/research/graph/export`. They project saved Supabase source records into topic, provider, paper/page, and matched institutional concept nodes. The Graph page visualizes and exports that projection. No new database or Kuzu instance was created.
- Chat looks up saved research and campus records alongside its existing institutional graph answer. For out-of-corpus academic requests, a strong saved-source match yields linked, extractive evidence rather than the old scope refusal. Other guardrails are preserved.
- Faculty can read college sources but cannot use the page ingestion form. Librarians and administrators retain page edits and concept annotations.
- Production Vercel deployment `dpl_b7AAGL8GByJTFt62iGfGMW1n6TgK`; canonical alias `https://archipelago-archipelago-6383.vercel.app` resolves to it.

## Verified

- 28 focused tests passed; Ruff, JavaScript syntax, file size, banned pattern, and architecture checks passed. Repository-wide Mypy remains failing on existing errors and missing imports in its isolated tool environment.
- Live local provider test fetched and saved 50 distinct database-transaction papers: 13 OpenAlex, 13 Crossref, 12 arXiv, 12 Europe PMC. Semantic Scholar was not configured. UEM/IEM sitemap discovery returned 62 candidates; an approved UEM page fetched and saved.
- Existing Supabase counts after that run: 706 papers and 7 institutional pages. The local route projected all 713 records into 777 nodes and 1,574 relationships. Research reply returned five linked passages. Both an out-of-corpus database question and an indexed graph question received source-linked chat evidence.
- Browser check: all seven routes returned 200 with no JavaScript page errors; Graph displayed all 537 institutional concepts and all 777 projected research nodes; faculty college editing form was hidden.
- Production canonical alias: deployment Ready; `/api/readiness` returned 200, full 537-concept corpus and research intake enabled; `/api/research/intake/metrics` returned 706 papers/7 pages; `/library` returned 200. `/research/graph` redirected to login without a staff session, as expected.

## Remaining limitations

- Hosted `ingestion` reports `false`: the separate PDF/TOC worker is not running on Vercel. This release stores scholarly metadata and available abstracts plus approved institutional HTML, not full paper PDFs, extracted full text, or rights-reviewed evidence in Kuzu.
- The Research graph is a durable projection of Supabase records, bounded to the latest 2,000 sources per request; it is not a separate database graph. Concept links are deterministic title/topic matches, not model-extracted relations.
- Vercel Cron and `CRON_SECRET` are configured; its handler and source adapters passed local checks, but a successful automatic run of this new deployment has not yet been observed. Production SerpAPI and Semantic Scholar keys are absent; Apify has not been integrated. Official sitemaps and public scholarly APIs work without them.
- No existing student, faculty, librarian, or administrator password/session was used for a live authenticated production browser run. Local role/API checks and production anonymous health checks passed; production staff write and chat flows remain unverified with a real session.
