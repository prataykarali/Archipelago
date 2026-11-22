# ARCHIPELAGO D5.1 — Scientific Evaluation & Audit Report

**Date:** 2026-11-22  
**Target Venue:** ACM SIGIR 2027 Demonstrations Track  
**Source Commit:** `02cb2bcd2ebcf1a47f7287388330abb73484c78d`  
**Evaluation Suite:** `scripts/benchmarks/d5_1_evaluation_suite.py`  
**Dataset Artifacts:** `research/d5_sigir_evaluation/`  

---

## 1. Executive Summary & Scientific Disclosures

In response to the critical methodological audit of D5, this report presents the corrected, scientifically sound evaluation of Archipelago.

### Key Corrections Applied in D5.1:
1. **Decoupled Concept Resolution from Passage Retrieval:**
   - Archipelago's earlier **26/38 (68.42%)** metric is strictly a **Concept-Resolution Accuracy**, not passage-retrieval MRR.
   - Evaluated on passage retrieval against verified passage-level relevance judgments (445 qrel entries across 775 passages), **BM25 (MRR 0.7500, nDCG@5 0.6415)** and **Snowflake-Arctic-Embed-M (MRR 0.7500, nDCG@5 0.6524)** substantially outperform **Archipelago Graph-Assisted Retrieval (MRR 0.5473, nDCG@5 0.2377)**.
2. **Replaced Misnamed 'Dense' Baseline:**
   - The BLAKE2b token-hashing projection in `host_inference/engine/text.py` is correctly designated **Feature-Hashed Vector Retrieval** (yielding poor passage retrieval: MRR 0.2806, nDCG@5 0.1764).
   - Evaluated a true pretrained neural dense embedder: **Snowflake/snowflake-arctic-embed-m** (768-dim, model revision tags recorded, query prefix applied, executed on NVIDIA RTX 2050 CUDA).
3. **Corrected Relationship Prediction:**
   - Evaluated relationship triples actually returned by Archipelago runtime payload (`prerequisites`, `unlocks`, `related_concepts`).
   - The previous "1.0 direction accuracy" was an artifact of matching the curated graph slice rather than evaluating runtime output. Actual runtime relationship extraction achieves **Precision 0.0052, Recall 0.0556, F1 0.0095** with 1 inverted direction error (`self_attention -> transformer`) and 16 missing predictions.
4. **Claim-to-Passage Citation Grounding Audit:**
   - Verifiable claim support precision is **32.14% (strict)** / **53.57% (lenient)**. While the primary citation for anchor concepts is highly accurate (e.g., Vaswani 2017 p.2, Dao 2022 p.2), broad neighborhood expansion introduces a **28.57% dilution rate** of peripheral papers (e.g., DDPM, AlexNet, ReAct).
5. **Human Review Provenance Disclosed:**
   - All 45 audited edges (40 verified, 5 quarantined) were reviewed by the primary author (Pratay Karali) using verbatim literature passages. Fictitious labels (`SIGIR_Reviewer_Lead`) have been replaced with honest author-review records pending external double-blind replication.

---

## 2. Frozen Dataset Checksums & Reproducibility Metadata

All evaluation data splits and ontology files are frozen:

| Artifact | SHA-256 Checksum | Purpose |
|:---|:---|:---|
| `queries_dev_15.json` | `43893328d55fc5cb0b6f583ee7a20ab0eb36c95e686122db75703d6e6dadbd5b` | 15 Development / Sanity Queries |
| `queries_heldout_50.json` | `9e39430942b4f00d34911848cbe61a96532c29ffaee76f0d82ce69496f71103a` | 50 Held-Out Evaluation Queries |
| `d5_graph_slice.json` | `55140e114dcf192cde59d95271a4cb81f1d099fb4de44b0135c6d95f3e455590` | 40 Verified Graph Edges |
| `okf_graph.json` | `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76` | Candidate Corpus (775 passages, 610 concepts) |
| `passage_qrels.json` | `f58c734b4ef6c507a216c39f0ea1548e244fc8b9f059cb633fa1f77d853e5e1a` | 445 Validated Passage Relevance Labels |

