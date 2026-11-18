# Archipelago S5-B1.1 Human Retrieval Relevance Annotation Protocol

## 1. Objective

Independently evaluate candidate passage relevance for 12 academic queries across computer science domains.
This protocol enforces strict double-blind evaluation: reviewers receive only query text, domain labels,
neutral candidate pair identifiers (`PAIR-001` through `PAIR-031`), and source-verified passages.

## 2. Discrete Grading Scale (0, 1, 2)

| Grade | Label | Operational Definition |
|---|---|---|
| **0** | Irrelevant / Distractor | The passage does not provide evidence answering the query, or addresses an unrelated topic. |
| **1** | Partially Relevant / Context | The passage discusses related terminology or background context, but is insufficient on its own to ground the answer. |
| **2** | Highly Relevant / Grounding Evidence | The passage directly answers the query or supplies an essential factual premise required to answer the query. |

## 3. Required Reviewer Judgment Fields

- `human_relevance_grade`: Discrete integer (`0`, `1`, or `2`).
- `human_evidence_quote`: Verbatim substring from the passage supporting grade `1` or `2` (leave blank for grade `0`).
- `human_confidence`: `HIGH`, `MEDIUM`, or `LOW`.
- `human_notes`: Optional free-text observation.

## 4. Independent Dual-Reviewer Procedure

- **Reviewer A** (`reviewer_a_retrieval_workbook.md`) and **Reviewer B** (`reviewer_b_retrieval_workbook.md`) complete judgments independently.
- Candidate ordering within each query has been randomized using deterministic seed `20261118`.
- Inter-annotator agreement is measured after both workbooks are locked using Cohen's Weighted Kappa.
