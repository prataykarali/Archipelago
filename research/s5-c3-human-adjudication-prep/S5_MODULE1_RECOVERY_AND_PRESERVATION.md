# S5 Module 1 — Workspace Recovery and Preservation Report

**Date:** 2026-11-19  
**Canonical Repository:** `/home/pratay-karali/Desktop/archipelago`  
**Branch / `HEAD`:** `research/s5-c2-annotation-audit` @ `249abc956b8d52d43c51937eafce5ac6718ceb4f`  
**Historical Reviewer A Comparison Status:** **`BLOCKED`** (original workbook SHA-256 `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` not found on disk)

---

## 1. Repository State & Frozen S5 Manifest Verification

- **Canonical Worktree:** `/home/pratay-karali/Desktop/archipelago` (nested `Archipelago/` directory no longer exists).
- **Working Tree Hygiene:** `197` dirty/untracked entries remain after restoring `S5C3_HUMAN_REVIEW_PROTOCOL.md`, including `188` pre-existing unrelated entries outside `research/` and `tests/unit/test_s5*` (strictly untouched).
- **Frozen S5-D0 Preservation Manifest** ([s5d0_preservation_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_preservation_manifest.json), 21 entries):
  - **19 / 19 tracked frozen artifacts:** **VERIFIED EXACT SHA-256 MATCH** (`0` mismatches).
  - **2 / 2 local Git-ignored S5-C2 originals:** **MISSING** (`data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md` and `data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md`).
- **Kuzu Graph Database (`okf_graph.db`):** Absent at repository root (`/home/pratay-karali/Desktop/archipelago/okf_graph.db`), causing local-corpus tests to skip (9) or fail on read-only open (1).

---

## 2. Historical Reviewer A Workbook Recovery Search

- **Target SHA-256:** `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` (`reviewer_a_s5b2_1_workbook.md`, `432,711` bytes).
- **Locations Searched:**
  - `/home/pratay-karali/Desktop/archipelago` (all `research/`, `data/annotation_local/`, `outputs/`, private/backup paths)
  - `/home/pratay-karali/Desktop`, `/home/pratay-karali/Downloads`, `/home/pratay-karali/Documents`
  - `/home/pratay-karali/.codex/worktrees`, `/home/pratay-karali/.local/share/Trash`, `/home/pratay-karali/backups`
- **Result:** **NOT FOUND** (`0` matches for Reviewer A SHA-256 `70049fa8...`; `0` matches for Reviewer B SHA-256 `ca3e6af8...`).
- **Decision:** Historical Reviewer A comparison is explicitly **`BLOCKED`** until the owner restores an unaltered copy matching `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` into `data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md`. No grades were reconstructed or synthesized.

---

## 3. Forensic Preservation & Restoration of `S5C3_HUMAN_REVIEW_PROTOCOL.md`

- **`.gitignore` Check:** `research/s5-c3-human-adjudication-prep/private/forensics/` is **not** Git-ignored. `/data/annotation_local/` **is** Git-ignored (`.gitignore:141`, verified via `git check-ignore -v`).
- **Forensic Backups Preserved (Read-Only `0444`, Git-Ignored):**

| Artifact | Path (Git-Ignored) | Bytes | SHA-256 |
|---|---|---:|---|
| Full uncommitted protocol (with AI-draft Appendix A) | `data/annotation_local/s5c3/forensics/S5C3_HUMAN_REVIEW_PROTOCOL_uncommitted_20261119.md` | `31,736` | `651602ec79ae77265ea566a3c5ab1a4906bced91d895184f36914b958fbe45d8` |
| Extracted Appendix A only | `data/annotation_local/s5c3/forensics/S5C3_HUMAN_REVIEW_PROTOCOL_appendix_a_only_20261119.md` | `25,597` | `a8c20fda7bc4cc1673c80ffdec61d975b9bcfcd84649cfd27e58b2fe7f9d46df` |
| Exact `git diff HEAD` patch | `data/annotation_local/s5c3/forensics/S5C3_HUMAN_REVIEW_PROTOCOL_uncommitted_20261119.diff` | `27,085` | `b7b2420f75486aa68a178996889f2ba761b9a141844bbdb03ab508ec47f1996e` |

