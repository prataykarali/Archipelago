# S5-B1.1 Final Annotation Readiness Gate Report

**Branch:** `research/s5-b1-integrity-repair` (and `research/s5-b1-1-annotation-readiness`)  
**Parent Commit:** `788976dcea0cc0429d232e3b3ce1ef930e285c0b`  
**Date:** 2026-11-18  
**Status:** COMPLETE — STOP CHECKPOINT REACHED

---

## 1. Executive Summary of S5-B1.1 Repairs

Following the review of commit `788976d`, seven remaining annotation-readiness and methodological issues were resolved without modifying production systems, expanding research scope, or fabricating human judgments:

| # | S5-B1.1 Requirement | Resolution Applied | Verification |
|---|---|---|---|
| **1** | Remove `category` and all answerability hints (`UNANSWERABLE`, etc.) from reviewer CSV, JSON, and local workbooks | Removed `category` column from `retrieval_query_candidate_pool_blinded.csv`, removed `category` and `category_distribution` from `retrieval_query_pool_blinded.json` and `retrieval_technical_evaluation_report.json`, and removed `({category})` from Reviewer A & B workbook headings and `RETRIEVAL_ANNOTATION_PROTOCOL.md`. | `grep` and unit test `test_all_reviewer_facing_files_contain_zero_leaked_keywords` confirm **0** occurrences of `UNANSWERABLE`, `SINGLE_HOP_CONTROL`, `TWO_HOP`, `CROSS_DOCUMENT`, or `category`. |
| **2** | Randomize candidate ordering using a recorded deterministic seed (`20261118`) | Candidate passage IDs in `corpus/s5b1_blinded_query_specs.json` are stored in neutral lexicographical order and shuffled per query via `random.Random(20261118)` before assigning `PAIR-001`..`PAIR-031`. | Across the 12 queries, `HARD_NEGATIVE` appears 1st in 6 queries, 2nd in 4 queries, and 3rd in 3 queries, breaking the positive-then-negative pattern. |
| **3** | Move admin manifest to Git-ignored storage; document historical exposure without rewriting history | Removed `admin_package/admin_retrieval_manifest.json` from Git tracking (`git rm -rf`), removed hardcoded roles/rationales from `build_s5b1_human_eval_package.py`, moved `admin_retrieval_manifest.json` and `admin_query_specs_local.json` to Git-ignored `annotation_local/` and `data/annotation_local/s5b1_admin/`, and added `**/*admin_retrieval_manifest*.json` and `research/**/admin_package/` to `.gitignore`. | `git ls-files "*admin_retrieval_manifest*"` returns empty; `git check-ignore -v` confirms `.gitignore` coverage. Historical exposure in `788976d` and `78d3f2f` is documented below. |
| **4** | Enforce runtime verification of embedding cache, passage-ID ordering, and corpus-text fingerprints | Added `verify_dense_cache_and_corpus_fingerprints()` in `run_s5b1_retrieval_benchmark.py`, executed at benchmark startup. Checks `corpus_passage_id_sha256`, `corpus_text_sha256`, `corpus_sha256`, `embedding_matrix_sha256`, and `(713, 768)` shape against `s5b1_model_manifest.json`; raises `ValueError` on any mismatch. | 4 unit tests in `TestRuntimeDenseEmbeddingFingerprintVerification` test authentic startup plus adversarial perturbations to passage order, passage text, and cache bytes. |
| **5** | Audit baseline Kùzu graph (`RepairedBaselineGraphRetriever`) for external information access and correct it | Audited all 610 `Concept` nodes and 1,988 edges (`REQUIRES`, `RELATED`, `UNLOCKS`) in `okf_graph.db`. Found 462 edges (23.24%) outside or unscoped to the 713-passage corpus (145 from excluded index/external chunks, 30 `pearson_batch1`, 29 `librarian_upload`, 98 `NULL` source, plus edges touching 56 external-only or 103 orphan concepts). Restricted `RepairedBaselineGraphRetriever` via `_is_corpus_verified_kuzu_edge()` to the **1,526** verified corpus edges and **451** eligible concepts. | `graph_information_access_audit.json` records the full breakdown; `test_baseline_kuzu_edge_filter_rejects_external_and_unscoped_sources` verifies edge filtering. |
| **6** | Produce separate Reviewer A and Reviewer B workbooks with verified passage text, neutral IDs, and empty judgment fields | `build_s5b1_human_eval_package.py` generates `reviewer_a_retrieval_workbook.md` (`REV_A`) and `reviewer_b_retrieval_workbook.md` (`REV_B`) in Git-ignored `annotation_local/`, containing verified passage text from `okf_graph.db`, neutral `PAIR-001`..`PAIR-031` IDs, and empty judgment fields. | `test_separate_reviewer_a_and_b_workbooks_contain_verified_text` verifies all 31 pairs in both workbooks. |
| **7** | Provide a fresh-environment reproducibility report (passed, failed, skipped tests) | Executed isolated fresh-clone verification in temporary directories across 4 modes and saved `reports/fresh_environment_reproducibility_report.json`. | Blinded CSV, JSON, protocol, and Reviewer A & B workbooks regenerate 100% byte-identically in a fresh clone. |

