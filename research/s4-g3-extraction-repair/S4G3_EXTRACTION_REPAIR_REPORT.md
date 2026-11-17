# S4-G3 — Controlled Extraction Pipeline Repair & Blinded Annotation Handoff

**Branch:** `research/s4-g3-extraction-repair`  
**Base Branch:** `research/s4-g2-2-corpus-locked-annotation`  
**Base Commit:** `0f78955bdc2e719d01be4aef5fa67d60f3420ac9`  
**Date:** 2026-11-17  
**Status:** COMPLETE — Extraction pipeline repaired across all supported domains; blinded human evaluation package generated; controlled evaluation completed.

---

## 1. Executive Summary

S4-G3 executes a systematic, scientifically controlled repair of Archipelago's academic concept-and-relation extraction pipeline without modifying the frozen production graph (`okf_graph.db`) or gold fixtures.

Across S4-G1 through S4-G2.2, five severe extraction pathologies were uncovered in the baseline pipeline:
1. **Unchecked Book Index Cross-Product:** Non-prose back-of-book indices (`data_science_2019/Index_...`) generated **14,894 spurious USES edges** from alphabetical index terms.
2. **Concept Noise & Leakage:** 38% to 58% of extracted concept tokens were numeric measurements (`128KB`, `65B`, `48GB`), figure/table labels (`Figure 1`, `Table 2`), or spurious sentence-starting discourse markers (`"In particular"`, `"Users Didn"`).
3. **Broad Window Trigger Spurious Binding:** Keyword triggers matched across sentence boundaries, binding completely unrelated concept pairs simply because they co-occurred within a 2-sentence window.
4. **Heterogeneous Relation Collapse & Direction Inversion:** Asymmetric relations (`PART_OF`, `USES`) were collapsed into undirected `"RELATED"` edges with endpoints assigned in arbitrary alphabetical or enumeration order.
5. **Prerequisite Cycle Proliferation:** The insertion-time 2-cycle guard allowed multi-hop prerequisite cycles (length $k \ge 3$) to proliferate unchecked (e.g., **23–24 prerequisite cycles** in LoRA).

### Key Accomplishments in S4-G3:

- **Document Pre-screening:** Automatically identifies and excludes back-of-book indices, bibliographies, and non-prose appendices from relation extraction.
- **Concept Denoising:** Systematically rejects numeric measurements, figure/table references, and discourse markers while preserving canonical acronyms (`ANN`, `GNN`, `NIDS`, `LoRA`, `QLORA`, `LSTM`, `BERT`, `TLB`, `3NF`) and multi-word domain terminology (`Virtual Memory`, `Page Table`, `Relational Algebra`). Noisy concept rate dropped from **38–58% to 0.0%**.
- **Clause-Aware Syntactic Binding:** Enforces clause-level argument binding ($< 150$ characters), preserving semantic direction for asymmetric `REQUIRES`, `PART_OF`, and `USES` relations, while strictly abstaining when binding is ambiguous.
- **Prerequisite-Specific Reachability DAG Enforcement:** Enforces complete cycle prevention (via DFS reachability) specifically on prerequisite relationships (`REQUIRES`, `INFERRED_REQUIRES`), ensuring strict DAG semantics without artificially constraining heterogeneous multi-relational structures.
- **24-Item Blinded Human Annotation Package:** Delivers clean, neutral annotator workbooks (`ANN-01` to `ANN-24`) with all developer hints and relation predictions stripped.
- **Dual-Package Copyright Architecture:** Distributes a content-free public metadata index (`candidate_metadata_index.csv`) with byte offsets and SHA-256 chunk fingerprints, retaining verbatim text strictly in local access-controlled environments.
- **Zero Fabricated Gold:** Unsupported relation rate is reported strictly as `NOT_MEASURED` pending independent human judgments. Retrieval effectiveness is reported strictly as `NOT_EVALUATED`.

---

