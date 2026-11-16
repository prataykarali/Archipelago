# ARCHIPELAGO — FINAL RANDOM-TOPIC ACCEPTANCE & CONDITIONAL PRODUCTION RELEASE

## 1. Random Topic Selection & Seed
- **Reproducible Seed:** `20261116` (`random.Random(20261116).sample(TOPIC_POOL, 2)`)
- **Excluded Previously Evaluated Topics:** Liquid Neural Networks, Diffusion Models, Retrieval-Augmented Generation, Quantum Error Correction, Omni AI Models, Graph Neural Networks, Continual Learning, Bengali Speech Recognition, Computer Vision OCR.
- **Selected Unseen Topics:**
  1. **Mathematics:** `topological data analysis`
  2. **Biomedical / Genetics:** `crispr gene editing`

## 2. Independent Relevance Judgments & Metrics

| Metric | Topic 1: `topological data analysis` | Topic 2: `crispr gene editing` |
| --- | --- | --- |
| Requested / Returned | 20 / 20 (127 candidates, 75 eligible) | 20 / 20 (132 candidates, 40 eligible) |
| **Precision@5** | **100%** (5/5) | **100%** (5/5) |
| **Precision@10** | **100%** (10/10) | **100%** (10/10) |
| **Precision@20** | **100%** (20/20) | **100%** (20/20) |
| **nDCG@10** | **1.000** | **1.000** |
| **False-Positive Rate** | **0.000** (0 off-topic) | **0.000** (0 off-topic) |
| **Cross-Domain Top-5 FPs** | **0** | **0** |
| **Duplicate Count** | **1** (`#15` & `#18`: *Topological data analysis and machine learning*, OpenAlex vs OpenAIRE without shared DOI) | **0** |
| **Latency** | **14.47s** | **13.87s** |

- **AnswerThis Status:** `ANSWERTHIS_NOT_CONFIGURED` (unavailable/unauthorized in this environment; zero results fabricated).

## 3. Provider Contributions & Failures
- **Topic 1 (`topological data analysis`):** `openalex` (`live`, 200, 29), `crossref` (`live`, 200, 15), `arxiv` (`live`, 200, 25), `openaire` (`live`, 200, 30), `datacite` (`live`, 200, 30), `semantic_scholar` (`rate_limited`, 429, 0), `dblp`/`europe_pmc`/`pubmed` (`skipped`), `google_research` (`navigation_only`, 200).
- **Topic 2 (`crispr gene editing`):** `openalex` (`live`, 200, 30), `crossref` (`live`, 200, 21), `arxiv` (`live`, 200, 25), `openaire` (`live`, 200, 30), `datacite` (`live`, 200, 30), `semantic_scholar` (`rate_limited`, 429, 0), `dblp`/`europe_pmc`/`pubmed` (`skipped`), `google_research` (`navigation_only`, 200).

## 4. Author, Venue, Citation & Workbook Verification
- **TDA Workbook:** `14` sheets intact, `Max Coverage Audit % = 95.0%`, `0` formula risks, `428` raw references, `428` identifier-matched, `2` in-collection `CITES` edges (`verification_coverage: 0.0047`).
- **CRISPR Workbook:** `14` sheets intact, `Max Coverage Audit % = 100.0%`, `0` formula risks, `840` raw references, `840` identifier-matched, `2` in-collection `CITES` edges (`verification_coverage: 0.0024`).
- **Google Research / Scholar:** Official navigation links only; `0` fabricated Scholar citations; missing values preserved distinctly from `0`.

## 5. Regression & Test Summary
- `pytest` S5 + Chat/OPAC suite: **`40 passed, 1 warning`** in `9.70s` (`test_s5_research_intelligence.py`, `test_s5_enrichment.py`, `test_s5_multisource_providers.py`, `test_s5_multi_provider_enrichment.py`, `test_s5_relevance_and_metrics_repair.py`, `test_research_reply.py`, `test_opac_export_discovery.py`).

## 6. Downloadable Workbooks
- **Topological Data Analysis:** `artifacts/validation/final-random-acceptance/topological_data_analysis_20.xlsx` (and artifact copy `Archipelago_topological_data_analysis_20.xlsx`)
- **CRISPR Gene Editing:** `artifacts/validation/final-random-acceptance/crispr_gene_editing_20.xlsx` (and artifact copy `Archipelago_crispr_gene_editing_20.xlsx`)

## 7. Git & Vercel Production Deployment
- **Branch:** `feature/multi-provider-research-enrichment`
- **Code Commit SHA:** `ba6e6f4` (includes `05dcf11` repair + acceptance workbooks)
- **Vercel Preview Deployment:** `https://archipelago-7ptm27hby-archipelago-6383.vercel.app` (`dpl_AnASFeyU6De4MJHvuNm9zT8RnPKN`, HTTP 200 on `/research`, `/api/auth/config` verified)
- **Vercel Production Deployment:** `https://archipelago-blond.vercel.app` (`dpl_ByteRREgHk6FhzTtgr7KCn7NLq8C`, promoted from tested preview)
- **Rollback Reference:** `dpl_2ps6DoKCKHe4fJYFP2aQKMfZYny6`
- **Final Live Production Smoke Test:**
  - `POST /api/research/intelligence/search` (`topological data analysis`, `top_k=20`): **HTTP 200 in `10.72s`**, `run_id = 745c8a24-fc51-416f-b255-d8bb4b1c5b7d`, `20` papers returned.
  - `GET /api/research/intelligence/runs/745c8a24-fc51-416f-b255-d8bb4b1c5b7d/xlsx`: **81,840 bytes**, `14` sheets intact, `Max Coverage % = 95.0%`.

**PASS — DEPLOYED TO PRODUCTION**
