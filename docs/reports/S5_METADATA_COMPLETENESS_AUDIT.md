# S5 Metadata Completeness Audit (`1st.xlsx` Baseline & Pipeline Remediation)

**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Audit Target:** `1st.xlsx` (`jarvis ai` — 41 selected papers from 77 candidates, 133 authors, 26 venues, 110 references)  
**Policy Constraint:** Zero paper ranking, author ranking, journal ranking, or composite quality scores. Licensed venue metrics (`Clarivate JIF`, `CiteScore`, `SJR`, `CORE Rank`) are strictly separated from OpenAlex `2yr_mean_citedness` and tagged `LICENSE_RESTRICTED`.

---

## 1. Root-Cause Audit of `1st.xlsx` Deficiencies

| Field | `1st.xlsx` Baseline | Root Cause Classification | Exact Technical Cause |
|---|---:|---|---|
| Paper DOI | 37 / 41 | `PROVIDER_FIELD_ABSENT` | 4 arXiv/preprint/conference records had no DOI assigned in upstream provider metadata. |
| Paper Abstract | 29 / 41 | `PROVIDER_FIELD_ABSENT` | Upstream OpenAlex `abstract_inverted_index`, Crossref `abstract`, and Semantic Scholar `abstract` were empty for 12 publisher-gated works. |
| Paper Methods | 9 / 41 | `UNSUPPORTED_EXTRACTION` + `PROVIDER_FIELD_ABSENT` | `extraction.py` matched only a 31-term static regex list against title+abstract; full-text PDFs/HTML were not fetched in Stage 1, and 12 papers lacked abstracts. |
| Paper Datasets | 0 / 41 | `UNSUPPORTED_EXTRACTION` + `NOT_FOUND_IN_AVAILABLE_EVIDENCE` | `extraction.py` matched only 21 benchmark names; `jarvis ai` results are largely enterprise/robotics/HCI/survey papers where standard ML datasets are genuinely absent from abstracts. |
| Paper Evaluation Metrics | 3 / 41 | `UNSUPPORTED_EXTRACTION` | `extraction.py` matched only 14 metric keywords and did not capture numerical results, baselines, tasks, or model names. |
| Author ORCID | 24 / 133 | `PROVIDER_FIELD_ABSENT` | OpenAlex `author.orcid` is populated only when authors link an ORCID record. |
| Author OpenAlex ID | 94 / 133 | `IDENTITY_UNRESOLVED` | 39 authors came from Crossref/arXiv/Semantic Scholar records without an OpenAlex `author.id` and were not cross-linked. |
| Author Publication Count | 8 / 133 | `ARTIFICIAL_REQUEST_CAP` | `MAX_AUTHOR_LOOKUPS = 8` in `archipelago/scholarly/intelligence/enrichment.py` stopped Stage-2 author lookups after 8 authors. |
| Author Citation Count | 8 / 133 | `ARTIFICIAL_REQUEST_CAP` | Same `MAX_AUTHOR_LOOKUPS = 8` cap. |
| Author h-index | 8 / 133 | `ARTIFICIAL_REQUEST_CAP` | Same `MAX_AUTHOR_LOOKUPS = 8` cap. |
| Author i10-index | 8 / 133 | `ARTIFICIAL_REQUEST_CAP` | Same `MAX_AUTHOR_LOOKUPS = 8` cap. |
| Venue ISSN | 15 / 26 | `PROVIDER_FIELD_ABSENT` | Workshop/preprint/arXiv/conference proceedings often lack an ISSN in OpenAlex/Crossref. |
| Venue URLs | 0 / 26 | `MISSING_SECOND_STAGE_ENRICHMENT` | `venue_observation()` only copied dehydrated `primary_location.source` (`id`, `display_name`, `issn_l`, `type`), never calling OpenAlex `/sources` for `homepage_url`. |
| Venue JIF / CiteScore / SJR | 0 / 26 | `LICENSE_RESTRICTED` | Clarivate JIF, Scopus CiteScore, SCImago SJR, and CORE Rank are proprietary/licensed datasets not exposed by OpenAlex, Crossref, Semantic Scholar, or arXiv. |
| Intra-collection Citation Edges | 0 / 41 | `GENUINE_ABSENCE` | The 41 returned works had no intra-set `referenced_works` overlap (110 external references were preserved in `References`). |

---

## 2. Discarded Upstream Provider Fields Fixed in Adapters

Inspection of `archipelago/scholarly/discovery/` showed that upstream APIs already returned rich scholarly metadata that adapters were discarding:

