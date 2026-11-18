# Archipelago S5-B2.1 Proposed Human Retrieval Relevance Annotation Protocol

**Status:** `PROPOSED_PENDING_INVESTIGATOR_APPROVAL` (Do not freeze or distribute until approved)

## 1. Scope & Statistical Claims Boundary

- Evaluates **10 active academic queries** across Operating Systems, AI & Machine Learning, and Computer Networks.
- **No Validated Cross-Document Query:** Following S5-B2.1 necessity auditing, this pilot contains **zero** validated cross-document queries (all active queries are single-passage or same-document two-passage). No cross-document gains, broad generalization, or statistical superiority may be claimed from this pilot.
- Candidate pool represents the deduplicated union of top-10 retrieved passages across all evaluated systems plus investigator-selected candidates (**265 unique pairs**).

## 2. Discrete Grading Scale (0, 1, 2)

| Grade | Label | Operational Definition |
|---|---|---|
| **0** | Irrelevant / Distractor | The passage does not provide evidence answering the query, or addresses an unrelated topic. |
| **1** | Partially Relevant / Background Context | The passage discusses related terminology or background context, but is insufficient on its own to answer the query. |
| **2** | Highly Relevant / Grounding Evidence | The passage directly answers the query or supplies an essential factual premise required to answer the query. |

## 3. Independent Dual-Reviewer Grading, Adjudication & Agreement Reporting

1. **Independent Grading:** Reviewer A and Reviewer B grade all `265` pairs independently in separate private workbooks without access to system identities, rankings, investigator judgments, or answerability labels.
2. **Inter-Annotator Agreement:** After both reviewers lock their grades, compute and report **Cohen's Weighted Kappa** (quadratic weights) and raw percent agreement across all `265` pairs.
3. **Disagreement Adjudication:** All pairs where Reviewer A and Reviewer B differ (`grade_A != grade_B`) undergo documented third-party / investigator adjudication prior to computing any retrieval metrics.
4. **Unjudged Passage Policy:** Unjudged passages outside the evaluated pool MUST NOT be treated as irrelevant.
