# S5-v3 Module A — Foundational Recovery & Reproducibility Report

**Date:** 2026-11-19  
**Branch / `HEAD`:** `research/s5-v3-benchmark-expansion` @ `4941f5d326a820d6ef5b4b7d5dd464b7472dd6e8`  
**Machine-Readable Inventory:** [s5v3_module_a_inventory.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/reports/s5v3_module_a_inventory.json)  
**Frozen S5-v2.1 Pilot Integrity:** **19 / 19** tracked frozen artifacts in [s5d0_preservation_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_preservation_manifest.json) remain **UNMODIFIED** (exact SHA-256 matches).

---

## 1. Executive Verdict

| Component | Status | Finding |
|---|---|---|
| **Original `okf_graph.db` (`s5a_eval_corpus_v1`, 713 passages)** | **`BLOCKED`** | Absent at repo root. The only `okf_graph.db` found anywhere (`~/.codex/worktrees/archipelago-library-release/Archipelago/okf_graph.db`, `16,384` B) is an **empty Kuzu DB (`0` tables, no `Chunk` table)**. Original-run corpus reproduction from `okf_graph.db` is **`BLOCKED`**. |
| **Dense Embedding Cache & HF Model (`snowflake-arctic-embed-m-v1.5`)** | **`BLOCKED`** | `data/artifacts/s5a_dense_embeddings_713.npy` and `~/.cache/huggingface/hub/` are absent on disk. |
| **Original Reviewer A Workbook (`70049fa8...`)** | **`BLOCKED`** | Preserved `BLOCKED` status; SHA-256 `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` not found anywhere on disk. Zero grades synthesized. |
| **Verified Local Open-Access Sources for Corpus v3** | **`LIMITED (4 local docs)`** | Only **4** verified open-access academic documents exist locally on disk (2 inside `data/academic_candidates/`, 2 in `~/Downloads/`). Local disk alone is **insufficient** for a large multi-domain Corpus v3 without authorized acquisition of verified open-access sources (e.g., arXiv / OSTEP / D2L / OpenStax) into Git-ignored storage. |

---

## 2. Legitimate Recovery Search Results

Searched `/home/pratay-karali/Desktop/archipelago`, `/home/pratay-karali/Desktop`, `/home/pratay-karali/Downloads`, `/home/pratay-karali/Documents`, `/home/pratay-karali/.codex/worktrees`, and `/home/pratay-karali/.local/share/Trash`:

1. **Kuzu `okf_graph.db`:**
   - `/home/pratay-karali/Desktop/archipelago/okf_graph.db` — **missing**.
   - `/home/pratay-karali/.codex/worktrees/archipelago-library-release/Archipelago/okf_graph.db` — exists (`16,384` B), opened read-only via `kuzu.Database(..., read_only=True)`: `CALL show_tables()` returns `[]` (**0 tables, 0 chunks**). Not restored.
2. **Graph JSON (`okf_graph.json`):**
   - Present at `okf_graph.json` (and identical copies in `host_inference/fixtures/okf_graph.json` and `host_inference/cache/okf_graph.json`): `6,489,729` B, SHA-256 `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76`.
   - Contains **610 concept nodes** (`507` with source refs, `532` with non-stub summaries) and **1,988 edges** (`267` `requires`, `387` `unlocks`, `1,334` `related`), plus `graph_rag_index` (`okf-graphrag-v1`). Does **not** contain full chunk passage texts from `okf_graph.db`.
3. **Private Frozen v2.1 Hydrated Subsets (Git-Ignored, Do Not Repurpose):**
   - `data/annotation_local/s5c3/independent_reviewer_c_s5c3_workbook.md` (`433,211` B, SHA-256 `acf6e86c...`): `254` pairs covering `172` unique passages across `29` docs (partial subset of `713`-passage v1 corpus).
   - `data/annotation_local/s5c3/s5c3_negative_control_verification_worksheets.md` (`111,424` B, SHA-256 `678cc2fc...`): `74` candidate entries (`68` unique passages).

---

## 3. Complete Inventory of Verified Local Sources & Exclusions

### 3.1 Verified Local Open-Access Academic Documents (4 Total)

| ID | Path | Title | Domain | Pages / Size | License | SHA-256 |
|---|---|---|---|---:|---|---|
| `local_oa_001` | `data/academic_candidates/39990e29...fe5.md` | Dive into Deep Learning — Ch. 3: Linear Regression | Machine Learning | `29,363` B (MD) | `CC-BY-SA-4.0` | `39990e2958ef5c3494918de03fd3d9ed594efa4572218cb644efc57194bb8fe5` |
| `local_oa_002` | `data/academic_candidates/8888aa20...a4f.pdf` | Efficient Guided Generation for LLMs (Willard & Louf, 2023; arXiv:2307.09702v2) | NLP / LLMs | `18` pp (`375,946` B) | `arXiv-perpetual-nonexclusive` | `8888aa2043588e41d0f222b59ca6896e5211816eeca8896db215234ba209aa4f` |
| `local_oa_003` | `~/Downloads/mml-book.pdf` | Mathematics for Machine Learning (Deisenroth, Faisal, Ong) | Math for ML | `417` pp (`17,565,898` B) | Free online PDF (`mml-book.github.io`) | `3f87b70c64a35d30ec4e565b4d5cfd18fe913002d3b3bed44691c7d0838911bc` |
| `local_oa_004` | `~/Downloads/metatron-paper.pdf` | METATRON: A Promptable Whole-Body Execution Layer for Humanoids (Tessler et al.) | Robotics / Control | `14` pp (`27,833,656` B) | Preprint (local extraction only) | `de2411a21822326b6afadd2724cbafa1b8b8850c8630197c2e706a41c2b6ecaa` |

