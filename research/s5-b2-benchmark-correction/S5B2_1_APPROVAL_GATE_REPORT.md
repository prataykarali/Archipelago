# S5-B2.1 — Approval-Blocker Resolution Report

**Branch:** `research/s5-b2-benchmark-correction`  
**Base Commit:** `39fcfeb622bcfba5e2df8e3a2cbba033687031fc`  
**Proposed Pooled Package Version:** `s5b2_1_proposed_pooled_v2.1_pending_approval`  
**Date:** 2026-11-18  
**Status:** PROPOSED — STOP CHECKPOINT (Pending Investigator Approval)

---

## 1. Negative-Control Audit (`Q03`, `Q08`, `Q11`)

Removed the unconditional `verified_corpus_unanswerable = True` flag. All three queries are now classified as **`PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK`** in [s5b2_negative_control_audit.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_negative_control_audit.json), separating exact-keyword hits, alternate terminology, frozen dense semantic top-5 findings, and inspected passage IDs:

| Query ID | Exact Target Hits | Alternate Terminology Hits | Top-5 Dense Semantic Neighbors Inspected | Adjudication Status |
|---|---|---|---|---|
| **Q-S5B2-03** (`Q03`) | `cortex`: 0, `a78`: 0, `nanosecond`: 0, `walk latency`: 0, `multi-level page`: 0 (`arm`: 5 unrelated) | `latency`: 46, `page table`: 1 (`08_paging::paging_seed_003`), `tlb`: 0, `page walk`: 0 | `08_paging::paging_seed_003` (0.482), `08_paging::paging_seed_001` (0.464), `06_address_spaces::virtual_memory_seed_003` (0.432), `07_address_translation::virtual_memory_seed_005` (0.422), `08_paging::paging_seed_002` (0.421) | `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` |
| **Q-S5B2-08** (`Q08`) | `llama-3`: 0, `405b`: 0, `h100`: 0, `16,000`: 0, `dollar`: 0, `electricity`: 0 | `llama`: 1 (`dettmers2023::chunk_029`), `training cost`: 2, `energy`: 4, `power consumption`: 0 | `brown2020_gpt3::chunk_029` (0.481), `brown2020_gpt3::chunk_004` (0.453), `dettmers2023_qlora::chunk_030` (0.440), `dettmers2023_qlora::chunk_006` (0.425), `brown2020_gpt3::chunk_002` (0.424) | `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` |
| **Q-S5B2-11** (`Q11`) | `cisco`: 0, `9300`: 0, `cve-`: 0, `buffer overflow`: 0, `firmware`: 0 (`catalyst`: 1 biochem hit) | `vulnerability`: 4, `switch`: 4, `exploit`: 4, `2025`: 1 (`real-time network security::chunk_005` submission date) | `real-time network security::chunk_005` (0.409), `chunk_004` (0.405), `chunk_003` (0.371), `chunk_006` (0.369), `chunk_002` (0.364) | `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` |

---

## 2. Two-Passage Necessity Matrix (`Q02`, `Q05`, `Q10`)

Recorded in [s5b2_1_passage_necessity_matrix.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_passage_necessity_matrix.json):

| Query ID | Passage A Alone Sufficient? | Passage B Alone Sufficient? | A + B Jointly Sufficient? | 2nd Passage Indispensable? | Classification | Basis |
|---|---|---|---|---|---|---|
| **Q-S5B2-02** (`07_address_translation`: `seed_004`, `seed_005`) | **No** (LDE goals only; no address translation) | **No** (Address translation only; references LDE without explaining it) | **Yes** | **Yes** | **`TWO_HOP`** | Both passages are required to connect LDE efficiency/control to hardware address translation. |
| **Q-S5B2-05** (`vaswani2017`: `chunk_011`, `chunk_012`) | **No** (Scaled Dot-Product formula only) | **Yes** (`chunk_012` alone defines Multi-Head projections `W_i^Q, W_i^K, W_i^V, W^O` & `Concat`) | **Yes** | **No** | **`SINGLE_HOP`** | Reclassified to `SINGLE_HOP` because `chunk_012` alone answers the question; `chunk_011` retained as supporting context only. |
| **Q-S5B2-10** (`real-time network security`: `chunk_005`, `chunk_008`) | **No** (Traditional NIDS latency + zero-day gap only) | **No** (D-MAGIC/SAGA GNN + packet-by-packet detection; omits traditional batch latency) | **Yes** | **Yes** | **`TWO_HOP`** | Both passages are indispensable (same-document synthesis). |

---

## 3. Evaluation-Pool Completeness (6 Frozen Systems × 10 Active Queries)

