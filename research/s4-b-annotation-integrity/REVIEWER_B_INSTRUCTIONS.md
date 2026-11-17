# Archipelago CIKM Pilot — Two-Stage Instructions for Reviewer B

**Study:** Archipelago CIKM 2027 QA Pilot Evaluation  
**Stage 1 Worksheet:** `artifacts/validation/local_only/s4b_reviewer_b_worksheet.md`  
**Stage 1 Template (JSON):** `artifacts/validation/local_only/s4b_reviewer_b_template.json`  
**Stage 2 Verification Map:** `artifacts/validation/local_only/s4b_stage2_verification_map.json`  

---

## 1. Study Protocol & Blinding

To maintain scientific integrity for our CIKM pilot, you are evaluating candidate passages under strict blinding:
- **No System Identifiers:** Retrieval systems (`bm25`, `dense`, `hybrid_rrf`), ranks, and retrieval scores are completely removed.
- **No Category Labels:** Question classifications (such as single-hop, multi-hop, or unanswerable) have been eliminated.
- **No Source Hints:** Expected source document lists and unanswerability clues are omitted.
- **No Peer Judgments:** Reviewer A's scores and notes are completely hidden.
- **Full Text Provided:** Passages are shown in their full, untruncated form (matching exactly what Reviewer A evaluated).

> **Important Disclosure:** Reviewer A's relevance judgments exist in prior repository commit history. To preserve the validity of this double-blind experiment, do **not** inspect repository Git history or external branches during your annotation work.

---

## 2. Stage 1: Independent Relevance & Answerability Judgments

Open `s4b_reviewer_b_worksheet.md`. For each of the 6 questions:

### A. Assign Relevance Scores (`0 / 1 / 2`)
For each candidate passage, assign an integer grade:
- **`0` (Not Relevant):** The passage does not answer or provide context for the question.
- **`1` (Partially Relevant / Context):** The passage contains useful background, definitions, or partial steps, but is insufficient on its own.
- **`2` (Directly Answers / Supports):** The passage directly answers the query or provides indispensable supporting evidence.

For any passage scored `1` or `2`, copy the exact **Supporting Quote Span** into the designated field.

### B. Query-Level Answerability Assessment
Judge whether the question is:
- `ANSWERABLE`: Can be answered from valid scholarly literature/concepts.
- `UNANSWERABLE_OUT_OF_CORPUS`: The requested information is not present or represents non-existent/future knowledge.
- `CANNOT_DETERMINE`: Question is ambiguous or contradictory.

### C. Multi-Passage Requirement
Record `YES` if answering fundamentally requires synthesizing two or more passages, or `NO` if a single passage provides a self-contained answer.

Submit your completed Stage 1 worksheet to the coordinator before proceeding to Stage 2.

---

## 3. Stage 2: Source & Page Verification

Once Stage 1 is submitted:
1. Open the local candidate-to-source map: `artifacts/validation/local_only/s4b_stage2_verification_map.json`.
2. Inspect the linked PDF/document for passages you marked relevant (score `1` or `2`).
3. Verify that the quote span is authentic and that the printed page number in the original PDF corresponds to the candidate metadata.
4. Record any discrepancies or mismatches in `reviewer_notes`.

---

## 4. Submission Checklist

- [ ] All 113 candidate passages scored (0, 1, or 2) in Stage 1.
- [ ] No candidate left blank or unjudged.
- [ ] Answerability assessed for all 6 questions.
- [ ] Multi-passage requirement recorded for all 6 questions.
- [ ] Stage 1 submitted prior to inspecting Stage 2 source maps.
