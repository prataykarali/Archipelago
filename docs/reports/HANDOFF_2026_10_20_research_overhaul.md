# Hosted library and research overhaul — 2026-10-20

## Built

- `/library` opens directly and shows the two hosted intake channels with aggregate counts.
- The staff research workspace has subject cards, pipeline status, source intake, an evidence reply view, and a dedicated graph studio. The graph loads all 537 concepts and 1,903 relationships on entry; selecting a concept narrows the view. Faculty can read, while librarians and administrators can save graph details and college page records.
- The hosted scholarly path now searches OpenAlex, Crossref, arXiv, and Europe PMC. An optional server-side Semantic Scholar key enables that adapter. Saved records are deduplicated by identifier; evidence queries search the full Supabase store, not just the recent-source window.
- Official UEM and IEM sitemap pages are discovered daily, constrained to approved HTTPS hosts and paths, checked against robots.txt, and saved with source URLs. SerpAPI is an optional sitemap fallback; Apify is not needed for the working primary path.
- A Vercel Cron route rotates 13 subject topics and four campus pages per day. It requires `CRON_SECRET` and writes to the existing Supabase project; no user accounts were changed.
- The complete graph was published to the existing private Supabase cache and public graph dataset.

## Verified

- Local hosted app: `/library` and `/library/` return 200; unauthenticated `/research` redirects to login; unauthenticated full research graph returns 401. The health response reports 537 concepts and a full corpus.
- Automated focused suite: 46 tests passed. Ruff and JavaScript syntax checks passed. Browser review rendered 10 subject cards and 537 of 537 graph nodes with no page errors.
- The production scheduled endpoint fetched and saved two subject batches and four sitemap pages. Additional subject runs populated all 13 domains; Supabase reported 701 paper records and six campus pages after the run.
- Final Vercel production deployment `dpl_E2xDSiPHiDvYBbzADa2cvnJpGFcb` is ready on `https://archipelago-archipelago-6383.vercel.app`. Protected live checks returned `/library` 200, `/api/health` 200 with 537 concepts, aggregate metrics 200, unauthenticated `/research` 302, and unauthenticated research graph and schedule 401.

## Scope and follow-up

- This hosted path stores scholarly metadata, available abstracts, and approved institutional HTML. The older PDF/TOC upload worker and the separate PostgreSQL/Kuzu Research Intelligence worker remain unreleased. OPAC and IEMCRP cannot be claimed as live ingestion sources until their access is available.
- The repository-wide strict mypy gate has pre-existing errors outside this change. The four-role browser verification still needs real authenticated sessions; the tests exercise role boundaries with controlled principals.