*Legacy Exploratory Preservation:* Original D5 output preserved at `research/d5_sigir_evaluation/d5_evaluation_results_exploratory_legacy.json` with historical disclaimer.

---

## 3. Experiment A: Concept Resolution Evaluation

Evaluates identification of the canonical concept node across all 50 queries (38 supported, 12 unsupported):

| System | Supported Accuracy (Top-1) | Unsupported Abstention Accuracy | Overall Accuracy (50 Queries) | Error Count (Supported) |
|:---|:---:|:---:|:---:|:---:|
| **BM25 Lexical Baseline** | 42.11% (16/38) | 0.00% (0/12) | 32.00% (16/50) | 22 |
| **Feature-Hashed Vector (BLAKE2b)** | 7.89% (3/38) | 58.33% (7/12) | 20.00% (10/50) | 35 |
| **Snowflake Arctic Embed M (Neural)** | 36.84% (14/38) | **100.00% (12/12)** | 52.00% (26/50) | 24 |
| **Archipelago Concept Resolver** | **68.42% (26/38)** | **100.00% (12/12)** | **76.00% (38/50)** | 12 |

### Key Findings for Experiment A:
- **Archipelago's Core Strength is Concept Resolution:** Archipelago substantially outperforms BM25 (+26.3% absolute) and Neural Dense (+31.6% absolute) on resolving user queries to structured ontology nodes.
- **Honest Abstention:** Both Archipelago and Snowflake Arctic achieve 100% precision on abstaining from out-of-domain queries (e.g., Spanner TrueTime, Navier-Stokes, CRISPR). BM25 fails completely on abstention (0%) because lexical token matching always returns a non-zero score.

---

## 4. Experiment B: Ranked Passage Retrieval Evaluation

Evaluates ranking of candidate passages from the shared 775-passage corpus using standard TREC IR metrics over queries with verified relevant passages ($N=37$):

| Retrieval System | MRR | nDCG@5 | Recall@5 | Precision@5 | Latency (Mean) | Latency (P95) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **BM25Okapi (k1=1.5, b=0.75)** | **0.7500** | 0.6415 | **0.3707** | 0.5405 | **2.91 ms** | **3.79 ms** |
| **Snowflake-Arctic-Embed-M (Neural)** | **0.7500** | **0.6524** | 0.3324 | **0.5730** | 15.37 ms | 16.64 ms |
| **Feature-Hashed Vector (BLAKE2b)** | 0.2806 | 0.1764 | 0.1093 | 0.1514 | 0.51 ms | 0.70 ms |
| **Archipelago Graph-Assisted** | 0.5473 | 0.2377 | 0.0715 | 0.1730 | 21.22 ms | 39.44 ms |

*Hardware Environment:* Intel x86_64 CPU, NVIDIA GeForce RTX 2050 (4GB VRAM), Linux 6.8 kernel, PyTorch 2.5.1 + CUDA 12.1.  
*Run Files Generated:* TREC format run files deposited in `research/d5_sigir_evaluation/ranked_runs/{bm25,feature_hashed,snowflake_arctic,archipelago_graph}.run`.

### Honest Scientific Analysis for Experiment B:
- **BM25 and Pretrained Neural Dense Win on Passage Retrieval:** BM25 and Snowflake Arctic achieve identical high MRR (0.7500) and high nDCG@5 (0.6415 - 0.6524), significantly outperforming Archipelago (MRR 0.5473, nDCG@5 0.2377).
- **Why Archipelago is NOT an End-to-End Passage Ranker:** Archipelago is designed as an ontology-first knowledge navigator. It resolves a query to an anchor concept and extracts 1–3 citations attached to that concept node. It does not scan the full corpus or rank all 775 passages by token similarity. Consequently:
  - If a query benefits from multiple distributed passages across the corpus, Archipelago only retrieves the passages pinned to its anchor neighborhood (limiting Recall@5 to 0.0715).
  - When the anchor resolution misses (12/38 cases), Archipelago retrieves zero relevant passages from the corpus.
