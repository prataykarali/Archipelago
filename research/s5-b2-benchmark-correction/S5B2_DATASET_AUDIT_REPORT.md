# S5-B2 — Investigator-Audited Benchmark Correction Report

**Branch:** `research/s5-b2-benchmark-correction`  
**Base Commit:** `c9d5a9f332a169a1f95ebe577054bfca43c6eb48` (`research/s5-b1-1-annotation-readiness`)  
**Proposed Dataset Version:** `s5b2_proposed_v2.0_pending_approval`  
**Date:** 2026-11-18  
**Status:** PROPOSED — STOP CHECKPOINT (Pending Investigator Approval)

---

## 1. Preservation of Frozen S5-B1.1 Baseline

The frozen S5-B1.1 pilot (`research/s5-b1-integrity-repair/`), its 713-passage corpus (`s5a_eval_corpus_v1` across 53 documents), its 31 original candidate pairs, and all S5-B1.1 reports and scripts are preserved **completely unmodified**. All S5-B2 audit outputs and proposed dataset artifacts reside separately under `research/s5-b2-benchmark-correction/` and Git-ignored `data/annotation_local/s5b2/`.

---

## 2. Query Evidence Matrix (All 12 Audited Queries)

Full verbatim passage excerpts for all S5-B1 and proposed S5-B2 candidates are stored in local access-controlled, Git-ignored storage: `data/annotation_local/s5b2/s5b2_query_evidence_matrix_local.md`.