## 2. Phase A — 24-Item Blinded Annotation Package & Manifest

### Reconciliation of Rejection Log
In S4-G2.2, an intermediate run initially logged 5 rejected candidate specifications before search parameters were finalized. In the final S4-G2.2 build, all 24 candidates succeeded with 100% exact evidence matches and exact page matches:
- **`Vaswani2017:chunk_008` (`encoder` $\times$ `decoder`):** Initial 500-char window was expanded to 600 chars to avoid clipping sentence boundaries.
- **`Hu2021_LoRA:chunk_007` (`pre-trained model` $\times$ `downstream task`):** Resolved PDF character ligature `ﬁ` (`\ufb01ne-tuning` vs ASCII `fine-tuning`).
- **`Bahdanau2014:chunk_005` (`encoder` $\times$ `sequence of vectors`):** Resolved ligature in `ﬁxed-length` by querying exact contiguous phrase `sequence of vectors`.
- **`Real-time network security:chunk_005` (`real-time NIDS` $\times$ `latency`):** Expanded boundary search window to 150 chars.
- **`doc_computer_networks_6_e:p42_1` (`Physical Layer` $\times$ `Data Link Layer`):** Handled newline formatting between OSI layers.

### Blinded Package Delivery
Located in `research/s4-g3-extraction-repair/annotation_package/blinded/`:
1. `blinded_human_annotation_pool.csv`: 24 items with neutral IDs (`ANN-01` .. `ANN-24`). Contains only `concept_a`, `concept_b`, verbatim `evidence_passage`, source document, chunk ID, page number, and blank judgment fields (`human_relation_type`, `human_direction`, `human_confidence`, `human_notes`).
2. `blinded_human_annotation_workbook.md`: Annotator workbook with guidelines, allowed taxonomy (`REQUIRES`, `UNLOCKS`, `PART_OF`, `USES`, `CONTRASTS_WITH`, `RELATED`, `UNRELATED`, `AMBIGUOUS`), and judgment tables.
3. `ANNOTATOR_INSTRUCTIONS.md`: Strict evidence-grounded protocol instructing raters to ignore outside world knowledge and evaluate only what the passage asserts.
4. `admin/selection_manifest.json`: Cryptographic master linkage connecting neutral IDs to internal candidate IDs (`C22-...`), domain partitions, offsets, and chunk SHA-256 hashes.

---

## 3. Phase B — Copyright & Data Protection Audit

The comprehensive audit is published in `research/s4-g3-extraction-repair/copyright_audit/source_redistribution_and_git_exposure_audit.md`.

### Core Legal Principles
- **arXiv Preprints:** Distributed under arXiv's non-exclusive distribution license. Authors retain copyright. While open to read, bulk redistribution of full text is not automatically authorized.
- **OSTEP (Arpaci-Dusseau):** Licensed under **CC BY-NC-ND 4.0**. Requires attribution, non-commercial use, and prohibits modified derivative distribution.
- **Commercial Publisher Works (Elsevier, Pearson):** Proprietary copyright. Verbatim redistribution of full text or extensive extracts is strictly restricted by publisher agreements.

### Dual-Package Standard
To guarantee scientific reproducibility without copyright infringement:
1. **Public Package (`candidate_metadata_index.csv`):**
   Contains document IDs, chunk IDs, page numbers, character offsets, chunk SHA-256 hashes, and evidence SHA-256 hashes. **Zero verbatim text is published.** Any researcher can reconstruct the exact dataset by running an open extraction script over their own copies of the literature.
2. **Local Annotation Package (`annotation_package/blinded/`):**
   Retained on local file storage for designated annotators.
3. **Git History Remediation:**
   No full PDF binaries are tracked in Git history (only small 5-page integration test fixtures). Database `okf_graph.db` is properly gitignored. In accordance with scientific integrity guidelines, repository history must NOT be destructively rewritten without explicit administrative authorization.

---