Reran all **6 frozen retrieval systems** (zero algorithm/corpus/model/fingerprint changes; verified against `s5b1_model_manifest.json`) on the 10 active v2 queries and built the deduplicated union of top-10 retrieved pairs plus the 25 investigator-selected pairs ([s5b2_1_topk_pool_coverage_refreshed.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_topk_pool_coverage_refreshed.json)):

- **Total unique pairs requiring human judgment:** **265** (up from 25 investigator-only pairs)
- **Per-query pooled counts:** `Q-S5B2-01`: 13, `Q-S5B2-02`: 22, `Q-S5B2-03`: 25, `Q-S5B2-04`: 31, `Q-S5B2-05`: 29, `Q-S5B2-06`: 31, `Q-S5B2-07`: 28, `Q-S5B2-08`: 27, `Q-S5B2-10`: 36, `Q-S5B2-11`: 23.
- **Top-5 & Top-10 coverage comparison:**

| Frozen System | Investigator-25 Top-5 Coverage | Investigator-25 Top-10 Coverage | Pooled v2.1 Top-5 & Top-10 Coverage |
|---|---:|---:|---:|
| `bm25` | 10/50 (20.0%) | 14/100 (14.0%) | **100.0%** |
| `dense_snowflake_arctic_768d` | 12/50 (24.0%) | 13/100 (13.0%) | **100.0%** |
| `hybrid_rrf_e2e` | 12/50 (24.0%) | 14/100 (14.0%) | **100.0%** |
| `baseline_graph_1hop` | 2/38 (5.26%) | 5/69 (7.25%) | **100.0%** |
| `repaired_graph_1hop_ablation` | 5/50 (10.0%) | 7/100 (7.0%) | **100.0%** |
| `repaired_graph_2hop_full` | 4/50 (8.0%) | 6/100 (6.0%) | **100.0%** |

Unjudged passages outside the pool are never treated as irrelevant, and no Recall@k, MRR, or nDCG metrics are computed.

---

## 4. Corpus Provenance Registry (`s5a_eval_corpus_v1`)

The frozen 713-passage corpus (`s5a_eval_corpus_v1`) is **unaltered** and its identifier is preserved ([s5b2_1_corpus_provenance_registry.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_corpus_provenance_registry.json)):

| Provenance Class | Count | Reproducible Evaluation Treatment |
|---|---:|---|
| `PDF_EXTRACTED_PAPER_OR_UPLOAD` | 675 | Admissible primary source literature. |
| `TRUNCATED_TEXTBOOK_STUB` | 21 | Flagged (~277–301 chars across `doc_*` entries). Queries cut off by truncation (`Q-S5A-09`) placed on `HOLD`. |
| `PDF_EXTRACTED_SEED_CHUNK` | 16 | Flagged (899–900 char excerpts from OSTEP/QLoRA/vLLM PDFs). Admissible only when verbatim text suffices without unextracted-page assumptions. |
| `CONSTRUCTED_PILOT_ANSWER_CARD` | 1 | `pilot/silberschatz_3nf_card.txt::third_normal_form_seed_001`. Queries depending on it (`Q-S5A-12`) placed on `HOLD`. Any future corpus exclusion must mint a new corpus version ID. |

---

## 5. Protocol, Claims Boundary & Proposed Complete Reviewer Package

- **No Validated Cross-Document Query:** Documented explicitly in [RETRIEVAL_ANNOTATION_PROTOCOL.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package_v2_1/RETRIEVAL_ANNOTATION_PROTOCOL.md) that this pilot contains **zero** validated cross-document queries; no cross-document gains, broad generalization, or statistical superiority may be claimed.
- **Proposed Complete Blinded Package (`seed = 20261119`, 265 pairs):**
  - [retrieval_query_candidate_pool_blinded.csv](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package_v2_1/retrieval_query_candidate_pool_blinded.csv)
  - [retrieval_query_pool_blinded.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package_v2_1/retrieval_query_pool_blinded.json)
  - [RETRIEVAL_ANNOTATION_PROTOCOL.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package_v2_1/RETRIEVAL_ANNOTATION_PROTOCOL.md)
  - Private Git-ignored Reviewer A & B workbooks (`data/annotation_local/s5b2_1/reviewer_a_s5b2_1_workbook.md`, `reviewer_b_s5b2_1_workbook.md`) and admin pool provenance (`data/annotation_local/s5b2_1/s5b2_1_admin_pool_provenance.json`) — completely free of system identities, investigator judgments, answerability labels, or rationales in reviewer-facing files.

---

## ⛔ STOP CHECKPOINT

Stopping after generating proposed S5-B2.1 artifacts. Investigator approval is required before freezing the dataset, distributing reviewer workbooks, computing final metrics, or starting S5-C.