| Query ID | Original Question (Abbreviated) | S5-B1 Candidate IDs | Evidence Sufficiency | Hop Requirement | Elsewhere in 713 Corpus? | Decision | Justification |
|---|---|---|---|---|---|---|---|
| **Q-S5A-01** | What is an address space and why does the OS provide it? | `06_address_spaces::virtual_memory_seed_003`, `06_address_spaces::paging_seed_005`, `08_paging::paging_seed_002` | Sufficient (`virtual_memory_seed_003` defines address space; `paging_seed_005` explains time-sharing motivation) | `SINGLE_HOP` / 2-passage | `False` | **KEEP** | Retained unchanged per investigator audit. |
| **Q-S5A-02** | How does hardware-based address translation use base and bounds registers...? | `08_paging::paging_seed_001`, `06_address_spaces::paging_seed_004`, `07_address_translation::virtual_memory_seed_004` | **Insufficient for original wording** (0 occurrences of `base and bounds`, `bounds register`, `dynamic relocation`). **Sufficient for revised wording** via `virtual_memory_seed_004` + `virtual_memory_seed_005`. | `TWO_HOP` (within `07_address_translation.pdf`) | `False` | **REVISE** | Exhaustive corpus search confirms base-and-bounds pages were not extracted in `07_address_translation.pdf` (only pp. 1–2 exist). Revise question to match extracted LDE + hardware address translation text and add `virtual_memory_seed_005`. |
| **Q-S5A-03** | Exact multi-level page table walk latency in nanoseconds for ARM Cortex-A78? | `08_paging::paging_seed_003`, `08_paging::paging_seed_001` | Unanswerable in corpus (0 hits for `cortex`, `a78`, `nanosecond`, `walk latency`, `multi-level page`) | `NEGATIVE_CONTROL` | `False` | **KEEP** | Verified corpus-unanswerable negative control (valid microarchitecture, absent from 713-passage corpus). |
| **Q-S5A-04** | Computational formula for Scaled Dot-Product Attention? | `vaswani2017::chunk_010`, `bahdanau2014::chunk_005` | **Missing in S5-B1 pool** (`chunk_010` only has heading); **Complete in corpus** at `vaswani2017::chunk_011` (p.4) | `SINGLE_HOP` | `True` (`chunk_011`) | **REVISE** | Add `vaswani2017::chunk_011` containing `Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V`. |
| **Q-S5A-05** | How does Multi-Head Attention combine multiple Scaled Dot-Product Attention projections...? | `vaswani2017::chunk_011`, `vaswani2017::chunk_010`, `devlin2018::chunk_003` | **Missing in S5-B1 pool** (`chunk_010`/`011` lack MultiHead equation); **Complete in corpus** via `vaswani2017::chunk_011` + `chunk_012` (p.5) | `TWO_HOP` (same-doc: `chunk_011` + `chunk_012`) | `True` (`chunk_012`) | **REVISE** | Replace `chunk_010` with `vaswani2017::chunk_012`, which defines `MultiHead(Q,K,V)=Concat(head_1..head_h)W^O` and projection matrices. |
| **Q-S5A-06** | How does LoRA freeze pre-trained Transformer weights while training rank decomposition matrices? | `dettmers2023::chunk_005`, `vaswani2017::chunk_007`, `hu2021_lora::chunk_005` | Sufficient in `hu2021_lora::chunk_005` alone (`vaswani2017::chunk_007` does not define `W_q, W_k, W_v`) | `SINGLE_HOP` (reclassified from `CROSS_DOCUMENT`) | `True` | **REVISE** | Reclassify to `SINGLE_HOP` and drop artificially forced `vaswani2017::chunk_007`. |
| **Q-S5A-07** | How does QLoRA combine 4-bit NormalFloat quantization with LoRA adapters to reduce GPU memory? | `dettmers2023::chunk_005`, `hu2021_lora::chunk_005`, `vaswani2017::chunk_008` | Sufficient in single passage `dettmers2023_qlora::chunk_005` (NF4, Double Quantization, Paged Optimizers, LoRA adapters) | `SINGLE_HOP` (reclassified from `CROSS_DOCUMENT`) | `True` | **REVISE** | Reclassify to `SINGLE_HOP` and drop artificially forced `hu2021_lora::chunk_005`. |
| **Q-S5A-08** | Total dollar cost in electric utility bills for training LLaMA-3 405B on 16,000 H100 GPUs? | `dettmers2023::chunk_006`, `brown2020::chunk_029` | Unanswerable in corpus (0 hits for `llama-3`, `405b`, `h100`, `16,000`, `dollar`, `electricity`) | `NEGATIVE_CONTROL` | `False` | **KEEP** | Verified corpus-unanswerable negative control; also carries an unsupported factual premise (utility bills unreported). |
| **Q-S5A-09** | Primary architectural layers defined in the OSI Reference Model? | `real-time network security::chunk_002`, `doc_computer_networks_6_e::doc_computer_networks_6_e_p42_1` | **Truncated/Incomplete**: `p42_1` is 285 chars, cuts off mid-word at Layer 2 (`facility in`); Layers 3–7 absent from DB | `HOLD` (ingestion defect) | `False` | **HOLD** | Source textbook stub truncated at 285 chars; Layers 3–7 do not exist in `okf_graph.db`. Hold/exclude from answerable scoring. |
| **Q-S5A-10** | How does dynamic graph modeling with GNNs address latency limitations of traditional signature-based NIDS? | `real-time network security::chunk_005`, `doc_computer_networks_6_e::p198_2`, `real-time network security::chunk_008` | Sufficient (`chunk_005`: batch latency + zero-day gap; `chunk_008`: D-MAGIC/SAGA GNNs + packet-by-packet real-time detection) | `TWO_HOP` (same-document synthesis) | `True` | **KEEP** | Legitimate same-document two-passage synthesis (`chunk_005` + `chunk_008`) within Simhon et al. (2026). |
| **Q-S5A-11** | Exact firmware vulnerability CVE for Cisco Catalyst 9300 switch buffer overflow in 2025? | `doc_computer_networks_6_e::p198_2`, `real-time network security::chunk_006` | Unanswerable in corpus (0 hits for `cisco`, `9300`, `cve-`, `buffer overflow`, `firmware`; 1 unrelated biochemistry hit for `catalyst`) | `NEGATIVE_CONTROL` | `False` | **KEEP** | Verified corpus-unanswerable negative control with an unverified/synthetic 2025 CVE premise. |
| **Q-S5A-12** | How does Third Normal Form (3NF) eliminate transitive dependencies? | `willard2023::chunk_005`, `doc_fundamentals_of_database_system_7e::p145_1`, `pilot/silberschatz_3nf_card.txt::third_normal_form_seed_001` | **Provenance defect**: sole 3NF passage is a constructed pilot card; `p145_1` omits 3NF and functional dependencies | `HOLD` (provenance defect) | `False` | **HOLD** | `pilot/silberschatz_3nf_card.txt` is a constructed pilot shelf card, not PDF-extracted evidence; `TWO_HOP` was artificially forced. |

---

## 3. Provenance Audit: `pilot/silberschatz_3nf_card.txt`

Inspection of `scripts/ops/seed_soference_catalog.py` (lines 120–155) confirms `pilot/silberschatz_3nf_card.txt::third_normal_form_seed_001` is a **constructed pilot answer card**, not source-derived PDF extraction:
- Defined inline under `"hand_chunks"` with `"pdfs": []` and shelf status `"available (pilot shelf seed)"`.
- Length: 363 characters; it is the **only** passage in the entire 713-passage corpus containing `third normal form`, `3nf`, `transitive`, `functional dependency`, `superkey`, or `prime attribute`.
- Recorded in [s5b2_silberschatz_provenance_audit.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_silberschatz_provenance_audit.json).

