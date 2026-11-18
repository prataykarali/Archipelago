# Archipelago S5-B2 Proposed Human Retrieval Relevance Annotation Protocol

**Status:** `PROPOSED_PENDING_INVESTIGATOR_APPROVAL` (Do not distribute until approved)

## 1. Objective

Independently evaluate candidate passage relevance for 10 active academic queries across computer science domains.
Reviewers receive only query text, domain labels, neutral pair identifiers (`S5B2-PAIR-001`..`S5B2-PAIR-025`),
and source-verified passages.

## 2. Discrete Grading Scale (0, 1, 2)

| Grade | Label | Operational Definition |
|---|---|---|
| **0** | Irrelevant / Distractor | The passage does not provide evidence answering the query, or addresses an unrelated topic. |
| **1** | Partially Relevant / Context | The passage discusses related terminology or background context, but is insufficient on its own to ground the answer. |
| **2** | Highly Relevant / Grounding Evidence | The passage directly answers the query or supplies an essential factual premise required to answer the query. |

## 3. Independent Dual-Reviewer Procedure

- **Reviewer A** (`reviewer_a_s5b2_workbook.md`) and **Reviewer B** (`reviewer_b_s5b2_workbook.md`) grade independently.
- Candidate ordering within each query is randomized using deterministic seed `20261119`.
- Unjudged passages from system top-k outputs are NOT assumed irrelevant.
