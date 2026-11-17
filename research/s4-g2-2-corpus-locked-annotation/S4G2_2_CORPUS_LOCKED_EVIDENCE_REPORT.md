# S4-G2.2 — Corpus-Locked Annotation Reconstruction: Report

**Branch:** `research/s4-g2-2-corpus-locked-annotation`  
**Base Branch:** `research/s4-g2-1-integrity-gate`  
**Base Commit:** `2147ececc3f7c09b4717381c23d5979548af97b7`  
**Date:** 2026-11-17  
**Status:** COMPLETE — 24-item mechanically verified annotation candidate pool constructed and validated.

---

## Executive Summary

S4-G2.2 constructs the first scientifically valid annotation candidate pool for the Archipelago multi-domain academic knowledge graph project. All 24 items are:

- **Directly queried from the frozen `okf_graph.db` corpus** — no synthetic text, no paraphrases.
- **Verified through the hardened 5-layer provenance validator** — every item has an existing document, an existing linked chunk, a correct page number, and a verbatim evidence match (EXACT).
- **Unlabeled** — `label_category = CANDIDATE_UNLABELED`, `human_relation_label = ""` for all items. Candidate categories (`POSSIBLE_RELATION`, `AMBIGUOUS`) are annotation task guidance, not verified ground truth.
- **Distinct from the 36 invalid S4-G2 items** — no original items reused; original pool preserved.

> [!IMPORTANT]
> These 24 items are **annotation candidates**, not a finished gold set. The next step is engaging independent human annotators with the blinded annotation protocol (`ANNOTATION_GUIDELINES.md`).

**Test suite:** 168/168 passing across S1–S4-G2.2.

---

## Phase A — Hardened Integrity Validators

### What Changed vs S4-G2.1

The `validate_edge_provenance()` function has been fully replaced by the hardened `validate_provenance_record()` with five explicit validation layers:

| Layer | What it checks | Failure behavior |
|-------|---------------|-----------------|
| **L0** | `claimed_doc_id` and `claimed_chunk_id` are non-empty strings | Returns immediately |
| **L1** | Document exists in DB (`Document.id` exact match) | Returns; chunk/evidence not checked |
| **L2** | Chunk linked to that exact document (`chunk_id` field match) | `actual_chunk_id=None` — NEVER substitutes claimed ID |
| **L3** | `claimed_page_number` matches `c.page_number` (advisory) | Flagged in `failure_layers`; does not block `is_valid` |
| **L4** | Evidence text occurs in chunk text (EXACT or WHITESPACE_NORMALIZED) | Blocks `is_valid` |

### Key Hardening Details

**L2 null-substitution invariant:** When a chunk lookup fails, `actual_chunk_id` is set to `None`. The claimed chunk ID is never echoed back as though it were verified. This was the root cause of the DBMS `chunk_001` multi-page conflict in S4-G2 — three different items all claimed `chunk_001` with different page numbers, and no validator caught it because the lookup silently fell back.

**L4 evidence classification:**

| Match Type | Valid for Admission? | Description |
|-----------|--------------------|-----------:|
| `EXACT` | ✅ Yes | Verbatim substring of chunk text |
| `WHITESPACE_NORMALIZED` | ✅ Yes | Matches after collapsing whitespace/unicode |
| `APPROXIMATE` | ❌ No | Trigram Jaccard ≥ 0.80 — likely paraphrase |
| `FAILED` | ❌ No | No match found |
| `INVALID_EVIDENCE` | ❌ No | Empty or punctuation-only after normalization |

Punctuation-only and empty strings are explicitly rejected — they cannot match any real passage.

**L5 (conceptual):** `semantic_support = "NOT_MEASURED"` and `redistribution_permitted = "UNKNOWN"` are always returned. These require independent human annotation and per-document licensing audit respectively.

### Adversarial Tests (40 new, all passing)

| Test Class | Tests | Adversarial Scenarios |
|-----------|-------|-----------------------|
| `TestNormalizeText` | 4 | Whitespace, empty, punctuation-only, Unicode NFC |
| `TestClassifyEvidenceMatch` | 7 | Exact, normalized, failed, approximate, empty, punctuation-only, admission gate |
| `TestValidateProvenanceRecordAdversarial` | 12 | Absent doc, wrong chunk ID, wrong page (advisory), fabricated evidence, paraphrase, empty evidence, punctuation-only, verbatim passes, DBMS chunk_001 null-substitution, semantic_support=NOT_MEASURED, L0 empty doc_id |
| `TestDetectDirectedCycles` | 9 | DAG, 2-cycle, 3-cycle, overlapping cycles, method field, edge type filter, determinism, nodes_in_cycles, self-loop guard |
| `TestChunkFingerprint` | 3 | 16-hex-char, deterministic, different texts |
| `TestAnnotationCandidatePool` | 5 | CSV exists, count in 12–24, all EXACT match, all UNLABELED, C22- ID convention |

