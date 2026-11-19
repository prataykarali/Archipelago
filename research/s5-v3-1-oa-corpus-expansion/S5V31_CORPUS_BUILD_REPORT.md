# S5-v3.1 Corpus Build & Verification Report (Stage B)

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-1-oa-corpus-expansion-canonical`  
**Builder CLI:** [build_corpus_v31.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/scripts/build_corpus_v31.py)  
**Public Metadata-Only Manifest:** [s5v31_corpus_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_corpus_manifest.json) (`SHA-256: adb282d88ba3440484750ba05570af9f5da8f4aede7f53d91405e771f040fc5f`)  
**Private Passage JSONL (Git-Ignored):** `data/annotation_local/s5v3_1/corpus_v31/s5v31_corpus_passages.jsonl`

---

## 1. Immutable Build Fingerprints & Determinism

Executed `build_corpus_v31.py` twice consecutively and verified byte-for-byte SHA-256 identity across all three outputs:

| Artifact | Scope | SHA-256 (Verified Identical Across Runs) |
|---|---|---|
| `data/annotation_local/s5v3_1/corpus_v31/s5v31_corpus_passages.jsonl` | Private (Git-ignored) | `6366477189b8058b3f523a9d6607abb4d2c249351927918d24979e17833937b9` |
| Ordered `passage_id` list (`1,958` IDs) | Fingerprint | `91a00119667f32edfaae99f70bb9a4b55df7d1b98fd211117b7b6fb97f6b6fa6` |
| `manifests/s5v31_corpus_manifest.json` | Public (metadata-only) | `adb282d88ba3440484750ba05570af9f5da8f4aede7f53d91405e771f040fc5f` |
| `manifests/s5v31_source_license_manifest.json` | Public (metadata-only) | `a2242b13c2f857dcb16cf0ff0670b5664ecd7e8a4336bbfe80e3ab79979a336b` |

- **`okf_graph_db_dependency`:** `false` (zero dependence on missing v2.1 `okf_graph.db`).
- **`contains_raw_passage_text`:** `false` in both public manifests.
- **Frozen S5-v3 Base Integrity:** Prior `data/annotation_local/s5v3/corpus_v3/s5v3_corpus_passages.jsonl` verified exact SHA-256 `dd8e973b727a981aeb4b8d0109513616c4ea709afe3eed40bde5c8b14ebeaee4` before retaining its exact `818` eligible passages (`is_usable=true`, `is_exact_duplicate=false`) with original `s5v3_*` IDs intact.

---

## 2. Corpus v3.1 Composition & Extraction Audit

- **Total Passages:** `1,958` (`818` retained S5-v3 eligible + `1,140` new OA CS passages)
- **Total Volume:** `2,279,524` characters, `380,796` whitespace tokens
- **Honest Page Provenance (Zero Fabricated Pages):**
  - `1,418` passages carry exact 1-based `page_start` / `page_end` (all PDF sources + retained v3 base).
  - `540` passages (`oa_os_001` EPUB `112` + `oa_db_001` HTML `208` + `oa_ds_001` LaTeX `220`) carry `page_start: null, page_end: null` with exact `section_ref` and `section_heading` preserved.
- **ID Collision Check:** `0` collisions (`s5v3_*` retained IDs vs `s5v31_{doc_id}_{loc}_c{idx:04d}` new IDs).

### Per-Source Extraction & Filtering Table (New OA Sources)

| Doc ID | Domain | Format | Raw Units | Candidate Chunks | Dropped Boilerplate / Bib | Dropped Malformed / Short | Dropped Exact Dups | Dropped Near Dups | Retained Passages |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `oa_os_001` | Operating Systems | EPUB | 53 | 123 | 0 | 10 | 0 | 1 | **112** |
| `oa_db_001` | Databases | HTML (16 ch.) | 217 | 251 | 11 | 32 | 0 | 0 | **208** |
| `oa_net_001` | Computer Networks | PDF (282 pp) | 281 | 684 | 40 | 44 | 0 | 0 | **600** |
| `oa_ds_001` | Distributed Systems | LaTeX | 32 | 227 | 0 | 7 | 0 | 0 | **220** |
| **New OA Subtotal** | **4 CS Domains** | — | **583** | **1,285** | **51** | **93** | **0** | **1** | **1,140** |

---

## 3. Global Deduplication & Provenance Summary

- **Exact Duplicates (Normalized SHA-256):** `0` exact duplicates across all `1,958` passages (`0` dropped from new OA sources; all `3` v3 exact duplicates were already excluded as unusable in the `818`-passage v3 eligible base).
- **Near-Duplicates (5-gram Shingle Jaccard `>= 0.80`):**
  - `2` pairs detected across the pre-filter combined pool:
    1. `s5v31_oa_os_001_s0000_c0086` vs `s5v31_oa_os_001_s0000_c0085` (Jaccard `0.8137`) -> **dropped** `s5v31_oa_os_001_s0000_c0086` from new OA passages.
    2. `s5v3_local_oa_003_p0255_c0436` vs `s5v3_local_oa_003_p0015_c0016` (Jaccard `0.8333`) -> retained intact as part of the immutable `818`-passage S5-v3 base (disclosed transparently).
  - `0` cross-document exact or near-duplicates across any of the 8 sources.
- **Provenance Class Distribution:**
  - `pdf_extracted`: `1,392` (`71.09%`)
  - `latex_oa_extracted`: `220` (`11.24%`)
  - `html_oa_extracted`: `208` (`10.62%`)
  - `epub_oa_extracted`: `112` (`5.72%`)
  - `markdown_oa_extracted`: `26` (`1.33%`)
