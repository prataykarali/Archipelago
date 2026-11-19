# S5-v3.1 Stage D — Multi-Domain Proposed Query Candidates

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-1-oa-corpus-expansion-canonical`  
**Proposed Manifest (metadata-only, zero raw text):** [s5v31_query_benchmark_proposed.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_query_benchmark_proposed.json)  
**Manifest SHA-256:** `4c281da97ed2251f8d8603beaa2f92cbfe43cb4930ddfe2f1055ab58de5ee161`  
**Corpus v3.1 JSONL (Git-ignored):** `data/annotation_local/s5v3_1/corpus_v31/s5v31_corpus_passages.jsonl` (`6366477189b8058b3f523a9d6607abb4d2c249351927918d24979e17833937b9`, `1,958` passages across `8` domains)  
**Status:** `AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION` — all categories, necessity claims, and negative-control labels are **`PROVISIONAL_PENDING_HUMAN_VERIFICATION`**.

> [!IMPORTANT]
> **Candidate Generation != Human Validation.** Zero queries in `s5v31_query_benchmark_proposed.json` have been human-validated. No relevance grades exist. The prior S5-v3 48-query manifest (`17914918...`) remains completely untouched.

---

## 1. Relationship to Prior S5-v3 Proposals (`48` Queries)

All `48` prior S5-v3 proposals in `research/s5-v3-benchmark-expansion/manifests/s5v3_query_benchmark_proposed.json` were preserved untouched and audited against Corpus v3.1 (`1,958` passages):

- **40 / 40 positive S5-v3 queries** (`local_oa_001..004`): **100% retained** with exact `passage_id` and `passage_sha256` verification (`0` missing passages, `0` hash mismatches), tracked via `origin_v3_query_id`.
- **4 / 8 S5-v3 negative controls** (`Q-S5V3-15` NVMe/`io_uring`, `Q-S5V3-45` FlashAttention-2, `Q-S5V3-46` Boston Dynamics Atlas, `Q-S5V3-48` vLLM PagedAttention): **retained** after confirming `0` occurrences across all `1,958` Corpus v3.1 passages.
- **4 / 8 S5-v3 deferred-domain negative controls** (`Q-S5V3-14` Raft, `Q-S5V3-16` PostgreSQL MVCC, `Q-S5V3-44` TCP BBR, `Q-S5V3-47` Linux CFS): **retired from v3.1 negative controls** because OS, Databases, Networks, and Distributed Systems are now ingested in Corpus v3.1 (e.g., Kleppmann's `oa_ds_001` covers Raft leader election!). Replaced by `4` freshly verified absent CS negative controls (`eBPF XDP`, `QUIC 0-RTT`, `Spanner TrueTime`, `RocksDB LSM-tree`).
- **+28 new CS-domain queries** (`10 dev`, `18 test`) grounded in the 4 newly ingested OA sources (`oa_os_001`, `oa_db_001`, `oa_net_001`, `oa_ds_001`).

---

## 2. Multi-Domain Breakdown & Split Allocation (`72` Queries)

### 2.1 Split & Category Summary (All Provisional)

| Category (`PROVISIONAL_PENDING_HUMAN_VERIFICATION`) | `dev` | `test` | Total | Share |
|---|---:|---:|---:|---:|
| `single_passage_fact_concept` | 8 | 12 | **20** | 27.8% |
| `same_doc_multi_passage` | 6 | 13 | **19** | 26.4% |
| `cross_doc_multi_passage` | 4 | 10 | **14** | 19.4% |
| `technical_terminology_paraphrase` | 4 | 7 | **11** | 15.3% |
| `negative_control` | 2 | 6 | **8** | 11.1% |
| **Total** | **24** | **48** | **72** | **100.0%** |

### 2.2 Domain & Source-Document Coverage (`8` Active OA Sources)

| `source_doc_id` | Domain | Corpus v3.1 Passages | Queries Citing Doc | Page / Section Provenance |
|---|---|---:|---:|---|
| `local_oa_001` | Machine Learning (D2L Ch.3) | 26 | 9 | Markdown (`page_start=1`) |
| `local_oa_002` | NLP / LLMs (Willard & Louf) | 23 | 9 | Exact PDF pages |
| `local_oa_003` | Math for ML (MML Book) | 719 | 23 | Exact PDF pages |
| `local_oa_004` | Robotics / Control (METATRON) | 50 | 9 | Exact PDF pages |
| `oa_os_001` | Operating Systems (Khokhar & Tran) | 112 | 6 | EPUB `section_ref` (`page_start=null`) |
| `oa_db_001` | Databases (Watt & Eng 2e) | 208 | 8 | LibreTexts `section_ref` (`page_start=null`) |
| `oa_net_001` | Computer Networks (Bonaventure CNP3) | 600 | 6 | Exact PDF pages (`CNP3.pdf`) |
| `oa_ds_001` | Distributed Systems (Kleppmann) | 220 | 8 | LaTeX `section_ref` (`page_start=null`) |

### 2.3 Graph-Anchor Regimes (Canonical `okf_graph.json`, `610` Concepts)

- **`rich` (>= 2 matched graph concepts):** `25` queries (`34.7%`)
- **`sparse` (0–1 matched graph concepts):** `47` queries (`65.3%`)

---

## 3. Programmatic Verification & Anti-Contamination Guarantees

Executed via [build_benchmark_v31.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/scripts/build_benchmark_v31.py) and tested in [test_s5v31_benchmark.py](file:///home/pratay-karali/Desktop/archipelago/tests/unit/test_s5v31_benchmark.py):

1. **Exact Corpus v3.1 Grounding (`0` errors):** Every `passage_id`, `source_doc_id`, `page_start`/`page_end` (preserving `null` for non-PDF sources — zero fabricated page numbers), and 64-hex `passage_sha256` matches `s5v31_corpus_passages.jsonl`.
2. **Zero Dev/Test Leakage:** `0` exact duplicate queries, `0` near-duplicates (`Jaccard >= 0.65`), and `0` shared `minimum_required_evidence_set` passages between `dev` (`24`) and `test` (`48`).
3. **Zero S5-v2.1 Reuse:** `0` ID collisions, `0` exact matches, and `0` paraphrases (`Jaccard >= 0.55`) against frozen `s5b2_proposed_blinded_query_specs.json`.
4. **Shortcut & Necessity Consistency:** All `19` `same_doc_multi_passage` and `14` `cross_doc_multi_passage` queries pass programmatic shortcut/source-count consistency checks (`shortcut_found=false`, `>= 2` distinct sources for cross-doc).
5. **Negative-Control Absence Scan:** All `8` negative controls (`Q-S5V31-14`, `42`, `43`, `44`, `54`, `70`, `71`, `72`) verified `0` real hits across all `1,958` Corpus v3.1 passages.
