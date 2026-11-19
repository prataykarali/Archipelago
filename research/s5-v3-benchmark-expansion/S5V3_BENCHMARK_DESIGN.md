# S5-v3 Module C — Proposed Query Benchmark Design

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-benchmark-expansion`  
**Proposed Manifest (metadata-only):** [s5v3_query_benchmark_proposed.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/manifests/s5v3_query_benchmark_proposed.json)  
**Manifest SHA-256:** `17914918ac1355a8e4768cf0fc57629c85d43630d244bbfee3f004a5c611c153`  
**Corpus v3 JSONL (Git-ignored):** `data/annotation_local/s5v3/corpus_v3/s5v3_corpus_passages.jsonl` (`dd8e973b727a981aeb4b8d0109513616c4ea709afe3eed40bde5c8b14ebeaee4`, `858` passages / `818` usable)  
**Provenance Status:** `AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION`  
**Answerability Status:** `CANDIDATE_UNVERIFIED_REQUIRES_HUMAN_AUDIT`

> [!IMPORTANT]
> **Candidate Generation != Human Validation.** Every query in `s5v3_query_benchmark_proposed.json` is an AI-proposed candidate grounded programmatically against Corpus v3 passage IDs, page ranges, and SHA-256 digests. **Zero** queries may enter the final evaluated S5-v3 benchmark until independent human assessors verify answerability, passage grounding, multi-passage/cross-document necessity, and negative-control absence.

---

## 1. Benchmark Scope & Honest Domain Coverage Gap

Corpus v3 currently contains **4** verified open-access local documents (`818` usable non-duplicate passages):

| `source_doc_id` | Document | Domain | Usable Passages | Queries Citing Doc |
|---|---|---|---:|---:|
| `local_oa_001` | Dive into Deep Learning — Ch. 3: Linear Regression (`CC-BY-SA-4.0`) | Machine Learning | 26 | 9 |
| `local_oa_002` | Efficient Guided Generation for LLMs (Willard & Louf, 2023; arXiv:2307.09702v2) | NLP / LLMs | 23 | 9 |
| `local_oa_003` | Mathematics for Machine Learning (Deisenroth, Faisal, Ong) | Math for ML | 719 | 23 |
| `local_oa_004` | METATRON: A Promptable Whole-Body Execution Layer for Humanoids (Tessler et al.) | Robotics / Control | 50 | 9 |

### Deferred CS Domains (`DEFERRED_PENDING_OA_SOURCE_INGESTION`)

Because copyrighted local textbooks (e.g., Elsevier, z-lib) and institutional notes were strictly excluded in Module A, the following core CS domains have **zero** eligible open-access source documents in Corpus v3 and are formally marked **`DEFERRED_PENDING_OA_SOURCE_INGESTION`** in `s5v3_query_benchmark_proposed.json`:

- **Operating Systems** — `DEFERRED_PENDING_OA_SOURCE_INGESTION`
- **Databases** — `DEFERRED_PENDING_OA_SOURCE_INGESTION`
- **Computer Networks** — `DEFERRED_PENDING_OA_SOURCE_INGESTION`
- **Distributed Systems** — `DEFERRED_PENDING_OA_SOURCE_INGESTION`

Positive answerable queries are strictly restricted to the 4 verified OA documents above. Three deferred-domain topics (Raft, PostgreSQL MVCC, TCP BBR, Linux CFS) appear **only** as independently verifiable `negative_control` queries (`answer_exists_in_eligible_corpus: false`), alongside ML/Robotics/LLM-serving negative controls that are also verifiably absent from all 858 Corpus v3 passages.

---

## 2. Query Mixture, Split Allocation & Graph-Anchor Regimes

The proposed benchmark contains **48 queries** partitioned into **16 `dev`** and **32 `test`** queries (1:2 ratio).

### 2.1 Category x Split Breakdown

| Category | `dev` | `test` | Total | Share |
|---|---:|---:|---:|---:|
| `single_passage_fact_concept` | 4 | 8 | **12** | 25.0% |
| `same_doc_multi_passage` | 3 | 7 | **10** | 20.8% |
| `cross_doc_multi_passage` | 3 | 7 | **10** | 20.8% |
| `technical_terminology_paraphrase` | 3 | 5 | **8** | 16.7% |
| `negative_control` | 3 | 5 | **8** | 16.7% |
| **Total** | **16** | **32** | **48** | **100.0%** |

### 2.2 Graph-Anchor Regime Classification

- **Graph Source Note:** `ui/graph/okf_graph.json` is a 99-byte stub (`total_concepts: 1`, `concepts: {}`, `edges: []`). Programmatic graph-anchor classification therefore uses the canonical repository-root [okf_graph.json](file:///home/pratay-karali/Desktop/archipelago/okf_graph.json) (`610` concepts, `1,988` edges, SHA-256 `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76`).
- **Rule:** Whole-phrase normalized matching against concept IDs and concept names (minimum length 4 chars). Queries matching **>= 2** graph concepts are classified `rich`; queries matching **0–1** concepts are classified `sparse`.

| Split | `rich` (>= 2 concepts) | `sparse` (0–1 concepts) | Total |
|---|---:|---:|---:|
| `dev` | 7 | 9 | 16 |
| `test` | 16 | 16 | 32 |
| **Total** | **23** | **25** | **48** |

---

## 3. Leakage Prevention, Provenance & Anti-Contamination Controls

Implemented in [benchmark_v3/](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/scripts/benchmark_v3/) and executed via [build_benchmark_v3.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/scripts/build_benchmark_v3.py):

1. **Corpus Grounding Verification:** Every `supporting_evidence` entry is resolved directly from `s5v3_corpus_passages.jsonl`, verifying exact `passage_id`, `source_doc_id`, `page_start`, `page_end`, and 64-hex `passage_sha256`. All cited passages were additionally verified to have `is_usable == true` and `is_exact_duplicate == false` (`0` unusable, `0` duplicate).
2. **Metadata-Only Public Manifest:** `FORBIDDEN_PUBLIC_TEXT_KEYS` (`text`, `passage_text`, `raw_text`, `chunk_text`, `full_text`) are programmatically forbidden from appearing anywhere in `s5v3_query_benchmark_proposed.json`. Zero raw source text is committed to Git.
3. **Zero Dev/Test Leakage:** `check_dev_test_leakage` enforces:
   - Zero exact duplicate query texts between `dev` and `test`.
   - Zero near-duplicate queries (`content_token Jaccard >= 0.65`) between `dev` and `test`.
   - Zero shared `minimum_required_evidence_set` passage IDs between `dev` and `test`.
4. **Zero S5-v2.1 Query Reuse:** `check_v21_reuse` checks all 48 proposed queries against frozen [s5b2_proposed_blinded_query_specs.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-b2-benchmark-correction/corpus/s5b2_proposed_blinded_query_specs.json) (`0` ID collisions, `0` exact duplicates, `0` paraphrases at `Jaccard >= 0.55`). No v2.1 test judgments were used to tune wording or parameters.
5. **Human-Verification Gate Enforcement:** The validator rejects any manifest that claims human verification (`provenance_status != AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION` or `answerability_verification_status != CANDIDATE_UNVERIFIED_REQUIRES_HUMAN_AUDIT`).

---

## 4. Reproducibility Commands

```bash
# Rebuild and validate the proposed 48-query manifest against Corpus v3
python3 research/s5-v3-benchmark-expansion/scripts/build_benchmark_v3.py

# Validate existing manifest without rewriting
python3 research/s5-v3-benchmark-expansion/scripts/build_benchmark_v3.py --validate-only

# Run Module C unit + live-manifest validation tests
python3 -m pytest tests/unit/test_s5v3_benchmark.py -v
```
