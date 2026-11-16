# Archipelago Cross-Provider Evidence Repair Report

**Date:** 2026-11-16  
**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/multi-provider-research-enrichment`  
**Repaired Workbook:** `artifacts/validation/Archipelago_Space_State_Model_Repaired.xlsx`  
**Deployment Status:** Local & unit/live verified. **Not redeployed** (awaiting review).

---

## 1. Executive Summary & Root Cause Analysis

On the reproducible failing case (`topic="space state model"`, `top_k=20`), the previous pipeline contacted 6 scholarly providers (128 raw records -> 126 canonical candidates) but exported **8 papers**, all 8 from **OpenAlex** (`8/8` primary, `0` from Crossref/arXiv/OpenAIRE/DataCite/Semantic Scholar), with `Metric_Observations` containing 175 OpenAlex rows, 7 OpenCitations rows, and 0 Crossref/Semantic Scholar rows.

### Phase 1 — Instrumented Candidate Waterfall (Before vs. After on `"space state model"`)

| Stage | Before (Baseline) | After (Repaired) |
|---|---|---|
| Raw records returned | OA=31, CR=12, S2=0 (429), arXiv=25, OAIRE=30, DC=30 (Total 128) | OA=31, CR=12, S2=0 (429), arXiv=25, OAIRE=30, DC=30 (Total 128) |
| Canonical unique candidates | 126 (only 2 OpenAIRE merged into OpenAlex) | 126 |
| Relevance-eligible candidates | **OA=8**, CR=0, arXiv=0, OAIRE=0, DC=0 | **61 total eligible** across OA, OpenAIRE, Crossref, DataCite |
| Primary rejection reason (Before) | `scattered_terms_without_phrase_or_proximity`: OA=23, CR=12, arXiv=25, OAIRE=28, DC=30 | Reordered compound `"state-space model"` / `"state space model"` accepted; arXiv `"space ... weather"` / `"cosmic"` distractors still rejected |
| Selected papers | 8 / 20 | **20 / 20** |
| Selected primary provider | OpenAlex=8 | OpenAlex=16, OpenAIRE=3, Crossref=1 |
| All contributing provenance (`Sources_Provenance`) | OpenAlex=8 (8 rows total) | **62 rows**: OpenAlex=19, OpenAIRE=18, Crossref=12, Semantic Scholar=11, DataCite=2 |
| Secondary Stage-2 enrichment matches | None (except OpenCitations=7, OpenAlex authors/venues) | OpenAlex=3, Crossref=11, Semantic Scholar=11, OpenAIRE=12, DataCite=2, OpenCitations=8 |
| `Metric_Observations` | OA=175, OC=7, S2=0, CR=0 | **384 rows**: OA=330, S2=24, CR=12, ORCID=10, OC=8 |
| `Authors` observations | OA=29 | **75 rows**: OA=51, S2=10, ORCID=10, paper metadata=4 |

### Root Causes Identified

1. **Strict ordered-phrase gate in `relevance_engine.py`**: `"space state model"` failed to match `"state-space model"` / `"state space models"` in Crossref (12/12 rejected) and OpenAIRE (28/28 rejected), leaving only 8 OpenAlex papers that happened to contain the literal order `"space state model"`. Additionally, 4+ term multi-concept queries (e.g., `"CRISPR base editing sickle cell"`, `"ocean acidification coral reefs"`) were rejected before reaching the bigram-overlap check.
2. **Incomplete canonical matching & metadata preservation (`canonicalizer.py`)**: `_find_match` did not match on `openalex_id`, `semantic_scholar_id`, or verified title-author-year, and `_merge_records` did not retain `contributing_providers`, `provider_records`, `field_provenance`, `conflicting_observations`, or `version_relationships`.
3. **Missing Stage-2 cross-provider paper enrichment (`enrichment.py`, `search.py`)**: After top-K selection, Crossref, OpenAlex (for non-OpenAlex primaries), Semantic Scholar (by DOI/arXiv), OpenAIRE, arXiv, and DataCite were never queried to enrich selected papers.
4. **Single-provider author/venue & contradictory manifest reporting (`workbook.py`, `workbook_extra.py`)**: `Authors` emitted only one observation per author, `enrich_orcid_authors` did not emit separate `orcid` observations, `Topic_Results` used a legacy keyword description, and `Run_Manifest` falsely stated `"No ranking or quality scores are computed"`.

---

## 2. Implemented Repairs

- **Phase 2 (`archipelago/scholarly/discovery/canonicalizer.py`, `orchestrator.py`)**:
  - Added matching by normalized DOI, canonical arXiv ID, normalized OpenAlex ID, Semantic Scholar ID, secondary IDs, and verified title + shared author surname + publication year (±1 year), guarded by `_conflicting_ids`.
  - Retained `primary_provider`, `contributing_providers`, `provider_records`, `field_provenance`, `conflicting_observations`, `version_relationships`, and `identity_match_confidence`.
  - Instrumented Stage-1 per-provider waterfall counts in `DiscoveryOrchestrator.last_selection["waterfall"]`.
- **Phase 3 (`archipelago/scholarly/intelligence/enrichment.py`, `search.py`)**:
  - Added bounded, cached, rate-limit-aware `enrich_papers_multi_provider()` for Crossref, OpenAlex (batched DOI lookup), Semantic Scholar (DOI/arXiv lookup with `SEMANTIC_SCHOLAR_API_KEY` support and graceful HTTP 429 handling), OpenAIRE, arXiv, and DataCite.
  - Never fabricates unsupported metrics (no Crossref h-index, no arXiv citation count, no Google Scholar scraping; `AnswerThis` remains `ANSWERTHIS_NOT_CONFIGURED` unless server credentials are set).
- **Phase 4 (`archipelago/scholarly/intelligence/enrichment.py`, `workbook.py`)**:
  - Enhanced `enrich_orcid_authors()` (using `/v3.0/{orcid}/record`) and added `orcid_author_observations()` to emit separate `provider="orcid"` author observations with works counts and employments.
  - Emits separate per-provider rows in `Authors` and `Metric_Observations` without merging authors by name alone.
  - Enhanced `venue_observation()` to retain Crossref/OpenAIRE/DataCite venue metadata when OpenAlex `venue_id` is absent.
- **Phase 5 (`archipelago/scholarly/intelligence/relevance_engine.py`, `provider_selector.py`)**:
  - Added `_has_tight_unordered_window(..., max_extra_gap=0)` for reordered compound terms (`"space state model"` <-> `"state-space model"`) and `four_term_bigram_ok` for 4+ term multi-concept queries without sacrificing precision.
  - Added `disambiguate_query()` to expose reordered compound and cross-disciplinary interpretations without silently rewriting the user query, and `resolved_domain` support in `select_providers()`.
- **Phase 6 (`archipelago/scholarly/intelligence/workbook.py`, `workbook_extra.py`)**:
  - Updated `Run_Manifest` (removed contradictory `ranking_policy`, added `sort_algorithm`, `sort_version`, `sort_definition`, `relevance_rule_version`, `candidate_waterfall`, `source_contributions`, `failed_enrichment_requests`, `query_disambiguation`), `Topic_Results` (`archipelago.relevance.v2` membership basis), `Sources_Provenance` (provider record ID & contribution type), `Authors`, and `Metric_Observations` across all 14 sheets.
  - Synced `host_inference/` via `scripts/ops/sync_s5_host_runtime.py`.

---

## 3. Cross-Discipline Live Evaluation (Phase 7)

| Topic | Domain | Ambiguous | Latency (s) | Candidates -> Filtered -> Selected | Primary Providers (Selected) | All Contributing Provenance | Citation Observations | Author Observations |
|---|---|---|---|---|---|---|---|---|
| `space state model` | `general` | Yes | 41.79 | 126 -> 61 -> 20 | OA=16, OAIRE=3, CR=1 | OA=19, OAIRE=18, CR=12, S2=11, DC=2 | OA=19, CR=12, S2=11, OC=8 | OA=51, S2=10, ORCID=10 |
| `state-space models` | `general` | Yes | 70.36 | 99 -> 69 -> 20 | OA=12, OAIRE=6, CR=1, DC=1 | OAIRE=18, OA=16, S2=8, CR=7, DC=6 | OA=16, S2=8, OC=8, CR=7, DC=1 | OA=56, S2=10, ORCID=10 |
| `CRISPR base editing sickle cell` | `general` | Yes | 36.47 | 89 -> 18 -> 10 | OA=6, OAIRE=3, CR=1 | OA=10, OAIRE=10, CR=9, S2=9, DC=1 | OA=10, CR=9, S2=9, OC=8 | OA=61, S2=10, ORCID=10 |
| `retrieval augmented generation` | `ai_cs` | Yes | 22.90 | 59 -> 47 -> 10 | arXiv=7, OA=2, CR=1 | arXiv=7, CR=4, OA=3, OAIRE=3, S2=1 | CR=4, OC=4, OA=3, S2=1 | OA=21, ORCID=10, S2=3 |
| `speech recognition benchmark datasets` | `datasets_software` | Yes | 70.74 | 58 -> 24 -> 10 | OAIRE=6, OA=2, CR=1, DC=1 | OAIRE=10, OA=8, DC=7, S2=5, CR=3 | OA=8, OC=8, S2=5, CR=3, DC=1 | OA=29, S2=10, ORCID=10 |
| `ocean acidification coral reefs` | `general` | Yes | 36.74 | 93 -> 43 -> 10 | OA=5, OAIRE=3, CR=1, DC=1 | OA=9, CR=9, S2=9, OAIRE=9, DC=2 | OA=9, CR=9, S2=9, OC=8, DC=1 | OA=35, S2=10, ORCID=10 |

### Source-Level Failure & Rate-Limit Summary

- **Semantic Scholar**: Search endpoint returned HTTP 429 during Stage-1 discovery across unauthenticated runs; Stage-2 DOI/arXiv lookup succeeded for 8–11 papers per topic before hitting HTTP 429 (`enrichment_failures`), at which point S2 calls stopped gracefully and other providers continued.
- **arXiv**: Returned 0 records on `state-space models` and `speech recognition benchmark datasets`; contributed `7/10` primary records on `retrieval augmented generation`.
- **DBLP**: Returned 0 records on `retrieval augmented generation`.
- **Missing metadata**: `space state model` had 1 missing abstract and 2 missing DOIs out of 20; all other evaluated topics had 0 missing abstracts and 0 missing DOIs (except `retrieval augmented generation` with 6 arXiv preprints lacking DOIs).

---

## 4. Verification & Acceptance Checklist

- **Unit Tests**: `pytest tests/unit/test_s5_*.py tests/unit/test_cross_provider_evidence_repair.py` -> **42 passed, 0 failed** (including the 40-query multidiscipline relevance precision benchmark).
- **Acceptance Criteria**:
  1. All reported provenance represents real contributing sources: **PASS**
  2. Cross-provider matching preserves verified supplemental evidence: **PASS**
  3. Unavailable metadata remains missing (`PROVIDER_FIELD_ABSENT` / `NOT_AVAILABLE`): **PASS**
  4. Author identities separated per provider (never merged by name alone): **PASS**
  5. No false publication/DOI merges: **PASS**
  6. No fabricated Google Scholar metrics: **PASS**
  7. Every exported metric has source and definition in `Metric_Observations`: **PASS**
  8. `Run_Manifest` accurately describes executed sort algorithm & waterfall: **PASS**
  9. Per-provider candidate losses auditable via `candidate_waterfall`: **PASS**
  10. All 14 XLSX sheets preserved and verified: **PASS**
