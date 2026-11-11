# Hosted research intake handoff — 2026-10-20

## Built

- `/library` serves the library page without a session redirect; its browser idle handler no longer sends readers to login.
- `/api/research/graph/full` serves the full hosted corpus. Verified 520 concepts, 1,862 relationships, and 55 source documents from the local Supabase-backed graph. The Research UI now starts on the full graph and offers source-document and research-source views.
- Added staff research intake on the existing Supabase project. OpenAlex and Crossref discovery accepts any topic, deduplicates by DOI, and saves metadata plus available abstracts. Approved IEM/UEM HTML pages are fetched with a host allowlist, no redirects, and a byte limit. Faculty may discover papers and read replies; librarians and administrators may also ingest college pages and edit graph annotations.
- Added a deterministic reply endpoint that returns matching saved abstract excerpts with original source links. It does not synthesize unsupported claims.
- Production Vercel deployment: `dpl_C57Zysfz2Qdfs8cPRMNM5EAjNH2S`.

## Verified

- Local hosted tests: 21 passed. Ruff and targeted strict Mypy passed for new backend modules; JavaScript syntax checks passed.
- Real provider and Supabase intake: five topics spanning flood adaptation, manuscript preservation, agriculture, public health, and constitutional law, plus two official college home pages. Supabase contains 119 paper records, 50 with abstracts, and 2 college page records with extracted text.
- HTTP route check: staff-backed local `records` returned 121; `reply` returned five cited excerpts for an urban flood query.
- Production canonical URL: `/api/readiness` returned `ok: true`, 520 concepts, full corpus, `research_intake.enabled: true`; `/library` returned 200 without redirect.

## Deferred / next pair

- The older PDF/TOC upload worker remains disabled on Vercel (`ingestion: false`). This release ingests scholarly metadata, available abstracts, and approved college HTML pages; it does not ingest full paper PDFs into the private research evidence tables or project those papers into Kuzu.
- The original five-topic full Research Intelligence staging evidence gate remains unmet. Do not label this release as the full Research Intelligence pipeline until the worker, rights checks, evidence validation, and PostgreSQL/Kuzu projection are deployed and tested with authenticated staff sessions.
- The repository-wide Mypy gate has existing errors outside the new hosted modules. Targeted new-code checks pass; the whole-repo gate needs separate cleanup.