---

## Phase B — Corrected Cycle Detection Terminology

### Problem

S4-G2.1 reported `detect_directed_cycles()` as finding "all directed elementary cycles". This was incorrect. The DFS back-edge enumeration finds **representative cycles** — one per distinct back-edge encountered. In graphs with overlapping cycles (e.g., two triangles sharing an edge), DFS may find fewer cycles than Johnson's algorithm would.

### Corrections Applied

The `detect_directed_cycles()` function now explicitly documents its method:

```python
"method": "DFS back-edge enumeration with minimum-rotation deduplication",
"methodological_note": (
    "cycle_count reports representative back-edge cycles, NOT the complete "
    "set of elementary cycles. Use Johnson's algorithm for exact elementary "
    "cycle enumeration. has_cycles is reliable; cycle_count may undercount "
    "in graphs with overlapping cycles."
),
```

**What is reliable:** `has_cycles` (existence detection) is always correct — if any directed cycle exists, DFS will find at least one back-edge.

**What is not reliable:** `cycle_count` as a precise count of elementary cycles. In manuscripts, report `cycle_count` as "at least N representative cycles detected via DFS back-edge enumeration, with possible undercount in dense subgraphs."

### Historical Results (Corrected Note)

| Document | Reported cycle_count | Correct interpretation |
|----------|---------------------|----------------------|
| `Hu2021_LoRA.pdf` | 24 | ≥24 representative prereq cycles (DFS back-edge); actual elementary count may be higher |
| `Bahdanau2014_Attention.pdf` | 18 | ≥18 representative prereq cycles |
| `Real-time network security...pdf` | 8 | ≥8 representative prereq cycles |
| `Vaswani2017`, `BERT`, `TOC`, `OS`, `DBMS` | 0 | 0 cycles (reliable — DAG confirmed for prereq subgraph) |

---

## Phase C — Corpus-Locked Annotation Candidates

### Construction Method

1. **Targeted chunk selection:** Specific chunk IDs were identified per document from earlier corpus probes — skipping cover, author list, and abstract-only chunks in favour of method and results sections.

2. **Evidence span extraction:** For each concept pair, `find_evidence_span()` locates both concepts in the chunk text, then expands to the nearest sentence boundaries. The resulting span is a verbatim contiguous substring of the chunk's `text_passage`.

3. **Provenance gate:** Every candidate is passed through `validate_provenance_record()` before admission. Any candidate where the evidence span is not EXACT or WHITESPACE_NORMALIZED is rejected.

4. **Concept grounding:** Concepts are chosen from terms that appear in the evidence span (case-insensitive). They are not generated from general knowledge.

### Pool Statistics

| Metric | Value |
|--------|-------|
| Total candidates | **24** |
| Rejected specs | 0 |
| Evidence match type | 24/24 EXACT |
| Domains | OS (5), AIML (11), NETS+NETS_DEV (4), TOC (2), DBMS (1), COMPILERS (1) |
| Candidate categories | POSSIBLE_RELATION: 23, AMBIGUOUS: 1, LIKELY_UNRELATED: 0 |
| Human labels generated | **None** — all CANDIDATE_UNLABELED |

### Sample Items

| Item ID | Domain | Concept A | Concept B | Chunk | Match |
|---------|--------|-----------|-----------|-------|-------|
| C22-OS-03 | OS | paging | segmentation | `paging_seed_001` | EXACT |
| C22-AIML-01 | AIML | Transformer | attention mechanism | `chunk_005` | EXACT |
| C22-AIML-04 | AIML | multi-head self-attention | feed-forward network | `chunk_009` | EXACT |
| C22-AIML-05 | AIML | Scaled Dot-Product Attention | Multi-Head Attention | `chunk_010` | EXACT |
| C22-AIML-06 | AIML | LoRA | low-rank matrices | `chunk_005` | EXACT |
| C22-NETS-01 | NETS | anomaly detection | signature-based systems | `chunk_006` | EXACT |
| C22-NETS-02 | NETS | Graph Neural Networks | D-MAGIC | `chunk_008` | EXACT |
| C22-DBMS-01 | DBMS | Relational Algebra | query language | `doc_..._p145_1` | EXACT |
| C22-COMPILERS-01 | COMPILERS | parser | context-free grammar | `doc_..._p192_1` | EXACT |

> [!NOTE]
> Evidence spans are stored in `annotation_candidates_verified.csv` with exact text offsets
> and SHA-256 chunk fingerprints. Do not publish verbatim evidence spans from
> copyrighted documents (Elsevier, Addison-Wesley) in public materials —
> publish only item IDs, offsets, and fingerprints.

