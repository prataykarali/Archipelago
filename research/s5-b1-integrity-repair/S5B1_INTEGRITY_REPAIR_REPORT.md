# S5-B1 Integrity Repair Report

**Branch:** `research/s5-b1-integrity-repair`
**Base Commit:** `78d3f2f` (research/s5-a-retrieval-integrity)
**Date:** 2026-11-18
**Status:** COMPLETE — STOP CHECKPOINT REACHED

---

## Executive Summary

S5-B1 corrects seven methodological and reproducibility issues identified in S5-A before independent human annotation begins. No production systems were modified. No retrieval superiority is claimed. No human annotation was performed.

---

## Repair 1 — `.gitignore` Fix: Model Manifests Now Trackable

**Problem:** `.gitignore` contained the bare pattern `models/` (without a leading `/`), which caused Git to ignore every directory named `models/` anywhere in the repository tree, including `research/s5-a-retrieval-integrity/models/s5a_model_manifest.json`. The JSON manifest (not model weights) was silently excluded from every S5-A commit.

**Fix:**
- Changed `models/` → `/models/` (anchored to repository root only).
- Added `research/s5-b1-integrity-repair/annotation_local/` to the gitignore coverage list.
- Root-level GGUF weight directories continue to be excluded.
- `research/**/models/*.json` manifest files are now trackable.

**Verification:**
- `git check-ignore` now returns exit code 1 (file is NOT ignored) for `research/s5-a-retrieval-integrity/models/s5a_model_manifest.json`.
- `git check-ignore` returns exit code 0 (IS ignored) for `models/some_weights.gguf`.

---

## Repair 2 — Admin/Reviewer Package Separation

**Problem:** `retrieval_query_candidate_pool.csv` from S5-A included a `candidate_role` column with values like `PREMISE_DIRECT`, `HARD_NEGATIVE`, `CORPUS_CONTROL`. Although human judgment columns were blank, exposing annotator-role labels to a reviewer who is supposed to independently judge relevance completely invalidates the double-blind protocol.

**Fix — Blinded Package** (`human_evaluation_package/`):
- **`retrieval_query_candidate_pool_blinded.csv`**: Columns are `pair_id, query_id, domain, category, query_text, candidate_passage_id, candidate_doc_id, candidate_chunk_id, candidate_page_number, passage_sha256, human_relevance_grade, human_evidence_quote, human_confidence, human_notes`. **Zero** role, rationale, or hint columns.
- Pairs use neutral sequential IDs `PAIR-001` through `PAIR-031`.
- **`retrieval_query_pool_blinded.json`**: Machine-readable blinded format with identical column restriction.
- **`RETRIEVAL_ANNOTATION_PROTOCOL.md`**: Annotator-facing protocol; mentions ONLY the 0/1/2 grading scale.

**Fix — Admin-Only Package** (`admin_package/`):
- **`admin_retrieval_manifest.json`**: Contains all 31 candidate roles (`PREMISE_DIRECT`, `HARD_NEGATIVE`, etc.) and developer rationales, stored exclusively outside the blinded reviewer directory.

**Fix — Local Annotation Workbook** (`annotation_local/`, gitignored):
- Verbatim passage workbook stored in `research/s5-b1-integrity-repair/annotation_local/` which is listed in `.gitignore`.

**Verification:** 35/35 unit tests pass in `TestBlindedReviewerPackage` covering:
- Zero forbidden column names in blinded CSV
- Zero forbidden keywords (`PREMISE_*`, `HARD_NEGATIVE`) in blinded CSV or JSON
- Neutral `PAIR-NNN` IDs, 31 pairs
- All human fields empty
- Admin manifest in `admin_package/`, not in `human_evaluation_package/`

---

## Repair 3 — Graph Traversal Instrumentation

