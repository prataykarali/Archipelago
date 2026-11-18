# S5-B2.1 — Approval-Blocker Resolution Report

**Branch:** `research/s5-b2-benchmark-correction`
**Proposed Pooled Package Version:** `s5b2_1_proposed_pooled_v2.1_pending_approval`
**Date:** 2026-11-18
**Status:** PROPOSED — STOP CHECKPOINT (Pending Investigator Approval)

> All tables and counts in this report are generated programmatically from committed JSON artifacts.

---

## 1. Negative-Control Audit (`Q03`, `Q08`, `Q11`)

Removed unconditional `verified_corpus_unanswerable = True`. All three queries carry `adjudication_status = PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` and `human_inspection_status = NOT_YET_PERFORMED` in [s5b2_negative_control_audit.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_negative_control_audit.json).

| Query ID | Exact Target Hits | Alternate Terminology Hits (>0) | Top-5 Dense Semantic Neighbors (`search_selected_candidate_passage_ids`) | Adjudication Status |
|---|---|---|---|---|
| **Q-S5B2-03** | `arm`: 5, `cortex`: 0, `a78`: 0, `nanosecond`: 0, `walk latency`: 0, `multi-level page`: 0 | `cycle`: 2, `latency`: 14 | `papers/dettmers2023_qlora.pdf::chunk_017` (0.3665), `papers/kwon2023_vllm.pdf::chunk_023` (0.328), `papers/kwon2023_vllm.pdf::chunk_013` (0.3249), `papers/kipf2016_gcn.pdf::chunk_019` (0.3205), `papers/edge2024_graphrag.pdf::chunk_031` (0.3202) | `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` |
| **Q-S5B2-08** | `llama-3`: 0, `llama 3`: 0, `405b`: 0, `h100`: 0, `16,000`: 0, `dollar`: 0, `electricity`: 0, `utility`: 4 | `llama`: 11, `training cost`: 5, `$`: 2, `energy`: 8 | `papers/dettmers2023_qlora.pdf::chunk_017` (0.4066), `papers/dettmers2023_qlora.pdf::chunk_004` (0.4001), `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_021` (0.3991), `papers/dettmers2023_qlora.pdf::qlora_seed_002` (0.3781), `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_026` (0.3773) | `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` |
| **Q-S5B2-11** | `cisco`: 0, `catalyst`: 1, `9300`: 0, `cve-`: 0, `buffer overflow`: 0, `firmware`: 0 | `switch`: 9, `exploit`: 9, `2025`: 1 | `papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_027` (0.3573), `papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_051` (0.351), `papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_013` (0.3436), `papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_004` (0.3305), `papers/real-time network security: integrating ann and dynamic graph-based.pdf::chunk_025` (0.3276) | `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` |

---

## 2. Two-Passage Necessity Matrix (`Q02`, `Q05`, `Q10`)

Recorded in [s5b2_1_passage_necessity_matrix.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_passage_necessity_matrix.json):

| Query ID | Passage A Alone? | Passage B Alone? | A + B Jointly? | 2nd Passage Indispensable? | Classification |
|---|---|---|---|---|---|
| **Q-S5B2-02** | No | No | Yes | Yes | **`TWO_HOP`** |
| **Q-S5B2-05** | No | Yes | Yes | No | **`SINGLE_HOP`** |
| **Q-S5B2-10** | No | No | Yes | Yes | **`TWO_HOP`** |

---

## 3. Evaluation-Pool Completeness (6 Frozen Systems × 10 Active Queries)

- **Total unique pooled pairs requiring human judgment:** **254** (deduplicated union of top-10 outputs across 6 frozen systems + 25 investigator-selected pairs, persisted in [s5b2_1_frozen_ranked_results.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_frozen_ranked_results.json)).
- **Per-query pooled counts:** `Q-S5B2-01`: 13, `Q-S5B2-02`: 22, `Q-S5B2-03`: 25, `Q-S5B2-04`: 31, `Q-S5B2-05`: 29, `Q-S5B2-06`: 31, `Q-S5B2-07`: 28, `Q-S5B2-08`: 27, `Q-S5B2-10`: 25, `Q-S5B2-11`: 23

| Frozen System | Investigator-25 Top-5 Coverage | Investigator-25 Top-10 Coverage | Pooled v2.1 Top-5 & Top-10 Coverage |
|---|---:|---:|---:|
| `bm25` | 10/50 (20.0%) | 13/100 (13.0%) | **100.0%** |
| `dense_snowflake_arctic_768d` | 11/50 (22.0%) | 13/100 (13.0%) | **100.0%** |
| `hybrid_rrf_e2e` | 11/50 (22.0%) | 14/100 (14.0%) | **100.0%** |
| `baseline_graph_1hop` | 3/38 (7.89%) | 6/69 (8.7%) | **100.0%** |
| `repaired_graph_1hop_ablation` | 6/50 (12.0%) | 8/100 (8.0%) | **100.0%** |
| `repaired_graph_2hop_full` | 5/50 (10.0%) | 7/100 (7.0%) | **100.0%** |

---

## 4. Corpus Provenance Registry (`s5a_eval_corpus_v1`)

Frozen 713-passage corpus (`s5a_eval_corpus_v1`) preserved unaltered ([s5b2_1_corpus_provenance_registry.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_corpus_provenance_registry.json)):

| Verification Tier | Count |
|---|---:|
| `source_verified_constructed_pilot_card` | 1 |
| `source_verified_truncated_textbook_stub` | 21 |
| `convention_inferred_seed_chunk` | 16 |
| `convention_inferred_paper_or_upload_chunk` | 675 |

---

## ⛔ STOP CHECKPOINT

Stopping pending investigator approval before freezing `s5b2_1_proposed_pooled_v2.1`, distributing reviewer workbooks, computing final metrics, or starting S5-C.
