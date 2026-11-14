# Archipelago Final Research Demonstration Sign-Off

**Date:** 2026-11-14  
**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Verified Release Commit SHA:** `aaa15b83db96f82d9c4a475f3d7f494381259bf5`  
**Protected Vercel Preview (`archipelago-6383`):** [`https://archipelago-1cz4ptmed-archipelago-6383.vercel.app`](https://archipelago-1cz4ptmed-archipelago-6383.vercel.app) (Deployment ID: `2FNRhCDAidr5vEwK7yoV9mgScTtG`, Inspect: [`vercel.com/archipelago-6383/archipelago/2FNRhCDAidr5vEwK7yoV9mgScTtG`](https://vercel.com/archipelago-6383/archipelago/2FNRhCDAidr5vEwK7yoV9mgScTtG))  
**Currently Active Production Domain (`https://archipelago-blond.vercel.app/`):** `5FjVNLvksWfJGzhyj7FNWTgDJM8z` (pre-patch commit `4b19d309f1a928cde1756716602299fffdb2e0b7`; awaiting authorized promotion)  
**Overall Verdict:** **`CONDITIONALLY RELEASED — VERIFIED ON PROTECTED PREVIEW, AWAITING PRODUCTION PROMOTION AUTHORIZATION`** (`aaa15b8` verified locally and live on protected Vercel preview `2FNRhCDAidr5vEwK7yoV9mgScTtG`; `--prod` promotion to `archipelago-blond.vercel.app`, `shinaura` librarian deployment, and S4 human review remain external operator gates).

---

## 1. Git Commit, Push & Vercel Preview / Production Status

- **Committed & Pushed to GitHub:** `aaa15b83db96f82d9c4a475f3d7f494381259bf5` on `origin/feature/s6-final-platform-integration` (collapsing exact-title duplicate deposit/preprint versions while preserving `alternate_dois` and provenance, applying multi-round `clean_scholarly_text()` HTML entity/markup cleanup across all providers, and tightening GNN central-concept eligibility).
- **Protected Vercel Preview Deployed & Verified (`archipelago-6383`):**
  - Deployment `2FNRhCDAidr5vEwK7yoV9mgScTtG` built and became `Ready` at `https://archipelago-1cz4ptmed-archipelago-6383.vercel.app`.
  - **Live Preview Checks (`vercel curl` with minted Supabase JWTs):**
    - `GET /api/research/intelligence/readiness` → `200 {"ready":true}`
    - `POST /api/research/intelligence/search` (Topic A, `top_k=50`, `2020–2026`, `newest`) → `200`, `run_id: 9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3`, `22` papers
    - `GET /api/research/intelligence/runs/9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3/xlsx` → `200`, `115,356` bytes, `14` sheets (`Papers`: `22` rows)
    - `POST /api/chat` (`"Which papers discuss quantization?"` with `research_run_id`) → `200` (`RESEARCH_EVIDENCE`, `7/22` papers with exact/synonym snippets)
    - `POST /api/chat` (`"Export this collection to Excel."` with `research_run_id`) → `200` (`RESEARCH_EVIDENCE`, `/api/research/intelligence/runs/9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3/xlsx (22 papers)`)
    - **Cross-User Isolation:** Student token (`12024002028038@student.iem.archipelago.invalid`) querying librarian `run_id` `9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3` on `/api/research/intelligence/runs/<run_id>` and `/xlsx` → `404` on both endpoints.
- **Required Operator Action for Production Promotion:** `npx vercel --prod --yes` is blocked in this environment by the pre-tool security hook. Once release authorization is granted, an authorized `archipelago-6383` operator should promote the verified preview build to `https://archipelago-blond.vercel.app/`:
  ```bash
  npx vercel promote https://archipelago-1cz4ptmed-archipelago-6383.vercel.app --yes
  ```

---

## 2. Automated & Regression Test Results

- `ruff check archipelago/scholarly/ tests/unit/test_s5_multisource_providers.py`: **`All checks passed!`**
- `pytest` across focused suites: **`53 passed in 14.77s`** (including regression tests for exact-title deposit collapsing with `alternate_dois`, cross-provider `clean_scholarly_text()` HTML entity/tag cleanup, GNN central-concept gating, AI/CS routing, and Research Chat concept filters + 14-sheet workbook export wording).

---

## 3. Collection Counts & Provider Status (`aaa15b83db96f82d9c4a475f3d7f494381259bf5`)

### Topic A: `"Efficient Small Language Models for On-Device and Edge Inference"` (`top_k=50`, `2020–2026`, `newest`)
- **Domain Classification:** `ai_cs`.
- **Providers Queried:** `openalex` (`33` live), `semantic_scholar` (`HTTP 429` `rate_limited`), `arxiv` (`25` live), `dblp` (`HTTP 202` `blocked_bot_challenge` — Anubis PoW gate preserved without bypass), `crossref` (`48` live); `openaire`, `datacite`, `europe_pmc`, `pubmed` skipped (`not_selected_for_domain:ai_cs`).
- **Counts & Quality:**
  - `101` deduplicated candidates → **`22`** unique eligible papers (`76` OpenAlex author observations).
  - **Exact-Title Deduplication:** `0` exact-title duplicates remain (`22` unique normalized titles); alternate deposits collapsed while preserving `alternate_dois` (`[6]` retains `['10.2139/ssrn.6698538', '10.21203/rs.3.rs-10597421/v1']`; `[8]` retains `['10.5281/zenodo.24105953', '10.5281/zenodo.24105853']`).
  - **HTML/Markup Cleanup:** `0` HTML entities or markup tags remain (`html=False` across all `22` papers).
  - **Comparison vs. Original `39`-Paper Set:** `24` retained, `15` rejected (`missing_central_concepts:slm` / `missing_central_concepts:edge_on_device`).

### Topic B: `"Graph Neural Networks for Scientific Machine Learning"` (`top_k=20`)
- **Domain Classification:** `ai_cs`.
- **Providers Queried:** `openalex` (`34` live), `arxiv` (`25` live), `crossref` (`23` live), `semantic_scholar` (`HTTP 429` `rate_limited`), `dblp` (`HTTP 202` `blocked_bot_challenge`).
- **Counts:** `82` deduplicated candidates → **`8`** selected papers, **`30`** OpenAlex author observations (`9,677.4 ms`).

---

## 4. Actual 14-Sheet Final Excel Workbook

- **Repository Path:** [`Archipelago_Edge_SLM_Research_Report_FINAL.xlsx`](file:///home/pratay-karali/Desktop/archipelago/Archipelago/artifacts/validation/final-research-demo/Archipelago_Edge_SLM_Research_Report_FINAL.xlsx) (`115,401` bytes)
- **Artifact Copy:** [`Archipelago_Edge_SLM_Research_Report_FINAL.xlsx`](file:///home/pratay-karali/.gemini/antigravity/brain/b239371b-36c1-4fa5-bf52-2d4b7a7e35b9/Archipelago_Edge_SLM_Research_Report_FINAL.xlsx)
- **Validation JSON:** [`patched_final_validation.json`](file:///home/pratay-karali/Desktop/archipelago/Archipelago/artifacts/validation/final-research-demo/patched_final_validation.json)
- **Verified `openpyxl` Counts (14/14 Sheets):**
  `Papers` (`22`), `Authors` (`99`), `Venues` (`17`), `References` (`770`), `Citation_Edges` (`3`), `Topic_Results` (`22`), `Sources_Provenance` (`29`), `Errors_Review` (`5`), `Run_Manifest` (`17`), `Institutions_Affiliations` (`28`), `Funding_Grants` (`0`), `Research_Claims` (`74`), `Metric_Observations` (`394`), `Coverage_Audit` (`8`).
- **Integrity Checks:** `42` clickable hyperlinks in `Papers`, `fk_claims_valid = True`, zero composite ranking columns.
- **`Coverage_Audit`:** DOI `20/22` (`90.9%`), Abstract `19/22` (`86.4%`), Methods `14/22` (`63.6%`), Evaluation Metrics `15/22` (`68.2%`), Datasets `0/22` (`NOT_FOUND_IN_AVAILABLE_EVIDENCE`), Author Bibliometrics `76/99` resolved (`76.8%`; `23` `IDENTITY_UNRESOLVED`), Venue URLs `8/17` (`47.1%`), Licensed JIF/CiteScore/SJR `0/17` (`LICENSE_RESTRICTED`).

---

## 5. Independent 15-Paper External Audit (Crossref / OpenAlex REST APIs)

All 15 sampled papers matched `title`, `year`, and `authors_count` exactly against `api.crossref.org/works/{doi}` or `api.openalex.org/works/https://doi.org/{doi}`:

| # | Year | DOI | External Source | Title / Year / Author Match | Audit Verdict |
|---:|---:|---|---|---|---|
| 1 | 2026 | `10.21203/rs.3.rs-11378808/v1` | `crossref_rest_api` | Exact (`2026`, `1/1`) | **VERIFIED** |
| 2 | 2026 | `10.56201/wjimt.v9.no12.2025.pg271.302` | `crossref_rest_api` | Exact (`2026`, `1/1`) | **VERIFIED** |
| 3 | 2026 | `10.1007/s12065-026-01255-7` | `crossref_rest_api` | Exact (`2026`, `3/3`) | **VERIFIED** |
| 4 | 2026 | `10.48550/arxiv.2606.14711` | `openalex_works_api` | Exact (`2026`, `3/3`) | **VERIFIED** |
| 5 | 2026 | `10.63282/3050-9416.ijaibdcms-v7i1p132` | `crossref_rest_api` | Exact (`2026`, `1/1`) | **VERIFIED** |
| 6 | 2026 | `10.2139/ssrn.6698538` | `crossref_rest_api` | Exact (`2026`, `4/4`) | **VERIFIED** |
| 7 | 2026 | `10.1109/tmc.2026.3738470` | `crossref_rest_api` | Exact (`2026`, `5/5`) | **VERIFIED** |
| 8 | 2026 | `10.5281/zenodo.24105953` | `openalex_works_api` | Exact (`2026`, `4/4`) | **VERIFIED** |
| 9 | 2025 | `10.63278/jicrcr.vi.3492` | `crossref_rest_api` | Exact (`2025`, `1/1`) | **VERIFIED** |
| 10 | 2025 | `10.23939/acps2025.02.233` | `crossref_rest_api` | Exact (`2025`, `3/3`) | **PARTIAL** (edge inference, no SLM focus) |
| 11 | 2025 | `10.14419/nb420z19` | `crossref_rest_api` | Exact (`2025`, `6/6`) | **PARTIAL** (scientometric review of neural ODEs) |
| 12 | 2025 | `10.1016/j.jmps.2025.106152` | `crossref_rest_api` | Exact (`2025`, `4/4`) | **VERIFIED** |
| 13 | 2025 | `10.1137/23m1609786` | `crossref_rest_api` | Exact (`2025`, `5/5`) | **VERIFIED** |
| 14 | 2024 | `10.1002/mgea.50` | `crossref_rest_api` | Exact (`2024`, `5/5`) | **VERIFIED** |
| 15 | 2023 | `10.1016/j.jcp.2023.112537` | `crossref_rest_api` | Exact (`2023`, `4/4`) | **VERIFIED** |

**Audit Summary:** **13/15 (`86.7%`) `VERIFIED`**, **2/15 (`13.3%`) `PARTIAL`**, **0 `INCORRECT`**, **0 `NOT_VERIFIABLE`**. Zero exact-title duplicates and zero HTML/markup corruptions remain.

---

## 6. Research Chat Verification (`LOCAL` + Protected Vercel Preview)

- `"Which papers discuss quantization?"` → Returned **`7/22`** papers with exact match (`title`/`abstract`) vs. documented synonym (`quantized`) snippets and DOIs (verified both locally and live on `2FNRhCDAidr5vEwK7yoV9mgScTtG`).
- `"Which papers discuss low-memory inference?"` → Returned **`3/22`** papers with documented synonyms (`memory footprint`, `memory-efficient`, `ram`).
- `"Which papers do not report datasets?"` → Reported literal extracted methods/metrics per paper (`none stated in the available abstract` where absent) with zero hallucinated datasets.
- `"Export this collection to Excel."` → Returned `/api/research/intelligence/runs/local-edge-slm-final/xlsx (22 papers)` locally and `/api/research/intelligence/runs/9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3/xlsx (22 papers)` live on the protected preview.

---

## 7. S1–S6 Regression Matrix & Remaining External Gates

- **S1–S3 (Academic Chat, Kùzu `610` concepts / `9818ac0e8fd3`, OPAC, Supabase Auth):** **PASS** (verified live in `s6_live_acceptance_report.json` & unchanged).
- **S4 (Academic Automation & Review Guard):** **PASS / GATED** (candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` remains `BLOCKED` pending independent human review).
- **S5 (Multi-Source Research Intelligence, 14-Sheet XLSX, Chat, Monitoring):** **PASS (LOCAL + PROTECTED PREVIEW)** (`aaa15b8` verified locally and live on `https://archipelago-1cz4ptmed-archipelago-6383.vercel.app`; awaiting authorized promotion to `https://archipelago-blond.vercel.app/`).
- **S6 (Library Analytics & Librarian App):** **PASS (Main) / EXTERNAL GATE (Librarian)** (`https://archipelago-librarian.vercel.app/` still requires `shinaura` team owner promotion from `host_research/`).

**Final Verdict:** **`CONDITIONALLY RELEASED`**
