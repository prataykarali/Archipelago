# S5-D0 — Six-System Technical Diagnostics (Pre-Gold-Label)

**Base Commit:** `6450585f60b3c1bea7bef2f411458800552cea0b`  
**Date:** 2026-11-19  
**Status:** COMPLETE — STOP CHECKPOINT FOR INVESTIGATOR REVIEW  
**Evidence Sources:**
- [s5b2_1_frozen_ranked_results.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_frozen_ranked_results.json) (6 frozen systems × 10 active queries)
- [retrieval_query_pool_blinded.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package_v2_1/retrieval_query_pool_blinded.json) (254 pooled pairs)
- [retrieval_timing_report.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/reports/retrieval_timing_report.json) & [retrieval_technical_evaluation_report.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/reports/retrieval_technical_evaluation_report.json) (S5-B1.1 timing measurements)
- Reproducible generator: [generate_s5d0_diagnostics.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/scripts/generate_s5d0_diagnostics.py) → [s5d0_technical_diagnostics.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_technical_diagnostics.json) & [s5d0_preservation_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_preservation_manifest.json)

> [!IMPORTANT]
> **Methodological Boundary:** All comparisons below are strictly **relevance-agnostic technical diagnostics** (overlap, graph traversal depth, fallback frequency, result-slot coverage, and recorded latency). **No** relevance-based effectiveness metrics (Recall@k, Precision@k, MRR, nDCG@k) are computed, **no** disagreements are resolved, and **no** superiority or statistical significance claims are made.

---

## 1. Frozen Artifact Preservation Check

Running [generate_s5d0_diagnostics.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/scripts/generate_s5d0_diagnostics.py) verified **21 preserved artifacts** ([s5d0_preservation_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_preservation_manifest.json)):
- **12 / 12 exact SHA-256 matches** against the hashes recorded in [S5B2_1_FINAL_RELEASE_CHECK.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/S5B2_1_FINAL_RELEASE_CHECK.md) and [s5c2_audit_summary.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/s5c2_audit_summary.json), including the 254-pair blinded pool CSV/JSON, frozen six-system rankings, and preserved local Reviewer A (`70049fa8...`) and Reviewer B (`ca3e6af8...`) original workbooks.
- **9 / 9 additional frozen S5-B1.1 and S5-C2 reports/manifests** verified present and unmodified.
- Zero modifications were made to any retrieval algorithm, corpus, model, frozen dataset, ranking, or annotation file.

---

## 2. Retrieval-Result Overlap Across Six Frozen Systems

Computed across the 10 active S5-B2.1 queries (`Q-S5B2-01`–`Q-S5B2-08`, `Q-S5B2-10`, `Q-S5B2-11`).

### 2.1 Mean Pairwise Top-10 Jaccard Similarity (and Mean Top-5 Jaccard in Parentheses)

| System | `bm25` | `dense` | `hybrid_rrf` | `baseline_graph_1hop` | `repaired_1hop` | `repaired_2hop` |
|---|---:|---:|---:|---:|---:|---:|
| **`bm25`** | 1.0000 (1.0000) | 0.4739 (0.4869) | 0.6091 (0.7440) | 0.1466 (0.1222) | 0.4800 (0.4472) | 0.4852 (0.4583) |
| **`dense_snowflake_arctic_768d`** | 0.4739 (0.4869) | 1.0000 (1.0000) | 0.6480 (0.5663) | 0.1088 (0.1000) | 0.2106 (0.1540) | 0.2159 (0.1651) |
| **`hybrid_rrf_e2e`** | 0.6091 (0.7440) | 0.6480 (0.5663) | 1.0000 (1.0000) | 0.1216 (0.1333) | 0.2742 (0.3262) | 0.2795 (0.3373) |
| **`baseline_graph_1hop`** | 0.1466 (0.1222) | 0.1088 (0.1000) | 0.1216 (0.1333) | 1.0000 (1.0000) | 0.1164 (0.1222) | 0.1216 (0.1222) |
| **`repaired_graph_1hop_ablation`** | 0.4800 (0.4472) | 0.2106 (0.1540) | 0.2742 (0.3262) | 0.1164 (0.1222) | 1.0000 (1.0000) | 0.8636 (0.8250) |
| **`repaired_graph_2hop_full`** | 0.4852 (0.4583) | 0.2159 (0.1651) | 0.2795 (0.3373) | 0.1216 (0.1222) | 0.8636 (0.8250) | 1.0000 (1.0000) |

### 2.2 Fallback-Adjusted Overlap with BM25 & System Exclusivity

