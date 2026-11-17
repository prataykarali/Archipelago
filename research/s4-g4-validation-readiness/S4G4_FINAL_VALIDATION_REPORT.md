# Archipelago — S4-G4 Final Extraction Validation & Retrieval Readiness Report

**Date:** November 17, 2026  
**Status:** **COMPLETE & SCIENTIFICALLY VERIFIED**  
**Base Branch:** `research/s4-g3-extraction-repair` (`8ff96f22bf3cb39c37a7f59648f8c0872e9d6148`)  
**Current Branch:** `research/s4-g4-validation-readiness`  
**Test Suite Status:** **274 / 274 Tests Passing (100%)**  

---

## 1. Executive Summary

Phase S4-G4 establishes the final validation gate for the repaired academic concept and relation extraction pipeline, secures annotation materials against public repository copyright exposure, audits concept filtering and relation coverage tradeoffs, freezes extractor hyperparameters, conducts an offline multi-hop retrieval comparison smoke test across 5 retrieval paradigms, and reconciles all test suite counts across the Archipelago research trajectory.

### Primary Objectives & Outcomes

| Objective | Target | Outcome in S4-G4 | Scientific Status |
| :--- | :--- | :--- | :--- |
| **Public Repository Exposure Audit** | Identify all tracked verbatim text across history; audit copyrights | Complete audit of 10 commits, 11 documents; Pearson & Elsevier identified | **VERIFIED** (Audit documented; `.gitignore` enforced; metadata-only index deployed) |
| **Safe Annotation Storage** | Move annotator passages to local-only storage; provide on-demand hydrator | Hydrator script reconstructs 24 items in `data/annotation_local/` from `okf_graph.db` with 100% hash match | **VERIFIED** (Local storage gitignored; public index has 0 verbatim text) |
| **Independent Concept Quality Audit** | Sample candidates across OS, AIML, Networks; avoid self-evaluating circularity | 54-item blinded audit pool (27 retained, 27 rejected) produced; no labels prefilled | **VERIFIED** (Filter consistency: 100%; Semantic precision/recall: `NOT_MEASURED`) |
| **Relation Coverage & Zero-Edge Audit** | Diagnose why 4 documents produced 0 edges | Detailed syntactic and structural root cause analysis for all 4 zero-edge documents | **VERIFIED** (Distinguished syntax, structure, entity gap, and absence of evidence) |
| **Multi-Hop Retrieval Smoke Test** | Construct offline harness for BM25, Dense, RRF, Baseline Graph, Repaired Graph | All 5 systems executed on identical 764-passage corpus across 3 queries (0 crashes, 0 schema errors) | **FUNCTIONAL** (Effectiveness strictly `NOT_EVALUATED`; no superiority claimed) |
| **Extractor Parameter Freeze** | Document all regexes, thresholds, and DAG rules in versioned JSON | `okf/pilot/repaired_extractor_config.json` frozen (version `s4-g3-repaired-v1.0`) | **FROZEN** |
| **Test Suite Reconciliation** | Explain discrepancy between 270 stated tests and 264 collected tests | Identified 6-test delta in `test_s4e_graph_diagnosis.py` (stated 12, actual 6) | **RECONCILED** (264 baseline + 10 new = 274 passed) |

---

## 2. Phase 1 — Public Repository Exposure & Safe Annotation Handoff

### 2.1 Tracked File Exposure Audit
The Archipelago GitHub repository is public. A systematic audit of the Git log identified that commits `8ff96f2`, `0f78955`, `2147ece`, `abad203`, `e3af789`, and `57744db` committed files containing verbatim excerpts from copyrighted textbooks and journal publications:
- `research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_pool.csv`
- `research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_workbook.md`
- `research/s4-g2-2-corpus-locked-annotation/annotation_candidates/annotation_candidates_verified.csv`
- Earlier audit pools from S4-B and S4-D.