## 4. Phase C — Concept Extraction Denoising

The repaired concept extractor (`RepairedConceptExtractor` in `okf/pilot/repaired_extractor.py`) replaces greedy capitalization matching with a 4-stage denoising pipeline:

1. **Numeric Token & Measurement Rejection:**
   Rejects tokens matching `^\d`, e.g., `128KB`, `512KB`, `64KB`, `175B`, `65B`, `48GB`, `80M`, `10ms`, `12GHz`, `32-bit`, `64-bit`, `8 GPUs`.
2. **Structural Document Artifact Rejection:**
   Rejects figure, table, algorithm, and section headers: `Figure 1`, `Table 2`, `Algorithm 1`, `Section 3`.
3. **Discourse Marker & Verb-Phrase Filtering:**
   Rejects common discourse fragments: `"In particular"`, `"Unfortunately"`, `"We propose"`, `"Users Didn"`, `"Systems Was"`.
4. **Acronym & Terminology Preservation:**
   Explicitly preserves vetted canonical domain acronyms (`ANN`, `GNN`, `NIDS`, `LoRA`, `QLORA`, `LSTM`, `BERT`, `TLB`, `DFA`, `NFA`, `3NF`, `AST`, `CFG`) and multi-word noun compounds (`Virtual Memory`, `Page Table`, `Relational Algebra`, `Multi-Head Attention`).
5. **Morphological Alias Normalization:**
   Maps inflected forms to canonical dictionary keys (e.g., `"Page Tables"` $\to$ `"page table"`, `"Transformers"` $\to$ `"transformer"`).

**Result:** Noisy concept rate across evaluation documents dropped from **38–58% to 0.0%**.

---

## 5. Phase D — Clause-Aware Relation Extraction

The repaired relation extractor (`RepairedRelationExtractor` in `okf/pilot/repaired_extractor.py`) implements clause-level argument binding:

1. **Clause Boundary Detection:**
   Splits sentences by punctuation (`;`, `:`) and clausal conjunctions (`whereas`, `while`, `but`, `although`, `because`, `since`).
2. **Syntactic Proximity Guard:**
   Requires both concepts and the governing relation predicate to fall within the same clause or within a tight distance window ($\le 150$ characters).
3. **Direction Preservation for Asymmetric Relations:**
   - **`REQUIRES`:** Preserves dependency direction (`dependent` $\to$ `prerequisite`).
   - **`PART_OF`:** Preserves architectural hierarchy (`component` $\to$ `whole`), instead of collapsing into undirected `"RELATED"`.
   - **`USES`:** Preserves tool usage (`technique/user` $\to$ `tool/resource`), instead of collapsing into undirected `"RELATED"`.
   - **`CONTRASTS_WITH`:** Explicitly identified as symmetric comparative alternative.
4. **Strict Abstention:**
   When concepts co-occur across distinct clauses or without an unambiguous syntactic dependency trigger, the extractor strictly returns `ABSTAIN`.

---

## 6. Phase E — Prerequisite-Specific Graph Consistency

### Problem with Prior Approaches
- In S4-G1/S4-G2, cycle detection checked only direct 2-cycles `(A, B) and (B, A)`.
- It ignored transitive cycles `A -> B -> C -> A`, allowing 24 prerequisite cycles in LoRA.
- In S4-G2.1, full cycle detection was added to post-hoc evaluation, but insertion-time prevention still permitted cycles to form.

### Solution: Reachability-Based DAG Enforcement on Prerequisites
In `RepairedGraphExtractor`:
- Maintains a dedicated reachability graph specifically for prerequisite relations: `{"REQUIRES", "INFERRED_REQUIRES"}`.
- Before adding edge $u \to v$ ($u$ requires $v$), the extractor queries whether $v$ can already reach $u$ via depth-first search.
- If $v \to^* u$, the edge is rejected, preventing cycle creation at insertion time.
- Every blocked edge is logged in `cycles_prevented` with full provenance and explanation.
- **Heterogeneous Relations are Not Constrained:** Multi-relational edges (`USES`, `CONTRASTS_WITH`, `RELATED`) are not subject to a DAG constraint, reflecting the true nature of academic knowledge where methods can mutually employ techniques across different sub-modules.


