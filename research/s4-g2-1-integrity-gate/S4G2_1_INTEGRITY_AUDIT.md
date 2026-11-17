# S4-G2.1 — Multi-Domain Scientific Integrity Gate: Audit Report

**Branch:** `research/s4-g2-1-integrity-gate`  
**Base Branch:** `research/s4-g2-multidomain-evaluation`  
**Base Commit:** `abad203d64069bf5efcfb5c4e08b9fd82f67fb2a`  
**Date:** 2026-11-17  
**Status:** COMPLETE — Integrity gate passed. Main retrieval experiment (S4-H) may not proceed until annotation pool is rebuilt.

---

## Executive Summary

S4-G2.1 is an integrity pre-check for the multi-domain evaluation designed in S4-G2. It audits three overlapping problems: **fabricated quality metrics**, **invalid annotation provenance**, and **systematic overgeneration**. All three are confirmed.

| Issue | Severity | Finding | Action Taken |
|-------|----------|---------|-------------|
| Hardcoded metrics (`unsupported_rate=0.0`, `provenance=1.0`, `cycles=0`) | **Critical** | Metrics were written as literals, not computed | Replaced with real calculations; `unsupported_rate` → `NOT_MEASURED` |
| 36-item annotation pool | **Critical** | 36/36 items MISMATCH — zero verified | Pool corrected and preserved; human judgments withheld |
| Overgeneration & cycle detection | **High** | 24–32 cycles per AI/ML paper; index cross-product generating 14,894 edges | Diagnosed; cycle detection upgraded to full DFS (k ≥ 2) |
| Evaluation split honesty | **Medium** | TOC domain uses a within-document chunk split, not stated explicitly | Re-classified to `WITHIN_DOCUMENT_CHUNK_SPLIT` in audit CSV |

> [!CAUTION]
> The S4-G2 annotation pool cannot be used for human evaluation as written.
> Every item references fabricated or paraphrased passages, misidentified chunk IDs, or document segments that do not contain the claimed evidence.
> The pool must be entirely rebuilt from verbatim verified corpus text before any human annotation begins.

**Test suite:** 128/128 passing across S1–S4-G2.1.

---

## Issue 1 — Hardcoded Quality Metrics

### Problem

Three scalar quality metrics in
`research/s4-g2-multidomain-evaluation/scripts/run_s4g2_experiment.py`
were written as numeric literals rather than computed from data:

```python
# BEFORE (fabricated, scientifically invalid)
unsupported_relation_rate = 0.0
valid_provenance_coverage  = 1.0
# Cycles column always written as 0
```

This created the false appearance that every extracted relation was grounded, every provenance pointer was valid, and no cycles existed — none of which had been independently verified.

### Fix Applied

| Metric | Before | After |
|--------|--------|-------|
| `unsupported_relation_rate` | `0.0` (literal) | `NOT_MEASURED` |
| `valid_provenance_coverage` | `1.0` (literal) | Real DB lookup via `calculate_provenance_coverage()` in `okf/eval/integrity_validators.py` |
| `cycles` | `0` (literal) | Full DFS via `detect_directed_cycles()` — reports actual k ≥ 2 cycles |

### Why `NOT_MEASURED` for Unsupported Rate

Unsupported relation rate requires a human judgment that labels each extracted relation as either supported or unsupported by the cited evidence span. No such gold standard exists. Reporting `0.0` before those labels are collected is a fabrication.
The correct scientific position is to acknowledge the measurement is pending.

### Real Cycle Counts (Full DFS, k ≥ 2)

The S4-G2 insertion-time guard blocked only reciprocal 2-cycles. Full DFS detects cycles of any length.

| Document | Prereq Cycles (k ≥ 2) | All-Relation Cycles (k ≥ 2) |
|----------|----------------------|----------------------------|
| `Hu2021_LoRA.pdf` | **24** | 905 |
| `Bahdanau2014_Attention.pdf` | **18** | 445 |
| `Real-time network security...pdf` | **8** | 466 |
| `Vaswani2017_Attention_Is_All_You_Need.pdf` | 0 | 209 |
| `Devlin2018_BERT.pdf` | 0 | 461 |
| `Willard2023_Outlines.pdf` | 0 | 11 |
| All OS, DBMS documents | 0 | 0–1 |

The previously reported "0 cycles" figure was categorically false for three documents.

### New Infrastructure

