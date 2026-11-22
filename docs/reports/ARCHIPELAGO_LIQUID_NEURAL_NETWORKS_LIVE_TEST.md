# ARCHIPELAGO — LIVE RESEARCH TEST: LIQUID NEURAL NETWORKS

## 1. Execution Context & Deployment
- **Production URL:** `https://archipelago-blond.vercel.app/`
- **Deployment ID:** `dpl_2ps6DoKCKHe4fJYFP2aQKMfZYny6` (`archipelago-6383/archipelago`)
- **Branch:** `feature/multi-provider-research-enrichment`
- **Live Research Run ID:** `77eb88be-9932-46ab-89ec-5cdf8fe3b859`
- **Retrieved At:** `2026-11-16T05:11:45.724145+00:00`
- **Topic:** `Liquid Neural Networks` (`top_k=20`, default sort `newest`)

## 2. Provider Status Summary
| Provider | Status | HTTP | Records | Notes |
| --- | --- | --- | --- | --- |
| **OpenAlex** | `live` | 200 | 23 | Full metadata, author IDs, FWCI, references |
| **Crossref** | `live` | 200 | 33 | DOI metadata, references, publisher |
| **OpenAIRE** | `live` | 200 | 30 | Open-access research products |
| **Europe PMC** | `live` | 200 | 25 | Indexed preprints & biomedical/interdisciplinary papers |
| **Semantic Scholar** | `rate_limited` | 429 | 0 | Shared-IP rate limit surfaced honestly (`RATE_LIMITED`) |
| **arXiv** | `rate_limited` | 429 | 0 | Shared-IP rate limit surfaced honestly (`RATE_LIMITED`) |
| **DBLP** | `blocked_bot_challenge` | 202 | 0 | Bot protection gate respected without bypass |
| **DataCite / PubMed** | `skipped` | — | 0 | `not_selected_for_domain:ai_cs` |
| **Google Research** | `navigation_only` | 200 | 0 | Official link `https://research.google/pubs/?search=Liquid%20Neural%20Networks` |

## 3. Qualifying Papers & Metadata Coverage
- **Deduplicated candidates:** 103 (`53` after topic/filter eligibility; `20` returned for `top_k=20`).
- **Provider contributions in top 20:** `europe_pmc` (14), `openalex` (4), `openaire` (2), `crossref` (1) (21 provenance rows across 20 papers).
- **Topic Relevance Audit (Step 1 & 7):**
  - **10 / 20** papers genuinely concern Liquid Neural Networks / Liquid Time-Constant (LTC) / Closed-form Continuous-time (CfC) architectures (e.g., *Integrating Vision Liquid Time-Constant and Wavelet...*, *Multi-Rate Mixture of Experts for Accelerating Liquid Neural Network Training*, *Hybrid vehicle state estimation using closed-form liquid neural networks...*, *TLNN: Tau-Liquid Neural Network*, *Liquid neural networks for adaptive DDoS detection...*).
  - **10 / 20** papers are false-positive token matches where `"liquid"`, `"neural"`, and `"networks"` appeared separately (e.g., *Soft Liquid Metal Neural Interface*, *vapor–liquid equilibria*, *pure-liquid viscosity*, *liquid level sensors*), largely because `europe_pmc` returned 14 of the 20 newest-first 2026 records and `assess_topic_eligibility` currently checks individual bag-of-words tokens rather than phrase proximity.
- **Unique Authors:** 72 author rows in `Authors` sheet (`Kim E` collision preserved separately without merging).
- **Unique Venues:** 6 venue rows in `Venues` sheet (`peer_reviewed_journal`, `preprint_repository`, `unknown`); JIF/CiteScore/SJR/CORE marked `LICENSE_RESTRICTED`.

## 4. Citation Graph Statistics
- **Graph nodes:** 124 · **Graph edges:** 150
- **Raw references (`total_reference_links`):** 25
- **Resolvable OpenAlex/DOI identifiers (`resolved_known_works`):** 25 (`100%` syntax/identifier resolution among returned reference IDs; independent existence of all 25 external targets was not re-fetched individually)
- **Directed `CITES` edges within the 20-paper set (`in_collection_edges`):** 0 (all 20 newest-first papers are from 2026 and do not yet cite one another)
- **Unresolved references:** 0

## 5. Google Research & Google Scholar Status
- **Google Research:** `navigation_only` (`https://research.google/pubs/?search=Liquid%20Neural%20Networks`). `0` papers verified as `GOOGLE_RESEARCH_OFFICIAL_LISTING` (never conflated with author affiliation).
- **Google Scholar:** Paper-level and author-level search links generated; profile metrics marked `NOT_AVAILABLE` (no scraping, no invented counts).

## 6. Sort Validation (Same 20-Paper Set)
Verified all 7 sort orders without mutating stored records or zero-filling missing values:
1. `newest`: 2026 publication dates descending (*Peri-Infarct Cortical Network...* first).
2. `most_cited`: All 2026 papers with `0` citations first; `None` citation counts sorted last.
3. `citations_per_year`: `0.0` first; `None` sorted last.
4. `fwci`: OpenAlex papers with `fwci=0.0` first (*PARALLELIZATION OF COMPUTATIONS IN LIQUID NEURAL NETWORKS...*); `None` sorted last.
5. `open_access`: `is_open_access=True` first (*A coarse-to-fine modulation classification...*).
6. `evidence_completeness`: Highest evidence count (5/7) first (*Multi-Rate Mixture of Experts for Accelerating Liquid Neural Network Training*).
7. `relevance` / `provider`: Preserves provider order.

