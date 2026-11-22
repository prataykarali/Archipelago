# S5-C3-P4 — Canonical Workspace & Template Verification Report

**Stage:** S5-C3-P4 (Human Review Handoff)  
**Date:** 2026-11-19  
**Final Status:** **`AWAITING_GENUINE_HUMAN_REVIEW`**

---

## 1. Canonical Git Worktree Verification (Step 1)

| Path Checked | Exists? | `git rev-parse --show-toplevel` | Branch / `HEAD` | Finding |
|---|---|---|---|---|
| `/home/pratay-karali/Desktop/archipelago/` | **Yes** | `/home/pratay-karali/Desktop/archipelago` | `research/s5-c2-annotation-audit` @ `249abc956b8d52d43c51937eafce5ac6718ceb4f` | **Canonical worktree** (contains commit `249abc956b8d52d43c51937eafce5ac6718ceb4f`: `research(s5-d0,s5-c3): add reproducibility diagnostics, read-only gold evaluator, and human adjudication prep protocols`, 16 files, `+4,368` lines). |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/` | **No** | N/A | N/A | Nested directory no longer exists; repository was flattened into `/home/pratay-karali/Desktop/archipelago/`. |

---

## 2. Private S5-C3 Workspace Inventory (Git-Ignored at `.gitignore:141`)

All private human-review templates, immutable blank backups, and quarantined AI drafts reside strictly inside Git-ignored `/home/pratay-karali/Desktop/archipelago/data/annotation_local/s5c3/`:

| Role | Relative Path (Git-Ignored) | Size (bytes) | SHA-256 | Verified State |
|---|---|---:|---|---|
| **Editable Reviewer C Workbook** | `data/annotation_local/s5c3/independent_reviewer_c_s5c3_workbook.md` | `433,211` | `acf6e86cb23e91a0febaf5181eec8ae3eadbe5ece66ec4d6f1907f74aa10f188` | **100% blank** (`0/254` grades, `0/254` notes, blank provenance header); matches P0 release hash. |
| **Editable Negative-Control Worksheets** | `data/annotation_local/s5c3/s5c3_negative_control_verification_worksheets.md` | `111,424` | `678cc2fcdd6bd5fa1ce0deec90c6ebdd1ece6e2bd3764c226c1318467e32662c` | **100% blank** (`0/74` candidate checks, `0/3` final classifications); matches P0 release hash. |
| **Blank Reviewer A Attestation Template** | `data/annotation_local/s5c3/REVIEWER_A_PROVENANCE_ATTESTATION_TEMPLATE.md` | — | *(newly created)* | **100% blank** human-completable provenance declaration (zero prefilled independence claims or signatures). |
| **Immutable Blank Backup (Rev C)** | `data/annotation_local/s5c3/immutable_blank_backups/independent_reviewer_c_s5c3_workbook_BLANK_BACKUP.md` | `433,211` | `acf6e86cb23e91a0febaf5181eec8ae3eadbe5ece66ec4d6f1907f74aa10f188` | Read-only (`chmod 444`) byte-identical backup of clean blank template. |
| **Immutable Blank Backup (Neg Controls)** | `data/annotation_local/s5c3/immutable_blank_backups/s5c3_negative_control_verification_worksheets_BLANK_BACKUP.md` | `111,424` | `678cc2fcdd6bd5fa1ce0deec90c6ebdd1ece6e2bd3764c226c1318467e32662c` | Read-only (`chmod 444`) byte-identical backup of clean blank template. |
| **Quarantined AI Draft #1 (From Downloads)** | `data/annotation_local/s5c3/excluded_ai_drafts_archive/s5c3_disagreement_adjudication_packet_51.md` | `150,819` | `25cea3625348ac674c8827642996e2f60bd43d565edf0937ce04efd32debf4e6` | Read-only (`chmod 444`) quarantine copy; explicitly `AI_ASSISTED_OR_GENERATED` (`0/51` human sign-offs); excluded from human ground truth. |
| **Quarantined AI Draft #2 (From Downloads)** | `data/annotation_local/s5c3/excluded_ai_drafts_archive/S5C3_HUMAN_REVIEW_PROTOCOL.md` | `31,688` | `47cc97cf86d129dcad1ab54b309dd95e08af7766099047f702988026c211564d` | Read-only (`chmod 444`) quarantine copy; contains Appendix A `AI_DRAFT_PENDING_HUMAN_REVIEW`; excluded from human ground truth. |
| **Completed Submissions Intake Dir** | `data/annotation_local/s5c3/submissions/` | — | — | Empty directory prepared for signed human submissions. |

---

## 3. Workspace Discrepancies Reported (No Files Silently Overwritten)

1. **Nested Path Flattening:** `/home/pratay-karali/Desktop/archipelago/Archipelago/` no longer exists; all tracked paths now live directly under `/home/pratay-karali/Desktop/archipelago/`.
2. **Missing Local `s5c2/originals/` Archive in Flattened Tree:** `data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md` (expected SHA-256 `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c`) and `data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md` (`ca3e6af8...`) are currently absent under `/home/pratay-karali/Desktop/archipelago/data/annotation_local/` after the directory restructure. Before running future A/C validation, restore the preserved `reviewer_a_s5b2_1_workbook.md` copy (and verify its SHA-256 equals `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c`) into `data/annotation_local/s5c2/originals/`.
3. **Uncommitted Working-Tree Modification on `S5C3_HUMAN_REVIEW_PROTOCOL.md`:** `research/s5-c3-human-adjudication-prep/S5C3_HUMAN_REVIEW_PROTOCOL.md` (`31,736` bytes) currently differs from commit `249abc95` (`79` lines) because Appendix A (AI-draft negative-control proposals) was appended earlier. Per S5-C3-P4 rules, it was **not** silently overwritten; the investigator should restore it from `git checkout 249abc95 -- research/s5-c3-human-adjudication-prep/S5C3_HUMAN_REVIEW_PROTOCOL.md` before committing public docs.
4. **Downloads AI-Draft Isolation:** All 4 files requested from `/home/pratay-karali/Downloads/` are now present inside `/home/pratay-karali/Desktop/archipelago/data/annotation_local/s5c3/`, with the 2 clean blank templates in the active handoff root and the 2 AI-assisted drafts strictly isolated in `excluded_ai_drafts_archive/` so they cannot contaminate human review.