---

## Phase D — Evaluation Independence

### Domain Eligibility Decisions

| Domain | Decision | Rationale |
|--------|----------|-----------|
| OS | ELIGIBLE | 3 OSTEP chapters; CC BY-NC-ND; document-disjoint split |
| AIML | ELIGIBLE | Multiple arXiv papers; rich concept density; held-out Devlin2018_BERT not used in pool |
| NETS | ELIGIBLE | 2 documents; document-disjoint; copyrighted publisher paper restricted to offsets |
| TOC | EXPLORATORY | Single document, within-document chunk split; Willard2023 is NOT classical automata |
| DBMS | EXPLORATORY | Only 2 real chunks; insufficient for multi-item eval |
| COMPILERS | EXPLORATORY | Only 1 chunk; diagnostic value only |
| STAT | EXCLUDED | Book index cross-product; sparse appendix |
| DSA, SE, InfoSec, CoArch, Math | EXCLUDED | No eligible prose documents |

### Split Integrity

- **5 eligible documents** use strictly document-disjoint splits.
- **TOC** is WITHIN_DOCUMENT_CHUNK_SPLIT — documented and excluded from held-out evaluation denominators.
- **Book indices** (`data_science_2019/Index_2019_Data-Science.pdf`, etc.) are excluded from all relation extraction.
- **`upload_*` documents** are excluded — unknown provenance.
- **`doc_*` catalog entries** (single chunks from Elmasri, Dragon Book, Tanenbaum) contribute at most 1 exploratory candidate each.

### Extractor Denoising (Identified — Not Yet Implemented)

The following denoising rules are required before scaling the extraction pipeline:

1. Reject documents of type `book_index`, `bibliography_only`, `appendix_sparse`.
2. Reject concept tokens matching: pure numerics, measurement units (`128KB`, `10ms`), figure labels (`Figure 1`, `Table 2`), all-caps abbreviations without at least 2 lowercase chars.
3. Require concept-trigger-concept within the same syntactic clause, not merely the same passage window.
4. Replace greedy 2-cycle insertion guard with batch post-processing topological sort.

---

## Phase E — Reproducibility

### File Inventory

| File | Description |
|------|-------------|
| `okf/eval/integrity_validators.py` | Hardened validators (5-layer, v2) + backward-compat alias |
| `research/s4-g2-2-corpus-locked-annotation/scripts/build_corpus_locked_candidates.py` | Targeted candidate builder (v2) |
| `research/s4-g2-2-corpus-locked-annotation/annotation_candidates/annotation_candidates_verified.csv` | 24-item verified pool with offsets and fingerprints |
| `research/s4-g2-2-corpus-locked-annotation/annotation_candidates/candidate_pool_summary.json` | Pool statistics and eligibility matrix |
| `research/s4-g2-2-corpus-locked-annotation/domain_audit/domain_eligibility_and_split_report.md` | Domain eligibility and split classification |
| `tests/unit/test_s4g2_2_corpus_locked_annotation.py` | 40 adversarial and regression tests |

### Test Results

```
========================= test session info =========================
Branch: research/s4-g2-2-corpus-locked-annotation
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
tests/unit/test_s4g2_2_corpus_locked_annotation.py  40 passed
─────────────────────────────────────────────────────
TOTAL                                          164 passed  (+ 4 compat tests = 168)
========================= 168 passed in 6.53s ==========================
```

**0 failures. 0 errors. 0 skips.**

---

## Scientific Safeguards Verified

| Safeguard | Status |
|-----------|--------|
| `okf_graph.db` unmodified | ✅ Read-only throughout |
| Gold fixtures (`gold_lora.json`, `gold_attention.json`) unmodified | ✅ Not accessed |
| Original S4-G2 annotation pool preserved | ✅ This pool is entirely new (C22- IDs) |
| Human judgment fields blank | ✅ All 24 items have empty human label columns |
| No synthetic/AI-generated passages | ✅ All spans are verbatim corpus substrings |
| No new graph edges or concepts added to production DB | ✅ Confirmed |
| Candidate categories ≠ verified labels | ✅ Explicitly documented in schema and summary JSON |

---

## STOP Confirmation

S4-G2.2 is complete. The main retrieval experiment (S4-H) remains blocked until:

1. **Human annotators label the 24-item pool** using the blinded protocol (`ANNOTATION_GUIDELINES.md`).
2. **Concept extractor denoising** applied (book-index reject, numeric/figure token filter, clause-scoped trigger matching).
3. **Cycle prevention upgraded** (topological-sort-aware insertion replacing greedy 2-cycle guard).
4. **TOC domain** acquires a second genuinely independent document for a disjoint split.

Do not begin human annotation with the original 36-item pool — that pool is classified 36/36 MISMATCH and cannot be used.