---

## 2. Historical Git Exposure Disclosure (Admin Manifest & S5-A Roles)

In compliance with repository governance rules, Git history was **not** rewritten (`git filter-repo` and `git push --force` were not executed). Standard `git rm` removes files from the current HEAD tree and future commits, but historical commits remain accessible in Git object history until owner-authorized history scrubbing is performed:

1. **Commit `788976dcea0cc0429d232e3b3ce1ef930e285c0b` (`research/s5-b1-integrity-repair`):**
   - Tracked `research/s5-b1-integrity-repair/admin_package/admin_retrieval_manifest.json` and `research/s5-b1-integrity-repair/scripts/build_s5b1_human_eval_package.py` containing expected `candidate_role`, `admin_rationale`, and query `category` labels (`UNANSWERABLE`, etc.), as well as `category` columns in `retrieval_query_candidate_pool_blinded.csv` and `retrieval_query_pool_blinded.json`.
   - **Current Tree Remediation (S5-B1.1):** Untracked `admin_package/admin_retrieval_manifest.json` via `git rm -rf`, stripped all roles, rationales, and categories from tracked scripts and reviewer files, moved admin artifacts to Git-ignored `annotation_local/` and `data/annotation_local/s5b1_admin/`, and added ignore rules to `.gitignore`.
2. **Commit `78d3f2f53443b7147ca2e92cffb85816bb6e4215` (`research/s5-a-retrieval-integrity`):**
   - Tracked `research/s5-a-retrieval-integrity/human_evaluation_package/retrieval_query_candidate_pool.csv`, `retrieval_query_manifest.json`, and `scripts/build_retrieval_human_eval_package.py` containing pre-randomization `candidate_role` and `admin_rationale` fields.
3. **Operational Mitigation for Human Pilot:**
   - Independent human annotators (Reviewer A and Reviewer B) must be provided **only** their isolated workbook files (`reviewer_a_retrieval_workbook.md` / `reviewer_b_retrieval_workbook.md`) and `retrieval_query_candidate_pool_blinded.csv` outside of Git repository access, ensuring reviewers do not inspect historical commits (`788976d`, `78d3f2f`).

---

## 3. Baseline Kùzu Graph vs. Repaired Heterogeneous Graph Information-Access Audit

Both graph retrieval baselines were audited against the frozen 713-passage evaluation corpus (`s5a_eval_corpus_v1`, 53 eligible documents out of 79 total documents and 786 total chunks in `okf_graph.db`):

| Graph System | Unconstrained DB Scope | Eligible 713-Passage Scope | Excluded / External Elements | S5-B1.1 Enforcement |
|---|---:|---:|---:|---|
| **Repaired Heterogeneous Graph** (`1-hop` & `2-hop`) | 148 edges (786 chunks across 79 docs) | **146 edges** (713 eligible passages across 53 docs) | **2 edges** from external uploads (`upload_bdedc151`, `upload_cb7badb2`) | Chunks filtered by `(canon_doc_id, chunk_id) in eligible_chunk_keys` prior to extraction. |
| **Baseline Kùzu Graph** (`baseline_graph_1hop`) | 610 `Concept` nodes; 1,988 edges (`267 REQUIRES`, `1,334 RELATED`, `387 UNLOCKS`) | **451 `Concept` nodes**; **1,526 verified edges** (`179 REQUIRES`, `1,019 RELATED`, `328 UNLOCKS`) | **159 `Concept` nodes** (56 external-only + 103 orphan); **462 edges** (23.24%: 305 external/index-chunk edges, 30 `pearson_batch1`, 29 `librarian_upload`, 98 `NULL` source) | `_is_corpus_verified_kuzu_edge()` verifies `r.source` resolves to `{doc_id}::{chunk_id}` in the 713-passage corpus and both concepts occur in eligible passages. |