### 2.2 Legal & Licensing Audit
Exhaustive licensing analysis revealed that **none of the 11 audited academic documents permit unrestricted third-party redistribution of verbatim text on public GitHub**:
- **Pearson Textbooks** (`doc_fundamentals_of_database_system_7e`, `doc_computer_networks_6_e`, `doc_compilers_...`): Proprietary commercial copyright. Verbatim redistribution on public GitHub is strictly prohibited.
- **Elsevier Journal Publication** (`papers/Real-time network security...`): Published in Computers & Security (2024). Subscription/hybrid copyright. Verbatim redistribution prohibited. (S4-G3's classification as `OPEN_RESEARCH_ACCESS` was an error and is corrected to `RESTRICTED_METADATA_ONLY`).
- **OSTEP Textbooks** (`06_Address_Spaces.pdf`, `08_Paging.pdf`): Freely readable online, but "All rights reserved. Do not redistribute without permission."
- **arXiv Preprints** (`Vaswani2017`, `Hu2021`, `Dettmers2023`, `Bahdanau2014`, `Willard2023`): Distributed under arXiv non-exclusive licenses; derivative repository redistribution is unverified and restricted to metadata.

### 2.3 Protection & Safe Remediation Architecture
1. **Public Metadata Index:** Created `research/s4-g4-validation-readiness/annotation_package/public/candidate_metadata_index.csv` containing exclusively structural and cryptographic pointers (`blind_id, doc_id, chunk_id, page_number, concept_a, concept_b, offsets, sha256`). Zero verbatim text columns are present.
2. **Access-Controlled Local Storage:** Configured `.gitignore` to strictly exclude `data/annotation_local/` and local annotation files.
3. **On-Demand Local Hydrator:** Implemented `hydrate_local_annotation_pool.py`. When run by an authorized researcher with access to the local `okf_graph.db`, it queries the database, extracts passages at the recorded offsets, validates 100% of SHA-256 hashes, and generates local annotator workbooks without checking verbatim text into Git.
4. **Historical Remediation Protocol:** Normal file deletion (`git rm`) does not remove historical packfile objects. A complete `git-filter-repo` playbook is provided in `PUBLIC_EXPOSURE_AND_REMEDIATION_AUDIT.md` for execution by the repository administrator upon explicit approval.

---

## 3. Phase 2 — Independent Concept Quality Audit

In S4-G3, concept noise was reported as 0.0% by running the extractor's internal filter function `is_valid_technical_concept()` over its own output, creating an evaluation circularity.

In S4-G4, we constructed an independent, reproducibly sampled audit across three core domains:
- **Operating Systems** (18 items)
- **AI & Machine Learning** (18 items)
- **Computer Networks** (18 items)
- **Total Audit Items:** 54 candidates

### 3.1 Sampling Methodology
Candidates were sampled from raw text matching technical patterns (acronym expansions, capitalized phrases, single technical words) before filtering. The pool intentionally includes:
- **27 Retained Candidates:** Valid technical terms (e.g., `Sliding Window Protocols`, `Scaled Dot-Product Attention`, `Graph Neural Networks`, `Address Space`, `Translation Lookaside Buffer`, `PC`).
- **27 Rejected Candidates:** Common extraction noise (e.g., `2026` [date/numeric token], `Figure` [figure marker], `Next` [discourse marker], `Compared` [participle/discourse], `Brown` [author citation], `Users Didn` [verb phrase]).

### 3.2 Evaluation Independence
- **Public Blinded Package:** `research/s4-g4-validation-readiness/concept_audit/concept_validity_audit_pool_public.csv` contains neutral identifiers (`CVAL-01` through `CVAL-54`), candidate strings, source document IDs, chunk IDs, context snippets, and completely blank judgment fields (`human_is_valid_concept`, `human_concept_type`, `human_confidence`, `human_notes`).
- **Filter Consistency:** 100.0% of candidate filtering decisions adhere strictly to documented deterministic rules without stochastic variation (`concept_filter_consistency_report.json`).
- **Scientific Labeling:** Semantic precision and semantic recall are explicitly designated as **`NOT_MEASURED`**. They cannot be claimed until independent human judgments are completed on the blinded package.

---

## 4. Phase 3 — Relation Coverage & Zero-Edge Document Audit

Across the 12 evaluation documents from S4-G3, the repaired extractor produced 53 high-precision heterogeneous edges (`REQUIRES`: 6, `USES`: 15, `PART_OF`: 6, `CONTRASTS_WITH`: 26) with zero prerequisite cycles. However, four valid multi-chunk documents produced zero edges.

### Root Cause Analysis of Zero-Edge Documents

| Document | Domain | Chunks | Concepts | Abstentions | Primary Failure Mechanism | Technical Diagnosis |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `08_Paging.pdf` | OS | 3 | 3 | 2 | **Genuine Absence of Evidence** | The 3 seed chunks contain introductory framing and ASCII diagrams (`64 48 32...`). No explicit relational triggers occur within the 150-char clause window. |
| `doc_computer_networks_6_e` | Networks | 2 | 6 | 10 | **Document Structure (Numbered List)** | Entities appear as coordinate list items (`1. Physical Layer: ... \n 2. Data Link Layer: ...`). Linebreak and colon boundaries prevent ungrounded inter-layer edges. |
| `doc_fundamentals_of_database_system_7e` | DBMS | 1 | 4 | 6 | **Cross-Sentence Distance** | `The Relational Model` (sentence 1) and `Relational Algebra` (sentence 2) are in separate sentences. The 150-char single-clause limit prevents spurious co-occurrence. |
| `doc_compilers_principles...` | Compilers | 1 | 2 | 1 | **Entity Detection Surface Form** | Lowercase nouns (`the parser`, `the context-free grammar`) were not extracted by title-case heuristics. Only `Syntax Analysis` (heading) and `Abstract Syntax Tree` (sentence 2) were retained. |

### Coverage vs. Precision Tradeoff
- The repaired extractor intentionally trades recall for precision: edge count dropped from 51,079 (unsupported co-occurrences) to 53 (syntactically grounded).
- Returning zero edges for fragmentary or list-structured excerpts is scientifically truthful. Relaxing clause boundaries or sentence distance would re-introduce massive phantom overgeneration (208 cycles in S4-G1).

---

## 5. Phase 4 — Offline Multi-Hop Retrieval Readiness Smoke Test

We constructed an offline multi-hop retrieval comparison harness in `research/s4-g4-validation-readiness/scripts/run_retrieval_smoke_test.py`.

### 5.1 Experimental Configuration
- **Corpus:** Identical 764 passages across 59 documents from `okf_graph.db` (`build_fixed_corpus_from_kuzu`).
- **Retrievers Tested:**
  1. `BM25Retriever`: Robertson/Sparck Jones BM25Okapi ($k_1=1.5, b=0.75$).
  2. `DenseRetriever`: Deterministic 64-dimensional semantic projection encoder.
  3. `Hybrid RRF`: Reciprocal Rank Fusion fusing BM25 and Dense ($k=60$).
  4. `BaselineGraphRetriever`: 1-hop traversal over existing KùzuDB baseline edges.
  5. `RepairedHeterogeneousGraphRetriever`: 2-hop traversal over 148 corpus-wide repaired typed edges (`REQUIRES`: 1.0, `PART_OF`: 0.9, `USES`: 0.8, `CONTRASTS_WITH`: 0.7, 2-hop decay: 0.5).
- **Queries Evaluated:**
  - `Q-AIML-01`: *"How does multi-head attention improve upon scaled dot-product attention in Transformer architectures?"*
  - `Q-OS-01`: *"How does address space virtualization rely on hardware page tables and TLBs?"*
  - `Q-NETS-01`: *"How do Graph Neural Networks enhance real-time network anomaly detection?"*

### 5.2 Smoke Test Execution Summary

| System | Technical Sanity | Latency (avg) | Schema Errors | Crashes | Top Retrievable Passage (Sample Q-AIML-01) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BM25** | PASS | 4.88 ms | 0 | 0 | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010` |
| **Dense** | PASS | 1.02 ms | 0 | 0 | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010` |
| **Hybrid RRF** | PASS | 0.04 ms | 0 | 0 | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010` |
| **Baseline Graph** | PASS | 31.84 ms | 0 | 0 | `data_science_2019/index_2019_data-science.pdf::chunk_014` |
| **Repaired Graph** | PASS | 0.98 ms | 0 | 0 | `papers/devlin2018_bert.pdf::chunk_003` |

### 5.3 Scientific Boundaries & Integrity Constraints
- **Retrieval Effectiveness:** Strictly marked as **`NOT_EVALUATED`**.
- **No Superiority Claims:** The harness verifies computational soundness, zero schema errors, valid score distributions, and clean 2-hop graph traversals. Ranking metrics (Recall@k, MRR, nDCG@k) cannot be scientifically reported until an independently annotated gold relevance benchmark exists.

---

## 6. Phase 5 — Extractor Configuration Freeze & Test Reconciliation

### 6.1 Extractor Configuration Freeze
Hyperparameters and rules are formally frozen in `okf/pilot/repaired_extractor_config.json`:
- **Document Pre-screening:** 6 regex patterns targeting book indices, author lists, and TOCs.
- **Denoising:** 32 canonical acronyms, numeric tokens filtered, figure/table markers filtered, 55 generic discourse stopwords rejected.
- **Clause Proximity:** Maximum 150 characters between arguments; clause split delimiters enforced.
- **Relations Supported:** `REQUIRES`, `INFERRED_REQUIRES`, `PART_OF`, `USES`, `CONTRASTS_WITH`, `RELATED`.
- **Cycle Prevention:** Reachability DFS cycle prevention enforced strictly on prerequisite relations (`REQUIRES`, `INFERRED_REQUIRES`), preserving the strict DAG property while permitting heterogeneous relations.

### 6.2 Test Suite Count Reconciliation

Previous documentation noted a discrepancy between 270 stated tests and 264 collected tests. Systematic audit identified the exact single source:
- In `S4G3_EXTRACTION_REPAIR_REPORT.md`, the summary table listed `test_s4e_graph_diagnosis.py` as having **12 items**.
- The actual implementation of `test_s4e_graph_diagnosis.py` contains exactly **6 test functions**.
- Arithmetic delta: $270 - 12 + 6 = \mathbf{264}$.

### Comprehensive Trajectory Test Registry

| Phase | Test Suite File | Previous Stated | Actual Baseline | New S4-G4 Tests | Final S4-G4 Count | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S2** | `tests/unit/test_dataset_integrity_s2.py` | 11 | 11 | 0 | 11 | **PASS** |
| **S3** | `tests/unit/test_retrieval_baselines_s3.py` | 10 | 10 | 0 | 10 | **PASS** |
| **S4-A** | `tests/unit/test_annotation_pilot_s4a.py` | 5 | 5 | 0 | 5 | **PASS** |
| **S4-B** | `tests/unit/test_annotation_integrity_s4b.py` | 19 | 19 | 0 | 19 | **PASS** |
| **S4-D** | `tests/unit/test_s4d_human_audit_comparison.py` | 9 | 9 | 0 | 9 | **PASS** |
| **S4-E** | `tests/unit/test_s4e_graph_diagnosis.py` | 12 (erroneous) | 6 | 0 | 6 | **PASS** |
| **S4-F** | `tests/unit/test_s4f_evaluator_repair.py` | 24 | 24 | 0 | 24 | **PASS** |
| **S4-G1** | `tests/unit/test_s4g1_extraction_pilot.py` | 16 | 16 | 0 | 16 | **PASS** |
| **S4-G2** | `tests/unit/test_s4g2_multidomain_evaluation.py` | 17 | 17 | 0 | 17 | **PASS** |
| **S4-G2.1** | `tests/unit/test_s4g2_1_integrity_gate.py` | 11 | 11 | 0 | 11 | **PASS** |
| **S4-G2.2** | `tests/unit/test_s4g2_2_corpus_locked_annotation.py` | 40 | 40 | 0 | 40 | **PASS** |
| **S4-G3** | `tests/unit/test_s4g3_extraction_repair.py` | 96 | 96 | 0 | 96 | **PASS** |
| **S4-G4** | `tests/unit/test_s4g4_validation_readiness.py` | — | — | 10 | 10 | **PASS** |
| **TOTALS** | **13 Test Suites** | **270** | **264** | **10** | **274** | **100% PASS** |

---

## 7. Deliverables Checklist

- [x] Dedicated branch `research/s4-g4-validation-readiness` created from base commit `8ff96f22bf3cb39c37a7f59648f8c0872e9d6148`.
- [x] Public repository exposure audit and safe remediation guide (`PUBLIC_EXPOSURE_AND_REMEDIATION_AUDIT.md`).
- [x] Public metadata-only candidate index (`candidate_metadata_index.csv`) with accurate licensing classifications.
- [x] `.gitignore` updated to strictly ignore `data/annotation_local/` and local annotation files.
- [x] Safe local hydration script (`hydrate_local_annotation_pool.py`) with 100% SHA-256 verification against local database.
- [x] Independent concept quality audit package (`concept_validity_audit_pool_public.csv`, `concept_filter_consistency_report.json`) across OS, AIML, Networks with blank human fields.
- [x] Relation coverage & zero-edge document audit (`RELATION_COVERAGE_AND_ZERO_EDGE_AUDIT.md`).
- [x] Frozen repaired extractor configuration (`okf/pilot/repaired_extractor_config.json`).
- [x] Multi-hop retrieval readiness comparison harness (`run_retrieval_smoke_test.py`) and report (`retrieval_smoke_test_report.json`).
- [x] Test suite count reconciliation documenting the exact 6-test delta.
- [x] Validation test suite `tests/unit/test_s4g4_validation_readiness.py` (10 tests passing).
- [x] Full regression test suite passing: **274 / 274 tests passed**.
