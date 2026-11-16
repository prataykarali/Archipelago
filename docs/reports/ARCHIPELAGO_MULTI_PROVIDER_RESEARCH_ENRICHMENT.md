# ARCHIPELAGO — MULTI-PROVIDER SCHOLARLY ENRICHMENT, GOOGLE RESEARCH DISCOVERY & RANKING-READY METADATA

## 1. Provider Availability & HTTP Results

| Provider | Before (`1st(2).xlsx` baseline) | After (Live 3-Topic Eval) | Notes |
| --- | --- | --- | --- |
| **OpenAlex** | HTTP 200 | HTTP 200 (`live`: 33 / 23 / 22 records) | Batched author & venue enrichment + FWCI |
| **Crossref** | HTTP 200 | HTTP 200 (`live`: 27 / 33 / 30 records) | Extracts DOI references, grants, `published-online`, `update-to` retractions |
| **Semantic Scholar** | HTTP 429 (no retry/limit) | HTTP 200 on `omni ai models` (39 records); HTTP 429 on rapid follow-up topics | Rate-limited + `Retry-After` + circuit breaker (`RATE_LIMITED` surfaced honestly) |
| **arXiv** | HTTP 429 | `ReadTimeout` / HTTP 429 under burst | Rate-limited (1.0s min interval) + polite `mailto:` User-Agent; `preprint` / `peer_reviewed=False` |
| **Europe PMC** | Skipped (`not_selected_for_domain:ai_cs`) | HTTP 200 (`live`: 25 / 25 / 25 records) | Now enabled for `ai_cs` and `general` domains |
| **OpenAIRE** | Skipped (`not_selected_for_domain:ai_cs`) | HTTP 200 (`live`: 30 / 30 / 30 records) | Now enabled for `ai_cs` and `general` domains |
| **DBLP** | HTTP 202 bot gate | HTTP 202 (`blocked_bot_challenge`) | Bot gate respected without bypass |
| **ORCID** | Unused in S5 enrichment | Public `/v3.0/{orcid}/person` enrichment | Verifies ORCID profiles when ORCID IDs are present |
| **Google Research** | Not integrated | HTTP 200 (`navigation_only`) / 403-safe | Official `https://research.google/pubs/?search=...` links + strict affiliation vs official listing separation |

## 2. Before / After Source Contributions (`omni ai models`, `top_k=20`)

- **Before (`1st(2).xlsx`)**: 14 returned / 20 requested; OpenAlex-dominated; 154 authors; 3 venues; 1 citation edge; 0% datasets; 0% funding; 21.4% eval metrics; 78.6% methods.
- **After (`omni_ai_models_20.xlsx`)**:
  - **Returned**: **20 / 20** qualifying papers (from 119 deduplicated candidates across 5 live providers)
  - **Paper provenance contributions**: `europe_pmc` (9), `openalex` (8), `openaire` (7), `semantic_scholar` (4) — 28 provenance rows across 20 papers
  - **Authors**: 232 author rows, 127 enriched author observations
  - **References**: 249 reference rows (`100%` resolved to OpenAlex/DOI identifiers)
  - **Research Claims**: 99 evidence-anchored claims (`80.0%` methods coverage, `40.0%` evaluation metrics coverage)
  - **Metric Observations**: 505 provider-stamped rows

## 3. Author Identity-Resolution Results

- Implemented `detect_author_collisions` in `archipelago/scholarly/intelligence/enrichment.py` to flag normalized name collisions without merging distinct researchers (`IDENTITY_REVIEW_REQUIRED`).
- On `omni ai models`, detected and preserved separate records for colliding name `"yuan yao"`.
- Added Semantic Scholar author enrichment (`enrich_s2_authors`) and ORCID public person verification (`enrich_orcid_authors`), separating paper-specific affiliations from `current_affiliations`.

## 4. Paper Metadata Coverage

- **omni ai models**: 20/20 papers, 80.0% methods, 40.0% evaluation metrics, 0.0% datasets, 0.0% funding (honest `NOT_FOUND_IN_AVAILABLE_EVIDENCE` / `PROVIDER_FIELD_ABSENT` — zero fabricated fields).
- **liquid neural networks**: 20/20 papers (103 candidates; `europe_pmc`: 14, `openalex`: 4, `openaire`: 2, `crossref`: 1), 69 claims, 25 references, 91 metric observations.
- **retrieval augmented generation**: 20/20 papers (105 candidates; `europe_pmc`: 20, `crossref`: 1), 114 claims, 48 metric observations.
- Added `citations_per_year`, `first_online_date`, `arxiv_version`, `published_vs_preprint`, `field_statuses`, `code_repo_urls`, and `dataset_repo_urls` (extracted only from explicit evidence).

## 5. Venue Metadata Coverage

