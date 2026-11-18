# S5-B1 & S5-B1.1 Integrity Repair Report

**Branch:** `research/s5-b1-integrity-repair` (and `research/s5-b1-1-annotation-readiness`)  
**Base Commit:** `78d3f2f53443b7147ca2e92cffb85816bb6e4215` (`research/s5-a-retrieval-integrity`)  
**S5-B1 Commit:** `788976dcea0cc0429d232e3b3ce1ef930e285c0b`  
**Date:** 2026-11-18  
**Status:** COMPLETE — STOP CHECKPOINT REACHED

---

## Executive Summary

S5-B1 and S5-B1.1 correct all methodological, blinding, and reproducibility issues identified in S5-A before independent human annotation begins. No production systems were modified. No retrieval superiority is claimed. No human annotation was performed. See [S5B1_1_ANNOTATION_READINESS_REPORT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/S5B1_1_ANNOTATION_READINESS_REPORT.md) for the dedicated S5-B1.1 gate report.

---

## Summary of Repairs (S5-B1 + S5-B1.1)

1. **`.gitignore` Fix & Model Manifest Tracking:**
   - Replaced bare `models/` with anchored `/models/` so root GGUF weights remain ignored while `research/s5-a-retrieval-integrity/models/s5a_model_manifest.json` and `research/s5-b1-integrity-repair/models/s5b1_model_manifest.json` are tracked in Git.
   - Added ignore rules for `research/s5-b1-integrity-repair/annotation_local/`, `research/**/admin_package/`, `**/*admin_retrieval_manifest*.json`, and `**/*admin_query_specs*.json`.

2. **Complete Reviewer Blinding & Deterministic Candidate Randomization (`seed = 20261118`):**
   - Removed `candidate_role`, `admin_rationale`, `category`, and `category_distribution` (including `UNANSWERABLE`, `SINGLE_HOP_CONTROL`, `TWO_HOP`, `CROSS_DOCUMENT`) from `retrieval_query_candidate_pool_blinded.csv`, `retrieval_query_pool_blinded.json`, `RETRIEVAL_ANNOTATION_PROTOCOL.md`, and the Reviewer A & B workbooks.
   - Candidate passages for each query are stored in neutral lexicographical order in `corpus/s5b1_blinded_query_specs.json` and shuffled deterministically with `random.Random(20261118)` before assigning `PAIR-001`..`PAIR-031`, breaking the pattern of positive premises followed by hard negatives.
   - Separate Reviewer A (`reviewer_a_retrieval_workbook.md`) and Reviewer B (`reviewer_b_retrieval_workbook.md`) workbooks containing verified source passage text from `okf_graph.db`, neutral pair IDs, and empty judgment fields are generated in Git-ignored `annotation_local/`.

3. **Admin Manifest Isolation & Historical Exposure Disclosure:**
   - Untracked `admin_package/admin_retrieval_manifest.json` (`git rm -rf`) and moved `admin_retrieval_manifest.json` and `admin_query_specs_local.json` exclusively to Git-ignored storage (`research/s5-b1-integrity-repair/annotation_local/` and `data/annotation_local/s5b1_admin/`).
   - Historical Git exposure in commits `788976d` and `78d3f2f` is documented in `S5B1_1_ANNOTATION_READINESS_REPORT.md`; Git history was not rewritten without owner authorization.

4. **Graph Traversal Instrumentation, BM25 Fallback & Exception Transparency:**
   - Replaced the unsorted substring fallback with deterministic `corpus_bm25` ranking (`fallback_strategy: "corpus_bm25"`).
   - Replaced hard-coded `actual_hop_count = max_hops` with true observed hop depth (`0` on fallback, `1` on 1-hop, `2` when novel 2-hop concepts are reached) and recorded `paths_traversed`.
   - Removed `except Exception: pass` and logged/recorded Kùzu exceptions explicitly in `traversal_errors`.

5. **Runtime Cryptographic Fingerprint Verification:**
   - `verify_dense_cache_and_corpus_fingerprints()` verifies `corpus_passage_id_sha256` (`f7fe70031781b005d712a7a9a4aa2452a8b17d7353531305b39b09d88eeecd98`), `corpus_text_sha256` (`8464acaea13cbfae0f345ea29ce1cf707dc39e76832c7729fca33fbd763bc68c`), `corpus_sha256` (`6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7`), `embedding_matrix_sha256` (`ffb94053fa66471d14758771253c8c5404bb4adf2e7b14d2c9e4c30b2cbd4ee2`), and `(713, 768)` shape at benchmark startup, raising `ValueError` on any mismatch.

6. **Complete Graph Information-Access Audit (Heterogeneous Extractor & Baseline Kùzu Graph):**
   - Audited both `RepairedHeterogeneousGraphRetriever` (146 corpus-scoped edges vs 148 unconstrained, removing 2 external upload edges) and `RepairedBaselineGraphRetriever` (1,526 corpus-verified Kùzu edges out of 1,988 total edges, excluding 462 external/index/unscoped/null-source edges and 159 non-eligible concept nodes). Both graph baselines now share strictly identical 713-passage information access with BM25 and Dense.

7. **Reconciled Latency Accounting (Application Cold-Start vs. First-Query vs. Warm Distributions):**
   - Application cold-start: `corpus_load_ms = 400.246`, `dense_embedding_cache_load_ms = 21.353`, `dense_model_load_ms = 7630.455`, `bm25_index_build_ms = 407.279`, `corpus_scoped_graph_build_ms = 2458.478`.
   - Per-query warm mean / P95 (ms): `bm25` (4.344 / 5.979), `dense_snowflake_arctic_768d` (148.281 / 178.982), `hybrid_rrf_e2e` (153.233 / 183.876), `baseline_graph_1hop` (20.077 / 60.184), `repaired_graph_1hop_ablation` (2.317 / 5.312), `repaired_graph_2hop_full` (2.188 / 4.933).

---

## ⛔ STOP CHECKPOINT

S5-B1 and S5-B1.1 are complete. Do not perform human annotation, assert retrieval superiority, or proceed to S5-C.