- **`openalex_adapter.py`**: Now retains `pmid`, `grants` (`funder`, `funder_display_name`, `award_id`), `fwci`, `citation_normalized_percentile`, `oa_status`, `version_status` (`primary_location.version`), `landing_page_url`, `primary_topic` hierarchy (`domain`, `field`, `subfield`), `is_corresponding`, and `author_institutions` (`id`, `display_name`, `ror`, `country_code`, `type`).
- **`crossref_adapter.py`**: Now retains `grants` (`funder` array with `DOI`, `name`, `award`) and `landing_page_url` (`URL`).
- **`live_sources.py` (Semantic Scholar)**: Now retains `authors.authorId` (`semantic_scholar_author_id`) alongside `paperId` and `externalIds`.

---

## 3. Pipeline Enhancements Implemented

1. **Removed `MAX_AUTHOR_LOOKUPS = 8` Cap (`enrichment.py`)**:
   - Replaced per-author serial requests with OpenAlex **50-ID batch queries** (`filter=openalex_id:...&per-page=50`) with in-memory run/process caching (`_AUTHOR_CACHE`) and transient retry handling.
   - Any overflow beyond `MAX_AUTHOR_BATCH_IDS = 200` is explicitly marked `ENRICHMENT_PENDING` rather than silently dropped.
2. **Added Stage-2 OpenAlex Venue Enrichment (`enrich_venues` in `enrichment.py`)**:
   - Batch-queries OpenAlex `/sources` (50 IDs per request, `_VENUE_CACHE`) for `homepage_url`, `issn`, `issn_l`, `is_oa`, `is_in_doaj`, `works_count`, `cited_by_count`, `summary_stats.h_index`, `summary_stats.i10_index`, `summary_stats.2yr_mean_citedness`, and `host_organization_name`.
   - Keeps `openalex_2yr_mean_citedness` strictly distinct from `LICENSE_RESTRICTED` Clarivate JIF, CiteScore, and SJR.
3. **Evidence-Anchored Claim Extraction (`extraction.py`)**:
   - Upgraded `extract_evidence()` to emit structured claims (`METHOD`, `MODEL`, `DATASET`, `TASK`, `EVALUATION_METRIC`, `NUMERICAL_RESULT`, `BASELINE`, `LIMITATION`, `CONTRIBUTION`) with `evidence_text`, `evidence_location`, and `status` (`AVAILABLE`, `NOT_FOUND_IN_AVAILABLE_EVIDENCE`, or `EVIDENCE_INSUFFICIENT`).
4. **14-Sheet Normalized Excel Workbook (`workbook.py` + `workbook_extra.py`)**:
   - Preserves all 9 original sheets (`Papers`, `Authors`, `Venues`, `References`, `Citation_Edges`, `Topic_Results`, `Sources_Provenance`, `Errors_Review`, `Run_Manifest`).
   - Adds 5 normalized sheets: `Institutions_Affiliations`, `Funding_Grants`, `Research_Claims`, `Metric_Observations`, and `Coverage_Audit`.
   - Every missing/unavailable field reports a structured reason (`PROVIDER_FIELD_ABSENT`, `ENRICHMENT_PENDING`, `IDENTITY_UNRESOLVED`, `LICENSE_RESTRICTED`, `EVIDENCE_INSUFFICIENT`, `NOT_FOUND_IN_AVAILABLE_EVIDENCE`).

---

## 4. Before vs. After Comparison (`jarvis ai`, 41 Papers)

| Metric | `1st.xlsx` Before | Enriched S6 (`jarvis_ai_enriched_s6.xlsx`) | Change |
|---|---:|---:|---|
| OpenAlex Author Bibliometrics | 8 / 94 (8.5%) | **94 / 94 (100.0% of resolved IDs)** | +86 authors (+91.5 pp) |
| Venue Official URLs | 0 / 26 (0.0%) | **10 / 26 (38.5%)** | +10 venues |
| Venue OpenAlex 2yr Mean Citedness | 0 / 26 (0.0%) | **19 / 26 (73.1%)** | +19 venues |
| Institutions & Affiliations Rows | 0 | **22** | New normalized sheet |
| Evidence-Anchored Research Claims | 0 | **41** (across 22 papers) | New normalized sheet |
| Metric Observations Rows | 0 | **551** | New normalized sheet |
| Coverage Audit Rows | 0 | **8** | New normalized sheet |
| Clarivate JIF / CiteScore / SJR | 0 / 26 | 0 / 26 (`LICENSE_RESTRICTED`) | Honest provenance preserved |