---

## 4. Corpus-Wide Negative-Control Audit (Q03, Q08, Q11)

Exhaustive regex search across all 713 passages ([s5b2_negative_control_audit.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_negative_control_audit.json)):
- **Q-S5A-03 (Verified Corpus-Unanswerable):** `cortex`: 0, `a78`: 0, `nanosecond`: 0, `walk latency`: 0, `multi-level page`: 0 (`arm`: 5 unrelated NLP/RL hits).
- **Q-S5A-08 (Verified Corpus-Unanswerable + Unsupported Factual Premise):** `llama-3`: 0, `llama 3`: 0, `405b`: 0, `h100`: 0, `16,000`: 0, `dollar`: 0, `electricity`: 0 (`utility`: 4 unrelated hits).
- **Q-S5A-11 (Verified Corpus-Unanswerable + Unsupported Factual Premise):** `cisco`: 0, `9300`: 0, `cve-`: 0, `buffer overflow`: 0, `firmware`: 0 (`catalyst`: 1 unrelated hit in `doc_lehninger_principles_of_biochemistry`).

---

## 5. Evaluation-Pool Coverage Against Frozen Top-K Outputs

Comparison of the 31-pair S5-B1.1 candidate pool against retrieved top-5 and top-10 outputs across all 6 frozen systems in `retrieval_technical_evaluation_report.json` ([s5b2_topk_pool_coverage_audit.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_topk_pool_coverage_audit.json)):

| Frozen System | Top-5 In-Pool Coverage | Top-5 Unjudged Pairs | Top-10 In-Pool Coverage | Top-10 Unjudged Pairs |
|---|---:|---:|---:|---:|
| `bm25` | 12 / 60 (20.0%) | 48 | 16 / 120 (13.3%) | 104 |
| `dense_snowflake_arctic_768d` | 13 / 60 (21.7%) | 47 | 15 / 120 (12.5%) | 105 |
| `hybrid_rrf_e2e` | 14 / 60 (23.3%) | 46 | 16 / 120 (13.3%) | 104 |
| `baseline_graph_1hop` | 4 / 44 (9.1%) | 40 | 8 / 80 (10.0%) | 72 |
| `repaired_graph_1hop_ablation` | 8 / 60 (13.3%) | 52 | 10 / 120 (8.3%) | 110 |
| `repaired_graph_2hop_full` | 7 / 60 (11.7%) | 53 | 9 / 120 (7.5%) | 111 |

Across all 6 systems, there are **138 unique unjudged `(query_id, passage_id)` pairs at top-5** and **277 at top-10**. **Policy:** Unjudged passages are NOT treated as irrelevant, and final Recall@k, MRR, and nDCG are NOT computed from incomplete judgments.

---

## 6. Proposed Corrected Blinded Package & Corpus-Coverage Weaknesses

- **Proposed Package (`s5b2_proposed_v2.0_pending_approval`):** 10 active queries, 25 randomized candidate pairs (`seed = 20261119`), neutral IDs `S5B2-PAIR-001`..`S5B2-PAIR-025`, zero `category`/role hints:
  - [retrieval_query_candidate_pool_blinded.csv](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package/retrieval_query_candidate_pool_blinded.csv)
  - [retrieval_query_pool_blinded.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package/retrieval_query_pool_blinded.json)
  - [RETRIEVAL_ANNOTATION_PROTOCOL.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package/RETRIEVAL_ANNOTATION_PROTOCOL.md)
  - Separate local Reviewer A (`data/annotation_local/s5b2/reviewer_a_s5b2_workbook.md`) and Reviewer B (`data/annotation_local/s5b2/reviewer_b_s5b2_workbook.md`) workbooks.
- **Unresolved Corpus-Coverage Weaknesses:**
  1. Textbook `doc_*` entries in `okf_graph.db` are ~300-char truncated stubs (causing Q09's missing OSI Layers 3–7 and Q12's lack of extracted 3NF text).
  2. OSTEP chapters in `okf_graph.db` only contain 2–3 seed chunks each (missing base-and-bounds pages in `07_address_translation.pdf`).
  3. Top-k pool coverage (7.5%–23.3%) means S5-C evaluation will require either condensed-list metrics (`bpref`/in-pool judging) or pooled top-k annotation after investigator approval.

---

## ⛔ STOP CHECKPOINT

**S5-B2 proposed artifacts are complete.** Investigator approval is required before freezing `s5b2_proposed_v2.0_pending_approval` or distributing workbooks to independent reviewers.