Overall Jaccard between the repaired graph retrievers and `bm25` (`0.4800` / `0.4852`) is **mechanically inflated** by `corpus_bm25` fallback on 4 of 10 queries (where Jaccard = `1.0000`). Separating non-fallback queries reveals substantially lower lexical overlap:

| Graph System | Non-Fallback Queries | Mean Top-10 Jaccard vs `bm25` (Non-Fallback Only) | Mean Shared Top-10 Passages vs `bm25` (Non-Fallback Only) |
|---|---:|---:|---:|
| `baseline_graph_1hop` | 9 / 10 | **0.0518** | 0.89 / 10 |
| `repaired_graph_1hop_ablation` | 6 / 10 | **0.1333** | 2.17 / 10 |
| `repaired_graph_2hop_full` | 6 / 10 | **0.1421** | 2.33 / 10 |

**Top-10 Exclusivity Across All 10 Queries (Query–Passage Pairs):**

| System | Total Top-10 Pairs Retrieved | Exclusive to This System | Shared with ≥1 Other System | Rank-1 Agreement with `bm25` / `dense` |
|---|---:|---:|---:|---:|
| `bm25` | 100 | 9 (9.0%) | 91 | 10 / 5 |
| `dense_snowflake_arctic_768d` | 100 | 21 (21.0%) | 79 | 5 / 10 |
| `hybrid_rrf_e2e` | 100 | 8 (8.0%) | 92 | 5 / 8 |
| `baseline_graph_1hop` | 69 | **45 (65.2%)** | 24 | 1 / 1 |
| `repaired_graph_1hop_ablation` | 100 | 7 (7.0%) | 93 | 4 / 1 |
| `repaired_graph_2hop_full` | 100 | 6 (6.0%) | 94 | 4 / 1 |

Key observations:
- `hybrid_rrf_e2e` shares an average of `7.4` Top-10 passages with `bm25` and `7.5` with `dense_snowflake_arctic_768d`, matching `dense` at Rank 1 on `8/10` queries and `bm25` on `5/10` queries.
- `baseline_graph_1hop` produces the most disjoint candidate set (`45/69` = 65.2% exclusive pairs; mean Top-10 Jaccard `0.1088`–`0.1466` with every other system).

---

## 3. Graph 1-Hop vs. 2-Hop Retrieval Behavior

Comparison of `baseline_graph_1hop` (Kùzu corpus-scoped 1-hop, 1,526 verified edges), `repaired_graph_1hop_ablation` (heterogeneous graph, 146 corpus-scoped edges, `max_hops=1`), and `repaired_graph_2hop_full` (`max_hops=2`, decay factor `0.5` at hop 2):

| Query ID | Domain | `baseline_1hop` Anchors / Paths / Hop | `repaired_1hop` Anchors / Concepts / Paths / Hop | `repaired_2hop` Concepts / Paths (H1+H2) / Hop | `1-hop` vs `2-hop` Top-5 / Top-10 Jaccard | `2-hop` Top-10 Set Diff (Add / Drop) & Rank Shifts |
|---|---|---|---|---|---:|---|
| `Q-S5B2-01` | OS | `[]` / 0 / 0 (FB) | `[]` / 0 / 0 / 0 (FB) | 0 / 0 (0+0) / 0 (FB) | 1.0000 / 1.0000 | Identical (BM25 fallback) |
| `Q-S5B2-02` | OS | `['translation']` / 2 / 1 | `[]` / 0 / 0 / 0 (FB) | 0 / 0 (0+0) / 0 (FB) | 1.0000 / 1.0000 | Identical (BM25 fallback) |
| `Q-S5B2-03` | OS | `['act']` / 0 / 0 | `[]` / 0 / 0 / 0 (FB) | 0 / 0 (0+0) / 0 (FB) | 1.0000 / 1.0000 | Identical (BM25 fallback) |
| `Q-S5B2-04` | AI/ML | `['transformer']` / 5 / 1 | `['attention', 'the transformer', 'transformer']` / 13 / 21 / 1 | 33 / 96 (21+75) / **2** | 1.0000 / 0.6667 | +2 / −2 passages; 2 shared rank shifts |
| `Q-S5B2-05` | AI/ML | `['multi-head attention']` / 5 / 1 | `['attention']` / 3 / 2 / 1 | 5 / 4 (2+2) / **2** | **0.2500 / 0.3333** | +5 / −5 passages; 5 shared rank shifts |
| `Q-S5B2-06` | AI/ML | `['low-rank adaptation', 'transformer']` / 9 / 1 | `['low-rank adaptation', 'transformer']` / 13 / 12 / 1 | 34 / 68 (12+56) / **2** | 0.6667 / 0.8182 | +1 / −1 passage; 8 shared rank shifts |
| `Q-S5B2-07` | AI/ML | `['adapter', 'fine-tuning', 'qlora', 'quantization']` / 12 / 1 | `['gpu', 'qlora']` / 6 / 4 / 1 | 17 / 21 (4+17) / **2** | 0.6667 / 1.0000 | +0 / −0 passages; 9 shared rank shifts |
| `Q-S5B2-08` | AI/ML | `['llama']` / 0 / 0 | `['gpu']` / 4 / 3 / 1 | 15 / 20 (3+17) / **2** | 0.6667 / 0.8182 | +1 / −1 passage; 8 shared rank shifts |
| `Q-S5B2-10` | Net | 6 anchors / 24 / 1 | `['nids']` / 4 / 3 / 1 | 4 / 3 (3+0) / 1 | 1.0000 / 1.0000 | Identical (0 hop-2 outgoing edges from neighbors) |
| `Q-S5B2-11` | Net | `['act']` / 0 / 0 | `[]` / 0 / 0 / 0 (FB) | 0 / 0 (0+0) / 0 (FB) | 1.0000 / 1.0000 | Identical (BM25 fallback) |

