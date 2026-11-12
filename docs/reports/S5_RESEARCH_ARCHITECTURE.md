# S5 research intelligence architecture

## Gap matrix at start

| Capability | Existing component | S5 change | Status |
|---|---|---|---|
| Scholarly discovery | `LiveResearchSources` for OpenAlex, Crossref, arXiv and Semantic Scholar | Reused through `DiscoveryOrchestrator` | Implemented and live tested |
| Identity | DOI/arXiv canonicalizer, conservative conflict handling | Kept; explicit DOI version collapse requires same title, lead author and year | Implemented and tested; preprint versus published work remains reviewable |
| Ranking | Title/abstract coverage shortlist | Added Top-K, filters, recency, small citation visibility signal and reasons | Implemented; relevance quality not yet human judged |
| Research graph | Existing research projections | Separate run-scoped Paper/Author/Venue/Institution/Topic projection | Implemented and live data inspected |
| Export | JSON OKF export | Nine-sheet XLSX from stored run | Implemented and validated locally |
| Scheduling | Existing S4 timers and research intake cron | Independent, opt-in S5 monitor state and operator runner | Local and Postgres queue code; no production scheduler enabled |
| Hosted deployment | `host_inference` is packaged alone | Checked-in lightweight scholarly runtime under its Vercel root | Built preview artifact includes S5 imports; hosted search still blocked by database configuration |

The S5 path is `topic → fixed official metadata APIs → canonicalizer → deterministic rank/filter → owner-scoped research snapshot → graph/XLSX`. It never calls academic GPU extraction or writes S4 staging, approval, or production graph files. `host_inference` renders the replacement `/research` page reached from Library Details. Existing academic librarian upload and S4 routes remain separate.

Local snapshots use `ARCHIPELAGO_RESEARCH_DB` or `data/research_intelligence.sqlite3`. Vercel uses `ARCHIPELAGO_RESEARCH_DATABASE_URL` and fails closed if the variable is absent; no hosted `/tmp` SQLite fallback exists. Migration `20261112000000_s5_durable_research.sql` adds owner-scoped private runs, monitors, history and notifications alongside the existing `research_intelligence` schema. The private schema is not exposed to browser roles. Authenticated API routes derive owner ID from the verified Supabase session. The migration has **not** been applied: the connected Supabase plugin exposes only the unrelated PrismLab project, while Archipelago's configured project is `spllaastejfwclllfndp`.

The Vercel preview build completed on 2026-11-12 and its function manifest includes the search, enrichment, Postgres and workbook modules. It excludes `.env` files. This proves packaging, not database connectivity or a working hosted API. The separate librarian UI now renders the same S5 research page and proxies authenticated API requests to the main Archipelago origin. The academic graph remains separate; its new link points to metadata search. Neither graph browsing nor paper search requires SLM/OCR.