---

## 4. Reconciled Benchmark Latency & Traversal Summary

All figures below match `reports/retrieval_timing_report.json` and `reports/retrieval_technical_evaluation_report.json` exactly:

### 4.1 Application Cold-Start Latency
- `corpus_load_ms`: **400.246 ms**
- `dense_embedding_cache_load_ms` (including runtime SHA-256 verification): **21.353 ms**
- `dense_model_load_ms` (`Snowflake/snowflake-arctic-embed-m-v1.5` CPU load): **7,630.455 ms**
- `bm25_index_build_ms`: **407.279 ms**
- `corpus_scoped_graph_build_ms`: **2,458.478 ms**

### 4.2 Per-Query Latency & Graph Traversal Instrumentation (12 Queries, 5 Warm Repetitions)

| System | First-Query Mean (ms) | First-Query Max (ms) | Warm Mean (ms) | Warm Median (ms) | Warm Std (ms) | Warm P95 (ms) | Fallback Rate | Observed Avg Hop Depth | Total Paths Traversed | Effectiveness |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `bm25` | 4.798 | 6.383 | 4.344 | 4.353 | 0.888 | 5.979 | 0.000 (0/12) | N/A | 0 | `NOT_EVALUATED` |
| `dense_snowflake_arctic_768d` | 164.950 | 361.618 | 148.281 | 142.261 | 17.325 | 178.982 | 0.000 (0/12) | N/A | 0 | `NOT_EVALUATED` |
| `hybrid_rrf_e2e` | 156.402 | 196.444 | 153.233 | 149.064 | 15.487 | 183.876 | 0.000 (0/12) | N/A | 0 | `NOT_EVALUATED` |
| `baseline_graph_1hop` | 21.953 | 61.523 | 20.077 | 8.261 | 20.864 | 60.184 | 0.167 (2/12) | 0.50 | 46 | `NOT_EVALUATED` |
| `repaired_graph_1hop_ablation` | 2.561 | 5.564 | 2.317 | 1.530 | 2.127 | 5.312 | 0.500 (6/12) | 0.50 | 45 | `NOT_EVALUATED` |
| `repaired_graph_2hop_full` | 2.452 | 5.240 | 2.188 | 1.673 | 1.937 | 4.933 | 0.500 (6/12) | 1.00 | 215 | `NOT_EVALUATED` |

---

## 5. Fresh-Environment Reproducibility Report

Full details are stored in `reports/fresh_environment_reproducibility_report.json`:

| Execution Mode | Environment Setup | Command Executed | Passed | Failed | Skipped | Artifact Byte-Identity |
|---|---|---|---:|---:|---:|---|
| **Mode 1: Pure Tracked Git Clone** | Isolated `/tmp` directory with ONLY `git ls-files` tracked files (no `okf_graph.db`, no dense cache, no local admin manifest) | `pytest tests/unit/test_s5b1_integrity_repair.py -v` | **14** | **0** | **7** (DB/cache/admin tests skip cleanly) | N/A |
| **Mode 2: Public Researcher Fresh Clone + Read-Only DB/Cache** | Isolated `/tmp` clone + read-only `okf_graph.db` and `s5a_dense_embeddings_713.npy` (no local admin secrets) | `build_s5b1_human_eval_package.py` + `pytest test_s5b1_integrity_repair.py test_s5a_retrieval_integrity.py` | **34** | **0** | **1** (admin-manifest-only test skips cleanly) | **5/5 regenerated files byte-identical** (CSV, JSON, protocol, Reviewer A & B workbooks) |
| **Mode 3: Local Research Suite (S4 + S5-A + S5-B1.1)** | Full workspace with `okf_graph.db`, dense cache, and local gitignored admin manifest | `pytest tests/unit/test_s4* tests/unit/test_s5a* tests/unit/test_s5b1*` | **310** (`21/21` in S5-B1.1) | **0** | **0** | Verified |
| **Mode 4: Whole-Repository Unit Suite** | Full `tests/unit/` across all legacy product/UI/hosted/research modules | `pytest tests/unit/` | **2,084** | **41** (all pre-existing on base branch `78d3f2f` in product/UI/hosted-sync tests) | **8** | Verified |

---

## 6. STOP Checkpoint

**S5-B1.1 is complete.** All 7 final annotation readiness gates are verified. Stopping prior to independent human annotation and S5-C evaluation.
