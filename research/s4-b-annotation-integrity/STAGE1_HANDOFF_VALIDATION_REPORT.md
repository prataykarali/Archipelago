# Archipelago — S4-B Stage 1 Annotator Handoff Validation Report

**Branch:** `research/s4-b-annotation-integrity`  
**Date:** 2026-11-17T09:15:00+05:30  
**Phase:** Stage 1 Blinded Independent Reviewer Handoff  

---

## 1. Status of Prior Reviewer Files & Calibration Classification

In accordance with scientific and methodological integrity protocols:
1. **Reviewer A Worksheets:**
   - `artifacts/validation/local_only/s4a_human_annotation_worksheet.md` (SHA-256: `304ee2d4cc167d93874624871b41e79a303d3126015c66b9287b489caebb1ce3`)
   - `artifacts/validation/local_only/s4a_human_annotation_worksheet.json` (SHA-256: `bfae3f9306efb0f7c03e389fce47d6767a2937d0cccc7e8080c4f1309e161246`)
   - `artifacts/validation/local_only/s4b_reviewer_a_scored.json` (SHA-256: `343d28f55581ba277467c4068ce0eb3bbecf0454124462eacb8d4240ccba68c6`)
   - **Status:** **Preserved immutably without modification.**

2. **Classification of Partially Completed Reviewer B File:**
   - `artifacts/validation/local_only/s4b_reviewer_b_worksheet.md` (SHA-256: `a7dc871f98b6975b338156a1e07a1bdd3720f89b72825d25883d7fd80ed78ace`)
   - `artifacts/validation/local_only/s4b_reviewer_b_template.json` (SHA-256: `ba6fb9568bdf7eceec3872438c59ae5b741e24ca9329363acd65f1df61067ea8`)
   - **Methodological Status:** **CALIBRATION RECORD ONLY.**  
     *Any annotations or preliminary scoring conducted in these files occurred after the experimental setup had been exposed to Reviewer A's judgments in repository context. Therefore, these files are explicitly marked as a pilot calibration / orientation artifact and MUST NOT be used as independent double-blind adjudication evidence.*
   - **Action:** Preserved intact as calibration records; NOT overwritten.

---

## 2. Clean Stage 1 Handoff Package Specification

A clean, isolated Stage 1 handoff package has been prepared for the new independent human reviewer:
- **Location:** `artifacts/validation/local_only/stage1_handoff_package/`
- **Constituent Files:**
  1. `stage1_independent_worksheet.md`: Full human-readable markdown worksheet for independent scoring.
  2. `stage1_independent_template.json`: Clean machine-readable JSON template with 100% null judgment fields.
  3. `INDEPENDENT_REVIEWER_GUIDE.md`: Dedicated reviewer onboarding and rubric guide.

### Blinding & Integrity Checklist:
- [x] **No Human Relevance Judgments Prefilled:** All 113 relevance scores in both MD and JSON are blank (`___` / `null`).
- [x] **No Reviewer A Data:** Zero scores, annotations, notes, or adjudication hints from Reviewer A exist in this package.
- [x] **No Question Categories:** Removed all category metadata tags (`multi_hop_prerequisite`, `cross_paper_comparison`, `unanswerable_out_of_corpus`, etc.).
- [x] **No System Identity / Retrieval Ranks:** System names (`bm25`, `dense`, `hybrid_rrf`), ranks, and retrieval scores are completely omitted.
- [x] **Full Passage Text:** All 113 candidates retain their complete, untruncated text identical to Reviewer A's source corpus.
- [x] **Clear 0/1/2 Rubric:** Unambiguous definitions provided for `0` (not relevant), `1` (partially relevant / context), and `2` (directly answers / supports).
- [x] **Query-Level Assessments:** Mandatory fields for answerability (`ANSWERABLE`, `UNANSWERED_IN_POOL`, `UNANSWERABLE_OUT_OF_CORPUS`, `CANNOT_DETERMINE`) and multi-passage requirement (`YES` / `NO`).
- [x] **Corpus vs. Pool Scope Limitation:** Explicitly instructs the reviewer that they can evaluate evidence in the supplied pool, but cannot certify absence from the entire corpus without access to a corpus-wide audit.
- [x] **Stage 2 Isolation:** The candidate-to-source verification map (`s4b_stage2_verification_map.json`) is strictly withheld and will only be distributed after Stage 1 submission.

---

## 3. Candidate & Query Verification

| Query ID | Candidate Count | Status | Notes |
| :--- | :---: | :---: | :--- |
| `CIKM-PILOT-001` | 17 | Verified | All candidates blank, full text present |
| `CIKM-PILOT-005` | 14 | Verified | All candidates blank, full text present |
| `CIKM-PILOT-013` | 16 | Verified | All candidates blank, full text present |
| `CIKM-PILOT-002` | 17 | Verified | All candidates blank, full text present |
| `CIKM-PILOT-004` | 22 | Verified | All candidates blank, full text present |
| `CIKM-PILOT-023` | 27 | Verified | All candidates blank, full text present |
| **Total** | **113** | **100% Verified** | **Exactly 113 candidates across 6 queries** |

---

## 4. File Provenance & Hash Register

| File Path | SHA-256 Hash | Role / Status |
| :--- | :--- | :--- |
| `artifacts/validation/local_only/s4a_human_annotation_worksheet.md` | `304ee2d4cc167d93874624871b41e79a303d3126015c66b9287b489caebb1ce3` | Reviewer A Original Worksheet (Preserved) |
| `artifacts/validation/local_only/s4a_human_annotation_worksheet.json` | `bfae3f9306efb0f7c03e389fce47d6767a2937d0cccc7e8080c4f1309e161246` | Reviewer A Blinded Pool JSON (Preserved) |
| `artifacts/validation/local_only/s4b_reviewer_a_scored.json` | `343d28f55581ba277467c4068ce0eb3bbecf0454124462eacb8d4240ccba68c6` | Reviewer A Deterministic Scores (Preserved) |
| `artifacts/validation/local_only/s4b_reviewer_b_worksheet.md` | `a7dc871f98b6975b338156a1e07a1bdd3720f89b72825d25883d7fd80ed78ace` | Prior Reviewer B Calibration Worksheet |
| `artifacts/validation/local_only/s4b_reviewer_b_template.json` | `ba6fb9568bdf7eceec3872438c59ae5b741e24ca9329363acd65f1df61067ea8` | Prior Reviewer B Calibration JSON |
| `artifacts/validation/local_only/s4b_stage2_verification_map.json` | `871350bdff947ee82239524dbb38cc62769e73fe938cfc5fcc4537db98281e3b` | Stage 2 Verification Map (Withheld until Stage 1 complete) |
| `artifacts/validation/local_only/stage1_handoff_package/stage1_independent_worksheet.md` | `e5c8e047ad10320e3a28bc74bd558ddcf606686de3d905e6601c59b34cd802fb` | New Independent Reviewer Stage 1 Worksheet |
| `artifacts/validation/local_only/stage1_handoff_package/stage1_independent_template.json` | `ec563d55085342f676cf34707d47188cd447d3e4a83a9b7b5e2ba8603d6e9f54` | New Independent Reviewer Stage 1 JSON Template |
| `artifacts/validation/local_only/stage1_handoff_package/INDEPENDENT_REVIEWER_GUIDE.md` | `1ba34a6331d09a500cbecf53462b3079b797170b94af5e0b34281dd6f16aac59` | New Independent Reviewer Onboarding Guide |
