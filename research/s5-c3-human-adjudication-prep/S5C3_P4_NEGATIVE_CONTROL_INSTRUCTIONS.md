# S5-C3-P4 — Human Negative-Control Verifier Instructions

**Status:** `AWAITING_GENUINE_HUMAN_REVIEW`  
**Assigned Editable File (Git-Ignored):** `data/annotation_local/s5c3/s5c3_negative_control_verification_worksheets.md`  
**Verified Blank Backup (Do Not Edit):** `data/annotation_local/s5c3/immutable_blank_backups/s5c3_negative_control_verification_worksheets_BLANK_BACKUP.md` (`SHA-256: 678cc2fcdd6bd5fa1ce0deec90c6ebdd1ece6e2bd3764c226c1318467e32662c`)

---

## 1. Queries Requiring Independent Human Corpus-Wide Verification

1. **`Q-S5B2-03`:** *"What is the exact multi-level page table walk latency in nanoseconds for the ARM Cortex-A78 microarchitecture?"*
2. **`Q-S5B2-08`:** *"What was the exact total electricity cost in US dollars to train Meta's Llama-3 405B model on 16,000 H100 GPUs?"*
3. **`Q-S5B2-11`:** *"What is the exact CVE identifier and patched firmware version for the 2025 Cisco Catalyst 9300 remote buffer overflow vulnerability?"*

---

## 2. Mandatory Corpus-Wide Scope Rule (713 Eligible Passages / 53 Documents)

- Verification MUST address the **entire eligible frozen corpus (`s5a_eval_corpus_v1`: 713 passages across 53 documents, `corpus_sha256: 6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7`)** — **not** merely the pooled Top-10 retrieval candidates.
- **Critical Guardrail:** The search-selected / hydrated candidate passages listed in each worksheet (`21` for Q03, `31` for Q08, `22` for Q11) **guide inspection**, but **must NOT by themselves be treated as proof** that the remaining passages in the 713-passage corpus contain no answer.
- To classify a query as `NO_ANSWER_IN_FROZEN_CORPUS`, you must independently verify BOTH:
  1. Every hydrated candidate passage in the worksheet (`contains_answer` = `YES | NO | PARTIAL_OR_AMBIGUOUS` + brief `inspection_note`), **AND**
  2. The full 53-document corpus inventory and independent corpus-wide keyword/synonym/document checks across all 713 eligible passages (recording any additional queries you ran in `additional_corpus_queries_run_by_verifier`). If you only inspect the hydrated candidates without establishing full corpus-wide exclusion, you MUST select `NO_ANSWER_IN_SELECTED_PASSAGES` instead of `NO_ANSWER_IN_FROZEN_CORPUS`.

---

## 3. Supported Classifications (Select Exactly One per Query)

1. **`NO_ANSWER_IN_FROZEN_CORPUS`** — Verified corpus-wide unanswerable across all 713 eligible passages / 53 documents.
2. **`NO_ANSWER_IN_SELECTED_PASSAGES`** — Inspected candidates contain no answer, but full corpus-wide exclusion is not established.
3. **`AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION`** — Question premise is ambiguous, unverified, or factually unsupported/synthetic.
4. **`QUESTION_REQUIRING_REVISION`** — Question is answerable in the frozen corpus (provide exact `passage_id` and verbatim quote) or malformed and requires revision.

Also assess `external_factual_premise_assessment` truthfully (whether the external real-world factual premise of the question is verified, unverified/unreported, or synthetic/false).

---

## 4. Truthful Provenance Declaration & Saving

- Do **NOT** use LLM/AI outputs (including `AI_JUDGE_B_STRICT_AUDIT` or files in `excluded_ai_drafts_archive/`) to populate these worksheets.
- Record for each of the 3 queries:
  - `verifier_id` (your human name or registered pseudonym)
  - `provenance_class` (`INDEPENDENT_HUMAN` only if zero AI assistance/exposure; otherwise truthfully record `HUMAN_POST_AI_EXPOSURE` or `AI_ASSISTED_OR_GENERATED`)
  - `verification_date_utc` (ISO-8601 UTC)
  - `checked_passage_ids` and `verification_rationale` (explicitly summarizing both candidate inspection and corpus-wide 53-doc / 713-passage scope).
- Save the completed file to:
  `data/annotation_local/s5c3/submissions/s5c3_negative_control_verification_worksheets_COMPLETED.md`