## 7. Sampled Author & Venue Enrichment (5 Authors, 5 Venues)
- **Enriched OpenAlex Authors:**
  - `Shilong Zong` (ORCID `0000-0002-6858-4167`, OA `A5071108491`, Virginia Tech, 3 pubs, 5 cit, h=1)
  - `Almuatazbellah Boker` (ORCID `0000-0002-9484-7266`, OA `A5013572009`, NC State, 65 pubs, 316 cit, h=9)
  - `Hoda Eldardiry` (ORCID `0000-0002-9712-6667`, OA `A5038305381`, PARC / Purdue, 128 pubs, 1485 cit, h=19)
  - `Монгуш Максим Андреевич` (OA `A5159416260`, 1 pub, 0 cit, h=0)
  - `Mrs. J.Shilpa Kommera Mahesh Reddy` (OA `A5155456796`, 1 pub, 0 cit, h=0)
- **Unresolved Europe PMC Authors:** `Kim E` (two separate rows preserved, `IDENTITY_UNRESOLVED`), `Lee J`, `Jeong I`, `Hong YM`.
- **5 Venues:** *Research Result Information Technologies* (`peer_reviewed_journal`), *Computers & Chemical Engineering* (`unknown`), *American Chemical Society (ACS)* (`unknown`), *International Journal of Engineering Research and Science & Technology* (`peer_reviewed_journal`), *arXiv (Cornell University)* (`preprint_repository`).

## 8. Independent Verification of 5 Random Papers (vs Crossref API)
1. `10.21203/rs.3.rs-11326561/v1` (*Wafer-scale integration of atomically thin metal oxide...*): Title, year (2026), citations (0) **MATCH**. Discrepancy: Europe PMC tagged `journal-article`, Crossref reports `posted-content` (preprint).
2. `10.1002/adhm.71933` (*Peri-Infarct Cortical Network Remapping...*): Title, year (2026), type (`journal-article`), citations (0) **MATCH**. (Off-topic false positive: liquid metal neural interface).
3. `10.3390/s26175464` (*Development of Autoranging Functionality...*): Title, year (2026), type (`journal-article`), citations (0) **MATCH**. (Off-topic false positive: liquid level sensor).
4. `10.21203/rs.3.rs-11048383/v1` (*Deep Learning for Option Pricing...*): Title, year (2026), citations (0) **MATCH**. Discrepancy: Europe PMC tagged `journal-article`, Crossref reports `posted-content` (preprint).
5. `10.1016/j.isatra.2026.06.027` (*Hybrid vehicle state estimation using closed-form liquid neural networks...*): Title, year (2026), type (`journal-article`), citations (0) **MATCH**.

## 9. Workbook Validation (`Archipelago_Liquid_Neural_Networks_Research_Test.xlsx`)
- **Size:** 67,694 bytes · **Sheets:** All 14 expected sheets present and non-corrupt.
- **Row counts:** `Papers` (20), `Authors` (72), `Venues` (6), `References` (25), `Citation_Edges` (0), `Topic_Results` (20), `Sources_Provenance` (21), `Errors_Review` (2), `Run_Manifest` (17), `Institutions_Affiliations` (2), `Funding_Grants` (0), `Research_Claims` (69), `Metric_Observations` (91), `Coverage_Audit` (11).
- **Cross-sheet Paper ID integrity:** PASS · **Formula injection protection:** PASS (0 unescaped formulas) · **Hyperlink validation:** PASS.
- **Real Errors / Observations:**
  1. `POST /api/research/intelligence/search` took ~53s on Vercel (`10:40:52` → `10:41:45`, HTTP 200), while the client's 120s socket read timed out waiting on the response (the run itself saved cleanly in Supabase).
  2. `semantic_scholar` and `arxiv` returned HTTP 429 from Vercel's shared IP.
  3. Europe PMC `journal-article` default type mislabels Research Square `posted-content` preprints, and bag-of-words topic matching allows `"liquid"` + `"neural"` + `"networks"` false positives.

## 10. Download Locations
- **Local Artifact Workbook:** `/home/pratay-karali/.gemini/antigravity/brain/dea69ec5-445d-49df-bd07-fc2cbc10680e/Archipelago_Liquid_Neural_Networks_Research_Test.xlsx`
- **Repo Validation Copy:** `Archipelago/artifacts/validation/Archipelago_Liquid_Neural_Networks_Research_Test.xlsx`
- **Authenticated Production XLSX Export URL:** `https://archipelago-blond.vercel.app/api/research/intelligence/runs/77eb88be-9932-46ab-89ec-5cdf8fe3b859/xlsx`
- **Production UI Run URL:** `https://archipelago-blond.vercel.app/research?run=77eb88be-9932-46ab-89ec-5cdf8fe3b859`
