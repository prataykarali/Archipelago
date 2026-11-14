# S5 Scholarly Enrichment Validation Report

**Date:** 2026-11-14  
**Branch:** `feature/s6-final-platform-integration`  
**Production Backend Tested:** `https://archipelago-blond.vercel.app`  
**Validation Artifacts:**
- Local 6-topic run: `s5_enrichment_validation.json` + `jarvis_ai_enriched_s6.xlsx`
- Live hosted run (`jarvis ai`, `max_papers=15`): `run_id=79f73edf-b5a0-49b8-92cc-346799dfac1d`, XLSX `68,805` bytes (`HTTP 200`)

---

## 1. Six-Topic Live Validation Matrix

| Topic | Papers | Candidates | DOIs | Abstracts | OpenAlex Authors Enriched | Venues w/ URL | Venues w/ 2yr Citedness | Extracted Claims (Papers) | Elapsed (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `jarvis ai` | 41 | 77 | 37 | 29 | **94 / 94** | 10 / 26 | 19 / 26 | 41 (22) | 10,101.0 |
| `graph neural networks` | 20 | 63 | 18 | 14 | **37 / 37** | 7 / 14 | 7 / 14 | 47 (19) | 7,233.3 |
| `retrieval-augmented generation` | 20 | 77 | 15 | 15 | **29 / 29** | 2 / 13 | 3 / 13 | 73 (18) | 7,180.1 |
| `continual learning` | 20 | 76 | 15 | 14 | **31 / 31** | 4 / 14 | 4 / 14 | 47 (14) | 8,658.7 |
| `ocr and document understanding` | 20 | 74 | 16 | 16 | **68 / 68** | 7 / 14 | 9 / 14 | 111 (19) | 8,229.7 |
| `bengali speech recognition` | 20 | 67 | 19 | 7 | **15 / 15** | 2 / 17 | 2 / 17 | 46 (15) | 6,336.8 |

**Key Observations:**
- **100% Stage-2 OpenAlex Author Completion**: Across all 6 topics, **274 / 274** authors with resolved OpenAlex IDs received `publication_count`, `citation_count`, `h_index`, and `i10_index` in batched 50-ID requests (average ~7.95 seconds per topic end-to-end).
- **Evidence-Anchored Claims**: Total **365 structured claims** extracted across the 6 topics without hallucinating dataset or metric names when absent from abstracts (`NOT_FOUND_IN_AVAILABLE_EVIDENCE` / `EVIDENCE_INSUFFICIENT`).

---

## 2. 14-Sheet Workbook Verification (`jarvis_ai_enriched_s6.xlsx` & Live Hosted Export)

### Local `jarvis_ai_enriched_s6.xlsx` Sheet Row Counts (41 papers)
1. `Papers`: 41
2. `Authors`: 133
3. `Venues`: 26
4. `References`: 110
5. `Citation_Edges`: 0
6. `Topic_Results`: 41
7. `Sources_Provenance`: 50
8. `Errors_Review`: 16
9. `Run_Manifest`: 15
10. `Institutions_Affiliations`: 22
11. `Funding_Grants`: 0 (1 grant observed in `graph neural networks` and 1 in `bengali speech recognition`)
12. `Research_Claims`: 41
13. `Metric_Observations`: 551
14. `Coverage_Audit`: 8

### Live Hosted Production Export (`https://archipelago-blond.vercel.app`)
- `POST /api/research/intelligence/search` (`{"topic": "jarvis ai", "max_papers": 15}`) -> `HTTP 200` (`20` papers, `26` claims, `run_id=79f73edf-b5a0-49b8-92cc-346799dfac1d`).
- `GET /api/research/intelligence/runs/79f73edf-b5a0-49b8-92cc-346799dfac1d/xlsx` -> `HTTP 200` (`68,805` bytes), valid `.xlsx` containing all 14 sheets and the following `Coverage_Audit` rows:
  - `Papers: DOI`: `20 / 20` (`100%`)
  - `Papers: Abstract`: `16 / 20` (`80%`, remaining `PROVIDER_FIELD_ABSENT`)
  - `Papers: Methods`: `6 / 20` (`30%`, remaining `NOT_FOUND_IN_AVAILABLE_EVIDENCE`)
  - `Papers: Datasets`: `0 / 20` (`0%`, `NOT_FOUND_IN_AVAILABLE_EVIDENCE`)
  - `Papers: Evaluation Metrics`: `3 / 20` (`15%`, remaining `NOT_FOUND_IN_AVAILABLE_EVIDENCE`)
  - `Authors: Provider Bibliometrics`: `49 / 49` eligible (`100%` of resolved IDs, `76.6%` of `64` total authors; `15` `IDENTITY_UNRESOLVED`)
  - `Venues: Official URL`: `5 / 12` (`41.7%`, remaining `PROVIDER_FIELD_ABSENT`)
  - `Venues: Licensed JIF/CiteScore/SJR`: `0 / 12` (`0%`, `LICENSE_RESTRICTED`)

---

## 3. Automated Test & Lint Verification

- `ruff check archipelago/scholarly/` -> `All checks passed!`
- `pytest -q tests/unit/test_s5_research_intelligence.py tests/unit/test_s6_platform_integration.py tests/unit/test_host_inference_deployment.py tests/unit/test_research_transport.py tests/integration/test_s4_academic_dashboard.py` -> **45 passed in 14.91s**.
- `scripts/source_size_gate.py`: Zero modified/added `archipelago/scholarly/` files exceed the 400-line limit (`enrichment.py` 301, `extraction.py` 153, `search.py` 263, `workbook.py` 364, `workbook_extra.py` 159).

---

## 4. Remaining Honest Upstream Limitations

1. **Licensed Journal Metrics**: Clarivate JIF, Scopus CiteScore, SCImago SJR, and CORE rankings require paid/licensed feeds and remain `LICENSE_RESTRICTED`.
2. **Closed-Access Abstracts & Full Text**: Papers lacking open abstracts in OpenAlex/Crossref/Semantic Scholar cannot yield full method/dataset/metric claims without institutional full-text PDF access.
3. **Unresolved Cross-Provider Author IDs**: Authors surfaced only by Crossref/arXiv without an OpenAlex ID are marked `IDENTITY_UNRESOLVED` rather than guessed by fuzzy name matching.
