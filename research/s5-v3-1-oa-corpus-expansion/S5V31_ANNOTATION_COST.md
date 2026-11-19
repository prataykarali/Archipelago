# S5-v3.1 Stage E — Human Annotation Cost, Compute/Storage & Feasible Strategy Forecast

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-1-oa-corpus-expansion-canonical`  
**Machine-Readable Report:** [s5v31_cost_estimate.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/reports/s5v31_cost_estimate.json)  
**Grounded In Actual Measured Pools:** [s5v31_retrieval_diagnostics.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/reports/s5v31_retrieval_diagnostics.json) (`SHA-256: 07cf30cc...`), [s5v31_corpus_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_corpus_manifest.json) (`SHA-256: adb282d8...`), [s5v31_query_benchmark_proposed.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_query_benchmark_proposed.json) (`SHA-256: 4c281da9...`), [s5v31_retrieval_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_retrieval_manifest.json) (`SHA-256: 8915d97b...`).

> [!IMPORTANT]
> **Estimated Forecast vs. Actual Completed Human Work:**
> - **Actual completed human query verifications:** **`0 / 72`**
> - **Actual completed human negative-control verifications:** **`0 / 8`**
> - **Actual completed human relevance judgments:** **`0`** pairs (depth-5 or depth-10)
> - **Actual completed third-party adjudications:** **`0`**
> - **Effectiveness metrics computed:** **`NONE`** (`NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS`)
>
> All hours and budgets below are **Python-verified pre-annotation forecasts** computed directly from the **actual measured relevance-agnostic pool sizes** produced by Stage C across all 8 S5-v3.1 retrieval systems. AI-assisted labeling is never counted as an independent human assessor (`faggioli2023perspectives`).

---

## 1. Actual Measured Corpus, Benchmark & Pool Inputs (Stages A–D)

| Input Dimension | Measured S5-v3.1 Value | Provenance |
|---|---:|---|
| **Eligible Corpus v3.1** | **`1,958` passages** across **`8` domains** (`818` retained eligible v3 + `1,140` new OA CS: OS `112`, DB `208`, Networks `600`, Distributed Systems `220`) | `s5v31_corpus_manifest.json` (`okf_graph_db_dependency: false`) |
| **Proposed Queries (Total)** | **`72` queries** (`64` positive + `8` negative controls) | `s5v31_query_benchmark_proposed.json` (`PROVISIONAL_PENDING_HUMAN_VERIFICATION`) |
| **Dev Split** | **`24` queries** (`22` positive + `2` negative controls) | Zero text or evidence overlap with `test` |
| **Test Split** | **`48` queries** (`42` positive + `6` negative controls) | Locked evaluation split (`N_test = 42` answerable) |
| **Pooled Retrieval Systems** | **`8` systems** (`3` controls: `v31_lexical_bm25`, `v31_dense_snowflake`, `v31_hybrid_rrf_bm25_dense` + `5` v3 graph variants) | `s5v31_retrieval_diagnostics.json` (`all_systems_deterministic: true`) |
| **Measured Depth-5 Pool (All 8 Systems)** | **`1,001` unique pairs** (`mean = 13.90`, `std = 4.20`, `min = 6`, `max = 24`) — `dev`: **`326`** (`13.58/q`), `test`: **`675`** (`14.06/q`) | Controls-only: `587` (`8.15/q`); Graph-v3-only: `727` (`10.10/q`) |
| **Measured Depth-10 Pool (All 8 Systems)** | **`1,855` unique pairs** (`mean = 25.76`, `std = 7.08`, `min = 11`, `max = 45`) — `dev`: **`617`** (`25.71/q`), `test`: **`1,238`** (`25.79/q`) | Controls-only: `1,153` (`16.01/q`); Graph-v3-only: `1,361` (`18.90/q`) |

*Note on pool density vs. earlier S5-v3 forecast:* In `S5V3_ANNOTATION_COST_ESTIMATE.md`, we conservatively forecasted `18` pairs/query at `k = 5` and `32` pairs/query at `k = 10`. Real Stage C pooling over `1,958` passages and `8` systems yielded **`13.90` pairs/query at `k = 5`** and **`25.76` pairs/query at `k = 10`** (~`19.5%` smaller than the conservative pre-run forecast, closely matching v2.1's `25.4` pairs/query).

---

## 2. Calibration Parameters

| Parameter | Central Value | Calibration Source |
|---|---:|---|
| **Single-annotator grading pace** | `90 sec/pair` (`40` pairs/hr) | Technical CS/ML/Systems passage reading + `0/1/2` grade + verbatim supporting quote for grades `1/2` |
| **Independent human annotators / pair** | `2` (dual blind) | Required for inter-human reliability (`κ`, quadratic weighted `κ_w`; `cohen1968weighted`) |
| **Inter-annotator disagreement rate** | `20.0%` | Calibrated directly to S5-C2 observed disagreement (`51 / 254 = 20.08%`) |
| **Adjudication pace (3rd human)** | `2.5 min/disagreement` (`24`/hr) | Reading passage, query, and both blinded quotes/rationales |
| **Negative-control (NC) verification** | `0.50 hr / NC query` (`30` min) | Independent human inspection of top lexical/dense corpus candidates + absence rationale |
| **Pre-freeze query verification (QV)** | `0.10 hr / query` (`6` min) | Human audit of proposed query wording, provenance, passage necessity, and single-passage shortcuts |
| **Illustrative hourly rate** | `$25/hr – $50/hr` | Person-hours are the primary invariant metric; USD is illustrative only |

---

## 3. Python-Verified Effort & Cost Matrix (Measured S5-v3.1 Pools)

Formula: `Total Person-Hours = Dual Independent Grading (2×) + Adjudication + NC Verification + Query Verification`.

| Scenario | Queries (`Q`) | NC | Depth | Measured Pairs | Pairs / Q | 1× (hr) | 2× Dual (hr) | Est. Disagreements (20%) | Adjudication (hr) | NC Verify (hr) | Query Verify (hr) | **Total Person-Hours** | Illustrative USD (`$25–$50/hr`) |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `dev_only_depth_5` | `24` | `2` | `k = 5` | `326` | `13.58` | `8.15` | `16.30` | `65` | `2.71` | `1.00` | `2.40` | **`22.41 hr`** | `$560 – $1,120` |
| `test_only_depth_5` | `48` | `6` | `k = 5` | `675` | `14.06` | `16.88` | `33.76` | `135` | `5.62` | `3.00` | `4.80` | **`47.18 hr`** | `$1,180 – $2,359` |
| `full_72_depth_5` | `72` | `8` | `k = 5` | `1,001` | `13.90` | `25.02` | `50.04` | `200` | `8.33` | `4.00` | `7.20` | **`69.57 hr`** | `$1,739 – $3,478` |
| `dev_only_depth_10` | `24` | `2` | `k = 10` | `617` | `25.71` | `15.43` | `30.86` | `123` | `5.12` | `1.00` | `2.40` | **`39.38 hr`** | `$984 – $1,969` |
| **`test_only_depth_10`** | **`48`** | **`6`** | **`k = 10`** | **`1,238`** | **`25.79`** | **`30.95`** | **`61.90`** | **`248`** | **`10.33`** | **`3.00`** | **`4.80`** | **`80.03 hr`** | **`$2,001 – $4,002`** |
| `hybrid_dev_k5_test_k10` | `72` | `8` | `dev=k5, test=k10` | `1,564` | `21.72` | `39.10` | `78.20` | `313` | `13.04` | `4.00` | `7.20` | **`102.44 hr`** | `$2,561 – $5,122` |
| `full_72_depth_10` | `72` | `8` | `k = 10` | `1,855` | `25.76` | `46.38` | `92.76` | `371` | `15.46` | `4.00` | `7.20` | **`119.42 hr`** | `$2,986 – $5,971` |

---

## 4. Pacing & Disagreement Sensitivity

### 4.1 Pacing Sensitivity (`60 s` Fast / `90 s` Central / `120 s` Careful)

| Target Pool | Fast (`60 s/pair`) | Central (`90 s/pair`) | Careful (`120 s/pair`) |
|---|---:|---:|---:|
| **`test_only_depth_10`** (`48` q, `1,238` pairs) | `59.39 hr` (`41.26` dual + `10.33` adj + `7.80` QV/NC) | **`80.03 hr`** (`61.90` dual + `10.33` adj + `7.80` QV/NC) | `100.67 hr` (`82.54` dual + `10.33` adj + `7.80` QV/NC) |
| **`full_72_depth_10`** (`72` q, `1,855` pairs) | `88.50 hr` (`61.84` dual + `15.46` adj + `11.20` QV/NC) | **`119.42 hr`** (`92.76` dual + `15.46` adj + `11.20` QV/NC) | `150.32 hr` (`123.66` dual + `15.46` adj + `11.20` QV/NC) |

### 4.2 Disagreement-Rate Sensitivity (`test_only_depth_10`, `1,238` Pairs, `90 s/pair`)
- **`15%` disagreement (`186` pairs):** `7.75 hr` adjudication -> **`77.45 hr` total**
- **`20%` disagreement (`248` pairs, S5-C2 calibrated):** `10.33 hr` adjudication -> **`80.03 hr` total**
- **`25%` disagreement (`310` pairs):** `12.92 hr` adjudication -> **`82.62 hr` total**

---

## 5. Compute & Local Storage Cost (Measured)

All retrieval engineering, dense embedding generation, and diagnostics ran **100% locally** (`$0.00` marginal cloud/API cost) on the verified workstation (`Intel Core i5-13420H 8c/12t`, `15 GiB RAM`, `NVIDIA GeForce RTX 2050 4 GiB VRAM`, CPU inference verified):

- **One-time Snowflake Corpus v3.1 Encoding (`1,958` passages, CPU `float32`):** `270.19 s` (`4.50 min`, `7.25` passages/s) -> cached deterministically at `data/annotation_local/s5v3_1/embeddings/s5v31_snowflake_embeddings.npy`.
- **Per-Query Warm CPU Inference (`72` queries):** `v31_lexical_bm25` `84.92 ms`, `v31_dense_snowflake` `231.05 ms`, `v31_hybrid_rrf_bm25_dense` `324.39 ms`, `v31_graph_2hop_coverage_routed` `97.52 ms` (max peak Python memory `<= 0.92 MB` per query).
- **Measured Local Disk Footprint (Git-ignored):**
  - `data/annotation_local/s5v3_1/raw_sources/`: `1,420.78 MB`
  - `data/annotation_local/s5v3_1/corpus_v31/`: `4.34 MB`
  - `data/annotation_local/s5v3_1/embeddings/`: `6.02 MB`
  - `data/annotation_local/s5v3_1/query_audit/`: `0.45 MB`
  - `data/annotation_local/s5v3/models/snowflake-arctic-embed-m-v1.5/`: `436.81 MB`
  - **Total Local Storage:** **`1,868.40 MB` (`1.87 GB`)** (`$0.00` cloud storage cost).

---

## 6. Recommended Feasible Annotation Strategy (`PHASED_TEST_K10_STRUCTURAL_DEV`)

1. **Stage 1 — Pre-Freeze Query & Negative-Control Audit (`11.20 hr` across all `72` queries, or `7.80 hr` for `test` only):** Complete human verification in the blinded workbook (`data/annotation_local/s5v3_1/query_audit/`) *before* freezing any pool, discarding or revising any query with shortcut or premise defects.
2. **Stage 2 — Structural Dev Freeze (`0 hr` dev grading, or optional `22.41 hr` `dev_only_depth_5` pilot):** Freeze all 8 system configurations using relevance-agnostic structural diagnostics on `dev` (or run a small `dev_only_depth_5` pilot of `326` pairs = `19.01 hr` grading+adjudication to calibrate annotator pacing and inter-annotator `κ_w` before committing to `test`).
3. **Stage 3 — Locked Test Depth-10 Dual Annotation (`80.03 hr` including test QV/NC, or `72.23 hr` incremental grading+adjudication after Stage 1):** Pool all 8 systems at `k = 10` on the locked `48`-query `test` split (`42` answerable + `6` NC = `1,238` measured pairs). This preserves complete depth-10 coverage (`nDCG@10`, `Recall@10`, `MRR@10`, zero unjudged passages) across all 8 CS/ML domains while saving **`39.39 person-hours` (`33.0%`)** relative to `full_72_depth_10` (`119.42 hr`).
4. **Budget-Constrained Fallback:** If total human capacity is capped at `<= 50 hr`, execute `test_only_depth_5` (`675` pairs, **`47.18 hr`**) and restrict primary metrics strictly to `@5` (`nDCG@5`, `Recall@5`, `Precision@5`, `MRR@5`), never silently zero-imputing unjudged ranks `6–10` (`buckley2004retrieval`).