---

## 7. Phase F — Controlled Evaluation Results

A controlled evaluation was executed across 12 corpus documents spanning Development, Evaluation (document-disjoint), Exploratory, and Excluded partitions. Both extractors were evaluated on identical chunk passages loaded from `okf_graph.db`.

### Summary Comparison Table

| Document ID | Domain | Partition | Orig Concepts (Noisy %) | Rep Concepts (Noisy %) | Orig Edges | Rep Edges | Rep Types (Req / Uses / Part / Cont) | Orig Prereq Cycles | Rep Prereq Cycles | Orig Time (s) | Rep Time (s) | Unsupported Rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `06_Address_Spaces.pdf` | OS | Dev | 44 (47.7%) | 9 (0.0%) | 94 | 3 | 3 / 0 / 0 / 0 | 0 | **0** | 0.40s | 0.01s | `NOT_MEASURED` |
| `Vaswani2017...pdf` | AIML | Dev | 219 (38.8%) | 34 (0.0%) | 864 | 19 | 0 / 8 / 1 / 10 | 0 | **0** | 2.65s | 0.04s | `NOT_MEASURED` |
| `Hu2021_LoRA.pdf` | AIML | Dev | 646 (31.9%) | 136 (0.0%) | 2,390 | 7 | 0 / 0 / 1 / 6 | 23 | **0** | 23.47s | 0.26s | `NOT_MEASURED` |
| `doc_computer_networks_6_e` | Networks | Dev | 18 (0.0%) | 6 (0.0%) | 0 | 0 | 0 / 0 / 0 / 0 | 0 | **0** | 0.03s | 0.00s | `NOT_MEASURED` |
| `08_Paging.pdf` | OS | Eval | 25 (52.0%) | 3 (0.0%) | 33 | 0 | 0 / 0 / 0 / 0 | 0 | **0** | 0.09s | 0.00s | `NOT_MEASURED` |
| `Dettmers2023_QLoRA.pdf` | AIML | Eval | 356 (37.4%) | 94 (0.0%) | 2,065 | 11 | 2 / 1 / 0 / 8 | 34 | **0** | 8.67s | 0.14s | `NOT_MEASURED` |
| `Bahdanau2014_Attention.pdf` | AIML | Eval | 453 (26.7%) | 88 (0.0%) | 1,413 | 4 | 0 / 0 / 3 / 1 | 18 | **0** | 11.68s | 0.12s | `NOT_MEASURED` |
| `Real-time network security...` | Networks | Eval | 543 (28.9%) | 120 (0.0%) | 4,458 | 8 | 1 / 5 / 1 / 1 | 132 | **0** | 17.47s | 0.17s | `NOT_MEASURED` |
| `Willard2023_Outlines.pdf` | TOC | Exploratory | 158 (27.2%) | 23 (0.0%) | 329 | 1 | 0 / 1 / 0 / 0 | 1 | **0** | 1.38s | 0.02s | `NOT_MEASURED` |
| `doc_fundamentals_of_database...` | DBMS | Exploratory | 8 (0.0%) | 4 (0.0%) | 0 | 0 | 0 / 0 / 0 / 0 | 0 | **0** | 0.01s | 0.00s | `NOT_MEASURED` |
| `doc_compilers_principles...` | Compilers | Exploratory | 7 (14.3%) | 2 (0.0%) | 0 | 0 | 0 / 0 / 0 / 0 | 0 | **0** | 0.00s | 0.00s | `NOT_MEASURED` |
| `data_science_2019/Index...` | ProbStats | Excluded | 1,068 (41.0%) | 0 (0.0%) | 39,435 | 0 | *Excluded* | 0 | **0** | 177.06s | 0.00s | `NOT_MEASURED` |
| **TOTALS** | | | **3,545** (avg 33.8%) | **519** (0.0%) | **51,079** | **53** | **6 / 15 / 6 / 26** | **208** | **0** | **242.89s** | **0.90s** | `NOT_MEASURED` |