*(Note: The working-tree copy differed by `+48` bytes from the earlier quarantined Downloads copy at `data/annotation_local/s5c3/excluded_ai_drafts_archive/S5C3_HUMAN_REVIEW_PROTOCOL.md`, SHA-256 `47cc97cf86d129dcad1ab54b309dd95e08af7766099047f702988026c211564d`, due to wording edits in the Appendix A heading and summary table.)*

- **Restoration Verified:** Executed `git checkout HEAD -- research/s5-c3-human-adjudication-prep/S5C3_HUMAN_REVIEW_PROTOCOL.md` without altering Git history.
  - Restored state: `79` lines, `6,133` bytes, SHA-256 `24e1dd76767b6ccb4158ccacc2f60fb5a9b8848915f8990c28b848bc1e5ad000` (clean against `HEAD`).

---

## 4. Audit of Remaining Dirty S5 Files & Authorized Restoration

| File | Git Status | Cause of Dirty State | Needed for Preservation Tests? |
|---|---|---|---|
| [run_s5b2_1_gate.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-b2-benchmark-correction/scripts/run_s5b2_1_gate.py) | `M` | 4 markdown links updated from absolute `file:///.../Archipelago/...` paths to relative `research/s5-b2-benchmark-correction/...` paths after directory flattening. | No (all S5-B2 tests pass). |
| [run_s5c2_audit.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-c2-annotation-audit/scripts/run_s5c2_audit.py) | Restored (`HEAD`) | Previously deleted in working tree (`-529` lines relative to `6450585`). Restored from `HEAD` (`git checkout HEAD -- research/s5-c2-annotation-audit/scripts/run_s5c2_audit.py`) per coordinator approval (#12): `529` lines, `26,197` bytes, SHA-256 `f8844ee42ffa520730167af52d44a6cf785dbcd5eb9c6af6712f7f679896de5a`. | Not required for `test_s5c2_annotation_audit.py` (`3 passed, 1 skipped` before & after), but now intact for reproducibility. |
| [test_s5b2_benchmark_correction.py](file:///home/pratay-karali/Desktop/archipelago/tests/unit/test_s5b2_benchmark_correction.py) | `M` | 1-line edit at L251 removing commit `6450585`'s fallback matcher `or (f"Reviewer ID: {rev_id}" in wb)` inside a test currently skipped when `okf_graph.db` is absent. | No (currently passes/skips cleanly). |

---

## 5. Clean Blank S5-C3 Templates, Immutable Backups & Untracked P3/P4 Docs

### 5.1 Private Git-Ignored Templates (`data/annotation_local/s5c3/`)

| File | Bytes | Mode | SHA-256 | Verification |
|---|---:|---|---|---|
| `independent_reviewer_c_s5c3_workbook.md` | `433,211` | `0664` | `acf6e86cb23e91a0febaf5181eec8ae3eadbe5ece66ec4d6f1907f74aa10f188` | **100% blank** (`254/254` pairs; `254/254` empty grades, confidences, notes); matches P0 manifest & immutable backup. |
| `immutable_blank_backups/independent_reviewer_c_s5c3_workbook_BLANK_BACKUP.md` | `433,211` | `0444` | `acf6e86cb23e91a0febaf5181eec8ae3eadbe5ece66ec4d6f1907f74aa10f188` | Read-only byte-identical backup. |
| `s5c3_negative_control_verification_worksheets.md` | `111,424` | `0664` | `678cc2fcdd6bd5fa1ce0deec90c6ebdd1ece6e2bd3764c226c1318467e32662c` | **100% blank** (`74/74` empty `contains_answer` fields; `3/3` unchosen classification templates); matches P0 manifest & immutable backup. |
| `immutable_blank_backups/s5c3_negative_control_verification_worksheets_BLANK_BACKUP.md` | `111,424` | `0444` | `678cc2fcdd6bd5fa1ce0deec90c6ebdd1ece6e2bd3764c226c1318467e32662c` | Read-only byte-identical backup. |
| `REVIEWER_A_PROVENANCE_ATTESTATION_TEMPLATE.md` | `3,059` | `0644` | `52aacd86809552bc976413caef968678a71c8aadb7758f0fe06d5987f28afd72` | Clean blank human provenance attestation template. |
| `submissions/` | — | `0775` | — | Empty (`0` files). |

### 5.2 Untracked S5-C3 P3/P4 Handoff Docs (`research/s5-c3-human-adjudication-prep/`)

| Untracked File | Lines | Bytes | SHA-256 |
|---|---:|---:|---|
| [S5C3_P3_HUMAN_SUBMISSION_RECONCILIATION.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P3_HUMAN_SUBMISSION_RECONCILIATION.md) | 96 | 14,325 | `fa1cb02342ed34bcaf220a8046af96e50c80a78cb340d3b501b47f09cac686cd` |
| [S5C3_P4_AC_VALIDATION_COMPATIBILITY_PLAN.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P4_AC_VALIDATION_COMPATIBILITY_PLAN.md) | 56 | 5,544 | `5730487b6d0244f8c537ec79d3e7e0f5f28d41cd0d9b79d71cd6130786d5334d` |
| [S5C3_P4_CANONICAL_WORKSPACE_VERIFICATION.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P4_CANONICAL_WORKSPACE_VERIFICATION.md) | 40 | 5,533 | `f7e1b4bc599b25e7d96aa8199cec109e6c050fe42826d2bceae8e470aa38204a` |
| [S5C3_P4_HUMAN_HANDOFF_CHECKLIST.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P4_HUMAN_HANDOFF_CHECKLIST.md) | 41 | 4,823 | `320373bedcc8c648c7066157adc30a8728a365c3e27eda53b02fd92b88e10146` |
| [S5C3_P4_NEGATIVE_CONTROL_INSTRUCTIONS.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P4_NEGATIVE_CONTROL_INSTRUCTIONS.md) | 47 | 3,849 | `b5d6ab3734b9d56301d0617396b4cb8c666103baec0702bff3e1b4b2749c462b` |
| [S5C3_P4_REVIEWER_C_INSTRUCTIONS.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P4_REVIEWER_C_INSTRUCTIONS.md) | 46 | 3,266 | `369a10252a01114c1e4f3fae1683086fb608c8566d10b0afcb2a954735198b14` |

---

## 6. Frozen Preservation Test Execution

- **Test Runner:** `/home/pratay-karali/.local/bin/pytest` (Python `3.12.3`, pytest `9.1.1`; `.venv/` is not present in this workspace).
- **Results across the 5 S5 research preservation suites (`57` tests):**

| Test Suite | Passed | Skipped | Failed | Notes |
|---|---:|---:|---:|---|
| `tests/unit/test_s5a_retrieval_integrity.py` | 13 | 0 | 1 | `test_precomputed_embeddings_cache_validity` fails (`RuntimeError: Cannot create an empty database under READ ONLY mode`) solely because `okf_graph.db` is absent. |
| `tests/unit/test_s5b1_integrity_repair.py` | 15 | 6 | 0 | 6 skips due to missing local `okf_graph.db` / local workbooks. |
| `tests/unit/test_s5b2_benchmark_correction.py` | 11 | 2 | 0 | 2 skips due to missing local `okf_graph.db` / local workbooks. |
| `tests/unit/test_s5c2_annotation_audit.py` | 3 | 1 | 0 | 1 skip due to missing local `data/annotation_local/s5c2/S5C2_DISAGREEMENT_ADJUDICATION.md`. |
| `tests/unit/test_s5d0_analysis_prep.py` | 5 | 0 | 0 | All 5 passed (including `test_preserved_artifacts_match_frozen_hashes`). |
| **Total** | **47** | **9** | **1** | **0 failures** in S5-B1, S5-B2, S5-C2, and S5-D0 (`34 passed, 9 skipped`). |
