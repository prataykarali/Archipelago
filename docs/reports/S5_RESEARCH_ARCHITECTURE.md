# S5 research intelligence architecture

## Gap matrix at start

| Capability | Existing component | S5 change | Status |
|---|---|---|---|
| Scholarly discovery | `LiveResearchSources` for OpenAlex, Crossref, arXiv and Semantic Scholar | Reused through `DiscoveryOrchestrator` | Implemented and live tested |
| Identity | DOI/arXiv canonicalizer, conservative conflict handling | Kept; explicit DOI version collapse requires same title, lead author and year | Implemented and tested; preprint versus published work remains reviewable |
| Ranking | Title/abstract coverage shortlist | Added Top-K, filters, recency, small citation visibility signal and reasons | Implemented; relevance quality not yet human judged |
| Research graph | Existing research projections | Separate run-scoped Paper/Author/Venue/Institution/Topic projection | Implemented and live data inspected |
| Export | JSON OKF export | Nine-sheet XLSX from stored run | Implemented and validated locally |
| Scheduling | Existing S4 timers and research intake cron | Independent, opt-in S5 monitor state and operator runner | Implemented locally; no scheduler enabled |
| Hosted deployment | `host_inference` is packaged alone | Local package route and replacement `/research` page | Hosted S5 API blocked until package and durable storage are deployed |

The S5 path is `topic → fixed official metadata APIs → canonicalizer → deterministic rank/filter → owner-scoped research snapshot → graph/XLSX`. It never calls academic GPU extraction or writes S4 staging, approval, or production graph files. `host_inference` renders the replacement `/research` page reached from Library Details. Existing academic librarian upload and S4 routes remain separate.

Local snapshots use `ARCHIPELAGO_RESEARCH_DB` or `data/research_intelligence.sqlite3`. This is suitable for a persistent local service; the hosted Vercel image packages only `host_inference` and has no durable SQLite volume. Its S5 API returns `research_runtime_unavailable` rather than claiming a working hosted search. A server-side research package and durable store must be deployed before release.