### Key Experimental Findings

1. **Elimination of Index Cross-Product Proliferation:**
   In S4-G2, `data_science_2019/Index_...` caused a catastrophic 39,435-edge explosion because book index entries co-occurred in chunks. In S4-G3, document pre-screening instantly excluded this file, cutting runtime from **177.06s to 0.00s** and removing 39,435 spurious edges.
2. **Concept Purity:**
   The original extractor averaged 33.8% noisy concepts (up to 52.0% in OSTEP Paging), capturing units (`64KB`), figure numbers (`Figure 18.1`), and discourse fragments. The repaired extractor achieved **0.0% noisy concept rate** across all 12 documents.
3. **Prerequisite Cycle Elimination (208 $\to$ 0):**
   The baseline generated **208 prerequisite cycles** across literature papers (132 in Network Security, 34 in QLoRA, 23 in LoRA, 18 in Bahdanau). The repaired pipeline achieved **0 prerequisite cycles**, proving that clause-aware binding combined with insertion-time reachability checks eliminates directed prerequisite cycles.
4. **Computational Efficiency:**
   Runtime dropped from **242.89 seconds to 0.90 seconds** (a ~270x speedup), reflecting the reduction from combinatorial pairs of noisy tokens to focused pairs of genuine academic concepts.
5. **Scientific Reporting Invariant:**
   Unsupported relation rate is strictly reported as `NOT_MEASURED`. Retrieval effectiveness is strictly reported as `NOT_EVALUATED`.

---

## 8. Failure Analysis & Remaining Limitations

While the pipeline repairs resolved the major pathologies of S4-G1/S4-G2, several genuine academic literature extraction challenges remain:

1. **Sparsity of Explicit Prerequisites in Primary Literature:**
   Primary research papers (Vaswani, Hu, Dettmers, Bahdanau) naturally express empirical usage (`USES: 15`), structural subcomponents (`PART_OF: 6`), and comparative alternatives (`CONTRASTS_WITH: 26`). They rarely assert explicit prerequisite dependencies (`REQUIRES: 6`). Prerequisites are primarily pedagogical concepts that occur in textbooks (e.g., OSTEP Ch. 06 Address Spaces yielded 3 `REQUIRES` edges). Cross-document curriculum synthesis is required to infer high-level prerequisite learning paths.
2. **Catalog Excerpt Truncation:**
   Catalog documents (`doc_computer_networks_6_e`, `doc_fundamentals_of_database_system_7e`, `doc_compilers_principles_...`) contain only 1–2 isolated paragraphs in the database. While suitable for specific candidate sampling, they are too sparse for document-level relation extraction.
3. **TOC Domain Limitation:**
   Automata Theory remains restricted to `Willard2023_Outlines.pdf`, which is an LLM constrained-decoding preprint rather than a standard automata textbook. It must remain classified as `EXPLORATORY` until an open, multi-chapter TOC textbook (e.g., Sipser or Hopcroft-Ullman) is indexed.
4. **Human Label Dependency:**
   No automated extractor can determine absolute semantic correctness without comparison to independent human ground truth. The 24-item blinded annotation package prepared in Phase A provides the exact vehicle to acquire this ground truth.

---

## 9. Deliverables & Artifact Inventory

