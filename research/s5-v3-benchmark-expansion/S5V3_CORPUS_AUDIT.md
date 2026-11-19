# S5-v3 Module B — Corpus v3 Audit & Provenance Report

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-benchmark-expansion`  
**Builder CLI:** [build_corpus_v3.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/scripts/build_corpus_v3.py)  
**Public Metadata-Only Manifest:** [s5v3_corpus_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/manifests/s5v3_corpus_manifest.json)  
**Private Passage JSONL (Git-Ignored):** `data/annotation_local/s5v3/corpus_v3/s5v3_corpus_passages.jsonl`

---

## 1. Executive Summary & Frozen S5-v2.1 Integrity

- **Frozen S5-v2.1 Corpus Status:** The historical 713-passage `okf_graph.db` (`s5a_eval_corpus_v1`) remains **MISSING** as established in [S5V3_REPRODUCIBILITY_REPORT.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/S5V3_REPRODUCIBILITY_REPORT.md). It was **never** repaired, reconstructed, or faked.
- **Corpus v3 Build Summary:** Built deterministically from the **4 verified local open-access sources** inventoried in Module A using PyMuPDF (`fitz` 1.28.0) and a deterministic Markdown parser:
  - **Total Passages:** `858` (`818` usable / `95.3%`, `40` unusable / `4.7%`, `138` flagged / `16.1%`)
  - **Total Volume:** `1,013,758` characters, `174,820` whitespace tokens
  - **Exact Determinism:** Repeated builds produce byte-identical JSONL (`dd8e973b727a981aeb4b8d0109513616c4ea709afe3eed40bde5c8b14ebeaee4`) and byte-identical manifest (`776616220062667bce9d174bc40623e980b5bdb52723dfd4c713fbae9ecfc48b`).
  - **Privacy / Git Hygiene:** Raw passage text is written exclusively to Git-ignored `data/annotation_local/s5v3/corpus_v3/s5v3_corpus_passages.jsonl` (`.gitignore` line 141). The tracked manifest `s5v3_corpus_manifest.json` contains **zero raw passage text**.

---

## 2. Eligible Source Manifest, License & Redistribution Table

Only sources explicitly verified in Module A and passing SHA-256 + eligibility + exclusion guards are ingested:

| Doc ID | Title | Domain | Provenance Class | Format / Pages | License | Redistribution Permission | Source SHA-256 (prefix) | Passages (Usable / Total) |
|---|---|---|---|---:|---|---|---|---:|
| `local_oa_001` | Dive into Deep Learning (D2L) — Ch. 3: Linear Regression | Machine Learning | `markdown_oa_extracted` | MD (1 logical page) | `CC-BY-SA-4.0` | `share_alike_with_attribution` | `39990e2958ef...` | `26 / 27` |
| `local_oa_002` | Efficient Guided Generation for LLMs (Willard & Louf, 2023; arXiv:2307.09702v2) | NLP / LLMs | `pdf_extracted` | PDF (`18` pp) | `arXiv-perpetual-nonexclusive` | `local_research_only_no_republishing` | `8888aa204358...` | `23 / 24` |
| `local_oa_003` | Mathematics for Machine Learning (Deisenroth, Faisal, Ong) | Mathematics for ML | `pdf_extracted` | PDF (`417` pp, `6` blank) | Free online PDF (`mml-book.github.io`; CUP) | `local_research_only_no_republishing` | `3f87b70c64a3...` | `719 / 757` |
| `local_oa_004` | METATRON: A Promptable Whole-Body Execution Layer for Humanoids (Tessler et al.) | Robotics / Control | `pdf_extracted` | PDF (`14` pp) | Preprint (local extraction only) | `local_research_only_no_republishing` | `de2411a21822...` | `50 / 50` |

### Strictly Excluded Sources (Programmatically Enforced)
`validate_source_eligibility` in [extractors.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/scripts/corpus_v3/extractors.py) rejects any source that:
1. Has `eligible=False` or an invalid `provenance_class`.
2. Matches any excluded path substring (`predictive_analytics_and_data_mining`, `z-library`, `z-lib`, `elsevier`, `data/private`, `data/uploads`, `test_upload`, `data/annotation_local/s5c3`).
3. Is smaller than `1,024` bytes (blocks synthetic test stub PDFs).
4. Fails exact SHA-256 verification against its registered digest.

---

## 3. Extraction & Page-Aware Chunking Protocol

- **PDF Extraction:** PyMuPDF (`fitz`) extracts each 1-based page (`page_number = idx + 1`). Ligatures (`\ufb00`–`\ufb06`) and soft hyphens (`\u00ad`) are normalized deterministically, line-wrap hyphenation is joined (`[A-Za-z]-\n[a-z]`), and encoding artifacts (`\ufffd`, `(cid:\d+)`) are recorded per page.
- **Markdown Extraction:** UTF-8 text is read directly with `page_start = 1, page_end = 1` (logical page) and active Markdown headings (`#`–`####`) tracked in `section_heading`.
- **Page-Aware Chunking ([chunking.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/scripts/corpus_v3/chunking.py)):**
  - Named constants: `TARGET_CHUNK_CHARS = 1200`, `MAX_CHUNK_CHARS = 1600`, `MIN_CHUNK_CHARS = 220`.
  - Oversized paragraphs are split deterministically on sentence boundaries (falling back to word boundaries).
  - Every passage retains exact 1-based `page_start` and `page_end` derived from the contributing page segments, plus `source_doc_id`, `source_sha256`, `passage_id` (`s5v3_{doc_id}_p{page_start:04d}_c{chunk_index:04d}`), `normalized_text_sha256`, and `passage_sha256`.