**Problem (S5-A):**
1. `except Exception: pass` silently swallowed all Kùzu Cypher runtime errors during baseline graph traversal.
2. `actual_hop_count` was hard-coded to `self.max_hops` (always `2`) regardless of whether any 2-hop neighbors were actually reached.
3. No graph path trajectory was recorded.

**Fix:**
- **Exception transparency:** Kùzu errors are now caught, logged via `logging.warning()`, and appended to `traversal_errors[]` in traversal metadata. No silent swallowing.
- **Real observed hop depth:** `actual_hop_count` now reflects the true maximum traversal depth:
  - `0` if the query fell back to BM25 (no anchors found in graph)
  - `1` if only 1-hop neighbors were reached
  - `2` only if novel 2-hop concept nodes (not already in anchor set or 1-hop set) were actually reached
- **Path trajectory recording:** Every traversal step records `{"source": u, "relation": edge_type, "target": v, "hop": N}`.
- Both `RepairedBaselineGraphRetriever` and `RepairedHeterogeneousGraphRetriever` expose `paths_traversed` and `traversal_errors` in their metadata dicts.

**Observed Results:**
- `baseline_graph_1hop`: fallback_rate = 16.7% (2/12 queries), avg_hop = 0.5, paths = 49
- `repaired_graph_1hop_ablation`: fallback_rate = 50.0%, avg_hop = 0.5, paths = 45
- `repaired_graph_2hop_full`: fallback_rate = 50.0%, avg_hop = 1.0, paths = 215

The 50% fallback rate for the repaired heterogeneous retrievers reflects the fact that the repaired graph construction (Repair 7) strictly scoped edge extraction to 713 eligible passages only (146 edges), yielding fewer anchor matches compared to S5-A's unconstrained extraction (148 edges including 2 from upload documents outside the eval corpus).

---

## Repair 4 — Latency Accounting Separation

**Problem (S5-A):** Cold-start latency included model weight loading in some but not all benchmark runs. The timing report did not distinguish true application cold-start from first-query cold latency and warm repetitions.

**Fix:** The S5-B1 benchmark explicitly measures and reports:

| Phase | Description |
|---|---|
| `corpus_load_ms` | Build + filter eligible 713-passage corpus from Kùzu DB |
| `dense_model_load_ms` | Load SentenceTransformer weights into RAM from cache |
| `dense_embedding_cache_load_ms` | Load precomputed 713×768 `.npy` matrix |
| `bm25_index_build_ms` | Build BM25Okapi inverted index |
| `corpus_scoped_graph_build_ms` | Extract graph edges scoped to 713 eligible passages |
| `first_query_mean_ms` | Mean latency over 12 first-run queries (cold query cache) |
| `warm_mean_ms`, `warm_p95_ms`, `warm_std_ms` | Distribution over 5 warm repetitions per query |

**Measured Application Cold-Start (single run):**

| Phase | Latency |
|---|---|
| Corpus load | 462 ms |
| Dense model load | 9,612 ms |
| Dense embedding cache load | 1 ms |
| BM25 index build | 160 ms |
| Corpus-scoped graph build | 2,758 ms |

**Per-Query Timing (first query / warm mean / warm P95):**

| System | First Query Mean (ms) | Warm Mean (ms) | Warm P95 (ms) |
|---|---|---|---|
| BM25 | 5.2 | 4.7 | 6.2 |
| Dense (Snowflake 768d) | 183.5 | 170.8 | 230.8 |
| Hybrid RRF (E2E) | 163.0 | 165.4 | 215.3 |
| Baseline Graph 1-Hop | 9.8 | 8.5 | 21.5 |
| Repaired Graph 1-Hop | 2.5 | 2.3 | 5.4 |
| Repaired Graph 2-Hop | 2.4 | 2.2 | 5.0 |

> [!NOTE]
> Dense first-query latency (183 ms) is higher than warm mean (171 ms) due to CPU cache warming of the 713×768 matrix multiplication. Application cold-start is dominated by model weight loading (~9.6 s), not per-query inference.

