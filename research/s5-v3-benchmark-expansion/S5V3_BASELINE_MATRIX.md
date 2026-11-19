# S5-v3 Module E — Baseline Matrix, Hardware Feasibility & Evaluation Plan

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-benchmark-expansion`  
**Status:** PRE-HUMAN-ANNOTATION EXPERIMENTAL DESIGN CONTRACT  
**Run Manifest Template:** [s5v3_retrieval_run_manifest_template.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/manifests/s5v3_retrieval_run_manifest_template.json)

> [!CAUTION]
> **Explicit Ban on Unvalidated Superiority Claims:** Neither this document nor any S5-v3 diagnostic script may report, imply, or extrapolate system superiority, relevance improvement, or statistical significance without **validated, independently confirmed, adjudicated human gold relevance labels** passing the fail-closed evaluation gate. Software correctness (verified via unit tests and relevance-agnostic diagnostics) is strictly distinct from retrieval effectiveness.

---

## 1. Frozen v2.1 Controls vs. S5-v3 Evaluation Matrix

All **six frozen S5-v2.1 retrieval systems** (`S5D0_EXPERIMENTAL_SETUP.md` §2) are preserved **completely unmodified** as reference controls alongside the cleanly versioned S5-v3 retrieval variants and optional neural reranking baseline.

| Family | System Identifier | Role in S5-v3 | Eligible Collection | Pretrained / External Access Disclosure | Local Execution Status Today |
|---|---|---|---|---|---|
| **Lexical Control** | `bm25` (`BM25Okapi`, `k1=1.5`, `b=0.75`, `[a-z0-9]+`) | Frozen v2.1 control | Identical Corpus v3 | None (pure corpus statistics) | **READY** (pure Python, zero external weights) |
| **Dense Control** | `dense_snowflake_arctic_768d` (`Snowflake/snowflake-arctic-embed-m-v1.5`, 768-dim, mean pool, asymmetric query prefix) | Frozen v2.1 control | Identical Corpus v3 | Pretrained bi-encoder weights (`merrick2024arctic`); no graph access | **BLOCKED ON LOCAL WEIGHTS** (`~/.cache/huggingface/hub/` absent; requires authorized HF download + SHA-256 pin) |
| **Hybrid Control** | `hybrid_rrf_e2e` (RRF `k=60`, top-50 `bm25` + `dense`) | Frozen v2.1 control | Identical Corpus v3 | Inherits `dense` pretrained weights (`cormack2009reciprocal`); no graph access | **BLOCKED ON LOCAL WEIGHTS** (depends on `dense`) |
| **Graph Control (v2.1)** | `baseline_graph_1hop` (Kùzu 1-hop, raw substring anchor, no backfill) | Frozen v2.1 control | Identical Corpus v3 | Uses corpus-scoped `okf_graph.json` concepts/edges; no pretrained weights | **FROZEN REFERENCE** (v2.1 `okf_graph.db` missing; on Corpus v3 runs only via corpus-scoped `okf_graph.json` adapter if evaluated, never altering v2.1 files) |
| **Graph Control (v2.1)** | `repaired_graph_1hop_ablation` (`max_hops=1`, heterogeneous typed edges) | Frozen v2.1 control | Identical Corpus v3 | Uses corpus-scoped heterogeneous extracted graph; no pretrained weights | **FROZEN REFERENCE** (preserved untouched in v2.1) |
| **Graph Control (v2.1)** | `repaired_graph_2hop_full` (`max_hops=2`, decay `0.5`, heterogeneous typed edges) | Frozen v2.1 control | Identical Corpus v3 | Uses corpus-scoped heterogeneous extracted graph; no pretrained weights | **FROZEN REFERENCE** (preserved untouched in v2.1) |
| **Graph Variants (v3)** | S5-v3 Modular Variants (Module D: token-boundary anchoring, alias normalization, corpus-grounded concept-passage index, deterministic fallback, partial-list backfill, controlled 1-hop/2-hop with fanout caps, coverage-aware routing) | Cleanly versioned S5-v3 experimental systems | Identical Corpus v3 | Uses `okf_graph.json` concept taxonomy + Corpus v3 inverted mapping + lexical fallback/backfill; zero pretrained neural weights | **READY** (implemented & unit-tested in Module D; exact system IDs & config SHA-256 hashes synced in §8) |
| **Neural Reranker (Proposed Strong Baseline)** | `rerank_minilm_l6_bm25_top50` (`cross-encoder/ms-marco-MiniLM-L-6-v2`) or `rerank_bge_base_hybrid_top50` (`BAAI/bge-reranker-base`) | Strong two-stage neural control (`Nogueira & Cho, 2019`) | Identical Corpus v3 | Pretrained cross-encoder weights (MS MARCO / multi-domain); no graph access | **HARDWARE-FEASIBLE, CURRENTLY UNCACHED** (see §2) |

### Identical Eligible Document Collection Contract & Parity Disclosure
1. **Strict Passage-Collection Parity:** Every evaluated system MUST score and return passages strictly from the **exact same SHA-256-locked Corpus v3 eligible passage set** (`s5v3_corpus_passages.jsonl`, verified via `corpus_passage_id_sha256` and `corpus_text_sha256` in `s5v3_retrieval_run_manifest_template.json`). Zero external passages, unverified pages, or out-of-corpus graph snippets may enter any system's candidate list.
2. **Explicit Representation & Graph Access Disclosure:** Identical eligible passage collection does **not** mean identical prior knowledge. Every results table and run manifest MUST explicitly disclose:
   - Whether a system uses **pretrained neural weights** (`dense`, `hybrid_rrf`, `cross_encoder_rerank`) trained on external web/QA corpora (e.g., MS MARCO, web pairs).
   - Whether a system accesses an **external concept ontology (`okf_graph.json`)** or a **corpus-derived graph** (`repaired_graph_*`, `v3_graph_*`), and its exact SHA-256 hash.
   - Whether a system invokes **lexical fallback or partial-list backfill**, with per-query and per-rank attribution.

---

## 2. Hardware-Grounded Feasibility Assessment for Neural & Cross-Encoder Baselines

Measured directly on the local workstation (`2026-11-19`):

| Resource | Measured Value | Practical Constraint for S5-v3 |
|---|---|---|
| **CPU** | 13th Gen Intel Core i5-13420H (`8` cores / `12` threads) | Fast enough for pure-Python BM25, symbolic graph traversal, and small CPU reranking (`MiniLM-L-6`), but slow for large 568M-param models. |
| **System RAM** | `15 GiB` total (`6.1 GiB` available; `4.0 GiB` swap) | Sufficient for `<= 300M`-parameter models; tight for multi-GB models alongside IDE/OS. |
| **GPU** | **NVIDIA GeForce RTX 2050 (`4,096 MiB` total / `3,758 MiB` free VRAM)**, Driver `580.126.20` | **CUDA IS AVAILABLE** (`torch 2.5.1+cu121`, `cuda=True`). Easily runs FP16/FP32 bi-encoders and base cross-encoders (`<= 300M` params) with batch size `16–32`. **Too small (`4 GiB`)** for `bge-reranker-v2-m3` (`568M` params in FP32 ~`2.3 GB` weights + activations OOM risk at seq len 512–1024 without strict FP16/small batch). |
| **Installed Python ML Stack** | `/usr/bin/python3` (`3.12.3`): `torch 2.5.1+cu121`, `sentence_transformers 5.6.1`, `transformers 5.13.1`, `scipy 1.18.1`, `numpy 2.5.3`, `scikit-learn 1.9.0`, `kuzu 0.11.3`, `onnxruntime 1.26.0` | All neural bi-encoder and `CrossEncoder` inference dependencies are **already installed**. (`rank_bm25`, `faiss`, `pyserini`, `ranx`, `ir_measures`, `statsmodels` are NOT installed; Archipelago uses pure-Python BM25 + `numpy`/`scipy`.) |
| **Hugging Face Local Cache** | `~/.cache/huggingface/hub/` — **ABSENT (0 cached models)** | **Immediate blocker for offline execution:** neither `Snowflake/snowflake-arctic-embed-m-v1.5` nor any cross-encoder is cached locally. |
| **Free Disk Space** | `17 GiB` available on `/` (`89%` used of `147 GiB`) | Tight disk budget — must limit downloads to compact models (`<= 1.2 GB` total) and pin exact HF commit SHAs. |
| **Local Ollama Models** | `qwen3.5:0.8b`, `dual-ingest:v3`, `lib-qwen`, `lfm2.5:230m` (all `<= 1.0 GB`) | Small generative LLMs only; **none** are calibrated retrieval bi-encoders or cross-encoder rerankers. |

### Feasibility Verdict for Neural & Cross-Encoder Baselines
1. **`cross-encoder/ms-marco-MiniLM-L-6-v2` (~22.7M params, ~90 MB disk, <0.4 GB VRAM) — `HIGHLY FEASIBLE` (Recommended Primary Reranker Control):**
   - Fits effortlessly in `3.75 GiB` free RTX 2050 VRAM (or even CPU in `<200 ms` for top-50 candidates) and uses `<0.1 GB` of the `17 GiB` free disk.
   - Provides a canonical, reproducible two-stage neural reranking control (`BM25@50 -> MiniLM Cross-Encoder` and `Hybrid-RRF@50 -> MiniLM Cross-Encoder`; `Nogueira & Cho, 2019`).
2. **`Snowflake/snowflake-arctic-embed-m-v1.5` (~109M params, ~436 MB disk, ~0.8 GB VRAM FP16 / ~1.2 GB FP32) — `FEASIBLE` (Required Frozen v2.1 Dense Control):**
   - Fits comfortably in `3.75 GiB` free VRAM and `17 GiB` free disk once authorized download into local HF cache is performed and exact commit SHA (`f22f7b88939ba6d01306a445d48729fb5a2ff3f3` or pinned equivalent) is verified.
3. **`BAAI/bge-reranker-base` (~278M params, ~1.1 GB disk, ~1.5 GB VRAM FP16) — `FEASIBLE WITH FP16`:**
   - Viable on RTX 2050 in `float16` (`batch_size=16`, `max_length=512`), though `1.1 GB` disk footprint is noticeable on a `17 GiB`-free partition.
4. **`BAAI/bge-reranker-v2-m3` (~568M params, ~2.27 GB disk) — `NOT RECOMMENDED LOCALLY`:**
   - High VRAM pressure on `4 GiB` RTX 2050 and consumes >13% of remaining free disk space.

---

## 3. Dev / Test Split Isolation & Anti-Leakage Rules

1. **Strict Split Separation:** Proposed queries are partitioned into disjoint `dev` and `test` splits (`zero` shared `query_id`, `zero` paraphrased duplicates, and zero document/passage leakage where cross-document separation applies).
2. **Hyperparameter Selection Rule:** All tunable v3 parameters (anchor normalization alias table, hop-decay factor, fanout cap, coverage-routing threshold, RRF `k`, reranker candidate depth) MUST be tuned **exclusively on `dev`** (and/or via relevance-agnostic structural diagnostics). **NEVER use `test` relevance labels, `test` pools, or frozen v2.1 test judgments to select hyperparameters, tune thresholds, or edit query wording.**
3. **One-Shot Test Evaluation:** Once `dev` tuning is finalized, every system configuration is cryptographically frozen (`system_config_sha256` recorded in the run manifest) *before* computing `test` pools or running `test` evaluation.

---

## 4. Pool Construction & Blinding Protocol

- **Union Depth-$k$ Pooling:** For each split (`dev` and `test`), construct the deduplicated union of Top-$k$ outputs across **all evaluated controls + v3 variants** (plus verified seed evidence candidates), where `k = 10` is the primary target (`k = 5` is the reduced-budget fallback; see [S5V3_ANNOTATION_COST_ESTIMATE.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/S5V3_ANNOTATION_COST_ESTIMATE.md)).
- **Complete Coverage & Unjudged Policy:** Every pooled `(query_id, passage_id)` pair receives a neutral ID after deterministic shuffling (`seed = 20261119`), with zero system IDs, ranks, or scores exposed to human annotators. Following `buckley2004retrieval`, unjudged passages are **explicitly counted and NEVER silently treated as irrelevant (`0`)**; the scoring gate raises a hard error if any Top-$k$ passage in a primary metric lacks an adjudicated human gold label.
- **Human Provenance Gate:** Identical to S5-D0/S5-C3 — requires `status == "ADJUDICATED_HUMAN_GOLD_FINAL"`, dual independent human annotation, third-party adjudication of all disagreements, independent human verification of all negative controls, and `0` unconfirmed AI-assisted labels (`faggioli2023perspectives`).

---

## 5. Metrics, Stratification & Ablation Analysis Plan

### 5.1 Primary & Secondary Metrics (Answerable Queries Only)
- **Primary Metrics:** Graded **`nDCG@10`** (and **`nDCG@5`**; exponential gain $2^g - 1$, `jarvelin2002cumulated`), strict **`Recall@10`** (`grade >= 2`), and **`MRR@10`** (`grade >= 2`).
- **Secondary Metrics:** Lenient `Recall@5/10` (`grade >= 1`), `Precision@5/10` (strict & lenient), `nDCG@5`, and **Multi-Passage Evidence Recall (`Complete-Set Recall@k`)** — fraction of multi-passage / cross-document queries for which *all* passages in `minimum_required_evidence_set` appear in Top-$k$.
- **Negative-Control Metrics (Stratified Separately, Excluded from Recall/nDCG Denominators):** Returned count, fallback triggered rate, max observed human grade (`0` expected), and false-positive anchor rate.
- **Systems / Efficiency Metrics (Relevance-Agnostic, Measurable Now):** Cold-start latency (`ms`), warm per-query latency (`mean`, `median`, `p95` over `5` reps via `perf_counter_ns`), peak Python memory (`tracemalloc` KiB), GPU VRAM peak (`torch.cuda.max_memory_allocated` when applicable).

### 5.2 Mandatory Stratifications & Ablations
1. **Per-Query & Per-Domain Analysis:** Report full per-query distributions (no hiding variance behind macro averages) and per-domain breakdowns (ML, Math for ML, NLP/LLMs, Robotics/Control; explicitly marking OS/DB/Networks as `DEFERRED_PENDING_OA_SOURCE_INGESTION`).
2. **Fallback vs. Non-Fallback Stratification:** Every graph system MUST be reported in three slices: (a) all answerable queries, (b) **non-fallback queries only** (where graph anchoring actually fired), and (c) **fallback-triggered queries only** (where lexical fallback rescued 0-anchor queries).
3. **Graph-Coverage & Traversal-Depth Ablations:** Compare anchor-rich vs. anchor-sparse query strata, 0-hop (anchor-only) vs. 1-hop vs. 2-hop traversal, and graph-edge subsampling (`25% / 50% / 75% / 100%` coverage) to isolate coverage sensitivity.
4. **Short-List & Backfill Handling:** Report raw short-list rate (`returned < k`), total backfilled slots, and paired ablation of `backfill=OFF` vs. `backfill=ON` (exposing whether backfill improves or dilutes Top-$k$ precision).
5. **Failure-Case & Robustness Analysis:** Inspect worst-5 queries per system, paraphrase/terminology-mismatch queries, false-positive anchor traps, and cross-document bridge failures.

---

## 6. Conditional Confidence-Interval & Statistical-Analysis Plan

> [!WARNING]
> **More Queries Do NOT Automatically Confer Statistical Power:** Expanding from `10` queries (v2.1) to `~40–60` queries (v3) improves descriptive stability, but **does not automatically guarantee adequate statistical power** (`sakai2016statistical`). Power depends on the *number of answerable test queries ($N_{\text{test}}$)*, the *within-query paired variance ($\sigma_\Delta$)*, the *true effect size ($\delta$)*, and *multiplicity across pairwise system comparisons*.

1. **Sample-Size & Paired-Test Assumptions (Stated Honestly):**
   - In the proposed S5-v3 benchmark (`48` total queries: `16` `dev` [`13` positive + `3` negative controls] and `32` `test` [`27` positive + `5` negative controls]), the locked `test` split has **`N_test = 27` answerable queries**. This is larger than v2.1 (`7` answerable), but **still below Sakai's (2016) `>= 50`-topic benchmark** for moderate IR effect sizes.
   - If the locked **`test` split** contains **`N_test < 25` answerable queries** (e.g., if human verification rejects >2 proposed test queries): **formal null-hypothesis significance testing (NHST) is NOT permitted**; report descriptive point estimates plus **non-parametric paired bootstrap 95% confidence intervals** (`10,000` resamples, `seed = 20261119`) strictly as *exploratory uncertainty bounds*, not superiority proofs.
   - If **`N_test >= 25` answerable queries** (e.g., all `27` test positives survive human verification, or `>= 30` after multi-domain OA expansion): apply a **two-sided paired randomization test** (`100,000` permutations; `Smucker, Allan, & Carterette, 2007`, CIKM '07, DOI: `10.1145/1321440.1321528`), which avoids normality assumptions on bounded IR metrics (`nDCG`, `Recall`, `MRR`), while explicitly flagging `N_test < 50` as **moderate/limited statistical power** (`sakai2016statistical`).
2. **Multiple-Comparison Control:** Pre-register at most **3 primary pairwise hypotheses** (e.g., `v3_best_graph vs. bm25`, `v3_best_graph vs. hybrid_rrf`, `v3_2hop vs. v3_1hop`) and apply **Holm-Bonferroni** family-wise error correction ($\alpha = 0.05$). All remaining pairwise comparisons are labeled *exploratory* and never claimed significant.
3. **Effect-Size & Power Reporting:** Report mean paired difference $\bar{\Delta}$, paired standard deviation $s_\Delta$, standardized effect size $d_z = \bar{\Delta} / s_\Delta$, and post-hoc minimum detectable effect (MDE) at $80\%$ power so readers can see what differences the sample could and could not reliably detect.

---

## 7. Pre-Execution Checklist (Gate Before Any Relevance Scoring)

- [ ] Corpus v3 manifest locked (`s5v3_corpus_manifest.json`, deterministic SHA-256).
- [ ] All proposed queries human-verified (`premise`, `evidence_set`, `shortcut_check`, `negative_controls`).
- [ ] `dev`/`test` splits frozen with zero leakage and zero v2.1 overlap.
- [ ] Dense (`snowflake-arctic-embed-m-v1.5`) and Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) weights downloaded, SHA-256 pinned, and cached locally (if included in pool).
- [ ] All system configs frozen on `dev` and recorded via `s5v3_retrieval_run_manifest_template.json`.
- [ ] Dual independent human annotation + third-party adjudication completed (`ADJUDICATED_HUMAN_GOLD_FINAL`).

---

## 8. Synced S5-v3 Exact Corpus, Benchmark & Retrieval Counts

Synced directly from Modules B (`@corpus-v3`), C (`@benchmark-v3`), and D (`@retrieval-v3`):

### 8.1 Corpus v3 Snapshot (`s5v3_corpus_manifest.json`)
- **Public Manifest SHA-256:** `776616220062667bce9d174bc40623e980b5bdb52723dfd4c713fbae9ecfc48b`
- **Private JSONL (`data/annotation_local/s5v3/corpus_v3/s5v3_corpus_passages.jsonl`) SHA-256:** `dd8e973b727a981aeb4b8d0109513616c4ea709afe3eed40bde5c8b14ebeaee4` (`passage_ids_sha256`: `1e1c02a795342ef7c9dc44b85509f3dab17fbcafdd2498d3187f9c79748b839b`)
- **Counts:** **`858` total passages** (`818` usable, `40` unusable, `138` flagged; `3` exact duplicates, `1` near-duplicate at Jaccard `0.8333`; leakage guard `passed=true`) across **`4` verified local OA documents**:
  - `local_oa_001` (D2L Ch.3 Linear Regression, ML, `CC-BY-SA-4.0`): `27` passages (`26` usable)
  - `local_oa_002` (arXiv:2307.09702v2 Guided Generation, NLP/LLMs, 18 pp): `24` passages (`23` usable)
  - `local_oa_003` (MML Book, Math for ML, 417 pp): `757` passages (`719` usable)
  - `local_oa_004` (METATRON preprint, Robotics/Control, 14 pp): `50` passages (`50` usable)
- **Deferred CS Domains:** Operating Systems, Databases, Computer Networks, Distributed Systems (`MISSING_LOCAL_OA_SOURCE` / `DEFERRED_PENDING_OA_SOURCE_INGESTION`).

### 8.2 Proposed Benchmark v3 Snapshot (`s5v3_query_benchmark_proposed.json`)
- **Manifest SHA-256:** `17914918ac1355a8e4768cf0fc57629c85d43630d244bbfee3f004a5c611c153`
- **Status:** `AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION` / `CANDIDATE_UNVERIFIED_REQUIRES_HUMAN_AUDIT`
- **Total Queries:** **`48`** (`dev`: **`16`** [`13` positive + `3` NC]; `test`: **`32`** [`27` positive + `5` NC]; `0` dev/test overlap; `0` v2.1 reuse)
- **Category Breakdown:** `single_passage_fact_concept` (`12`: 4 dev / 8 test), `same_doc_multi_passage` (`10`: 3 dev / 7 test), `cross_doc_multi_passage` (`10`: 3 dev / 7 test; all `multi_document_truly_necessary=true`, `shortcut_found=false`), `technical_terminology_paraphrase` (`8`: 3 dev / 5 test), `negative_control` (`8`: 3 dev / 5 test; verified absent across all `858` passages).
- **Graph-Anchor Regime (against root `okf_graph.json`, 610 concepts):** `rich` (`>=2` concepts): `23` (`7` dev / `16` test); `sparse` (`0–1` concepts): `25` (`9` dev / `16` test).

### 8.3 S5-v3 Retrieval Variants & Relevance-Agnostic Diagnostics (`s5v3_retrieval_diagnostics.json`)
- **Diagnostics Report SHA-256:** `54b021e0c6ae06d680691d63519341c3991f5cfdb380c37732c2c5609d1ebf78` (`effectiveness_evaluation: "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS"`)
- **Corpus-Grounded Graph Coverage (boundary + alias):** `139/610` concepts (`22.79%`), `270/1,988` edges (`13.58%`).

| S5-v3 Variant ID | Config SHA-256 (prefix) | Anchor Hits (`/48`) | Fallback (`/48`) | Short Lists | Mean Latency (`ms`) | Notes (Strictly Relevance-Agnostic) |
|---|---|---:|---:|---:|---:|---|
| `v3_lexical_bm25_control` | `ce5c06bc5104...` | N/A | N/A | `0` | `40.68` | Pure lexical control; peak mem `124,807 B` |
| `v3_graph_naive_substring_ablation` | `baedfc1c02bd...` | `45` (FPs) | `0` | `6` | `10.43` | `3` zero-result queries; substring false-positive ablation |
| `v3_graph_1hop_no_backfill` | `899340783bc7...` | `42` (`87.5%`) | `8` (`16.7%`) | `1` | `16.90` | `6` zero-anchor + `2` zero-grounded fallbacks; `0` zero-results |
| `v3_graph_1hop_backfill` | `12534da6f856...` | `42` (`87.5%`) | `8` (`16.7%`) | `0` | `16.76` | Backfill resolves `1` short list (`1` backfilled passage) |
| `v3_graph_2hop_backfill` | `590a2bd86c68...` | `42` (`87.5%`) | `7` (`14.6%`) | `0` | `25.88` | Peak mem `657,042 B`; `0` short lists |
| `v3_graph_2hop_coverage_routed` | `5af80badfba2...` | `42` (`87.5%`) | Routed | `0` | `66.66` | Routes `17` `lexical_only`, `30` `balanced_hybrid`, `1` `graph_heavy` (mean anchor coverage `0.1910`); peak mem `684,970 B` |
