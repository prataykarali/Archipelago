# ARCHIPELAGO — RESEARCH PIPELINE ROOT CAUSE ANALYSIS

## 1. End-to-End Execution Path Traced
`USER QUERY` → `understand_query` (`relevance_engine.py`) → `classify_domain` / `select_providers` (`provider_selector.py`) → `DiscoveryOrchestrator.discover_with_status` (`orchestrator.py`) → `LiveResearchSources.search` (`live_sources.py` + `resilient_http.py`) → `Canonicalizer.canonicalize_candidates` (`canonicalizer.py`) → `evaluate_relevance` / `assess_topic_eligibility` (`relevance_engine.py`, `search.py`) → `by_work` deduplication (`search.py`) → `enrich_authors` / `enrich_s2_authors` / `enrich_orcid_authors` / `enrich_venues` (`enrichment.py`) → `build_graph` (`graph.py`) → `extract_evidence` (`extraction.py`) → `discover` sort (`search.py`) → `hosted_store().save_run` (`storage.py` / `postgres_storage.py`) → `research_intelligence.js` / `papers.html` → `build_workbook` (`workbook.py`, `workbook_extra.py`).

## 2. Root Causes Identified
1. **Bag-of-Words Topic Eligibility (`search.py`)**: `assess_topic_eligibility` only checked whether each query word appeared *somewhere* in `title + abstract + fields`, admitting unrelated papers where `"liquid"`, `"neural"`, and `"networks"` appeared in separate contexts (e.g., *Soft Liquid Metal Neural Interface*, *vapor-liquid equilibria*).
2. **Biomedical Provider Leakage (`provider_selector.py`)**: `europe_pmc` was included in `ai_cs` and `general` profiles, flooding CS/AI queries with biomedical/materials preprints (14/20 results on `Liquid Neural Networks`).
3. **Preprint Type & Cross-Year Deduplication (`biomed_sources.py`, `search.py`)**: Europe PMC hardcoded `publication_type="journal-article"` for Research Square `posted-content` preprints, and `by_work` keyed on `(title, first_author, year)` instead of `(title, first_author)`, failing to collapse preprints with later-year published versions.
4. **Coverage Audit > 100% (`workbook_extra.py`)**: `"Papers: References Populated"` used `total_refs` (249) as `Populated Count` against `Total Entities = n_papers` (20), yielding `1245%`.
5. **Citation Graph Metric Conflation (`graph.py`)**: `resolved_known_works` counted syntactic identifier prefixes (`https://openalex.org/W...`, `10.`) as verified works without separating `identifier_matched_count` from `existence_verified_count`.
6. **Serverless Latency (~53s)**: Synchronous sequential loops over 20 S2 authors, 15 ORCID profiles, and 20 OpenCitations DOIs pushed `POST /api/research/intelligence/search` to ~53s on Vercel.

## 3. Fixes Applied
- Added `relevance_engine.py` with ordered-phrase proximity (`_has_ordered_phrase`), sentence-level TF-cosine, and research-field compatibility checks BEFORE sorting.
- Scoped `europe_pmc` / `pubmed` to `biomedical`, detected preprints in `biomed_sources.py`, and collapsed cross-year preprint/published pairs in `search.py`.
- Fixed `workbook_extra.py` denominator/numerator (`refs_pop <= n_papers`) and separated `graph.py` citation resolution metrics.
- Bounded synchronous enrichment calls, reducing `Liquid Neural Networks` live latency from ~53s to **24.14s** (`diffusion models`: 9.66s, `retrieval augmented generation`: 10.07s, `quantum error correction`: 6.02s).