**Measured Traversal Summary (10 Active Queries):**
- `repaired_graph_1hop_ablation` traversed **45** total hop-1 paths across 6 non-fallback queries.
- `repaired_graph_2hop_full` traversed **212** total paths (**45** hop-1 + **167** hop-2), reaching observed hop depth `2` on **5 / 10** queries (all in AI & Machine Learning: `Q-S5B2-04`, `05`, `06`, `07`, `08`).
- On `Q-S5B2-10` (Computer Networks), anchor `'nids'` reached 3 hop-1 paths but **0** hop-2 paths (`actual_hop_count = 1` for both 1-hop and 2-hop), yielding identical Top-10 rankings.
- Wherever 2-hop depth was reached (`5/5` queries), it altered the Top-10 ranking order; on `4/5` queries (`Q-S5B2-04`, `05`, `06`, `08`), it changed Top-10 set membership, with the largest shift on `Q-S5B2-05` (`5` passages replaced, Top-10 Jaccard `0.3333`).
- `baseline_graph_1hop` traversed **57** total 1-hop Kùzu paths with **0** recorded `traversal_errors`.

---

## 4. BM25 Fallback Frequency and Trigger Reasons

| System | Fallbacks (10 Active S5-B2.1 Queries) | Fallback Queries | Trigger Mechanism | Exact BM25 Top-10 Match? |
|---|---:|---|---|---|
| `bm25` | 0 / 10 (0.0%) | None | N/A | N/A |
| `dense_snowflake_arctic_768d` | 0 / 10 (0.0%) | None | N/A | N/A |
| `hybrid_rrf_e2e` | 0 / 10 (0.0%) | None | N/A | N/A |
| `baseline_graph_1hop` | **1 / 10 (10.0%)** | `Q-S5B2-01` | `anchor_found == False` (`ZERO_ANCHOR_MATCH_IN_CONCEPT_INDEX`) | **Yes** (`1/1` exact IDs & scores) |
| `repaired_graph_1hop_ablation` | **4 / 10 (40.0%)** | `Q-S5B2-01`, `02`, `03`, `11` | `anchor_found == False` (`ZERO_ANCHOR_MATCH_IN_CONCEPT_INDEX`) | **Yes** (`4/4` exact IDs & scores) |
| `repaired_graph_2hop_full` | **4 / 10 (40.0%)** | `Q-S5B2-01`, `02`, `03`, `11` | `anchor_found == False` (`ZERO_ANCHOR_MATCH_IN_CONCEPT_INDEX`) | **Yes** (`4/4` exact IDs & scores) |