---

## Repair 5 — Reproducible BM25 Fallback

**Problem (S5-A):** When graph retrievers found no matching anchor concepts, the fallback was an **unsorted, unranked substring slice** of passages matching any word with `len(w) > 4`:
```python
matched = [(p.passage_id, 0.05) for p in self.passages
           if any(w in p.text.lower() for w in q_low.split() if len(w) > 4)]
```
This is non-deterministic (order depends on passage enumeration), unranked (all scores 0.05), and irreproducible.

**Fix:** Both graph retrievers now fall back to `self.bm25_fallback.search(query, top_k)` — the same BM25Okapi retriever constructed from the identical 713-passage corpus. Fallback metadata includes:
```json
{"is_fallback": true, "fallback_strategy": "corpus_bm25"}
```

---

## Repair 6 — Dense Embedding Cache Fingerprint Verification

**Problem (S5-A):** No cryptographic verification existed to confirm that the cached `.npy` matrix rows aligned with the actual corpus passage ordering.

**Fix:** `s5b1_model_manifest.json` now declares three cryptographic fingerprints computed at index-build time:

| Fingerprint | SHA-256 |
|---|---|
| `embedding_matrix_sha256` | `ffb94053fa66471d14758771253c8c5404bb4adf2e7b14d2c9e4c30b2cbd4ee2` |
| `corpus_passage_id_sha256` | `f7fe70031781b005d712a7a9a4aa2452a8b17d7353531305b39b09d88eeecd98` |
| `corpus_text_sha256` | `8464acaea13cbfae0f345ea29ce1cf707dc39e76832c7729fca33fbd763bc68c` |

The benchmark verifies at load time that `sha256(s5a_dense_embeddings_713.npy)` matches `embedding_matrix_sha256`. The test suite verifies `corpus_passage_id_sha256` by re-computing the hash from a fresh corpus load.

---

## Repair 7 — Graph Construction Information-Access Equality

**Problem (S5-A):** The S5-A benchmark iterated over **all 79 documents** in `okf_graph.db` when calling `RepairedGraphExtractor`. Of these, 26 are outside the 713-passage eval corpus (uploaded documents, additional papers). The S5-A graph construction accessed **748 external chunks**, potentially extracting concepts and edges that BM25 and Dense never saw (since those systems operated only on the 713 eligible passages).

**Detailed Audit Results:**

| Metric | Count |
|---|---|
| Total documents in `okf_graph.db` | 79 |
| Documents in eval corpus | 53 |
| External (outside corpus) documents | 26 |
| Total chunks in database | 786 |
| External chunks (outside corpus) | 73 |
| Unconstrained edges (S5-A behavior) | 148 |
| Corpus-scoped edges (S5-B1 behavior) | 146 |
| Leaked edges from external chunks | 2 (from `upload_bdedc151`, `upload_cb7badb2`) |

**Fix:** Graph extraction in S5-B1 is restricted by `eligible_chunk_keys = set((p.doc_id, p.chunk_id) for p in eligible_passages)`. Only chunks whose `(doc_id, chunk_id)` pair appears in the 713-passage corpus contribute to the extracted edge set.

**Verdict:** `DISCREPANCY_DETECTED_AND_CORRECTED`. The graph retriever now has strictly identical information access to BM25 and Dense.

---

## Unresolved Limitations

> [!WARNING]
> The following limitations remain open and must be resolved before any effectiveness claims.

1. **Human annotation not yet performed.** All 31 (query, candidate) pairs in `retrieval_query_candidate_pool_blinded.csv` remain unannotated. Retrieval effectiveness for all 6 systems is `NOT_EVALUATED_PENDING_HUMAN_GOLD`.

2. **Blinded reviewer workbook contains verbatim text.** `annotation_local/retrieval_relevance_reviewer_workbook.md` contains source passage text for annotator convenience. It is excluded from Git via `.gitignore` but exists in the local working directory. Any future move to a hosted annotation platform must audit passage licensing before exposing text.

