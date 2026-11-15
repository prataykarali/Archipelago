# ACM CIKM 2027 Research QA Benchmark & Human Annotation Protocol

## 1. Research Question

> **Does provenance-verified, directed prerequisite-graph retrieval improve multi-hop academic retrieval and citation correctness compared with BM25, dense retrieval, hybrid RRF, and an untyped graph baseline?**

## 2. Benchmark Record Schema

Formal JSON Schema: `artifacts/validation/cikm_qa_pilot_schema.json`. Every record contains:

1. `query_id` (string): Unique identifier (e.g., `CIKM-PILOT-001`).
2. `source_doc_ids` (array[string]): Canonical `doc_id`s from `okf_graph.db` required to answer the query.
3. `question` (string): Academic question requiring multi-hop, prerequisite, or provenance-grounded retrieval.
4. `question_category` (enum): `single_hop_definition`, `multi_hop_prerequisite`, `cross_paper_comparison`, `provenance_citation_check`, `unanswerable_out_of_corpus`.
5. `gold_supporting_passages` (array[object]): Verified `{doc_id, chunk_id, page_number, quote_span}` entries (empty until human-annotated).
6. `exact_page_refs` (array[string]): Canonical `<doc_id>#page=<N>` references.
7. `relevant_passage_labels` (object): Mapping `<doc_id>:<chunk_id> -> graded_relevance (0=irrelevant, 1=partial, 2=essential)`.
8. `expected_prerequisite_paths` (array[array[string]]): Ordered directed prerequisite chains `[c_0, c_1, ..., c_k]` where applicable.
9. `answerability_status` (enum): `ANSWERABLE`, `PARTIALLY_ANSWERABLE`, `UNANSWERABLE_OUT_OF_CORPUS`, `PENDING_ANNOTATION`.
10. `annotator_id` (string | null): Identifier of primary human annotator (`null` for unverified candidates).
11. `annotation_confidence` (number | null): Annotator self-reported confidence `[0.0, 1.0]` and `disagreement_notes` (string | null).
12. `review_status` (enum): `UNVERIFIED_CANDIDATE`, `SINGLE_ANNOTATED`, `DOUBLE_ANNOTATED_DISAGREEMENT`, `ADJUDICATED_GOLD`.

## 3. Two-Annotator & Adjudication Protocol

1. **Candidate Preparation:** Candidate questions (`artifacts/validation/cikm_qa_pilot_candidates.jsonl`) are generated for annotation preparation only and MUST carry `review_status = "UNVERIFIED_CANDIDATE"`. They are **never** used as ground-truth evaluation labels until adjudicated.
2. **Independent Double Annotation:** Two domain-literate annotators (e.g., CS/ML graduate students or faculty-supervised annotators) independently inspect the cited PDFs and chunks, label `relevant_passage_labels` (`0/1/2`), mark `exact_page_refs`, verify `expected_prerequisite_paths`, and record `answerability_status` and `annotation_confidence`.
3. **Inter-Annotator Agreement (IAA):**
   - Compute **Cohen's $\kappa$** on `answerability_status` and binary passage relevance (`>= 1` vs `0`).
   - Compute **Krippendorff's $\alpha$** (ordinal) on graded passage relevance (`0/1/2`).
   - Target threshold before freezing gold: $\kappa \ge 0.75$, $\alpha \ge 0.75$.
4. **Adjudication:** Any query where Annotator A and Annotator B disagree on `answerability_status`, essential passage set (`label == 2`), or prerequisite edge direction enters `DOUBLE_ANNOTATED_DISAGREEMENT` and is resolved by a third senior/faculty reviewer into `ADJUDICATED_GOLD` with recorded `disagreement_notes`.
