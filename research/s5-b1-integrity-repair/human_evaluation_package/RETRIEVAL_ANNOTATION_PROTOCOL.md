# Archipelago S5-B1 Human Retrieval Relevance Annotation Protocol

## 1. Objective

Evaluate candidate passage relevance for 12 multi-hop queries across computer science domains.
This protocol establishes strict double-blind standards: annotators must not receive
system predictions, candidate roles, or expected answers.

## 2. Discrete Grading Scale (0, 1, 2)

| Grade | Label | Operational Definition |
|---|---|---|
| **0** | Irrelevant / Distractor | The passage does not answer or ground any aspect of the query, or is completely out of domain. |
| **1** | Partially Relevant / Context | The passage discusses related concepts or provides background context, but does not provide sufficient factual premise to answer the question. |
| **2** | Highly Relevant / Grounding Premise | The passage provides a direct answer or a critical grounding premise needed in multi-hop reasoning. |

## 3. Required Fields

- `human_relevance_grade`: Discrete integer (0, 1, 2).
- `human_evidence_quote`: Verbatim quote from the passage justifying grade 1 or 2 (empty for grade 0).
- `human_confidence`: `HIGH`, `MEDIUM`, or `LOW`.
- `human_notes`: Optional disambiguation notes.

## 4. Blinding Verification

- The candidate pool contains NO role indicators (such as PREMISE or HARD_NEGATIVE).
- Annotators evaluate each pair independently without knowledge of retriever rankings.