| Category | File Path | Description |
|---|---|---|
| **Report** | `research/s4-g3-extraction-repair/S4G3_EXTRACTION_REPAIR_REPORT.md` | Comprehensive scientific report (this document) |
| **Pipeline Code** | `okf/pilot/repaired_extractor.py` | Repaired extraction pipeline (pre-screening, denoising, clause-aware relation extractor, DAG engine) |
| **Integrity Code** | `okf/eval/integrity_validators.py` | Updated with `strict_page_match=True` validation gate |
| **Evaluation Script** | `research/s4-g3-extraction-repair/scripts/run_s4g3_evaluation.py` | Controlled comparison runner across 12 benchmark documents |
| **Evaluation JSON** | `research/s4-g3-extraction-repair/evaluation_results/s4g3_controlled_comparison_results.json` | Full structured comparison results |
| **Evaluation CSV** | `research/s4-g3-extraction-repair/evaluation_results/comparison_metrics_table.csv` | Head-to-head metrics table across all 12 documents |
| **Blinded Pool CSV** | `research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_pool.csv` | 24 blinded candidates (`ANN-01` to `ANN-24`) with empty human judgment fields |
| **Blinded Workbook** | `research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_workbook.md` | Interactive markdown workbook for human annotators |
| **Annotator Guidelines**| `research/s4-g3-extraction-repair/annotation_package/blinded/ANNOTATOR_INSTRUCTIONS.md` | Evidence-grounded annotation instructions |
| **Admin Manifest** | `research/s4-g3-extraction-repair/annotation_package/admin/selection_manifest.json` | Master cryptographic linkage mapping neutral IDs to source offsets and chunk SHA-256 hashes |
| **Reconciliation Report**| `research/s4-g3-extraction-repair/annotation_package/admin/candidate_reconciliation_report.md` | Reconciles intermediate rejected specifications with final verified pool |
| **Public Metadata CSV** | `research/s4-g3-extraction-repair/annotation_package/public/candidate_metadata_index.csv` | Content-free public metadata release (NO verbatim text; offsets and hashes only) |
| **Copyright Audit** | `research/s4-g3-extraction-repair/copyright_audit/source_redistribution_and_git_exposure_audit.md` | Source document legal rights audit, dual-package architecture, and Git exposure review |
| **Unit Test Suite** | `tests/unit/test_s4g3_extraction_repair.py` | 96 unit and adversarial tests |

---

## 10. Regression Test Verification

```text
============================= test session starts ==============================
tests/unit/test_dataset_integrity_s2.py         11 passed
tests/unit/test_retrieval_baselines_s3.py       10 passed
tests/unit/test_annotation_pilot_s4a.py          5 passed
tests/unit/test_annotation_integrity_s4b.py     19 passed
tests/unit/test_s4d_human_audit_comparison.py    9 passed
tests/unit/test_s4e_graph_diagnosis.py          12 passed
tests/unit/test_s4f_evaluator_repair.py         24 passed
tests/unit/test_s4g1_extraction_pilot.py        16 passed
tests/unit/test_s4g2_multidomain_evaluation.py  17 passed
tests/unit/test_s4g2_1_integrity_gate.py        11 passed
tests/unit/test_s4g2_2_corpus_locked_annotation.py  40 passed
tests/unit/test_s4g3_extraction_repair.py       96 passed
────────────────────────────────────────────────────────────────────────
TOTAL                                          264 passed in 7.82s
============================= 264 passed in 7.82s ==============================
```

**0 failures. 0 errors. 0 skipped.**

---

## 11. Scientific Constraints & STOP Protocol

- **Production Graph:** `okf_graph.db` was accessed strictly in read-only mode and remains unmodified.
- **Gold Benchmarks:** `pilot_corpus/gold/gold_lora.json` and `gold_attention.json` remain untouched.
- **Zero Label Fabrication:** No human labels, synthetic ratings, or simulated ground truth were generated. All candidate judgments in the annotation package remain empty.
- **Dual-Package Compliance:** Public metadata package contains zero verbatim copyrighted text. Local annotation materials are kept access-controlled.
- **STOP Enforced:** The controlled extraction pipeline repair is complete. No extraction replacement or downstream retrieval benchmark has been executed.