**Critical Trigger & Substring-Matching Diagnostics:**
1. **Domain concentration of fallbacks in the repaired heterogeneous graph:** All three Operating Systems queries (`Q-S5B2-01`, `Q-S5B2-02`, `Q-S5B2-03`) plus the Computer Networks negative control (`Q-S5B2-11`) had zero concept-name matches in the 146-edge heterogeneous graph adjacency index, triggering deterministic `corpus_bm25` fallback (`40.0%` fallback rate on the 10 active queries; `50.0%` / `6/12` in S5-B1.1 when held queries `Q-S5A-09` and `Q-S5A-12` were included).
2. **Substring false-positive anchor matching in `baseline_graph_1hop`:** Both `RepairedBaselineGraphRetriever.search()` and `RepairedHeterogeneousGraphRetriever.search()` match anchors via raw substring inclusion (`c in q_low`). In `baseline_graph_1hop`, the Kùzu concept `"act"` matched inside the word `"exact"` on `Q-S5B2-03` (*"What is the ex**act** multi-level page table walk latency..."*) and `Q-S5B2-11` (*"What is the ex**act** firmware vulnerability CVE..."*). Because `matched_anchors` was non-empty (`['act']`), BM25 fallback did **not** trigger, even though `"act"` had `0` outgoing verified edges and only `1` linked passage.
3. **No partial-result backfill:** When `anchor_found == True` but fewer than `top_k = 10` passages are linked to traversed concepts, `baseline_graph_1hop` returns the truncated list directly without BM25 backfilling.

---

## 5. Query-Level Retrieval Coverage and Missing Results

| Query ID (Legacy) | Domain | `bm25` | `dense` | `hybrid` | `baseline_1hop` | `repaired_1hop` | `repaired_2hop` | Unique Top-10 Union | Pooled v2.1 Pairs | Seed Candidates Outside Any Top-10 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `Q-S5B2-01` (`Q01`) | OS | 10 | 10 | 10 | 10 | 10 | 10 | 13 | 13 | 0 |
| `Q-S5B2-02` (`Q02`) | OS | 10 | 10 | 10 | **6** (−4) | 10 | 10 | 21 | 22 | 1 |
| `Q-S5B2-03` (`Q03`) | OS | 10 | 10 | 10 | **1** (−9) | 10 | 10 | 24 | 25 | 1 |
| `Q-S5B2-04` (`Q04`) | AI/ML | 10 | 10 | 10 | 10 | 10 | 10 | 30 | 31 | 1 |
| `Q-S5B2-05` (`Q05`) | AI/ML | 10 | 10 | 10 | 10 | 10 | 10 | 29 | 29 | 0 |
| `Q-S5B2-06` (`Q06`) | AI/ML | 10 | 10 | 10 | 10 | 10 | 10 | 30 | 31 | 1 |
| `Q-S5B2-07` (`Q07`) | AI/ML | 10 | 10 | 10 | 10 | 10 | 10 | 27 | 28 | 1 |
| `Q-S5B2-08` (`Q08`) | AI/ML | 10 | 10 | 10 | **1** (−9) | 10 | 10 | 25 | 27 | 2 |
| `Q-S5B2-10` (`Q10`) | Net | 10 | 10 | 10 | 10 | 10 | 10 | 24 | 25 | 1 |
| `Q-S5B2-11` (`Q11`) | Net | 10 | 10 | 10 | **1** (−9) | 10 | 10 | 21 | 23 | 2 |
| **Total** | — | **100** | **100** | **100** | **69 (−31)** | **100** | **100** | **244** | **254** | **10** |