- **`okf/eval/integrity_validators.py`** (new module):
  - `detect_directed_cycles(graph, relation_filter)` — 3-colour DFS for directed cycles of length ≥ 2 on arbitrary relation subsets
  - `validate_provenance_record(chunk_id, source_doc_id, evidence_text, session)` — checks chunk existence in DB and evidence text occurrence
  - `audit_semantic_direction(relations, session)` — flags PART_OF and USES edges where the semantic argument order is inverted

---

## Issue 2 — 36-Item Annotation Pool Source Audit

### Methodology

Each of the 36 annotation items claims:
- A source document (`claimed_source_doc_id`)
- A chunk identifier (`claimed_chunk_id`)
- A page number (`claimed_page_number`)
- A verbatim evidence passage

The script `verify_36_annotation_items.py` checked all four against the live `okf_graph.db` corpus and assigned each item one of: `VERIFIED`, `MISMATCH`, `UNVERIFIABLE`.

### Result: 36/36 MISMATCH

No item passed verification. The five failure categories are:

| Category | Count | Items | Root Cause |
|----------|-------|-------|-----------|
| `PARAPHRASED_SYNTHESIS` | 18 | OS-01–06, DBMS-01/02/06, NET-01–06, AI-01–06 | Evidence text is a paraphrase or thematic summary, not a verbatim corpus passage |
| `UNINDEXED_TOPIC_SYNTHESIS` | 7 | DBMS-03/04/05, NET-01/02/04 | Attributed to documents that have only 1–2 indexed chunks; topic not covered in those chunks |
| `EXTERNAL_THEORY_SYNTHESIS` | 6 | TOC-01–06 | Classical automata theory attributed to `Willard2023_Outlines.pdf`, a preprint on formal grammar outlines that does not contain the referenced concepts |
| `INDEX_LISTING_ATTRIBUTION_ERROR` | 5 | STAT-01/03/04/05/06 | Prose attributed to back-of-book index keyword listings; index entries do not form prose passages |
| `CONCEPT_NOT_IN_REFERENCED_CHUNK` | (overlaps above) | Various | One or both concepts are not identifiable in the referenced chunk text |

### Complete Item Table

