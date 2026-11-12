# S5 end-to-end acceptance

**Current state: engineering incomplete; no production deployment or academic publication.** The `/research` page linked from Library Details now renders the replacement metadata workspace locally. The browser smoke test used the actual saved live graph-neural-networks response as a mocked HTTP payload and rendered 20 paper cards; screenshot: `artifacts/validation/s5-research-intelligence/research-page-live-payload.png`. This is a UI rendering test, not proof of an authenticated production search.

Journey A: `recent efficient retrieval augmented generation` returned 20 real metadata records with `year_from=2021` and newest recency weighting. Journey B: `continual learning` returned 20 real paper records and author names/ORCIDs when supplied; author metrics and independent disambiguation were unavailable. Journey C: `graph neural networks` returned 20 papers, 28 verified in-set citation edges, and a validated nine-sheet workbook at `artifacts/validation/s5-research-intelligence/graph-neural-networks.xlsx`.

Focused tests: 44 passed, 2 pre-existing/independent cases deselected in the combined run. The exact output is in `artifacts/validation/s5-research-intelligence/tests.log`. Focused Ruff and S5 strict mypy passed (`ruff.log`, `mypy.log`); the workbook validation is in `workbook-validation.log`. The full quality gate remains red on repository-wide Ruff, strict mypy and file-size baseline failures. Hosted end-to-end tests, production durable storage, actual login role tests, authorized venue metrics, ORCID enrichment, human relevance judgments and scheduler deployment remain open. The existing S4 review candidate has not been published or synced by S5.

## S5-B validation, 2026-11-12

| Requirement | Status | Evidence or blocker |
|---|---|---|
| Main landing before sign-in | PASS | `https://archipelago-blond.vercel.app/` returned HTTP 200 with the cinematic landing title; auth appears on entry actions. The separate shinaura Vercel domain is intercepted by Vercel SSO. |
| Librarian and academic page code | PARTIAL | Librarian `/research#topic-form` now renders S5 search instead of local OCR/SLM ingestion; academic graph links to it and remains separate. Not yet deployed to the librarian production URL. |
| Hosted runtime packaging | PASS | `vercel build` preview succeeded; function manifest includes S5 search, enrichment, Postgres and workbook modules and excludes `.env` files. |
| Durable storage schema and code | PARTIAL | Private Postgres migration and adapter written, but migration is unapplied and no database URL is configured in Vercel preview. |
| Live local search | PASS | `recent efficient retrieval augmented generation` returned three selected papers from live OpenAlex, Crossref and arXiv; Semantic Scholar reported rate limiting. |
| Persisted graph and workbook | PARTIAL | Live graph-neural-networks run reopened from local SQLite after store reinitialization, had 30 nodes and 37 edges, and regenerated all nine sheets. Hosted Postgres proof pending. |
| Owner isolation | PARTIAL | Local API route tests cover run, graph, workbook and monitor mutation for two principals. Real Postgres and Supabase-authenticated cross-user tests pending. |
| Author and venue provenance | PARTIAL | Bounded OpenAlex author lookup and venue source metadata are implemented; human identity review and licensed venue metrics pending. |
| Monitor history and updates | PARTIAL | Private schema, code and in-app view implemented; no deployed worker or durable execution proof. |
| Human IR relevance benchmark | BLOCKED | Reviewer judgments are still absent. Precision@K and nDCG@K remain pending. |
| Protected hosted E2E and release | BLOCKED | Archipelago Supabase project is not exposed by the connected plugin; Vercel has no research DB URL. No production promotion or S4 publication was performed. |

The focused S5 unit suite passed locally, and the repository-wide quality gate still fails on existing Ruff, mypy and file-size debt. This update does not claim a working hosted search or production readiness.