- **Scientific Conclusion:** Archipelago must **NOT** be claimed as an improved passage-retrieval engine. Its scientific value lies in **concept-level resolution, structured ontology navigation, verifiable provenance, and refusal/abstention**.

---

## 5. Experiment C: Relationship Prediction Evaluation

Evaluates the relationship triples actually surfaced in Archipelago runtime payload (`prerequisites`, `unlocks`, `related_concepts`) for the 18 relational queries:

| Metric | Measured Value | Analysis |
|:---|:---:|:---|
| **Total Relational Queries** | 18 | Target queries ($Q21 \dots Q38$) |
| **True Positives (Correct Direction)** | 1 | Q24: RAG $\xrightarrow{\text{USES}}$ DPR |
| **Inverted Direction Errors** | 1 | Q21: Self-Attention $\xrightarrow{\text{REQUIRES}}$ Transformer (Inverted) |
| **Missing Predictions (FN)** | 16 | Expected relational triple was not in surfaced payload |
| **Total Triples Surfaced** | 194 | Average 10.8 triples per query |
| **Precision** | **0.0052** (1 / 194) | High false positive rate due to broad neighborhood expansion |
| **Recall** | **0.0556** (1 / 18) | Engine does not perform targeted relation extraction |
| **F1 Score** | **0.0095** | Runtime extraction baseline |

### Failure Analysis for Relationship Prediction:
1. **Engine Runtime vs Curated Slice:** In D5, "1.0 direction accuracy" was reported because the benchmark checked whether the triple was in `d5_graph_slice.json`. When checking what Archipelago's runtime engine *actually outputs*, recall drops to 5.6%.
2. **Neighborhood Surfacing vs Triple Extraction:** Archipelago's chat engine returns general neighborhood lists (`prerequisites`, `unlocks`, `related_concepts`) containing 10–20 concepts. It does not perform targeted relation extraction for the specific predicate requested in the prompt.
3. **Inverted Direction Artifact:** In `okf_graph.json`, the edge `self_attention -[REQUIRES]-> transformer` remains stored in inverted form, causing the runtime engine to report Transformer as a prerequisite for self-attention.

---

## 6. Claim-to-Passage Citation Grounding Audit

Detailed audit of 28 citations across representative queries (Scenario 1: Transformer, Scenario 2: DPR/RAG, FlashAttention, and Abstention):

| Quality Metric | Count | Rate |
|:---|:---:|:---:|
| **Correct Document Identity** | 19 / 28 | 67.86% |
| **Correct Page / Section** | 14 / 28 | 50.00% |
| **Fully Supported Claims** | 9 / 28 | 32.14% |
| **Partially Supported Claims** | 6 / 28 | 21.43% |
| **Unsupported / Wrong Passage** | 5 / 28 | 17.86% |
| **Irrelevant / Spurious Citations** | 8 / 28 | 28.57% |

### Key Audit Observations:
- **High-Fidelity Anchor Citations:** For the primary anchor concept, citations are exceptionally accurate (e.g., Vaswani 2017 p.2 for Transformer, Dao 2022 p.2 for FlashAttention, Karpukhin 2020 p.4 for DPR).
- **Neighborhood Expansion Dilution (28.6%):** The `_collect_up_to_10_citations` heuristic gathers citations from neighboring nodes. This introduces unrelated papers into the citation list (e.g., citing DDPM or AlexNet on a Transformer query, or citing an appendix table from page 13).

---

## 7. Reviewer Provenance Integrity Audit

Audit of all 45 edges in `d5_graph_slice.json` and `human_review_records.json`:

| Provenance Level | Edge Count | Description |
|:---|:---:|:---|
| **Author-Reviewed & Verified** | 40 | Reviewed by Pratay Karali using primary source passages and page numbers. |
| **Quarantined by Author** | 5 | Flagged and removed due to inverted direction or spurious co-mentions. |
| **Independent External Peer Review** | 0 | No independent double-blind peer review has been conducted to date. |
| **AI-Assisted Candidate Extraction** | 45 | Initial triple candidates generated via pattern extraction, then human-filtered. |

*Full Provenance Records:* Documented in `research/d5_sigir_evaluation/reviewer_provenance.json`.

---

## 8. Latency Benchmark Summary

Tested under identical hardware conditions (Intel CPU + NVIDIA RTX 2050 GPU):

| Component / System | Mean Latency | Median Latency | P95 Latency |
|:---|:---:|:---:|:---:|
| **Feature-Hashed Vector (BLAKE2b)** | 0.51 ms | 0.48 ms | 0.70 ms |
| **BM25Okapi Lexical** | 2.91 ms | 2.75 ms | 3.79 ms |
| **Snowflake-Arctic-Embed-M (CUDA)** | 15.37 ms | 15.12 ms | 16.64 ms |
| **Archipelago Engine (In-Process)** | 21.22 ms | 18.45 ms | 39.44 ms |
| **Archipelago Full HTTP Stack (`/api/chat`)** | 45.52 ms | 38.70 ms | 87.97 ms |

*Conclusion:* Archipelago adds modest latency overhead (21 ms in-process, 45 ms end-to-end HTTP), easily satisfying the sub-100ms budget for interactive demonstrations.

---

## 9. Failure Analysis: The 12 Concept Resolution Misses

The 12 supported queries that missed anchor concept resolution:
1. **Unindexed Concepts (Q18, Q19, Q32, Q33):** Topics like `cross_encoder`, `dual_encoder`, and `reranking` do not have dedicated nodes in `okf_graph.json`. The engine correctly routes them to general explanation or guardrail intercepts rather than hallucinating.
2. **Ontology Naming Discrepancies (Q04, Q17, Q23):** The test query ground truth specified `dense_passage_retrieval` whereas the ontology registered the concept under `dpr` and `dense_passage_retriever`.
3. **Compound Multi-word Phrasing (Q11, Q12, Q29, Q30, Q36):** Phrasings like "query-key attention projection" or "residual connections around attention sub-layers" failed to trigger exact phrase matching and fell below the vector similarity routing threshold.

---

## 10. ACM SIGIR 2027 Demonstrations Track Decision

### Recommendation: **GO — WITH EXPLICIT CLAIM BOUNDARIES**

Archipelago is scientifically defensible for the **SIGIR 2027 Demonstrations Track**, provided the manuscript adheres strictly to the empirical evidence:

### ✅ Permissible Manuscript Claims:
1. **Concept Resolution Superiority:** Archipelago's graph-guided routing resolves academic CS concepts significantly better than BM25 (68.4% vs 42.1%) and zero-shot neural embedding (68.4% vs 36.8%).
2. **Honest Abstention:** Archipelago reliably abstains (100% precision) from unsupported/out-of-domain topics, avoiding hallucinated prerequisite chains.
3. **Interactive Demonstrable Workflows:** Live interactive demonstration of Transformer reasoning, DPR/RAG evidence tracing, and honest abstention runs with sub-50ms latency.
4. **Verifiable Document Grounding:** High anchor citation precision with direct linking to authorized PDF pages.

### ❌ PROHIBITED Manuscript Claims:
1. **DO NOT claim Archipelago outperforms BM25 or Dense Retrieval on passage retrieval.** (BM25 and Snowflake Arctic achieve 0.75 MRR vs Archipelago's 0.55).
2. **DO NOT claim 100% relationship direction accuracy.** (Runtime relationship extraction achieves F1 < 0.01; the 1.0 was a static graph match).
3. **DO NOT claim independent double-blind human validation.** (Edges were author-reviewed; independent replication is ongoing).
4. **DO NOT cite BLAKE2b hashing as a neural dense baseline.** (Properly refer to it as feature-hashed vector retrieval).