- Added `classify_venue_category` to strictly separate `peer_reviewed_journal`, `peer_reviewed_conference`, `workshop`, `preprint_repository`, and `institutional_listing`.
- Licensed metrics (`Journal Impact Factor`, `CiteScore`, `SJR`, `CORE classification`) remain `LICENSE_RESTRICTED` — OpenAlex `h_index` is never substituted for JIF.

## 6. Google Research Discovery Results

- Added `archipelago/scholarly/discovery/google_research.py`:
  - Checks `https://research.google/pubs/` politely via `ProviderReliabilityClient` without bypassing 403/bot restrictions.
  - Provides official navigation URLs (`https://research.google/pubs/?search=...`) at run and paper levels.
  - Separately classifies `GOOGLE_RESEARCH_OFFICIAL_LISTING`, `GOOGLE_AUTHOR_AFFILIATION`, and `GOOGLE_COLLABORATOR`.

## 7. Google Scholar Limitations & Available Links

- Google Scholar has no official public bulk API and restricts automated scraping.
- Every run provides `google_scholar_url` for topic verification; every paper provides a paper-specific Google Scholar search link; every author provides a Google Scholar `author:"..."` search link.
- Unavailable Google Scholar metrics are recorded as `NOT_AVAILABLE` (never zero-filled).

## 8. Citation Graph Coverage

- Updated `archipelago/scholarly/intelligence/graph.py` to index `known` papers by OpenAlex ID (full and short), normalized DOI, Semantic Scholar ID, and arXiv ID, and added `coverage_report` (`total_reference_links`, `resolved_known_works`, `in_collection_edges`, `resolution_rate`).
- Live 3-topic results:
  - `omni ai models`: 249 reference links, 249 resolved known works (`resolution_rate: 1.0`), 0 in-collection edges (2026 recent papers do not cite each other yet).
  - `liquid neural networks`: 25 reference links, 25 resolved (`resolution_rate: 1.0`), 0 in-collection edges.
  - `retrieval augmented generation`: 0 reference links in the top-20 newest Europe PMC/Crossref records.

## 9. Ranking / Sorting Parameters & Definitions

Default ordering remains `newest` (`publication_date_desc`). Explicitly selectable grounded sort options (with missing values sorted last, never zero):
- `newest`: Descending by `publication_date`.
- `relevance`: Upstream provider search ranking.
- `citations`: Descending by highest single-provider citation count.
- `citations_per_year`: Descending by `citation_count / max(1, current_year - year + 1)`.
- `fwci`: Descending by OpenAlex Field-Weighted Citation Impact.
- `open_access`: Verified `is_open_access == True` first.
- `evidence_completeness`: Count of populated evidence fields (`abstract`, `doi`, `methods`, `datasets`, `evaluation_metrics`, `grants`, `references`).
- `provider`: Canonicalized provider return order.

## 10. XLSX Sample & Field-Level Provenance

- All 14 sheets preserved: `Papers`, `Authors`, `Venues`, `References`, `Citation_Edges`, `Topic_Results`, `Sources_Provenance`, `Errors_Review`, `Run_Manifest`, `Institutions_Affiliations`, `Funding_Grants`, `Research_Claims`, `Metric_Observations`, `Coverage_Audit`.
- Contradictory citation counts across providers are preserved as separate rows in `Metric_Observations` with provider name, timestamp, definition, and coverage notes.
- Exported evaluation workbooks stored under `artifacts/validation/multi-provider-eval/`.

## 11. Unresolved Fields & Provider Restrictions

- **DBLP**: HTTP 202 bot challenge (`blocked_bot_challenge`) — respected without bypass.
- **Semantic Scholar / arXiv**: Subject to shared-IP HTTP 429 under rapid consecutive queries without an API key (`SEMANTIC_SCHOLAR_API_KEY` recommended in Vercel env).
- **Google Scholar**: No bulk API; `NOT_AVAILABLE` for unverified profile metrics.
- **Clarivate JIF / Scopus CiteScore / SJR / CORE**: `LICENSE_RESTRICTED`.

## 12. Git SHA & Deployment Verification

- Branch: `feature/multi-provider-research-enrichment`
- Feature Commit SHA: `c500500`
- Unit Tests: `32 passed, 1 warning` (`test_s5_research_intelligence.py`, `test_s5_enrichment.py`, `test_s5_multisource_providers.py`, `test_s5_multi_provider_enrichment.py`)
- Runtime Sync Check: `python3 scripts/ops/sync_s5_host_runtime.py --check` exited `0`
- Vercel Preview Deployment: `https://archipelago-667xwngpn-archipelago-6383.vercel.app` (HTTP 200 on `/research`, auth-gated `/api/research/intelligence/readiness`)
- Vercel Production Promotion: `https://archipelago-blond.vercel.app/research?run=dab152b3-9821-4002-9ce4-5d3ca2292f30` (HTTP 200, verified live HTML & updated multi-provider filters/UI)