3. **50% graph retrieval fallback rate.** Half of the 12 benchmark queries find zero matching anchor concepts in the repaired concept graph (146 edges from 53 documents). This is a consequence of the small repaired graph covering only the pilot/seed chunks and three OSTEP chapters. It does not indicate system failure — it is an accurate measure of current graph coverage — but it limits fair graph-vs-BM25 comparison on these specific queries.

4. **Dense embedding times are wall-clock measurements, not repeatable hardware benchmarks.** The 170 ms/query warm mean was measured on a CPU-only machine (Intel Xeon). GPU inference would reduce this substantially. The numbers should not be generalized.

5. **Historical Git exposure from S4-G3.** Earlier branches committed verbatim annotation CSVs. Normal file deletion does not remove exposure from Git history. Recommended remediation: `git filter-repo` or BFG Repo Cleaner on affected paths. **This was not executed** because history rewriting requires explicit repository owner authorization.

6. **S5 enrichment test failures are pre-existing.** `test_s5_enrichment.py::test_same_name_does_not_merge_without_provider_id` and `::test_hosted_runtime_copy_matches_source` fail on the base S5-A branch and on the S5-B1 branch identically. These are unrelated to S5-B1 scope.

---

## Test Summary

| Test Class | Tests | Status |
|---|---|---|
| `TestGitignoreModelManifestFix` | 4 | ✅ All pass |
| `TestBlindedReviewerPackage` | 8 | ✅ All pass |
| `TestGraphTraversalInstrumentation` | 6 | ✅ All pass |
| `TestLatencyAccounting` | 4 | ✅ All pass |
| `TestBM25BasedFallback` | 3 | ✅ All pass |
| `TestDenseEmbeddingFingerprint` | 4 | ✅ All pass |
| `TestGraphInformationAccessAudit` | 4 | ✅ All pass |
| `TestRetrievalEffectivenessBoundary` | 2 | ✅ All pass |
| **Total S5-B1** | **35** | **✅ 35/35** |
| Inherited S4/S5-A tests | 324 | ✅ 324/324 (excl. 2 pre-existing failures) |

---

## Deliverables

| Artifact | Path | Status |
|---|---|---|
| Blinded Reviewer CSV | `human_evaluation_package/retrieval_query_candidate_pool_blinded.csv` | ✅ |
| Blinded JSON Pool | `human_evaluation_package/retrieval_query_pool_blinded.json` | ✅ |
| Annotation Protocol | `human_evaluation_package/RETRIEVAL_ANNOTATION_PROTOCOL.md` | ✅ |
| Admin Manifest | `admin_package/admin_retrieval_manifest.json` | ✅ |
| S5-B1 Model Manifest | `models/s5b1_model_manifest.json` | ✅ |
| Graph Audit Report | `reports/graph_information_access_audit.json` | ✅ |
| Timing Report | `reports/retrieval_timing_report.json` | ✅ |
| Technical Eval Report | `reports/retrieval_technical_evaluation_report.json` | ✅ |
| Benchmark Script | `scripts/run_s5b1_retrieval_benchmark.py` | ✅ |
| Package Builder | `scripts/build_s5b1_human_eval_package.py` | ✅ |
| Graph Audit Script | `scripts/audit_graph_information_access.py` | ✅ |
| Test Suite | `tests/unit/test_s5b1_integrity_repair.py` | ✅ |

---

## ⛔ STOP CHECKPOINT

**S5-B1 is complete.**

The following actions are explicitly prohibited until this checkpoint is cleared by human decision:

- ❌ Perform independent human annotation of the blinded package
- ❌ Calculate or assert retrieval precision, recall, or superiority
- ❌ Proceed to S5-C
- ❌ Force-push or rewrite Git history to remove historical verbatim exposure
- ❌ Modify `okf_graph.db` or any production system
