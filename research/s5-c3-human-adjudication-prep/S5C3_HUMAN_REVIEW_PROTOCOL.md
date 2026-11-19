# S5-C3 — Human Relevance Review & Annotation Provenance Protocol

**Stage:** S5-C3-P0 (Human Adjudication Preparation)  
**Base Commit (E0 Preserved):** `10c207ec58d9bc906b83b81badc5aadac37de374`  
**Date:** 2026-11-19  
**Status:** `HUMAN_REVIEW_REQUIRED` (Preparation complete; zero judgments generated)

---

## 1. Purpose & Scope

This protocol governs independent human relevance assessment for the frozen 254-pair S5-B2.1 pooled candidate set (`s5b2_1_proposed_pooled_v2.1_pending_approval`, `SHA-256: 2d13454655dda965304ac4aabddbeef5e39b77bc6927393bebfdaa94235fb037`) drawn from the frozen 713-passage corpus `s5a_eval_corpus_v1` (`SHA-256: 6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7`).

It establishes:
1. A strictly blinded private review package for independent human grading.
2. An explicit four-class **Annotation Provenance Taxonomy** that forbids disguising AI-assisted annotations as independent human judgments.
3. Mandatory per-reviewer and per-pair metadata requirements.

---

## 2. Private Blinded Reviewer Package (Git-Ignored Only)

Generated reproducibly by [build_s5c3_private_packages.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c3-human-adjudication-prep/scripts/build_s5c3_private_packages.py) and stored **exclusively** in Git-ignored `data/annotation_local/s5c3/` (confirmed ignored by `.gitignore:140`):

- `data/annotation_local/s5c3/independent_reviewer_c_s5c3_workbook.md` (254 blinded pairs with canonical `okf_graph.db` passage text, verified against `passage_sha256`)
- `data/annotation_local/s5c3/independent_reviewer_c_s5c3_sheet.csv` (matching 254-row blank structured response sheet)

### 2.1 Included Fields per Candidate Pair (All 254 Pairs)
- `query_id` and exact `query_text`
- Frozen `pair_id` (`S5B21-PAIR-001` through `S5B21-PAIR-254`, deterministic `seed = 20261119`)
- Canonical candidate passage text hydrated directly from `okf_graph.db` (`s5a_eval_corpus_v1`)
- Canonical document/chunk/page reference (`candidate_doc_id`, `candidate_chunk_id`, `candidate_page_number`) and `passage_sha256`
- Blank `relevance_grade` (`0 | 1 | 2`)
- Blank `supporting_quotation` (verbatim substring required for grades `1` and `2`; must be blank for grade `0`)
- Blank `confidence` (`HIGH | MEDIUM | LOW`)
- Blank `reviewer_notes`

### 2.2 Explicitly Excluded Information (Blinding Enforcement)
Automated verification in `build_s5c3_private_packages.py` enforces zero occurrences in non-passage metadata/headers of:
- Original Reviewer A (`REV_A`) or Reviewer B (`REV_B`) grades, quotes, or notes
- Model-generated or AI-suggested grades
- Retrieval-system identities (`bm25`, `dense_snowflake_arctic_768d`, `hybrid_rrf_e2e`, `baseline_graph_1hop`, `repaired_graph_1hop_ablation`, `repaired_graph_2hop_full`)
- Existing disagreement indicators
- Answerability, hop-count, or category hints (`UNANSWERABLE`, `NEGATIVE_CONTROL`, `SINGLE_HOP`, `TWO_HOP`, `CROSS_DOCUMENT`)

---

## 3. Annotation Provenance Taxonomy (Mandatory Classification)

Every submitted annotation stream and every adjudicated judgment MUST carry an explicit `provenance_class` from the four mutually exclusive categories below. **AI assistance must never be disguised, relabeled, or silently promoted into `INDEPENDENT_HUMAN`.**

| `provenance_class` | Operational Definition | Eligible as Independent Human Stream for Inter-Human Kappa? | Eligible as Final Gold Input to S5-D1? |
|---|---|---|---|
| **`INDEPENDENT_HUMAN`** | Judgment produced exclusively by a human assessor working from the blinded package with **zero** exposure to LLM/AI-generated candidate grades, rationales, or prior reviewer labels. | **Yes** | **Yes** (when paired with a second `INDEPENDENT_HUMAN` stream + adjudication, or under an explicitly disclosed single-human pilot) |
| **`HUMAN_POST_AI_EXPOSURE`** | Judgment produced or confirmed by a human assessor **after** viewing AI-generated or AI-assisted suggested grades/rationales (e.g., reviewing `REV_B`). Subject to anchoring bias; must be disclosed transparently. | **No** (cannot be reported as blind independent inter-human reliability) | Only if explicitly disclosed as AI-anchored human review; **not** equivalent to independent human grading |
| **`AI_ASSISTED_OR_GENERATED`** | Judgment drafted or proposed with LLM/AI assistance without independent human re-grading (includes `REV_B`'s 254/254 S5-C2 submission). | **No** | **No** (blocked by S5-D0/S5-C2 gate) |
| **`ADJUDICATED_HUMAN`** | Final resolution judgment produced by a designated human adjudicator examining canonical passage text and preserved disagreeing streams with documented written rationale. | N/A (resolution layer) | **Yes** (only when upstream streams meet declared provenance rules) |

---

## 4. Mandatory Provenance Metadata Schema

Every completed review workbook or CSV submission must record:
- `reviewer_identity_or_pseudonym` (e.g., `REV_C_HUMAN`, never anonymous/blank)
- `provenance_class` (`INDEPENDENT_HUMAN | HUMAN_POST_AI_EXPOSURE | AI_ASSISTED_OR_GENERATED | ADJUDICATED_HUMAN`)
- `assistance_declaration` (`NONE_INDEPENDENT_HUMAN | EXPOSED_TO_AI_SUGGESTIONS | AI_ASSISTED`)
- `review_start_date_utc` and `review_completion_date_utc` (ISO-8601)
- `evidence_source_used` (`okf_graph.db (s5a_eval_corpus_v1, 713 passages)`)
- `review_completion_status` (`NOT_STARTED | IN_PROGRESS | COMPLETED_254_OF_254`)

---

## 5. Discrete Relevance Grading Rubric

| Grade | Label | Operational Definition | Supporting Quote Rule |
|---:|---|---|---|
| **0** | Irrelevant / Distractor | Passage does not provide evidence answering the query, or addresses an unrelated topic. | Must be **blank** |
| **1** | Partially Relevant / Background Context | Passage discusses related terminology or background context, but is insufficient on its own to answer the query. | **Exact verbatim substring** from the canonical passage required |
| **2** | Highly Relevant / Grounding Evidence | Passage directly answers the query or supplies an essential factual premise required to answer the query. | **Exact verbatim substring** from the canonical passage required |
