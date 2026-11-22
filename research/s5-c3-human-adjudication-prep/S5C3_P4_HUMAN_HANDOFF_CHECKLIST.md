# S5-C3-P4 — Human Review Handoff Master Checklist

**Stage:** S5-C3-P4 (Human Review Handoff)  
**Canonical Worktree:** `/home/pratay-karali/Desktop/archipelago` (`research/s5-c2-annotation-audit` @ `249abc956b8d52d43c51937eafce5ac6718ceb4f`)  
**Date:** 2026-11-19  
**Final Status:** **`AWAITING_GENUINE_HUMAN_REVIEW`**

---

## 1. Handoff Package Readiness Checklist

| # | Handoff Item | Exact File Path | Status |
|---:|---|---|---|
| 1 | **Canonical Workspace Verification Report** | [S5C3_P4_CANONICAL_WORKSPACE_VERIFICATION.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P4_CANONICAL_WORKSPACE_VERIFICATION.md) | **READY** |
| 2 | **Blank Reviewer A Attestation Template** *(Git-ignored)* | [REVIEWER_A_PROVENANCE_ATTESTATION_TEMPLATE.md](file:///home/pratay-karali/Desktop/archipelago/data/annotation_local/s5c3/REVIEWER_A_PROVENANCE_ATTESTATION_TEMPLATE.md) | **READY (BLANK)** |
| 3 | **Editable Blank Reviewer C Workbook** *(Git-ignored; 0/254 filled)* | [independent_reviewer_c_s5c3_workbook.md](file:///home/pratay-karali/Desktop/archipelago/data/annotation_local/s5c3/independent_reviewer_c_s5c3_workbook.md) | **READY (BLANK; `acf6e86c...`)** |
| 4 | **Immutable Blank Backup (Reviewer C)** *(Git-ignored; `chmod 444`)* | [independent_reviewer_c_s5c3_workbook_BLANK_BACKUP.md](file:///home/pratay-karali/Desktop/archipelago/data/annotation_local/s5c3/immutable_blank_backups/independent_reviewer_c_s5c3_workbook_BLANK_BACKUP.md) | **LOCKED (`acf6e86c...`)** |
| 5 | **Reviewer C Human Instructions** | [S5C3_P4_REVIEWER_C_INSTRUCTIONS.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P4_REVIEWER_C_INSTRUCTIONS.md) | **READY** |
| 6 | **Editable Blank Negative-Control Worksheets** *(Git-ignored; 0/3 filled)* | [s5c3_negative_control_verification_worksheets.md](file:///home/pratay-karali/Desktop/archipelago/data/annotation_local/s5c3/s5c3_negative_control_verification_worksheets.md) | **READY (BLANK; `678cc2fc...`)** |
| 7 | **Immutable Blank Backup (Negative Controls)** *(Git-ignored; `chmod 444`)* | [s5c3_negative_control_verification_worksheets_BLANK_BACKUP.md](file:///home/pratay-karali/Desktop/archipelago/data/annotation_local/s5c3/immutable_blank_backups/s5c3_negative_control_verification_worksheets_BLANK_BACKUP.md) | **LOCKED (`678cc2fc...`)** |
| 8 | **Negative-Control Verifier Instructions** | [S5C3_P4_NEGATIVE_CONTROL_INSTRUCTIONS.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P4_NEGATIVE_CONTROL_INSTRUCTIONS.md) | **READY** |
| 9 | **A/C Validation & S5-D1 Compatibility Plan** | [S5C3_P4_AC_VALIDATION_COMPATIBILITY_PLAN.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-c3-human-adjudication-prep/S5C3_P4_AC_VALIDATION_COMPATIBILITY_PLAN.md) | **READY (DESIGN ONLY)** |
| 10 | **Quarantined AI Drafts Archive** *(Git-ignored; `chmod 444`; NEVER share with reviewers)* | `data/annotation_local/s5c3/excluded_ai_drafts_archive/` | **QUARANTINED** |

---

## 2. Investigator Distribution & Collection Checklist

- [ ] **Restore Preserved `REV_A` Original:** Confirm `reviewer_a_s5b2_1_workbook.md` (`SHA-256: 70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c`) is restored into `data/annotation_local/s5c2/originals/` (currently missing after flattening `Archipelago/`).
- [ ] **Deliver to Reviewer A:** Send only `REVIEWER_A_PROVENANCE_ATTESTATION_TEMPLATE.md`; collect signed file in `data/annotation_local/s5c3/submissions/reviewer_a_provenance_attestation_signed.md`.
- [ ] **Deliver to Independent Reviewer C (Outside GitHub):** Send only `independent_reviewer_c_s5c3_workbook.md` + `S5C3_P4_REVIEWER_C_INSTRUCTIONS.md`. Confirm zero exposure to `REV_A`, `REV_B`, rankings, or `excluded_ai_drafts_archive/`. Collect completed file in `data/annotation_local/s5c3/submissions/independent_reviewer_c_s5c3_workbook_COMPLETED.md`.
- [ ] **Deliver to Human Negative-Control Verifier:** Send `s5c3_negative_control_verification_worksheets.md` + `S5C3_P4_NEGATIVE_CONTROL_INSTRUCTIONS.md` (with access to `okf_graph.db` / 713-passage corpus for full corpus-wide checks). Collect completed file in `data/annotation_local/s5c3/submissions/s5c3_negative_control_verification_worksheets_COMPLETED.md`.
- [ ] **Post-Collection Next Stage (S5-C3-P5):** Validate SHA-256s and human provenance, compute A/C agreement, adjudicate all `REV_A != REV_C` disagreements with a human adjudicator, and only then prepare the versioned `s5d1_adjudicated_gold_ac_v2` pathway.

---

## 3. Hard Stop Gate

- **Zero automated relevance grades, adjudications, or gold labels were generated.**
- **`evaluate_gold_labels_readonly.py` was not modified and S5-D1 was not executed.**
- **Final Status:** **`AWAITING_GENUINE_HUMAN_REVIEW`**
