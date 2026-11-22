# S5-C3-P4 — Independent Human Reviewer C (`REV_C`) Instructions

**Status:** `AWAITING_GENUINE_HUMAN_REVIEW`  
**Assigned Editable File (Git-Ignored):** `data/annotation_local/s5c3/independent_reviewer_c_s5c3_workbook.md`  
**Verified Blank Backup (Do Not Edit):** `data/annotation_local/s5c3/immutable_blank_backups/independent_reviewer_c_s5c3_workbook_BLANK_BACKUP.md` (`SHA-256: acf6e86cb23e91a0febaf5181eec8ae3eadbe5ece66ec4d6f1907f74aa10f188`)

---

## 1. Strict Independence & Blinding Rules

- You must be a **genuine human assessor** grading all **254 candidate pairs** independently.
- **Do NOT** use any LLM or AI assistant to generate, draft, or suggest relevance grades, quotes, or notes.
- **Do NOT** view Reviewer A's workbook, Reviewer B's workbook, S5-C2/S5-C3 audit reports, retrieval system rankings, or files inside `excluded_ai_drafts_archive/`.
- Grade solely from the query text and the canonical candidate passage text provided in the workbook.

---

## 2. Step-by-Step Grading Procedure

### Step A — Complete the Provenance Header (Lines 8–16)
Before grading, fill in:
- `reviewer_identity_or_pseudonym`: Your real name or registered pseudonym (e.g., `REV_C_HUMAN_01`).
- `provenance_class`: `INDEPENDENT_HUMAN` (only if zero AI tools and zero prior labels are used).
- `assistance_declaration`: `NONE_INDEPENDENT_HUMAN`.
- `review_start_date_utc`: ISO-8601 UTC date/timestamp when you begin.

### Step B — Grade All 254 Candidate Pairs
For each pair (`S5B21-PAIR-001` through `S5B21-PAIR-254`), do **not** edit the Query ID, Pair ID, Canonical Document Reference, SHA-256, or Candidate Passage Text. Fill in only the 4 judgment fields:

1. **`relevance_grade (0 | 1 | 2)`**
   - **`0` — Irrelevant / Distractor:** Does not provide evidence answering the query (including off-topic mentions, analogies, or keyword collisions).
   - **`1` — Partially Relevant / Background Context:** Shares topic/terminology or provides helpful background, but does **not** independently answer the query or supply a required core factual premise.
   - **`2` — Highly Relevant / Grounding Evidence:** Directly answers the query or supplies an essential factual premise required to answer it.
2. **`supporting_quotation (verbatim for 1/2; blank for 0)`**
   - For grade **`1` or `2`**: Copy-paste an **exact, character-for-character verbatim substring** from the Candidate Passage Text above (no paraphrasing, no ellipses `...` inserted inside a quote).
   - For grade **`0`**: Leave strictly **blank**.
3. **`confidence (HIGH | MEDIUM | LOW)`**
   - Record `HIGH`, `MEDIUM`, or `LOW` reflecting your confidence in the assigned grade.
4. **`reviewer_notes`**
   - Write a brief 1-sentence human justification explaining why the passage received `0`, `1`, or `2`.

### Step C — Finalize & Save
1. Update `review_completion_date_utc` and set `review_completion_status` to `COMPLETED_254_OF_254`.
2. Save the completed file (without modifying the blank backup) to:
   `data/annotation_local/s5c3/submissions/independent_reviewer_c_s5c3_workbook_COMPLETED.md`
3. Record and share the SHA-256 hash of your completed file with the investigator (`sha256sum data/annotation_local/s5c3/submissions/independent_reviewer_c_s5c3_workbook_COMPLETED.md`).
