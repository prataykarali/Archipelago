# S5-v3.1 Pre-Pooling Scope, System Set & Hypothesis Decision Record

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-1-eval-compatibility`  
**Status:** BOUNDED PRE-POOLING DECISION — LOCKED BEFORE HUMAN ANNOTATION  
**Authoritative Inputs:** [s5v31_retrieval_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_retrieval_manifest.json), [s5v31_corpus_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_corpus_manifest.json), [S5V31_ANNOTATION_COST.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/S5V31_ANNOTATION_COST.md).

> [!IMPORTANT]
> **Freeze-Before-Pooling Rule:** No blinded annotation pool may be generated until the human query-audit workbook (`data/annotation_local/s5v3_1/query_audit/`) is completed, the approved query manifest is frozen, and the exact 8-system retrieval set below is SHA-256 locked. Adding any system *after* pooling violates complete-pool fairness (`zobel1998reliable`, `buckley2004retrieval`).

---

## 1. Bounded System-Set Decision: Retain Exactly the 8 Existing S5-v3.1 Systems

We adopt a **bounded, reproducible 8-system evaluation matrix** operating over the identical `1,958`-passage Corpus v3.1 (`SHA-256: 6366477189b8058b3f523a9d6607abb4d2c249351927918d24979e17833937b9`, `okf_graph_db_dependency: false`):

| # | System ID | Family | Config SHA-256 (prefix) | Representation / External Access Disclosure |
|---:|---|---|---|---|
| 1 | `v31_lexical_bm25` | Lexical control | `d41d1e49be68...` | Corpus-only BM25Okapi (`k1=1.5, b=0.75`); zero external weights/graph |
| 2 | `v31_dense_snowflake` | Dense control | `8bc0acf612a9...` | Pretrained `Snowflake/snowflake-arctic-embed-m-v1.5` (`e58a8f75...`, Apache-2.0, CPU `float32`, cache `c02f817f...`) |
| 3 | `v31_hybrid_rrf_bm25_dense` | Hybrid control | `37c14173308a...` | Parameter-free RRF (`k=60`) over `v31_lexical_bm25` + `v31_dense_snowflake` |
| 4 | `v31_graph_naive_substring` | Graph ablation | `affb711dd8ae...` | Corpus-grounded `okf_graph.json` (`610` concepts / `1,988` edges), raw substring anchors, no fallback/backfill |
| 5 | `v31_graph_1hop_no_backfill` | Graph v3.1 | `5dc0817e4bab...` | Token-boundary + alias anchors, 1-hop traversal, deterministic BM25 fallback, no partial backfill |
| 6 | `v31_graph_1hop_backfill` | Graph v3.1 | `f8e5f68edf50...` | Same as #5 + deterministic lexical partial-list backfill (`top_k` completion) |
| 7 | `v31_graph_2hop_backfill` | Graph v3.1 | `6c0b5489db33...` | Same as #6 + controlled 2-hop traversal (decay + fanout cap + cycle guard) |
| 8 | `v31_graph_2hop_coverage_routed` | Graph v3.1 | `407b1b774681...` | Coverage-aware routing (`lexical_only` / `balanced_hybrid` / `graph_heavy`) over #7 + #1 |

---

## 2. Explicit Decision: Do NOT Add a Cross-Encoder Reranker to S5-v3.1

**Decision:** **`REJECTED FOR S5-v3.1`** (keep optional rerankers such as `cross-encoder/ms-marco-MiniLM-L6-v2` and `BAAI/bge-reranker-base` out of the S5-v3.1 pool).

**Rationale:**
1. **Bounded scope & pool-cost discipline:** Adding a 9th neural reranking system before pooling would require downloading new uncached model weights, re-running verification, and expanding the human annotation pool beyond the already-measured `675` (`test` `k=5`) / `1,238` (`test` `k=10`) pairs (`47.18–80.03` person-hours).
2. **Clean paradigm comparability with v2.1:** The frozen v2.1 pilot compared lexical, zero-shot dense (`snowflake-arctic-embed-m-v1.5`), hybrid RRF, and symbolic graph retrieval. Retaining those exact four paradigms preserves longitudinal continuity without confounding retrieval architecture changes with two-stage cross-encoder reranking.
3. **Permanent disclosure:** Any manuscript reporting S5-v3.1 results MUST explicitly disclose that no two-stage cross-encoder reranker (`Nogueira & Cho, 2019`) was included, and must NEVER claim superiority over neural reranking pipelines.

---

## 3. Evaluation of Unscoped-vs-Scoped Graph Comparison & Narrowed Primary Hypothesis

**Question:** Should S5-v3.1 add a synthetic "unscoped graph" diagnostic system to test external-edge leakage directly on Corpus v3.1?

**Decision:** **`NO — DO NOT INTRODUCE AN UNEQUAL-ACCESS DIAGNOSTIC SYSTEM. NARROW THE PRIMARY HYPOTHESIS CLEANLY.`**

**Rationale:**
1. **No genuine external corpus exists in S5-v3.1:** Unlike v2.1 (where `okf_graph.db` held 79 documents / 786 chunks and `okf_graph.json` legitimately linked to `462/1,988` external/unscoped edges), S5-v3.1 has `0` dependence on `okf_graph.db` and grounds `okf_graph.json` directly against the `1,958` eligible Corpus v3.1 passages (`183/610` concepts, `341/1,988` edges). Fabricating an artificial "unscoped" edge set would test synthetic noise rather than real leakage and would violate strict corpus-scope parity.
2. **Historical v2.1 already documents the unscoped leakage mechanism:** The v2.1 audit (`graph_information_access_audit.json`, `462/1,988 = 23.24%` excluded edges) already provides verified structural evidence of external-edge leakage and should be cited as a **motivating methodological diagnostic**, not recreated artificially in v3.1.
3. **Narrowed, Directly Testable Primary Hypothesis for S5-v3.1:**
   > *Within a cryptographically corpus-scoped, provenance-verified multi-domain technical benchmark (`1,958` passages across `8` OA CS domains), explicit evaluation controls—specifically complete depth-$k$ pooling (`k=5` vs. `k=10`), fallback-vs.-non-fallback stratification, short-list/backfill accounting, passage-necessity & negative-control verification, and fail-closed dual-human adjudication—materially alter empirical conclusions about lexical, zero-shot dense, hybrid RRF, and corpus-grounded graph retrieval compared with unstratified aggregate reporting or incomplete/unadjudicated pools.*

Every factor in this narrowed hypothesis is **100% testable** by the 8 frozen S5-v3.1 systems once human query verification and dual human relevance annotation complete.

---

## 4. Freeze-Before-Pooling Contract

Before generating any blinded S5-v3.1 annotation pool (`s5v31_adjudicate_and_nc.py`), ALL five hashes below MUST be locked inside `s5v31_benchmark_config.json`:

1. **Corpus Lock:** `corpus_sha256` (`6366477189b8058b3f523a9d6607abb4d2c249351927918d24979e17833937b9`) and `passage_count = 1958`.
2. **Approved Query Lock:** `query_manifest_sha256` of the **post-human-audit** approved query manifest (explicitly recording `approved_query_ids`, `approved_negative_control_ids`, and `split` = `test` or `dev`).
3. **Retrieval & Model Lock:** `retrieval_manifest_sha256` + all `8` `system_hashes` + pinned Snowflake revision (`e58a8f756156a1293d763f17e3aae643474e9b8a`) and dense cache SHA-256 (`c02f817f...`).
4. **Blinded Pool Lock:** `pool_sha256`, `pool_depth_k` (`5` or `10`), and exact `expected_pair_count` generated once from the locked approved queries + locked 8-system rankings.
5. **No-Retroactive-System Policy:** Any 9th system added after pooling MUST NOT be scored against the frozen S5-v3.1 qrels (`zobel1998reliable`); doing so triggers a hard preflight failure in `s5v31_d1_evaluate.py`.