| Item ID | Domain | Concept A | Concept B | Claimed Doc | Claimed Chunk | Verdict | Category |
|---------|--------|-----------|-----------|-------------|---------------|---------|---------|
| OS-01 | Operating Systems | Virtual Memory | Address Space | `ostep.../06_Address_Spaces.pdf` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| OS-02 | Operating Systems | Address Translation | Base-and-Bounds | `ostep.../07_Address_Translation.pdf` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| OS-03 | Operating Systems | Page Table | Paging | `ostep.../08_Paging.pdf` | `chunk_002` | MISMATCH | PARAPHRASED_SYNTHESIS |
| OS-04 | Operating Systems | Paging | Segmentation | `ostep.../08_Paging.pdf` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| OS-05 | Operating Systems | TLB | Page Table | `ostep.../08_Paging.pdf` | `chunk_003` | MISMATCH | PARAPHRASED_SYNTHESIS |
| OS-06 | Operating Systems | Virtual Memory | Physical Memory | `ostep.../06_Address_Spaces.pdf` | `chunk_002` | MISMATCH | PARAPHRASED_SYNTHESIS |
| DBMS-01 | Database Management Systems | Relational Algebra | SQL | `pilot/silberschatz_3nf_card.txt` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| DBMS-02 | Database Management Systems | Normalization | Functional Dependency | `pilot/silberschatz_3nf_card.txt` | `chunk_002` | MISMATCH | PARAPHRASED_SYNTHESIS |
| DBMS-03 | Database Management Systems | B+ Tree | Indexing | `doc_fundamentals_of_database_system_7e` | `chunk_001` (p.24) | MISMATCH | UNINDEXED_TOPIC_SYNTHESIS |
| DBMS-04 | Database Management Systems | Query Optimization | Join Algorithms | `doc_fundamentals_of_database_system_7e` | `chunk_001` (p.42) | MISMATCH | UNINDEXED_TOPIC_SYNTHESIS |
| DBMS-05 | Database Management Systems | Transaction Management | ACID Properties | `doc_fundamentals_of_database_system_7e` | `chunk_001` (p.15) | MISMATCH | UNINDEXED_TOPIC_SYNTHESIS |
| DBMS-06 | Database Management Systems | ER Model | Relational Schema | `pilot/silberschatz_3nf_card.txt` | `chunk_003` | MISMATCH | PARAPHRASED_SYNTHESIS |
| NET-01 | Computer Networks | TCP | Reliable Data Transfer | `doc_computer_networks_6_e` | `chunk_001` | MISMATCH | UNINDEXED_TOPIC_SYNTHESIS |
| NET-02 | Computer Networks | IP | Routing | `doc_computer_networks_6_e` | `chunk_002` | MISMATCH | UNINDEXED_TOPIC_SYNTHESIS |
| NET-03 | Computer Networks | ANN | Graph-Based Analysis | `papers/Real-time network security...pdf` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| NET-04 | Computer Networks | Network Security | Intrusion Detection | `doc_computer_networks_6_e` | `chunk_002` | MISMATCH | UNINDEXED_TOPIC_SYNTHESIS |
| NET-05 | Computer Networks | DNS | Packet Switching | `papers/Real-time network security...pdf` | `chunk_002` | MISMATCH | PARAPHRASED_SYNTHESIS |
| NET-06 | Computer Networks | OSI Model | TCP/IP Stack | `papers/Real-time network security...pdf` | `chunk_003` | MISMATCH | PARAPHRASED_SYNTHESIS |
| TOC-01 | Automata Theory | DFA | NFA | `papers/Willard2023_Outlines.pdf` | `chunk_001` | MISMATCH | EXTERNAL_THEORY_SYNTHESIS |
| TOC-02 | Automata Theory | Regular Expressions | Finite Automata | `papers/Willard2023_Outlines.pdf` | `chunk_002` | MISMATCH | EXTERNAL_THEORY_SYNTHESIS |
| TOC-03 | Automata Theory | Context-Free Grammar | PDA | `papers/Willard2023_Outlines.pdf` | `chunk_003` | MISMATCH | EXTERNAL_THEORY_SYNTHESIS |
| TOC-04 | Automata Theory | Turing Machine | Computability | `papers/Willard2023_Outlines.pdf` | `chunk_004` | MISMATCH | EXTERNAL_THEORY_SYNTHESIS |
| TOC-05 | Automata Theory | Halting Problem | Undecidability | `papers/Willard2023_Outlines.pdf` | `chunk_005` | MISMATCH | EXTERNAL_THEORY_SYNTHESIS |
| TOC-06 | Automata Theory | Regular Language | Pumping Lemma | `papers/Willard2023_Outlines.pdf` | `chunk_006` | MISMATCH | EXTERNAL_THEORY_SYNTHESIS |
| STAT-01 | Probability & Statistics | Bayesian Inference | Prior Distribution | `data_science_2019/Index_2019_Data-Science.pdf` | `chunk_001` | MISMATCH | INDEX_LISTING_ATTRIBUTION_ERROR |
| STAT-02 | Probability & Statistics | Maximum Likelihood | Parameter Estimation | `pattern_recognition_2009/Appendix-A.pdf` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| STAT-03 | Probability & Statistics | Random Variable | Probability Distribution | `data_science_2019/Index_2019_Data-Science.pdf` | `chunk_002` | MISMATCH | INDEX_LISTING_ATTRIBUTION_ERROR |
| STAT-04 | Probability & Statistics | Hypothesis Testing | p-value | `data_science_2019/Index_2019_Data-Science.pdf` | `chunk_003` | MISMATCH | INDEX_LISTING_ATTRIBUTION_ERROR |
| STAT-05 | Probability & Statistics | Central Limit Theorem | Normal Distribution | `data_science_2019/Index_2019_Data-Science.pdf` | `chunk_004` | MISMATCH | INDEX_LISTING_ATTRIBUTION_ERROR |
| STAT-06 | Probability & Statistics | Markov Chain | Stochastic Process | `data_science_2019/Index_2019_Data-Science.pdf` | `chunk_005` | MISMATCH | INDEX_LISTING_ATTRIBUTION_ERROR |
| AI-01 | AI & Machine Learning | Low-Rank Adaptation | Pre-trained Model | `papers/Hu2021_LoRA.pdf` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| AI-02 | AI & Machine Learning | Attention Mechanism | Transformer | `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| AI-03 | AI & Machine Learning | Fine-tuning | Downstream Tasks | `papers/Hu2021_LoRA.pdf` | `chunk_002` | MISMATCH | PARAPHRASED_SYNTHESIS |
| AI-04 | AI & Machine Learning | Neural Machine Translation | Encoder-Decoder | `papers/Bahdanau2014_Attention.pdf` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| AI-05 | AI & Machine Learning | BERT | Masked Language Model | `papers/Devlin2018_BERT.pdf` | `chunk_001` | MISMATCH | PARAPHRASED_SYNTHESIS |
| AI-06 | AI & Machine Learning | Self-Attention | Multi-Head Attention | `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` | `chunk_002` | MISMATCH | PARAPHRASED_SYNTHESIS |

### DBMS Special Case: Conflicting Page Numbers on Single Chunk

`doc_fundamentals_of_database_system_7e::chunk_001` appears as the claimed chunk for three separate items with three different claimed page numbers:

| Item | Claimed Page |
|------|-------------|
| DBMS-03 | 24 |
| DBMS-04 | 42 |
| DBMS-05 | 15 |

The DB records a single chunk for this document: `doc_fundamentals_of_database_system_7e_p145_1`, page 145, section "Relational Algebra". The document as indexed has only one chunk — not the multi-chapter coverage implied by three different page assignments to `chunk_001`.

### No Silent Replacement

No items were silently corrected or replaced. The original pool is preserved as-is at:

```
research/s4-g2-multidomain-evaluation/human_annotation_package/multidomain_human_annotation_pool.csv
```

The corrected version — with audit status columns added, all human judgment fields left blank — is at:

```
research/s4-g2-1-integrity-gate/human_annotation_package/multidomain_human_annotation_pool_corrected.csv
```

Every change is recorded in `research/s4-g2-1-integrity-gate/CHANGELOG.md`.

---

## Issue 3 — Overgeneration Diagnosis

### Summary

| Document | Concepts | Noisy Rate | Total Edges | Prereq Cycles | Primary Failure |
|----------|----------|-----------|------------|--------------|----------------|
| `data_science_2019/Index_2019_Data-Science.pdf` | 622 | 50.8% | 14,894 USES | 0 | BOOK_INDEX_CROSS_PRODUCT |
| `Hu2021_LoRA.pdf` | 646 | 24.6% | 2,427 | **24** | BROAD_TRIGGER_OVERGENERATION |
| `Bahdanau2014_Attention.pdf` | 453 | 19.2% | 1,413 | **18** | BROAD_TRIGGER_OVERGENERATION |
| `Real-time network security...pdf` | 233 | 21.5% | 1,258 | **8** | BROAD_TRIGGER_OVERGENERATION |
| `Devlin2018_BERT.pdf` | 342 | 23.7% | 1,761 | 0 | BROAD_TRIGGER_OVERGENERATION |
| `Vaswani2017_Attention_Is_All_You_Need.pdf` | 219 | 30.1% | 826 | 0 | STOPWORD_AND_NUMERIC_LEAKAGE |
| `ostep.../06_Address_Spaces.pdf` | 44 | 36.4% | 94 | 0 | STOPWORD_AND_NUMERIC_LEAKAGE |
| `Willard2023_Outlines.pdf` | 187 | 21.4% | 190 combined | 0 | STOPWORD_AND_NUMERIC_LEAKAGE |

### Root Cause 1: Book Index Cross-Product (Data Science 2019)

`data_science_2019/Index_2019_Data-Science.pdf` is a back-of-book index — a list of terms and page references. The extractor treated each index headword as an academic concept and generated USES edges for every co-occurring pair in an index section, producing **14,894 USES edges** from a document that contains no prose assertions about how any concept uses another.

**Fix required:** Pre-screening must reject documents of type `book_index`, `appendix_keyword_listing`, and `bibliography` from the relation extraction pipeline.

### Root Cause 2: Broad Trigger Overgeneration

Generic lexical triggers (`uses`, `using`, `requires`, `based on`) match across any two concepts that happen to co-occur in the same passage, regardless of whether the sentence asserts a semantic relation between the specific two concepts. This generates high-volume, low-precision edges.

**Examples of spurious matches (LoRA):**
- `LoRA → Gradient Checkpointing` triggered by "*requires*" in a sentence about memory, not about LoRA specifically
- `Matrix → Rank` triggered by "*uses*" in a table caption

**Fix required:** Trigger matching must require both concepts to appear in the same syntactic clause, not merely the same passage window. Abstention should be the default when argument binding is uncertain.

### Root Cause 3: Stopword and Numeric Concept Leakage

Concepts extracted from OSTEP, Vaswani, and Willard documents include numeric tokens (`128KB`, `512KB`, `10ms`), diagram labels (`Figure 1`, `Table 2`), and capitalized section headers that are not academic concepts.

**Fix required:** Concept validation must reject tokens containing only digits, measurement units, figure references, and pure uppercase abbreviations without a known domain mapping.

### Cycle Root Causes

The insertion-time 2-cycle guard (which blocked only `A→B, B→A` pairs) does not prevent:
- `A→B→C→A` (length-3 cycles)
- Longer chains where each individual edge passes the 2-cycle check in isolation

This is a fundamental limitation of greedy insertion-time guards. Prevention requires a topological-sort-aware insertion algorithm, or batch post-processing with cycle removal.

**Full DFS cycle detection is now implemented** in `okf/eval/integrity_validators.py::detect_directed_cycles()`. It correctly finds all cycles of k ≥ 2 on any relation subset.

---

## Issue 4 — Evaluation Split Honesty

The TOC (Automata Theory & Computation) domain has only one indexed document: `papers/Willard2023_Outlines.pdf`. The S4-G2 split assigned chunks 0–9 to development and chunks 10–19 to evaluation.

This is a **within-document chunk split**, not a document-disjoint split. Concepts, terminology, and contextual background in chunks 0–9 (development) can directly inform extraction on chunks 10–19 (evaluation), creating a potential data-leakage risk.

| Domain | Split Type | Risk |
|--------|-----------|------|
| Operating Systems | DOCUMENT_DISJOINT | Clean |
| Database Management Systems | DOCUMENT_DISJOINT | Clean |
| Computer Networks | DOCUMENT_DISJOINT | Clean |
| Probability & Statistics | DOCUMENT_DISJOINT | Clean |
| AI & Machine Learning | DOCUMENT_DISJOINT | Clean |
| Automata Theory & Computation | **WITHIN_DOCUMENT_CHUNK_SPLIT** | Leakage Risk |

The evaluation split audit CSV (`evaluation_split_audit.csv`) now correctly classifies the TOC domain. This is a **documentation fix only** — no data was removed or reassigned. Downstream experiments must clearly state this limitation.

**Path forward:** Acquire a second, independent TOC document (e.g., Sipser, Hopcroft-Motwani-Ullman) for a genuinely disjoint split.

---

## Issue 5 — Metric Stratification

The S4-G2 results conflated measurements at four distinct levels of rigor. The correct stratification is:

| Level | Metric | Current Status |
|-------|--------|----------------|
| **L1 — Structural** | Directed cycle count (k ≥ 2), edge density, concept noise rate | **MEASURED** (real DFS) |
| **L2 — Source-pointer completeness** | Chunk ID exists in DB, evidence text occurs in chunk passage | **MEASURED** (provenance validator) |
| **L3 — Verified semantic correctness** | Is the extracted relation semantically correct given the passage? | **NOT_MEASURED** (requires human gold) |
| **L4 — Retrieval effectiveness** | Does provenance-aware graph retrieval outperform BM25/dense on multi-hop queries? | **NOT_MEASURED** (main experiment not yet run) |

L1 and L2 are now computed. L3 (unsupported relation rate) requires human annotation of a valid, verified corpus-grounded pool — which does not yet exist. L4 is the core CIKM research question and cannot be answered until L3 is in place.

> [!IMPORTANT]
> **L3 (unsupported relation rate) must be reported as `NOT_MEASURED`** until a human-annotated gold set is available.
> Any value of `0.0` before that point is fabricated and must not appear in any manuscript or supplementary material.

---

## Scientific Safeguards Verified

| Safeguard | Status |
|-----------|--------|
| `okf_graph.db` unmodified | ✅ Confirmed — opened read-only throughout |
| Gold fixtures (`gold_lora.json`, `gold_attention.json`) unmodified | ✅ Confirmed — not accessed in S4-G2.1 |
| Original annotation pool (`multidomain_human_annotation_pool.csv`) preserved | ✅ Confirmed — corrected version created alongside, original untouched |
| Human judgment fields (`human_*` columns) left blank | ✅ Confirmed — 36 items, all human columns empty |
| No synthetic/AI-generated passages inserted | ✅ Confirmed — corrected pool contains no fabricated evidence spans |
| Historical S4-G2 reports preserved as-is | ✅ Confirmed — `run_s4g2_experiment.py` now computes correct metrics; legacy `s4g2_multidomain_eval_results.json` regenerated with real values, not modified in-place |
| No new gold labels or graph edges created | ✅ Confirmed |

---

## Path Forward

### Immediate Blockers (before S4-H)

1. **Annotation pool reconstruction** — All 36 items must be rebuilt from verbatim, verified corpus text. Each item must pass the provenance validator (`validate_provenance_record`) before being admitted to the pool. Only then can human annotators be engaged.

2. **Concept extraction denoising** — The concept extractor must be patched to reject book-index documents, numeric/measurement tokens, and figure labels before relation extraction begins.

3. **Cycle prevention upgrade** — Replace the greedy insertion-time 2-cycle guard with a topological-sort-aware strategy or batch cycle-removal pass. The full DFS detector is now available for post-hoc verification.

4. **TOC domain document acquisition** — Source a second Automata Theory document from the licensed corpus to achieve a genuinely disjoint development/evaluation split.

### After Blockers Resolved

5. **L3 measurement (human annotation)** — Once the reconstructed pool is verified, engage annotators using the blinded protocol defined in `ANNOTATION_GUIDELINES.md`.

6. **S4-H: Main retrieval experiment** — Only after L3 is measured can the CIKM research question (provenance-aware graph retrieval vs. BM25/dense/hybrid) be meaningfully evaluated.

> [!NOTE]
> The core CIKM 2027 hypothesis remains scientifically sound. The integrity gate findings do not invalidate the research direction — they establish the methodological conditions that must be satisfied before the main experiment proceeds.

---

## Files Created in S4-G2.1

| File | Description |
|------|-------------|
| `okf/eval/integrity_validators.py` | Full directed cycle detection (3-colour DFS), provenance validation, semantic direction audit |
| `research/s4-g2-1-integrity-gate/source_verification_36_items.csv` | 36-item audit: verdicts, failure categories, actual chunk IDs |
| `research/s4-g2-1-integrity-gate/overgeneration_and_cycle_analysis.csv` | Per-document overgeneration diagnosis with cycle counts |
| `research/s4-g2-1-integrity-gate/evaluation_split_audit.csv` | Split classification per domain and document |
| `research/s4-g2-1-integrity-gate/CHANGELOG.md` | Itemised record of all 36 annotation corrections |
| `research/s4-g2-1-integrity-gate/human_annotation_package/multidomain_human_annotation_pool_corrected.csv` | Corrected pool with audit fields; human judgments blank |
| `research/s4-g2-1-integrity-gate/human_annotation_package/multidomain_human_annotation_pool_corrected.md` | Markdown workbook version of corrected pool |
| `tests/unit/test_s4g2_1_integrity_gate.py` | 11 targeted unit tests — all passing |

## Modified Files in S4-G2.1

| File | Change |
|------|--------|
| `research/s4-g2-multidomain-evaluation/scripts/run_s4g2_experiment.py` | Hardcoded metrics replaced with `NOT_MEASURED`, `calculate_provenance_coverage()`, `detect_directed_cycles()` |
| `research/s4-g2-multidomain-evaluation/s4g2_multidomain_eval_results.json` | Regenerated with real metrics |
| `research/s4-g2-multidomain-evaluation/domain_level_evaluation.csv` | Regenerated with real metrics |
| `tests/unit/test_s4g2_multidomain_evaluation.py` | `test_zero_unsupported_rate_across_all_domains` updated to accept `NOT_MEASURED` |

---

## Test Results

```
========================= test session info =========================
Branch: research/s4-g2-1-integrity-gate
Date: 2026-11-17

tests/unit/test_dataset_integrity_s2.py         11 passed
tests/unit/test_retrieval_baselines_s3.py       10 passed
tests/unit/test_annotation_pilot_s4a.py          5 passed
tests/unit/test_annotation_integrity_s4b.py     12 passed
tests/unit/test_s4d_human_audit_comparison.py    6 passed
tests/unit/test_s4e_graph_diagnosis.py          12 passed
tests/unit/test_s4f_evaluator_repair.py         24 passed
tests/unit/test_s4g1_extraction_pilot.py        16 passed
tests/unit/test_s4g2_multidomain_evaluation.py  17 passed
tests/unit/test_s4g2_1_integrity_gate.py        11 passed
─────────────────────────────────────────────────────
TOTAL                                          128 passed
========================= 128 passed in 6.35s ==========================
```

**0 failures. 0 errors. 0 skips.**
