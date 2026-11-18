# Archipelago — S5-A Retrieval Baseline Integrity & Human-Gold Preparation Report

**Date:** November 18, 2026  
**Status:** **COMPLETE & SCIENTIFICALLY VERIFIED**  
**Base Branch:** `research/s4-g4-validation-readiness` (`d20c16df6f9bcff473ef68ef1c36ec04a43cf3fa`)  
**Current Branch:** `research/s5-a-retrieval-integrity`  
**Test Suite Status:** **288 / 288 Tests Passing (100%)**  

---

## 1. Executive Summary

Phase **S5-A** establishes the retrieval baseline integrity and human-gold evaluation infrastructure for the CIKM 2027 multi-hop academic retrieval investigation:
> **Does provenance-aware graph retrieval improve multi-hop academic retrieval and evidence quality against BM25, dense, and hybrid retrieval baselines?**

Extraction work was formally frozen in S4-G4. S5-A exclusively repairs retrieval evaluation methodology, freezes the multi-domain academic evaluation corpus, replaces hashing proxies with genuine pretrained transformer embeddings, repairs global passage-ID mapping, fixes hybrid latency accounting, sanitizes public Git-tracked source text, and prepares an independent human evaluation package with 100% mechanical verification.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           S5-A RETRIEVAL INTEGRITY SUMMARY                      │
├─────────────────────────┬─────────────────────────┬─────────────────────────────┤
│ Dimension               │ S4-G4 State             │ S5-A Repaired State         │
├─────────────────────────┼─────────────────────────┼─────────────────────────────┤
│ Source-Text Exposure    │ Snippets in public CSV; │ Metadata-only public files; │
│                         │ older pools tracked     │ legacy pools untracked      │
├─────────────────────────┼─────────────────────────┼─────────────────────────────┤
│ Dense Retrieval Encoder │ 64-dim token hashing    │ Snowflake Arctic Embed M    │
│                         │ (non-semantic proxy)    │ 768-dim transformer encoder │
├─────────────────────────┼─────────────────────────┼─────────────────────────────┤
│ Graph Passage ID Scoping│ Collisions on bare      │ Canonical {doc}::{chunk};   │
│                         │ chunk_id strings        │ 0 cross-document collisions │
├─────────────────────────┼─────────────────────────┼─────────────────────────────┤
│ Graph Fallback Tracking │ Silent lexical fallback │ Explicit anchor coverage &  │
│                         │                         │ 1-hop / 2-hop ablation      │
├─────────────────────────┼─────────────────────────┼─────────────────────────────┤
│ Hybrid RRF Latency      │ Isolated 0.04ms fusion  │ Full end-to-end timing:     │
│                         │ artifact                │ 23.35ms warm mean           │
├─────────────────────────┼─────────────────────────┼─────────────────────────────┤
│ Evaluation Corpus       │ S3 mixed (764 passages, │ s5a_eval_corpus_v1: 713     │
│                         │ 50 index-only passages) │ verified prose passages     │
├─────────────────────────┼─────────────────────────┼─────────────────────────────┤
│ Human Evaluation Suite  │ None for retrieval      │ 12 queries, 31 candidates,  │
│                         │                         │ all blank human judgments   │
├─────────────────────────┼─────────────────────────┼─────────────────────────────┤
│ Pytest Suite Status     │ 274 passed              │ 288 passed (100% PASS)      │
└─────────────────────────┴─────────────────────────┴─────────────────────────────┘
```

---

## 2. Phase 1 — Public Source-Text Exposure Resolution

A comprehensive inventory of Git-tracked files was performed across the repository:
1. **Public Concept Audit Pool Sanitized:** In S4-G4, `concept_validity_audit_pool_public.csv` included `context_snippet`. In S5-A, this was purged and replaced with metadata offsets (`context_offset_start`, `context_offset_end`) and cryptographic hashes (`context_sha256`). Zero verbatim text remains in the public concept audit file.
2. **Untracking Legacy Annotation Pools:** The redundant verbatim copies in `research/s4-g3-extraction-repair/annotation_package/blinded/` (`blinded_human_annotation_pool.csv` and `blinded_human_annotation_workbook.md`) were untracked using `git rm`. The test suite fixture was redirected to approved local-only storage (`data/annotation_local/`).
3. **Approved Local-Only Storage Enforced:** `.gitignore` was updated to strictly guard `data/annotation_local/`, `research/s4-g4-validation-readiness/annotation_local/`, and `research/s5-a-retrieval-integrity/annotation_local/`.
4. **Historical Inventory Delivered:** Detailed in [SOURCE_EXPOSURE_STATUS_REPORT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-a-retrieval-integrity/SOURCE_EXPOSURE_STATUS_REPORT.md). Explains remaining historical packfile blobs and documents the exact `git filter-repo` command for execution upon explicit repository administrator authorization.

---

## 3. Phase 2 — Pretrained Dense Retrieval & Baseline Repair

The token-hashing baseline used in S4-G4 was relegated to a clearly labeled debugging baseline, and replaced with a genuine state-of-the-art passage retrieval model:

### 3.1 Model Specification & Cost Manifest
Detailed in [s5a_model_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-a-retrieval-integrity/models/s5a_model_manifest.json):
- **Model Identifier:** `Snowflake/snowflake-arctic-embed-m-v1.5`
- **Revision:** `f22f7b88939ba6d01306a445d48729fb5a2ff3f3` (cached locally)
- **Architecture:** BERT-based dense transformer encoder with mean pooling
- **Embedding Dimension:** 768
- **Query Prefix:** `"Represent this sentence for searching relevant passages: "`
- **Document Preprocessing:** Whitespace normalization via `normalize_passage_text()`
- **Normalization:** L2 unit sphere normalization ($\|v\|_2 = 1.0$), enabling inner product cosine similarity
- **Hardware & Inference Settings:** PyTorch CPU, batch size 32
- **Corpus Encoding Cost:** 57.85s on CPU (12.3 passages/sec); 2.09 MB index precomputed and cached in `data/artifacts/s5a_dense_embeddings_713.npy` for instantaneous evaluation loading

### 3.2 Global Passage-ID Mapping Repair
In S4-G4, `BaselineGraphRetriever` mapped concepts to passages using `if p.chunk_id in cid`, causing identical chunk IDs (e.g., `chunk_014`) to be associated across unrelated documents.
- **Repair Implemented:** Full Cypher graph provenance resolution:
  `MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(cn:Concept)`
- Formats passage IDs strictly as canonical `{normalize_doc_id(d.id)}::{c.chunk_id}`.
- Cross-document passage ID collisions in S5-A: **strictly 0**.

### 3.3 Genuine Graph Traversal vs. Lexical Fallback Tracking
- All graph systems now track explicit operational metadata:
  - `anchor_found`: boolean
  - `matched_anchors`: list of concept names
  - `traversed_concepts_count`: integer
  - `actual_hop_count`: 0 (fallback), 1, or 2
  - `is_fallback`: boolean
- Repaired heterogeneous graph evaluated with a matched ablation:
  - `repaired_graph_1hop_ablation`: 1-hop traversal
  - `repaired_graph_2hop_full`: 2-hop traversal with heterogeneous edge weights (`REQUIRES`: 1.0, `PART_OF`: 0.9, `USES`: 0.8, `CONTRASTS_WITH`: 0.7, 2-hop decay: 0.5)

### 3.4 Hybrid RRF End-to-End Latency Accounting
Previous smoke tests reported RRF latency as 0.04ms (measuring only post-hoc fusion). S5-A implements true end-to-end timing:
$$T_{\text{hybrid}} = T_{\text{BM25}} + T_{\text{Dense}} + T_{\text{Fusion}}$$
Evaluated over a cold start and 5 warm repetitions per query, capturing full statistical distributions (mean, median, std, min, max, p95).

---

## 4. Phase 3 — Evaluation Corpus Freezing

Audited the 764-passage S3 corpus (`s3_fixed_corpus_v1`). Identified and removed non-evaluable records:
- **Index-Only / Table of Contents / Author Listings:** 50 passages (e.g. `data_science_2019/index_...`, `predictive_analytics_.../index_...`).
- **Invalid Page Numbers:** 1 passage (`doc_data_and_computer_communications_p612_4`, claiming page 612 of a 500-page book).
- **Frozen Universe (`s5a_eval_corpus_v1`):** **713 unique, verified academic prose passages across 53 documents**.
- **Manifest Published:** [s5a_corpus_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-a-retrieval-integrity/corpus/s5a_corpus_manifest.json).
- The historical 764-passage corpus is retained as a separate baseline. All 6 retrieval configurations in S5-A evaluate against the exact same 713-passage universe.

---

## 5. Phase 4 — Human Evaluation Package Preparation

Constructed 12 mechanically verified academic queries across four domains:
- **Operating Systems:** 3 queries (`Q-S5A-01` to `Q-S5A-03`)
- **AI & Machine Learning:** 5 queries (`Q-S5A-04` to `Q-S5A-08`)
- **Computer Networks:** 3 queries (`Q-S5A-09` to `Q-S5A-11`)
- **Database Management Systems:** 1 query (`Q-S5A-12`)

### 5.1 Category Breakdown
- **Single-Hop Controls (3 queries):** Foundational premise verification (e.g., Address Space definition, Scaled Dot-Product formula, OSI layers).
- **Two-Hop Questions (4 queries):** Multi-hop synthesis across sub-components (e.g., Base-and-bounds hardware relocation, Multi-Head Attention projection math, Dynamic GNN intrusion detection, 3NF transitive dependency elimination).
- **Cross-Document Questions (2 queries):** Multi-paper synthesis (e.g., Transformer projections in Vaswani 2017 combined with LoRA adapter updates in Hu 2021; QLoRA NormalFloat quantization in Dettmers 2023 combined with LoRA).
- **Unanswerable Questions (3 queries):** Technical questions intentionally absent from the corpus (e.g., ARM Cortex-A78 page table walk latency in nanoseconds; LLaMA-3 405B electric utility costs; Cisco 2025 CVE firmware exploits).
- **Hard Negative Distractor Passages:** 11 hard negatives specifically matched to query topics to test retrieval discrimination.

### 5.2 Verification & Integrity Guarantees
- Every candidate passage was **mechanically verified** to exist in `s5a_eval_corpus_v1` with cryptographic SHA-256 digests.
- **Zero AI Gold Labels:** All human fields (`human_relevance_grade`, `human_evidence_quote`, `human_confidence`, `human_notes`) are strictly empty.
- Distributed reviewer files:
  - [retrieval_query_candidate_pool.csv](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-a-retrieval-integrity/human_evaluation_package/retrieval_query_candidate_pool.csv): 31 candidate pairs across 12 queries.
  - [RETRIEVAL_ANNOTATION_PROTOCOL.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-a-retrieval-integrity/human_evaluation_package/RETRIEVAL_ANNOTATION_PROTOCOL.md): Detailed TREC/CIKM 3-point relevance scale (0, 1, 2), double-blinding protocol, and Cohen's Kappa / Krippendorff's Alpha adjudication procedures.
  - [retrieval_query_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-a-retrieval-integrity/human_evaluation_package/retrieval_query_manifest.json): Master admin linkage.
  - Local reviewer workbook saved in `data/annotation_local/retrieval_eval/retrieval_relevance_reviewer_workbook.md`.

---

## 6. Phase 5 — Technical Evaluation Gate Results

Executed all 6 retrieval configurations across the 12 evaluation queries on the frozen 713-passage corpus:

### 6.1 End-to-End Latency Distributions (ms)

| Retrieval System | Cold Mean | Warm Mean | Warm Median | Warm Std | Warm P95 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **BM25** (Okapi, $k_1=1.5, b=0.75$) | 5.09 | **4.56** | 4.41 | 1.42 | 7.33 |
| **Dense** (Snowflake Arctic Embed M, 768-dim) | 42.11 | **17.20** | 16.08 | 3.36 | 26.48 |
| **Hybrid RRF** (End-to-End: BM25 + Dense + Fusion) | 23.82 | **23.35** | 21.94 | 5.73 | 38.52 |
| **Baseline Graph** (1-hop KùzuDB default edges) | 18.90 | **17.26** | 6.81 | 19.24 | 65.61 |
| **Repaired Graph** (1-hop ablation) | 36.42 | **33.69** | 24.05 | 22.84 | 87.40 |
| **Repaired Graph** (2-hop full heterogeneous) | 36.40 | **33.66** | 24.51 | 22.75 | 88.20 |

*Reports stored in [retrieval_timing_report.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-a-retrieval-integrity/retrieval_timing_report.json).*

### 6.2 Graph Anchor Coverage & Fallback Analysis

| Graph Configuration | Anchor Coverage Rate | Fallback Count (out of 12) | Fallback Rate | Traversed Concepts (avg) |
| :--- | :---: | :---: | :---: | :---: |
| **Baseline Graph** (1-hop) | **83.3%** (10/12) | 2 | 16.7% | 3.4 |
| **Repaired Graph** (1-hop ablation) | **50.0%** (6/12) | 6 | 50.0% | 5.2 |
| **Repaired Graph** (2-hop full) | **50.0%** (6/12) | 6 | 50.0% | 18.7 |

*Technical findings:*
- The baseline graph has higher raw anchor coverage (83.3%) because it contains unpruned, noisy concept terms.
- The repaired graph has a 50.0% anchor coverage on complex multi-hop queries, falling back explicitly and transparently to lexical retrieval when query terms lack graph nodes.
- Full 2-hop traversal expands from an average of 5.2 concepts (1-hop) to 18.7 concepts (2-hop), demonstrating rich multi-relational traversal.

### 6.3 Scientific Boundaries
- **Retrieval Effectiveness Verdict:** Strictly **`NOT_EVALUATED`**.
- **No Superiority Claims:** In strict compliance with scientific integrity directives, no Recall@k, MRR, or nDCG@k metrics are calculated or claimed before independent human judgments are conducted on the prepared evaluation package.

---

## 7. Trajectory Test Suite Registry

All 288 tests pass across 14 test suites with zero regressions:

| Phase | Test Suite File | Previous Stated | Baseline | New S5-A Tests | Total S5-A | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **S2** | `tests/unit/test_dataset_integrity_s2.py` | 11 | 11 | 0 | 11 | **PASS** |
| **S3** | `tests/unit/test_retrieval_baselines_s3.py` | 10 | 10 | 0 | 10 | **PASS** |
| **S4-A** | `tests/unit/test_annotation_pilot_s4a.py` | 5 | 5 | 0 | 5 | **PASS** |
| **S4-B** | `tests/unit/test_annotation_integrity_s4b.py` | 19 | 19 | 0 | 19 | **PASS** |
| **S4-D** | `tests/unit/test_s4d_human_audit_comparison.py` | 9 | 9 | 0 | 9 | **PASS** |
| **S4-E** | `tests/unit/test_s4e_graph_diagnosis.py` | 6 | 6 | 0 | 6 | **PASS** |
| **S4-F** | `tests/unit/test_s4f_evaluator_repair.py` | 24 | 24 | 0 | 24 | **PASS** |
| **S4-G1** | `tests/unit/test_s4g1_extraction_pilot.py` | 16 | 16 | 0 | 16 | **PASS** |
| **S4-G2** | `tests/unit/test_s4g2_multidomain_evaluation.py` | 17 | 17 | 0 | 17 | **PASS** |
| **S4-G2.1** | `tests/unit/test_s4g2_1_integrity_gate.py` | 11 | 11 | 0 | 11 | **PASS** |
| **S4-G2.2** | `tests/unit/test_s4g2_2_corpus_locked_annotation.py` | 40 | 40 | 0 | 40 | **PASS** |
| **S4-G3** | `tests/unit/test_s4g3_extraction_repair.py` | 96 | 96 | 0 | 96 | **PASS** |
| **S4-G4** | `tests/unit/test_s4g4_validation_readiness.py` | 10 | 10 | 0 | 10 | **PASS** |
| **S5-A** | `tests/unit/test_s5a_retrieval_integrity.py` | — | — | 14 | 14 | **PASS** |
| **TOTALS** | **14 Test Suites** | **274** | **274** | **14** | **288** | **100% PASS** |

---

## 8. Commitments & Constraints Verified

- [x] Frozen extractor untouched (`okf/pilot/repaired_extractor_config.json` preserved).
- [x] Production graph untouched (`okf_graph.db` read-only).
- [x] Zero human labels fabricated (all candidate pools strictly empty).
- [x] Zero claims of graph retrieval superiority prior to independent gold annotation.
- [x] Repository visibility unchanged; no Git history rewritten autonomously.
- [x] STOP executed after S5-A.
