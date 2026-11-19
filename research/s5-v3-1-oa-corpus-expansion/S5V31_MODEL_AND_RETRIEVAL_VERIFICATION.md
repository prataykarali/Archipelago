# S5-v3.1 Stage C — Model Pin Verification & Retrieval Technical Diagnostics

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-1-oa-corpus-expansion-canonical`  
**Schema Version:** `s5v31-retrieval-v1.0`  
**Retrieval Manifest:** `research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_retrieval_manifest.json` (`SHA-256: 8915d97be88c46e47f396d26dd994747a7386c38b11eb0eaa8b5ee6ec67e7625`)  
**Diagnostics Report:** `research/s5-v3-1-oa-corpus-expansion/reports/s5v31_retrieval_diagnostics.json` (`SHA-256: 07cf30cc54c8611d6f29ba016117a8cae125cbe333aaef2503f03e2b9fe1d6ea`)  
**Dependence on Missing v2.1 `okf_graph.db`:** **`False` (Zero Dependency)**  
**Frozen S5-v2.1 & S5-v3 Artifacts Modified:** **`False` (All Preserved Untouched)**

---

## 1. Scientific Boundary

> [!IMPORTANT]
> **Effectiveness Status: `NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS`**
> All measurements in this report are **strictly relevance-agnostic technical diagnostics** (cryptographic verification, determinism, corpus-grounded graph coverage, fallback/backfill rates, CPU latency, `tracemalloc` peak memory, and depth-5 / depth-10 unique pool sizes). **Zero human relevance grades exist and zero effectiveness or system superiority claims are made.**

---

## 2. Essential Model Verification & External Resource Disclosures

### 2.1 Pinned Dense Model (`Snowflake/snowflake-arctic-embed-m-v1.5`)
Verified offline (`local_files_only=True`) against `research/s5-v3-benchmark-expansion/hold_resolution/s5v3_essential_model_pin.json` (`SHA-256: 761a2a3a20c45a8a18467455ea1ba48b3bb4dbdf93625f1f869b3f26c8a57ba8`). No optional rerankers or new architectures were downloaded.

| Field | Verified Value |
|---|---|
| Repository ID | `Snowflake/snowflake-arctic-embed-m-v1.5` |
| Pinned Revision | `e58a8f756156a1293d763f17e3aae643474e9b8a` |
| License | `Apache-2.0` |
| Local Git-Ignored Path | `data/annotation_local/s5v3/models/snowflake-arctic-embed-m-v1.5` |
| Verified Pinned Files | **11 / 11 exact byte-size & SHA-256 matches** (`436,808,446` bytes total) |
| `model.safetensors` SHA-256 | `463d27a3e88a748997316367c419bbdab4d809300a5f24b9b19ba9b2dc08ffdd` |
| Controlled CPU Smoke Test | **PASS** — 2 neutral fixed sentences (`benchmark_query_or_label_used=False`), shape `[2, 768]`, `float32`, `all_finite=True`, `unit_norm_verified=True`, `repeat_run_deterministic=True` (`0.4382s` load, `0.3981s` encode) |

### 2.2 Hash-Pinned Corpus v3.1 Dense Embedding Cache
Stored exclusively in Git-ignored `data/annotation_local/s5v3_1/embeddings/s5v31_snowflake_embeddings.npy` (verified fail-closed on reload via `verify_embedding_cache_integrity`).

| Field | Verified Value |
|---|---|
| Corpus Scope | Exact identical eligible Corpus v3.1 (`1,958` passages; `0` excluded; JSONL SHA-256 `6366477189b8058b3f523a9d6607abb4d2c249351927918d24979e17833937b9`) |
| Embedding Matrix Shape / Dtype | `[1958, 768]`, `float32` (`6,015,104` bytes) |
| Embedding Matrix SHA-256 | `c02f817fc5f54c186c1b3ff15422c86e2283d848f534be3df9b17b933f5b31d1` |
| Corpus Passage-IDs SHA-256 | `e5dd0e58554aef90bbcbb6138a1c8d1ae2c4e619f5927370ac5fc9e3e9834c60` |
| Corpus Build Time | `270.1929s` (`7.25` passages/s on local RTX 2050 4 GiB) |

### 2.3 Graph Structure Disclosure
- **Canonical Graph File:** `okf_graph.json` (`610` concepts, `1,988` edges; zero Kùzu `okf_graph.db` dependency).
- **Corpus v3.1 Grounded Coverage (boundary + alias):** **`183 / 610` (`30.00%`)** concepts and **`341 / 1,988` (`17.15%`)** edges grounded in Corpus v3.1 (`1,958` passages), up from `139 / 610` (`22.79%`) concepts and `270 / 1,988` (`13.58%`) edges in Corpus v3 (`858` passages).

---

## 3. System Inventory, Determinism & CPU Latency / Memory Diagnostics (72 Queries)

All **8** systems ran over the exact identical `1,958`-passage Corpus v3.1 and `72` proposed queries (`manifests/s5v31_query_benchmark_proposed.json`, SHA-256 `4c281da97ed2251f8d8603beaa2f92cbfe43cb4930ddfe2f1055ab58de5ee161`). Repeat-run determinism check passed **`8 / 8` (`all_systems_deterministic = True`)**.

| System Variant | Config SHA-256 (12-char) | Anchor Hit | Fallback | Short-List (Before → After) | Zero-Result | Backfill | Mean CPU Latency (ms) | p95 Latency (ms) | Max Peak Mem (B) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `v31_lexical_bm25` | `d41d1e49be68` | N/A | N/A | 0 → 0 | 0 | 0 | 84.92 | 126.20 | 277,655 |
| `v31_dense_snowflake` | `8bc0acf612a9` | N/A | N/A | 0 → 0 | 0 | 0 | 231.05 | 298.64 | 276,276 |
| `v31_hybrid_rrf_bm25_dense` | `37c14173308a` | N/A | N/A | 0 → 0 | 0 | 0 | 324.39 | 393.55 | 383,925 |
| `v31_graph_naive_substring` | `affb711dd8ae` | 61/72 (84.7%) | 0/72 | 14 → 14 | 11 | 0 | 15.21 | 39.83 | 1,044,420 |
| `v31_graph_1hop_no_backfill` | `5dc0817e4bab` | 51/72 (70.8%) | 21/72 (29.2%) | 1 → 1 | 0 | 0 | 27.37 | 87.81 | 693,620 |
| `v31_graph_1hop_backfill` | `f8e5f68edf50` | 51/72 (70.8%) | 21/72 (29.2%) | 1 → 0 | 0 | 7 | 28.05 | 82.35 | 702,772 |
| `v31_graph_2hop_backfill` | `6c0b5489db33` | 51/72 (70.8%) | 21/72 (29.2%) | 1 → 0 | 0 | 4 | 39.33 | 90.84 | 923,618 |
| `v31_graph_2hop_coverage_routed` | `407b1b774681` | 51/72 (70.8%) | 21/72 (29.2%) | 1 → 0 | 0 | 0 | 97.52 | 147.78 | 920,314 |

*Notes:*
- All `21` fallbacks in the boundary-aware variants had `fallback_reason = "zero_anchors_matched"` (primarily on new CS Systems queries whose concepts are absent from legacy `okf_graph.json`, illustrating why graph coverage stratification is essential).
- `v31_graph_2hop_coverage_routed` routing distribution: `lexical_only: 36`, `balanced_hybrid: 35`, `graph_heavy: 1` (mean query anchor coverage `0.1488`).
- `v31_hybrid_rrf_bm25_dense` measures true end-to-end CPU latency (`T_bm25 + T_dense + T_fusion`, mean `324.39 ms`).

---

## 4. Actual Relevance-Agnostic Unique Pool Sizes (Depth 5 & Depth 10)

Measured directly across the `72` proposed S5-v3.1 queries (`24` dev, `48` test) for `@eval-design-v3` cost modeling:

| Pool Slice | Query Count | Depth-5 Total Pairs | Depth-5 Mean (Std / Min–Max) | Depth-10 Total Pairs | Depth-10 Mean (Std / Min–Max) |
|---|---:|---:|---|---:|---|
| **All 8 Systems (Full Benchmark)** | **72** | **1,001** | `13.90` (`4.20` / `6–24`) | **1,855** | `25.76` (`7.08` / `11–45`) |
| Controls Only (BM25, Dense, Hybrid RRF) | 72 | 587 | `8.15` (`1.79` / `5–13`) | 1,153 | `16.01` (`3.14` / `11–25`) |
| Graph v3 Variants Only (5 systems) | 72 | 727 | `10.10` (`3.30` / `5–18`) | 1,361 | `18.90` (`5.57` / `10–34`) |
| **`dev` Split (All 8 Systems)** | **24** | **326** | `13.58` (`4.02` / `6–20`) | **617** | `25.71` (`6.94` / `12–34`) |
| **`test` Split (All 8 Systems)** | **48** | **675** | `14.06` (`4.32` / `6–24`) | **1,238** | `25.79` (`7.21` / `11–45`) |

---

## 5. Verification & Code Quality

- **Unit Tests:** `python3 -m pytest tests/unit/test_s5v31_retrieval.py -v` — **5 passed, 0 failed**.
- **Lint & Format:** `ruff check` & `ruff format --check` on `research/s5-v3-1-oa-corpus-expansion/scripts/retrieval_v31/`, `run_retrieval_v31_verification.py`, and `tests/unit/test_s5v31_retrieval.py` — **All checks passed!**.
- **Line Counts:** All new Python files `<= 436` lines (limit `500`), `from __future__ import annotations`, full type hints, named constants, `0` banned patterns.