### 3.2 Remote Open-Access Catalogs (Metadata Only — Not Downloaded Locally)
- `data/catalogs/live_scholarly_manifest.json` (`42,237` B): `40` cataloged open-access items (`20` arXiv + `20` OpenAlex) across deep learning, computer networks, DSA, distributed systems, and NLP.
- `data/catalogs/hf_dataset_manifest.json` (`2,681` B): `51` PDFs listed in `Prataykarali/Library_books` (not downloaded locally; license status of each title would require per-file verification).

### 3.3 Explicitly Excluded Local Files
- **Repo root stub PDFs (`4` files, `129–131` B)** and **`data/uploads/` test fixtures (`23` files, `30–6,050` B):** synthetic test stubs.
- **Copyrighted textbooks in `~/Downloads/`:** `predictive_analytics_and_data_mining/` (`22` Elsevier PDFs, `46.1` MB) and `LLMs in Production (z-library...)` — excluded on copyright grounds.
- **Personal/private files:** `data/private/` login credentials, `~/Downloads/` CVs, transcripts, passports, and `os.pdf` (institutional course notes) — strictly excluded.

---

## 4. S5-A through S5-D1 Unit Test Reproducibility Breakdown

Executed via `/home/pratay-karali/.local/bin/pytest` across all 9 S5 test suites (**95 tests collected: 85 passed, 9 skipped, 1 failed**):

| Suite | Passed | Skipped | Failed | Reproducibility Classification |
|---|---:|---:|---:|---|
| `tests/unit/test_s5a_retrieval_integrity.py` | 13 | 0 | **1** | **13 reproducible; 1 blocked** (`test_precomputed_embeddings_cache_validity` fails with `RuntimeError: Cannot create an empty database under READ ONLY mode` due to missing `okf_graph.db`). |
| `tests/unit/test_s5b1_integrity_repair.py` | 15 | 6 | 0 | **15 reproducible; 6 skipped** (missing local `okf_graph.db` / workbooks). |
| `tests/unit/test_s5b2_benchmark_correction.py` | 11 | 2 | 0 | **11 reproducible; 2 skipped** (missing local `okf_graph.db` / workbooks). |
| `tests/unit/test_s5c2_annotation_audit.py` | 3 | 1 | 0 | **3 reproducible; 1 skipped** (missing local `S5C2_DISAGREEMENT_ADJUDICATION.md`). |
| `tests/unit/test_s5d0_analysis_prep.py` | 5 | 0 | 0 | **5/5 fully reproducible** (all frozen tracked hashes verified). |
| `tests/unit/test_s5_annotation_workbench.py` | 7 | 0 | 0 | **7/7 fully reproducible**. |
| `tests/unit/test_s5_ac_adjudication.py` | 7 | 0 | 0 | **7/7 fully reproducible**. |
| `tests/unit/test_s5_negative_control_verifier.py` | 10 | 0 | 0 | **10/10 fully reproducible**. |
| `tests/unit/test_s5_d1_pipeline.py` | 14 | 0 | 0 | **14/14 fully reproducible**. |
| **Total** | **85** | **9** | **1** | **85/85 reproducible tests pass (0 code regressions); 10 tests blocked/skipped solely by missing local `okf_graph.db` / local S5-C2 artifacts.** |

---

## 5. Recommendation for `@coordinator` (Modules B–G Gate)

1. **S5-v1/v2.1 original `okf_graph.db` reproduction** and **historical Reviewer A comparison** remain **`BLOCKED`** pending external restoration of `okf_graph.db` and `reviewer_a_s5b2_1_workbook.md` (`70049fa8...`).
2. **Corpus v3 (`s5_v3_corpus`) Decision:** Only **4** verified open-access documents are currently on local disk (`D2L Ch.3`, `arXiv:2307.09702v2`, `mml-book.pdf`, `metatron-paper.pdf`), plus the `610`-concept `okf_graph.json` (no chunk texts). To build a multi-domain, license-clean **Corpus v3** with full provenance for Modules B–G, authorize downloading a deterministic, license-verified set of open-access sources (e.g., arXiv preprints from `live_scholarly_manifest.json` + OSTEP/D2L/MML chapters) into Git-ignored `data/annotation_local/s5v3/raw_sources/` with full SHA-256 manifests.
