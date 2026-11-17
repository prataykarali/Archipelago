# Archipelago CIKM Pilot — Manual Instructions for Reviewer B

**Study:** Archipelago CIKM 2027 QA Pilot Evaluation  
**Worksheet:** `artifacts/validation/local_only/s4b_reviewer_b_worksheet.md`  
**Template (JSON submission):** `artifacts/validation/local_only/s4b_reviewer_b_template.json`  

---

## 1. Overview and Guidelines

You are acting as an **independent annotator (Reviewer B)** for a 6-question scientific QA pilot study.
- Your judgments must be formed independently.
- You do not have access to Reviewer A's judgments, retrieval system names, retrieval ranks, or system scores.
- Question category labels have been removed from your worksheet to avoid confirmation or indexing bias.
- **Do not assume that passages not in this candidate pool are irrelevant.** If necessary, verify claims against the original paper PDFs.

---

## 2. Graded Relevance Judgments (`0 / 1 / 2`)

For each candidate passage listed under a question, assign a relevance grade:

| Grade | Label | Operational Definition |
| :--- | :--- | :--- |
| **`0`** | **Not Relevant** | The passage does not answer or provide meaningful context for the question. Includes passages that are off-topic or merely share keywords without addressing the query. |
| **`1`** | **Partially Relevant / Context** | The passage provides relevant domain context, prerequisites, or partial information, but does not provide a complete answer by itself. |
| **`2`** | **Directly Answers / Supports** | The passage directly answers the question or provides core evidence/reasoning required to resolve it. |

---

## 3. Query-Level Annotations

For each of the 6 questions, record the following fields:

1. **Answerability Assessment:**
   - `ANSWERABLE`: The question can be answered from documents in the scholarly literature/corpus.
   - `UNANSWERABLE_OUT_OF_CORPUS`: The information requested is not present in the corpus or represents unreleased/future information.
   - `CANNOT_DETERMINE`: Information is ambiguous or contradictory.

2. **Requires Multiple Supporting Passages:**
   - `YES` (`true`): Answering the question fundamentally requires synthesizing information across two or more distinct passages/chunks (e.g. multi-step reasoning, cross-paper comparison).
   - `NO` (`false`): A single passage contains a self-contained answer.

3. **Quote and Page Verification:**
   - For every passage you score `1` or `2`, record the exact quote span and verify that the page number in the candidate matches the source PDF.
   - If a quote cannot be verified or page is inconsistent, note this in the reviewer notes.

---

## 4. How to Submit

1. Open `artifacts/validation/local_only/s4b_reviewer_b_worksheet.md` in your text editor.
2. Fill in the blank fields:
   - Relevance: replace `___` with `0`, `1`, or `2`.
   - Quote span: fill in direct quotation for relevant passages.
   - Answerability and multi-passage lines.
3. Alternatively (or additionally), fill in `artifacts/validation/local_only/s4b_reviewer_b_template.json` directly under `passage_relevance_judgments` and the query verification fields.
4. Verify all 113 candidate passages have been judged. Do not leave any candidate blank.
5. Notify the study coordinator upon completion. Do not share your worksheet with Reviewer A.