---

## 4. Document Completeness & Extraction Quality Audit

### 4.1 Per-Document Completeness

| Doc ID | Total Pages | Non-Empty Pages | Empty Pages | Total Chars | Mean Chars / Non-Empty Page | Flagged Passages | Usable Passages |
|---|---:|---:|---|---:|---:|---:|---:|
| `local_oa_001` | 1 | 1 | none | 29,251 | 29,251.00 | 2 | 26 / 27 (96.3%) |
| `local_oa_002` | 18 | 18 | none | 28,375 | 1,576.39 | 17 | 23 / 24 (95.8%) |
| `local_oa_003` | 417 | 411 | `[2, 6, 14, 16, 256, 412]` | 889,748 | 2,164.84 | 105 | 719 / 757 (95.0%) |
| `local_oa_004` | 14 | 14 | none | 66,809 | 4,772.07 | 14 | 50 / 50 (100.0%) |

### 4.2 Quality Flag Distribution (`858` Passages)

| Quality Flag | Severity | Count | Notes |
|---|---|---:|---|
| `MID_SENTENCE_TRUNCATION_END` | Minor | 51 | Passage ends without terminal punctuation (often equations or algorithm lines). |
| `MATH_EXTRACTION_NOISE` | Moderate | 32 | Single-character token ratio `>= 0.28` (dense symbolic math in PDFs). |
| `MID_SENTENCE_TRUNCATION_START` | Minor | 26 | Passage begins with a lowercase character after a split boundary. |
| `BROKEN_LIGATURES_OR_ENCODING` | Severe | 22 | All 22 occur in `local_oa_003` where LaTeX matrix bracket glyphs extract as control bytes (`0x14`/`0x15`). |
| `EMPTY_OR_TOO_SHORT` | Severe | 14 | `< 120` chars or `< 20` tokens (e.g., short section-opener or standalone caption pages). |
| `HEADER_FOOTER_ONLY` | Severe | 5 | Short running-header / title-only fragments without prose sentences. |
| `TOC_OR_INDEX_LIKE` | Moderate | 0 | No passages exceeded dot-leader or numeric-column thresholds without prose. |

Passages carrying any severe flag or scoring `< 0.50` are marked `is_usable = false` (`40` total) and retained in the private JSONL with explicit flags rather than silently dropped, enabling transparent downstream filtering and ablation.

---

## 5. Deduplication Report

Implemented in [dedup.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/scripts/corpus_v3/dedup.py):
- **Exact Duplicates (Normalized SHA-256):** `3` exact duplicates detected (`855` unique normalized hashes out of `858` passages). All 3 occur inside `local_oa_003` (`s5v3_local_oa_003_p0243_c0419`, `p0277_c0478`, `p0303_c0531` matching canonical `s5v3_local_oa_003_p0115_c0188` — repeated textbook boilerplate/page notices).
- **Near-Duplicates (5-gram Jaccard `>= 0.80`):** `1` near-duplicate pair detected (`s5v3_local_oa_003_p0255_c0436` vs `s5v3_local_oa_003_p0015_c0016`, Jaccard `0.8333`).
- **Cross-Document Duplication:** `0` exact or near-duplicates across different source documents.

---

## 6. Provenance Separation & Leakage Guard

- **Provenance Separation:**
  - `pdf_extracted`: `831` passages (`96.9%`)
  - `markdown_oa_extracted`: `27` passages (`3.1%`)
  - `hand_authored`: `0` passages
  - `derived`: `0` passages
  - No synthetic, hand-authored, or derived text is mixed into extracted source passages.
- **Leakage Guard ([leakage.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/scripts/corpus_v3/leakage.py)):**
  - Enforces zero exact normalized-hash overlap, zero near-duplicate straddling, and zero document-level overlap across `train`/`dev`/`test` splits, plus zero overlap with any forbidden/held-out hash set.
  - Current Corpus v3 build assigns all `858` passages to `corpus_shared` (shared retrieval collection for query-level `dev`/`test` splits) with `passed = true` and `0` violations.

---

## 7. Honest Multi-Domain Coverage Gap

Corpus v3 built from verified local open-access sources is **strongly skewed toward Machine Learning and Mathematics for Machine Learning** (`local_oa_003` alone accounts for `757 / 858` = `88.2%` of passages). The following core Computer Science domains have **zero verified local OA sources** and are explicitly marked `MISSING_LOCAL_OA_SOURCE` in `s5v3_corpus_manifest.json`:

| Missing Domain | Status | Recommended Future OA Acquisition (Out of Scope for Local-Only Build) |
|---|---|---|
| Operating Systems | `MISSING_LOCAL_OA_SOURCE` | *Operating Systems: Three Easy Pieces* (OSTEP, free online textbook) |
| Database Systems | `MISSING_LOCAL_OA_SOURCE` | CMU 15-445 open course notes / open-access DB architecture surveys |
| Computer Networks | `MISSING_LOCAL_OA_SOURCE` | *Computer Networks: A Systems Approach* (Peterson & Davie, CC-BY) |
| Distributed Systems | `MISSING_LOCAL_OA_SOURCE` | arXiv `cs.DC` open-access papers / Maarten van Steen DS free PDF |

**Conclusion:** `sufficient_for_full_cs_multidomain_claims = false`. Downstream benchmark design (Module C) and evaluation claims (Modules E–G) must scope claims strictly to the 4 covered ML/Math/NLP/Robotics domains until verified OA texts for OS, DB, Networking, and Distributed Systems are ingested.