**Coverage Findings:**
- **Missing result slots:** `baseline_graph_1hop` has **31 missing slots out of 100** (`Q-S5B2-02`: 4 missing; `Q-S5B2-03`, `Q-S5B2-08`, `Q-S5B2-11`: 9 missing each). All other 5 systems return `10/10` passages on all 10 queries (`0` missing slots).
- **Pool completeness:** `0` retrieved Top-10 pairs across all 6 systems are missing from the 254-pair `s5b2_1_proposed_pooled_v2.1` pool (`244` unique retrieved pairs + `10` investigator-selected seed candidates not retrieved in any system's Top-10 = **254** pooled pairs; `100.0%` Top-5 and Top-10 pool coverage for every system).

---

## 6. Existing Measured Latency and Runtime Diagnostics

> [!NOTE]
> **Measurement Scope:** Multi-repetition latency profiling was recorded during S5-B1.1 ([retrieval_timing_report.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/reports/retrieval_timing_report.json)) across **12 queries** (including held `Q-S5A-09` and `Q-S5A-12`, and pre-revision wordings of `Q-S5A-02` and `Q-S5A-10`) with **5 warm repetitions** per query on CPU. In S5-B2.1, only single-pass component timing for `hybrid_rrf_e2e` was recorded in `s5b2_1_frozen_ranked_results.json`. No new timing runs were executed in S5-D0.

### 6.1 Measured Observations

**Application Cold-Start Latency (S5-B1.1):**
- `dense_model_load_ms` (`Snowflake/snowflake-arctic-embed-m-v1.5`, CPU): **7,630.455 ms**
- `corpus_scoped_graph_build_ms` (Kùzu + heterogeneous extraction over 713 passages): **2,458.478 ms**
- `bm25_index_build_ms`: **407.279 ms**
- `corpus_load_ms` (Kùzu read + filtering): **400.246 ms**
- `dense_embedding_cache_load_ms` (`.npy` load + SHA-256 verification): **21.353 ms**

**Per-Query Latency Distributions (S5-B1.1, 12 Queries × 5 Warm Repetitions):**

| System | First-Query Mean (ms) | First-Query Max (ms) | Warm Mean (ms) | Warm Median (ms) | Warm Std (ms) | Warm Min / Max (ms) | Warm P95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bm25` | 4.798 | 6.383 | 4.344 | 4.353 | 0.888 | 2.445 / 6.230 | 5.979 |
| `dense_snowflake_arctic_768d` | 164.950 | 361.618 | 148.281 | 142.261 | 17.325 | 125.764 / 205.963 | 178.982 |
| `hybrid_rrf_e2e` | 156.402 | 196.444 | 153.233 | 149.064 | 15.487 | 132.627 / 194.791 | 183.876 |
| `baseline_graph_1hop` | 21.953 | 61.523 | 20.077 | 8.261 | 20.864 | 4.439 / 70.009 | 60.184 |
| `repaired_graph_1hop_ablation` | 2.561 | 5.564 | 2.317 | 1.530 | 2.127 | 0.132 / 5.576 | 5.312 |
| `repaired_graph_2hop_full` | 2.452 | 5.240 | 2.188 | 1.673 | 1.937 | 0.130 / 5.007 | 4.933 |

**Per-Query Measured Patterns:**
1. **Bimodal latency in `repaired_graph_*`:** Across S5-B1.1's 12 queries, warm mean latency was **0.149–0.656 ms** on the 6 non-fallback graph queries (`Q-S5A-04, 05, 06, 07, 08, 10`) versus **3.009–5.019 ms** on the 6 fallback queries (`Q-S5A-01, 02, 03, 09, 11, 12`).
2. **High variance in `baseline_graph_1hop`:** Warm mean ranged from **4.848 ms** (`Q-S5A-01`, BM25 fallback) and **7.513–8.792 ms** (1-anchor queries) up to **51.431 ms** (`Q-S5A-06`), **52.379 ms** (`Q-S5A-07`), and **61.989 ms** (`Q-S5A-10`, multi-anchor queries).
3. **Dense dominance in `hybrid_rrf_e2e` (S5-B2.1 single-pass breakdown, 10 active queries):** Across all 10 queries, `dense_ms` ranged from **138.401 to 229.783 ms** (95.4%–97.8% of `total_e2e_ms`), `bm25_ms` ranged from **3.601 to 9.819 ms**, and `fusion_ms` ranged from **0.112 to 0.161 ms** (`total_e2e_ms` range: **143.674–239.714 ms**).

### 6.2 Hypotheses & Unverified Interpretations (Clearly Separated from Measurements)

The following explanations are **hypotheses** consistent with code inspection, not directly isolated by controlled micro-benchmarks:
- **H1 (Bimodal `repaired_graph_*` latency & inverted 1-hop vs 2-hop mean):** The ~0.13 ms lower overall warm mean of `repaired_graph_2hop_full` (`2.188 ms`) relative to `repaired_graph_1hop_ablation` (`2.317 ms`) is hypothesized to reflect CPU scheduling/cache variance on the 6 BM25-fallback queries (`~0.2–0.5 ms` faster on fallback queries in the 2-hop pass), which masked the sub-millisecond hop-2 traversal cost (`+0.008` to `+0.206 ms` on `Q-S5A-04, 06, 07, 08`).
- **H2 (`baseline_graph_1hop` multi-anchor scaling):** The ~51–62 ms latency on multi-anchor queries (`Q-S5A-06, 07, 10`) is hypothesized to be driven by executing one Kùzu Cypher query per matched anchor inside `RepairedBaselineGraphRetriever.search()`, whereas `repaired_graph_*` traverses an in-memory Python adjacency dictionary.
- **H3 (Dense query-encoding cost on CPU):** The ~138–230 ms per-query latency of `dense_snowflake_arctic_768d` and `hybrid_rrf_e2e` is hypothesized to be dominated by CPU transformer forward-pass encoding of the single query string rather than the `(713, 768) @ (768,)` dot product; separate encoding vs. dot-product timers were not instrumented.
- **H4 (Scale extrapolation unverified):** Because the frozen corpus has only 713 passages and 146 heterogeneous graph edges, measured latencies do **not** establish scaling behavior on larger corpora (e.g., 10k–1M passages).
