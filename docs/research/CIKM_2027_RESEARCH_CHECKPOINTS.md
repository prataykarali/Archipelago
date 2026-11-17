# Archipelago — ACM CIKM 2027 Research Checkpoint Log & Policy

## Checkpoint Policy (S1–S3 and Subsequent Milestones)

For all research-repair milestones (`S4`, `S5`, and beyond):

1. **Dedicated Research Branch:** Work on an isolated milestone branch (e.g., `research/s4-...`) without rewriting history or force-pushing (`git push --force` is prohibited).
2. **No Unapproved Merges to `main`:** Do not merge research branches into `main` or production branches without explicit approval.
3. **Test Gate Before Commit:** Run all targeted milestone tests and prior milestone regression tests before committing.
4. **Security & Licensing Gate:** Never commit `.env` files, credentials, API keys, personal data, private research databases, copyrighted source PDFs, bulk passage text exports (`s3_retrieval_candidates_export.*`), model weights, or large binaries.
5. **Scientific Honesty:** Record failed experiments, invalidated benchmarks, and unverified metrics transparently. Passing unit tests does **not** imply publication readiness.

---

## Milestone Checkpoints

### S1 — Gold Graph Evaluation Correctness & Reproducibility
- **Scientific Objective:** Fix whole-graph vs. document-scoped evaluation, relation direction normalization, and schema handling in the gold graph evaluator.
- **Implemented Changes:**
  - `okf/eval/gold/edge_extraction.py`
  - `okf/eval/gold/part01_load_gold_graph.py`
  - `okf/eval/gold/part02_print_report.py`
  - `scripts/run_gold_eval.py`
  - `tests/unit/test_evaluate.py`
  - `artifacts/validation/gold_eval_s1_results.json`
- **Test Results:** `31/31` targeted S1/graph evaluation tests passing (included in the `48/48` S1–S3 suite).
- **Dataset & Benchmark Status:** Document-scoped Concept F1 = `19.05%` (LoRA), `40.00%` (Attention); Directed Edge F1 = `0.00%`.
- **Known Limitations:** Evaluator repairs do not improve model quality; Directed Edge F1 remains `0.00%`, with existing graph cycles and unscopable edges reported.
- **Branch / Remote:** `research/s3-retrieval-baselines` (base `1357204`) — [GitHub Branch](https://github.com/prataykarali/Archipelago/tree/research/s3-retrieval-baselines)

### S2 — Leakage-Free Experimental Dataset & Benchmark Integrity
- **Scientific Objective:** Audit the historical `97.22%` accuracy claim, eliminate train/test leakage via document-disjoint splits, and establish a pilot QA annotation protocol.
- **Implemented Changes:**
  - `archipelago/eval/dataset_integrity.py`
  - `scripts/build_clean_splits.py`
  - `scripts/eval_clean_extraction.py`
  - `tests/unit/test_dataset_integrity_s2.py`
  - `artifacts/validation/s2_historical_benchmark_audit.json`
  - `artifacts/validation/s2_clean_eval_report.json`
  - `artifacts/validation/cikm_qa_pilot_schema.json`
  - `artifacts/validation/cikm_qa_pilot_candidates.jsonl`
  - `docs/research/CIKM_2027_QA_ANNOTATION_PROTOCOL.md`
- **Test Results:** `10/10` S2 dataset integrity tests passing (`41/41` combined S1+S2).
- **Dataset & Benchmark Status:** Historical `97.22%` benchmark **INVALIDATED** (`19/20` evaluation examples present in training split; teacher-forced token accuracy). `clean_splits_v1` established (`113` documents, `748` rows, document-disjoint).
- **Known Limitations:** The `24` pilot QA queries in `cikm_qa_pilot_candidates.jsonl` are `UNVERIFIED_CANDIDATE` and lack human-verified gold annotations.
- **Branch / Remote:** `research/s3-retrieval-baselines` (base `1357204`) — [GitHub Branch](https://github.com/prataykarali/Archipelago/tree/research/s3-retrieval-baselines)

### S3 — Reproducible BM25, Dense Retrieval & Hybrid RRF Baselines
- **Scientific Objective:** Build a fixed, deduplicated, provenance-verified offline passage corpus and reproducible BM25, Dense, and Hybrid RRF baselines with standard IR metrics.
- **Implemented Changes:**
  - `archipelago/eval/retrieval_baselines.py`
  - `scripts/run_s3_retrieval_baselines.py`
  - `tests/unit/test_retrieval_baselines_s3.py`
  - `artifacts/validation/s3_corpus_manifest.json`
- **Test Results:** `7/7` new S3 tests passing; **`48/48` combined S1–S3 regression tests passing** (`pytest` on `research/s3-retrieval-baselines`).
- **Dataset & Benchmark Status:** Fixed corpus `s3_fixed_corpus_v1` contains `764` unique passages across `59` documents (`22` orphan chunks lacking provenance and `22` exact duplicate passages removed). **CIKM retrieval performance is NOT YET MEASURABLE.**
- **Known Limitations:** No human-verified retrieval relevance judgments exist yet (`verified_gold_queries: 0`). Candidate passage exports (`s3_retrieval_candidates_export.json` / `.csv`) are intentionally excluded from Git to avoid redistributing extracted source text.
- **Branch / Remote:** `research/s3-retrieval-baselines` — [GitHub Branch](https://github.com/prataykarali/Archipelago/tree/research/s3-retrieval-baselines)

### S3.1 — Research Evaluation Integration Repair
- **Scientific Objective:** Fix evaluation-runner integration defects (`VERIFIED_GOLD` vs `ADJUDICATED_GOLD`, `gold_supporting_passages` object-to-ID resolution, empty `{}` passed to `evaluate_rankings`, graded `0/1/2` qrels, explicit `UNANSWERABLE_OUT_OF_CORPUS` handling), remove silent 400-row S2 near-duplicate sampling, and add a non-destructive corpus quality audit.
- **Implemented Changes:**
  - `archipelago/eval/dataset_integrity.py`
  - `archipelago/eval/retrieval_baselines.py`
  - `scripts/run_s3_retrieval_baselines.py`
  - `artifacts/validation/s3_corpus_manifest.json`
  - `tests/unit/test_dataset_integrity_s2.py`
  - `tests/unit/test_retrieval_baselines_s3.py`
- **Test Results:** **`52/52` combined S1–S3.1 regression and integration tests passing** (`10` S3/S3.1 + `11` S2 + `31` S1/graph tests).
- **Dataset & Benchmark Status:** Runner is ready to evaluate genuine `ADJUDICATED_GOLD` qrels (`0/1/2` graded + separate `UNANSWERABLE_OUT_OF_CORPUS` tracking), while `cikm_qa_pilot_candidates.jsonl` still has `0` adjudicated queries (`CIKM retrieval performance is NOT YET MEASURABLE.`). Corpus audit flagged `50` index-only passages, `1` invalid page number (`page_number 612 > page_count 500`), `24` one-chunk documents, and `726` passages missing `doc_hash`/`pdf_url` without silent deletion.
- **Known Limitations:** Human annotation and adjudication of the 24 pilot queries has not been performed yet; `726/764` passages lack `doc_hash`/`pdf_url` provenance on `Document` nodes.
- **Branch / Remote:** `research/s3-1-evaluation-integrity` — [GitHub Branch](https://github.com/prataykarali/Archipelago/tree/research/s3-1-evaluation-integrity)

### S4-A — Human-Gold Annotation Pilot & Source Verification
- **Scientific Objective:** Prepare and validate the first 6 human-judged retrieval questions (3 multi-hop prerequisite, 1 single-hop factual, 1 cross-document comparison, 1 unanswerable) with blinded candidate pools, dual-reviewer templates, and source/quote verification.
- **Implemented Changes:**
  - `archipelago/eval/annotation_pilot.py`
  - `scripts/prepare_s4a_annotation_pilot.py`
  - `tests/unit/test_annotation_pilot_s4a.py`
  - `artifacts/validation/s4a_source_verification_report.json`
  - `artifacts/validation/s4a_reviewer_a_template.json`
  - `artifacts/validation/s4a_reviewer_b_template.json`
  - `.gitignore` (excludes `artifacts/validation/local_only/` and `s3_retrieval_candidates_export.*`)
- **Test Results:** **`57/57` combined S1–S4-A regression and pilot quality tests passing** (`5` new S4-A tests + `10` S3/S3.1 + `11` S2 + `31` S1/graph tests).
- **Dataset & Benchmark Status:** Source PDFs for all 5 answerable pilot questions are verified on local disk (`pdfs/papers/`), while `okf_graph.db` `Document` nodes lack `doc_hash`/`pdf_url` metadata. Dual-reviewer templates (`reviewer_a`, `reviewer_b`) and the local blinded worksheet (`artifacts/validation/local_only/s4a_human_annotation_worksheet.md`, gitignored) are ready for independent human annotation (`human_annotations_filled: 0`, `adjudicated_gold_count: 0`).
- **Known Limitations:** No human annotations have been filled yet (`CIKM retrieval performance is NOT YET MEASURABLE.`). Copyrighted/extracted passage text is kept local-only and excluded from Git.
- **Branch / Remote:** `research/s4-a-human-gold-pilot` — [GitHub Branch](https://github.com/prataykarali/Archipelago/tree/research/s4-a-human-gold-pilot)

### S4-B — Annotation Integrity, Blinded Reviewer Handoff & Corpus Verification
- **Scientific Objective:** Audit and preserve the AI-prepared Reviewer A annotations, prepare a fully blinded Reviewer B annotation package, verify all 764 corpus passages, run a near-duplicate/shingling audit, document GraphRAG fairness protocol, and enforce deterministic score extraction.
- **Implemented Changes:**
  - `archipelago/eval/annotation_integrity.py`
  - `scripts/run_s4b_annotation_integrity.py`
  - `tests/unit/test_annotation_integrity_s4b.py`
  - `research/s4-b-annotation-integrity/` (all handoff and audit artifacts)
  - `.gitignore` updated
- **Test Results:** **`54/54` combined S1–S4-B regression tests passing** (`19` new S4-B tests + prior 35).
- **Dataset & Benchmark Status:** Reviewer A annotations preserved and manifested. Reviewer B blinded package staged for independent annotation. Corpus verified at 764 passages. `0` adjudicated gold entries — CIKM retrieval performance remains NOT YET MEASURABLE.
- **Known Limitations:** Reviewer B human annotations not yet filled. GraphRAG fairness cannot be verified until graph-scoped retrieval is production-ready.
- **Provenance Note:** `human_annotation` filename in Reviewer A artifacts refers to AI-prepared annotations — not independent human judgments. Clearly distinguished in manifest and test assertions.
- **Branch / Remote:** `research/s4-b-annotation-integrity` — [GitHub Branch](https://github.com/prataykarali/Archipelago/tree/research/s4-b-annotation-integrity)
- **Remote HEAD:** `e3af789678b4b769d13b0af0f088dad0d4f572cb`

### S4-D — 24-Item Human Evidence Audit vs AI Annotations (Quality Control)
- **Scientific Objective:** Compare 24 human passage-relevance judgments against AI Reviewer A labels to assess annotation quality. Classified as internal quality control — NOT independent double-human gold data.
- **Implemented Changes:**
  - `research/s4-b-annotation-integrity/S4D_HUMAN_AUDIT_COMPARISON_REPORT.md`
  - `research/s4-b-annotation-integrity/human_audit_original.md` (sanitized; full text preserved locally)
  - `research/s4-b-annotation-integrity/human_audit_comparison.csv`
  - `research/s4-b-annotation-integrity/human_audit_disagreements.csv`
  - `scripts/run_s4d_human_comparison.py`
  - `tests/unit/test_s4d_human_audit_comparison.py`
- **Test Results:** **`54/54` regression + `9/9` new S4-D tests = `63` total PASS** (run on `research/s4-b-annotation-integrity`).
- **Agreement Metrics:** Overall agreement = `75.0%` (18/24); Cohen's κ = `0.584` (moderate). AI Reviewer A is consistently more lenient (+1 point) on ambiguous passages.
- **Known Limitations:** Reviewer B labels unavailable for comparison. Human QC sample (n=24) is insufficient for significance testing.
- **Source Redistribution:** `human_audit_original.md` committed to `e3af789` contained 24 verbatim blockquotes from 7 copyrighted papers (28,703 chars). These were sanitized in-place (provenance pointers substituted). Full text preserved at `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: `655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051`). No Git history rewriting (requires explicit authorization).
- **Branch / Remote:** `research/s4-b-annotation-integrity` — [GitHub Branch](https://github.com/prataykarali/Archipelago/tree/research/s4-b-annotation-integrity)
- **Remote HEAD:** `e3af789678b4b769d13b0af0f088dad0d4f572cb`

### S4-E — Research Integrity Audit & Graph Evaluation Diagnosis
- **Scientific Objective:** (1) Source redistribution audit of committed scholarly passages; (2) Full diagnosis of 0% Edge F1, 9 graph cycles, 157 provenance issues, and 101 unscopable edges in the gold-graph evaluator. No fixes implemented — diagnosis only.
- **Implemented Changes:**
  - `research/s4-e-graph-diagnosis/SOURCE_REDISTRIBUTION_AUDIT.md`
  - `research/s4-e-graph-diagnosis/GRAPH_EVALUATION_DIAGNOSTIC_REPORT.md`
  - `research/s4-e-graph-diagnosis/scripts/run_graph_diagnosis.py`
  - `research/s4-e-graph-diagnosis/graph_diagnosis_summary.json`
  - `research/s4-b-annotation-integrity/human_audit_original.md` (copyright sanitization carried over from S4-D)
  - `tests/unit/test_s4e_graph_diagnosis.py`
- **Test Results:** **`60/60` combined S1–S4-E regression tests passing** (`6` new S4-E + prior `54`).
- **Phase 1 — Source Redistribution Findings:**
  - Only `human_audit_original.md` had copyrighted text exposure (committed in `e3af789`).
  - Full original preserved locally with SHA-256 checksum. Tracked file sanitized (passages → provenance pointers). No history rewriting.
- **Phase 2 — Graph Diagnosis Root Causes:**
  1. **0% Edge F1 (Primary):** Endpoint resolution disparity — `compare_concepts()` uses fuzzy matching (token_set_ratio ≥ 90) but `compare_edges()` uses exact canonical key comparison, so fuzzy concept matches do not propagate to edge matching.
  2. **0% Edge F1 (Secondary):** 80% of LoRA gold concepts, 56% of Attention gold concepts were never extracted into `okf_graph.db`.
  3. **101 Unscopable Directed Edges:** Exactly 71 `REQUIRES` + 30 `UNLOCKS` edges carry invalid provenance tags (`pearson_batch1`, `librarian_upload`), making them unscopable to any evaluation document.
  4. **9 Unique Graph Cycles (raw DFS count: 9–10, non-deterministic):** 8 are length-2 symmetric dual insertions from `librarian_upload`; 1 is a length-6 cross-paper semantic cycle. Deduplication by minimum rotation yields stable count of 9.
  5. **1,334 RELATED Edges Skipped:** Evaluator unconditionally excludes `RELATED` edges; they are never evaluated regardless of gold graph content.
  6. **Vacuous Direction Accuracy:** Returns `1.0` when `matched_undirected == 0` — a measurement defect, not a success.
- **Proposed Repair Plan (NOT YET IMPLEMENTED — requires S4-F authorization):**
  - Fix `compare_edges()` to use the concept equivalence map built by `compare_concepts()`.
  - Re-extract missing gold concepts via targeted ingestion.
  - Fix `direction_accuracy` denominator guard (`max(1, matched_undirected)`).
  - Add `--include-related` flag to evaluator (do not remove RELATED by default).
  - Repair or remove the 101 directed edges with invalid provenance tags (requires human review).
- **Known Limitations:** 0% Edge F1 is genuine — not an evaluator-only artifact. Even with evaluator fixes, low concept recall will keep Edge F1 near 0%. No new Archipelago features introduced.
- **Branch / Remote:** `research/s4-e-graph-diagnosis` — [GitHub Branch](https://github.com/prataykarali/Archipelago/tree/research/s4-e-graph-diagnosis)

### S4-F — Gold Graph Evaluator Integrity Repair
- **Scientific Objective:** Repair five scientifically invalid evaluator behaviours without modifying gold fixtures, graph DB, extraction pipeline, or human annotations. Confirm that 0% Edge F1 is a genuine extraction failure, not an evaluator artifact.
- **Implemented Changes:**
  - `okf/eval/gold/compare_aligned.py` (new) — concept-aligned edge evaluator, direction accuracy guard, provenance scoping, relation semantics audit, `evaluate_pipeline_corrected()`
  - `okf/eval/gold/part01_load_gold_graph.py` — Task B fix: `direction_accuracy` returns `None` + `direction_accuracy_status="undefined"` when denominator=0, replacing spurious `1.0`
  - `research/s4-f-evaluator-repair/S4F_EVALUATOR_REPAIR_REPORT.md`
  - `research/s4-f-evaluator-repair/s4f_eval_results.json`
  - `research/s4-f-evaluator-repair/scripts/run_s4f_eval.py`
  - `tests/unit/test_s4f_evaluator_repair.py` (24 new tests)
  - `tests/unit/test_s4e_graph_diagnosis.py` (updated for direction_accuracy=None)
- **Test Results:** **84/84** combined S1–S4-F regression + targeted tests passing (60 prior + 24 new S4-F).
- **Task A — Concept-aligned edge evaluation:** New `compare_edges_aligned()` propagates the fuzzy equiv map from `compare_concepts()` into edge evaluation. Result: Directed Edge F1 **still 0.0** after alignment — confirmed genuine extraction failure (predicted edges connect different concept pairs, not just differently-labelled endpoints).
- **Task B — Direction accuracy guard:** `direction_accuracy=None` + `status="undefined"` when `matched_undirected==0`. Previous `1.0` was vacuous truth (denominator=0).
- **Task C — Provenance-aware scoping:** Scoping bucket now reports `in_scope`, `out_of_scope`, `unscopable`, and `skipped_related` separately. `evaluate_pipeline_corrected()` adds `globally_absent_gold_concepts` (16/20 LoRA, 16/25 Attention).
- **Task D — Relation semantics:** `audit_relation_semantics()` deduplicates DFS cycles via minimum-rotation; stable count = 9. RELATED edges confirmed excluded from cycle detection by design. REQUIRES direction inversion in `_add_edge_record()` verified correct.
- **Task E — Reproducible before/after:** `s4f_eval_results.json` contains baseline and corrected metrics side by side. All baseline concept F1 numbers preserved exactly.
- **Known Limitations:** 0% Edge F1 is genuine — requires extraction pipeline improvements (not evaluator fixes). 101 unscopable directed edges, 1334 unevaluated RELATED edges, and 9 graph cycles remain unchanged (all require human review or S4-G authorization).
- **Breaking change:** `direction_accuracy` field in `compare_edges()` return dict changed from `float` to `float | None`. Downstream callers that test `== 1.0` as success must be updated.
- **Branch / Remote:** `research/s4-f-evaluator-repair` — [GitHub Branch](https://github.com/prataykarali/Archipelago/tree/research/s4-f-evaluator-repair)

### S4-F — Gold Graph Evaluator Integrity Repair
- **Scientific Objective:** Repair five scientifically invalid evaluator behaviours without modifying gold fixtures, graph DB, extraction pipeline, or human annotations. Confirm that 0% Edge F1 is a genuine extraction failure, not an evaluator artifact.
- **Implemented Changes:**
  - `okf/eval/gold/compare_aligned.py` (new) — concept-aligned edge evaluator, direction accuracy guard, provenance scoping, relation semantics audit, `evaluate_pipeline_corrected()`
  - `okf/eval/gold/part01_load_gold_graph.py` — Task B fix: `direction_accuracy` returns `None` + `direction_accuracy_status="undefined"` when denominator=0, replacing spurious `1.0`
  - `research/s4-f-evaluator-repair/S4F_EVALUATOR_REPAIR_REPORT.md`
  - `research/s4-f-evaluator-repair/s4f_eval_results.json`
  - `research/s4-f-evaluator-repair/scripts/run_s4f_eval.py`
  - `tests/unit/test_s4f_evaluator_repair.py` (24 new tests)
  - `tests/unit/test_s4e_graph_diagnosis.py` (updated for direction_accuracy=None)
- **Test Results:** 84/84 combined S1-S4-F regression + targeted tests passing (60 prior + 24 new S4-F).
- **Key Finding (Task A):** After concept-aligned edge evaluation, Directed Edge F1 remains 0.0 for LoRA and Attention. This confirms the 0% result is a genuine extraction failure.
- **Key Finding (Task B):** direction_accuracy=None when matched_undirected=0. Previous 1.0 was vacuous (denominator=0 bug).
- **Key Finding (Task C):** 16 of 20 LoRA gold concepts and 16 of 25 Attention gold concepts are globally absent from okf_graph.db.
- **Key Finding (Task D):** 9 unique prerequisite-only cycles (8 length-2 symmetric, 1 length-6). RELATED edges excluded from cycle detection by design.
- **Breaking change:** direction_accuracy field changed from float to float|None. Callers testing == 1.0 must update.
- **Branch / Remote:** research/s4-f-evaluator-repair

### S4-G1 — Evidence-Grounded Graph Extraction Pilot
- **Branch:** `research/s4-g1-extraction-pilot`
- **Base Commit:** `6bf2ab69daa5f4e74ff1ba83f1b805517c35b3e9`
- **Scientific Objective:** Investigate and prototype improvements to concept extraction and prerequisite relation direction without modifying the frozen baseline, existing gold fixtures, or production graph.
- **Implemented Changes:**
  - `okf/pilot/heuristics_audit.py` (new) — automated audit tool inspecting 7 problematic baseline heuristics on `okf_graph.db` (reciprocal conflicts, unscopable edges, missing intermediate concepts, alphabetical correlation).
  - `okf/pilot/evidence_extractor.py` (new) — evidence-grounded prototype featuring multi-concept chunk extraction, explicit 6-way relation typing (REQUIRES, UNLOCKS, PART_OF, USAGE, CONTRAST, ABSTAIN), strict abstention without heuristic fallbacks, verbatim evidence quotes, and cycle prevention at insertion.
  - `research/s4-g1-extraction-pilot/scripts/run_s4g1_experiment.py` (new) — reproducible controlled experiment comparing baseline vs. prototype on LoRA, Attention, and held-out Bahdanau.
  - `research/s4-g1-extraction-pilot/s4g1_eval_results.json` (new) — structured before/after evaluation artifact.
  - `tests/unit/test_s4g1_extraction_pilot.py` (new) — 16 unit tests covering heuristics audit, relation typing, provenance, cycle prevention, and safety invariants.
  - `research/s4-g1-extraction-pilot/S4G1_EXTRACTION_PILOT_REPORT.md` (new) — comprehensive pilot diagnosis and experimental report.
- **Test Results:** **115/115** tests passing (16 new S4-G1 tests + 99 regression tests across S1–S4-F).
- **Key Findings:**
  - Audited 8 reciprocal REQUIRES/UNLOCKS conflict pairs causing 8 of 9 baseline cycles.
  - Confirmed 101 unscopable edges (15.44%) and 80%/64% missing intermediate concepts in LoRA/Attention.
  - Prototype reduced unsupported edge rate from 15.44% to 0.00%, increased valid provenance coverage from 84.56% to 100.00%, and achieved 0 cycles.
  - Confirmed that primary research papers naturally express usage, contrast, and architecture rather than pedagogical prerequisites, validating the need for cross-document curriculum synthesis in S4-G2.
- **Scientific Constraints Verified:** Zero modifications to `okf_graph.db` or gold fixtures; no hardcoding of LoRA/Transformer rules; pristine held-out source (`Bahdanau2014_Attention.pdf`) un-tuned.

### S4-G2 — Multi-Domain Graph Extraction, Fair Evaluation & Relation Recovery
- **Branch:** `research/s4-g2-multidomain-evaluation`
- **Base Commit:** `b62572f5e6b57ac7202f843f04216a2cceab02b6`
- **Scientific Objective:** Extend relation extraction across 6 core computing domains, diagnose and repair S4-G1 evaluation fairness flaws, recover diverse relation types without heuristic fallbacks, build an independent blinded human annotation package, and deliver a strategic recommendation on the CIKM 2027 paper hypothesis.
- **Implemented Changes:**
  - `okf/pilot/multidomain_extractor.py` (new) — MultiDomainExtractor with 6-way relation typing (REQUIRES, INFERRED_REQUIRES, PART_OF, USES, CONTRASTS_WITH, RELATED, ABSTAIN), multi-sentence windowed context, bidirectional/passive pattern matching, insertion-time cycle prevention, and verbatim snippet citation.
  - `research/s4-g2-multidomain-evaluation/academic_domain_coverage_matrix.csv` (new) — 12-domain audit distinguishing OPAC catalog holdings from accessible full-text corpora (62 full-text docs, 786 linked chunks in DB; catalog holdings legally restricted under copyright).
  - `research/s4-g2-multidomain-evaluation/multidomain_experimental_manifest.json` (new) — 6-domain experimental benchmark with 16 documents partitioned strictly into development (6 docs) and evaluation (10 docs).
  - `research/s4-g2-multidomain-evaluation/domain_level_evaluation.csv` & `s4g2_multidomain_eval_results.json` (new) — domain-level and aggregate metrics across OS, DBMS, DSA, Networks, Compilers, and AI/ML.
  - `research/s4-g2-multidomain-evaluation/scripts/run_s4g2_experiment.py` (new) — reproducible experiment runner.
  - `research/s4-g2-multidomain-evaluation/human_annotation_package/` (new) — independent, blinded human evaluation package with 36 items across 6 domains (`multidomain_human_annotation_pool.csv`, `.md`, `ANNOTATION_GUIDELINES.md`, `annotation_schema.json`, `build_markdown_workbook.py`).
  - `tests/unit/test_s4g2_multidomain_evaluation.py` (new) — 17 unit tests verifying domain coverage, manifest integrity, extractor relations, cycle prevention, and fairness.
  - `research/s4-g2-multidomain-evaluation/S4G2_MULTIDOMAIN_EVALUATION_REPORT.md` (new) — comprehensive scientific report detailing audit, fairness diagnosis, empirical evaluation, and CIKM recommendation.
- **Test Results:** **132/132** tests passing (17 new S4-G2 tests + 115 regression tests across S1–S4-G1).
- **Key Findings:**
  - **S4-G1 Fairness Diagnosis:** S4-G1 evaluated the baseline against the global 610-concept DB (601 false positives, 1.15% precision) while prototype was evaluated against single-document scope. Fair document-scoped baseline concept F1 is **19.05%** for LoRA and **40.00%** for Attention.
  - **Academic Corpus Reality:** Primary research literature and technical chapters express structural components (`PART_OF`), empirical tools (`USES`), and comparative alternatives (`CONTRASTS_WITH`). Explicit prerequisite assertions (*"X is required for Y"*) occur in <0.1% of co-occurring concept pairs.
  - **Prototype Performance:** 0.00% unsupported relations, 100.00% valid provenance coverage, and 0 cycles across all 6 domains.
  - **Strategic CIKM Recommendation:** **GO on Option C (Heterogeneous provenance-grounded knowledge graph)**. Preserves the core CIKM hypothesis (*"Does provenance-aware graph retrieval improve multi-hop academic retrieval and evidence quality against BM25, dense, and hybrid baselines?"*) by leveraging rich typed edges (`PART_OF`, `USES`, `CONTRASTS_WITH`, `REQUIRES`) with passage-level provenance.
- **Scientific Constraints Verified:** Zero modifications to `okf_graph.db` or gold fixtures; no hardcoded domain heuristics; no fabricated gold answers; blinded human evaluation package generated without synthetic labels.


### S4-G2.1 — Multi-Domain Scientific Integrity Gate
- **Branch:** `research/s4-g2-1-integrity-gate`
- **Base Branch:** `research/s4-g2-multidomain-evaluation`
- **Base Commit:** `abad203d64069bf5efcfb5c4e08b9fd82f67fb2a`
- **Scientific Objective:** Verify the scientific validity of the S4-G2 results and 36-item human annotation package before proceeding to independent human evaluation or the main graph-based retrieval experiment.
- **Implemented Changes:**
  - `okf/eval/integrity_validators.py` (new) — Full 3-colour DFS directed cycle detection (k ≥ 2), provenance record validation against `okf_graph.db`, and semantic argument direction auditing.
  - `research/s4-g2-1-integrity-gate/scripts/verify_36_annotation_items.py` (new) — Verifies all 36 items against the live corpus: chunk existence, page match, verbatim evidence occurrence, concept presence, licensing.
  - `research/s4-g2-1-integrity-gate/scripts/audit_overgeneration_and_splits.py` (new) — Diagnoses edge density, noisy concept rate, failure patterns, and evaluation split type per document.
  - `research/s4-g2-1-integrity-gate/source_verification_36_items.csv` (new) — 36-item audit CSV; all 36 classified as MISMATCH.
  - `research/s4-g2-1-integrity-gate/overgeneration_and_cycle_analysis.csv` (new) — Per-document overgeneration breakdown with real cycle counts.
  - `research/s4-g2-1-integrity-gate/evaluation_split_audit.csv` (new) — TOC domain correctly classified as WITHIN_DOCUMENT_CHUNK_SPLIT.
  - `research/s4-g2-1-integrity-gate/CHANGELOG.md` (new) — Itemised record of all 36 annotation audit findings.
  - `research/s4-g2-1-integrity-gate/human_annotation_package/multidomain_human_annotation_pool_corrected.csv` (new) — Corrected pool with audit status; all human judgment fields blank.
  - `research/s4-g2-1-integrity-gate/S4G2_1_INTEGRITY_AUDIT.md` (new) — Full scientific integrity audit report.
  - `tests/unit/test_s4g2_1_integrity_gate.py` (new) — 11 targeted unit tests for all integrity gate components.
  - `research/s4-g2-multidomain-evaluation/scripts/run_s4g2_experiment.py` (modified) — Hardcoded metrics replaced: `unsupported_relation_rate → NOT_MEASURED`, `valid_provenance_coverage → calculate_provenance_coverage()`, `cycles → detect_directed_cycles()`.
  - `tests/unit/test_s4g2_multidomain_evaluation.py` (modified) — `test_zero_unsupported_rate_across_all_domains` updated to accept `NOT_MEASURED` or `0.0`.
- **Test Results:** **128/128** tests passing (11 new S4-G2.1 tests + 117 regression tests across S1–S4-G2).
- **Key Finding (Issue 1 — Hardcoded Metrics):** `unsupported_relation_rate = 0.0`, `valid_provenance_coverage = 1.0`, and `cycles = 0` were literals, not measurements. Real cycle counts: LoRA=24, Bahdanau=18, Network Security=8. Unsupported rate now reported as `NOT_MEASURED` pending human gold labels.
- **Key Finding (Issue 2 — Annotation Pool):** **36/36 items MISMATCH.** Five failure categories: PARAPHRASED_SYNTHESIS (18), UNINDEXED_TOPIC_SYNTHESIS (7), EXTERNAL_THEORY_SYNTHESIS (6), INDEX_LISTING_ATTRIBUTION_ERROR (5). Special case: `doc_fundamentals_of_database_system_7e::chunk_001` claimed for three different page numbers (24, 42, 15) across DBMS-03/04/05; the document has exactly one indexed chunk at page 145. No items were silently replaced.
- **Key Finding (Issue 3 — Overgeneration):** Book-index cross-product: `data_science_2019/Index_2019_Data-Science.pdf` generated 14,894 USES edges from 622 headword entries — fundamentally wrong document type. Broad trigger patterns (`uses`, `requires`) match across unrelated concept pairs. Noisy concept rate 17–58% across documents.
- **Key Finding (Issue 4 — Split Honesty):** TOC domain uses a within-document chunk split (chunks 0–9 dev, 10–19 eval from same `Willard2023_Outlines.pdf`). Re-classified from implied DOCUMENT_DISJOINT to WITHIN_DOCUMENT_CHUNK_SPLIT. Five other domains are genuinely document-disjoint.
- **Scientific Constraints Verified:** `okf_graph.db` unmodified (read-only); gold fixtures (`gold_lora.json`, `gold_attention.json`) unmodified; original annotation pool preserved alongside corrected version; all human judgment fields remain blank; no synthetic passages inserted.
- **STOP Confirmed:** S4-G2.1 is complete. The main retrieval experiment (S4-H) may not proceed until (a) the annotation pool is rebuilt from verified verbatim corpus text, (b) concept extraction denoising is applied, (c) multi-hop cycle prevention is upgraded, and (d) TOC domain acquires a second independent document.


### S4-G2.2 — Corpus-Locked Annotation Reconstruction
- **Branch:** `research/s4-g2-2-corpus-locked-annotation`
- **Base Branch:** `research/s4-g2-1-integrity-gate`
- **Base Commit:** `2147ececc3f7c09b4717381c23d5979548af97b7`
- **Scientific Objective:** Construct the first mechanically verified, source-grounded annotation candidate pool directly from the frozen Kùzu corpus without synthetic text or general-knowledge fabrication.
- **Implemented Changes:**
  - `okf/eval/integrity_validators.py` — Hardened 5-layer provenance validator (`validate_provenance_record`): L0 input sanity, L1 doc existence, L2 chunk linked to document with strict null-substitution invariant (never substitutes claimed chunk ID), L3 advisory page number verification, L4 exact/whitespace-normalized evidence match rejection of empty/punctuation-only/approximate text, L5 explicit separation of source pointer validity from human semantic support (`NOT_MEASURED`). Added backward-compatibility adapter for `validate_edge_provenance`. Clarified cycle detection methodology note (DFS back-edge representative cycles vs elementary cycles).
  - `research/s4-g2-2-corpus-locked-annotation/scripts/build_corpus_locked_candidates.py` — Mechanical candidate generator extracting verbatim text spans from verified chunks with byte offsets and 16-hex SHA-256 chunk fingerprints.
  - `research/s4-g2-2-corpus-locked-annotation/annotation_candidates/annotation_candidates_verified.csv` — 24-item corpus-locked annotation candidate pool spanning OS, AIML, NETS, TOC, DBMS, and COMPILERS. All 24 items verified with EXACT evidence match.
  - `research/s4-g2-2-corpus-locked-annotation/annotation_candidates/candidate_pool_summary.json` — Structured audit metadata, candidate categories (`POSSIBLE_RELATION: 23`, `AMBIGUOUS: 1`), domain stats, and eligibility matrix.
  - `research/s4-g2-2-corpus-locked-annotation/domain_audit/domain_eligibility_and_split_report.md` — Domain eligibility classification and evaluation split documentation (OS, AIML, NETS eligible with document-disjoint splits; TOC exploratory with within-document chunk split; book indices excluded).
  - `research/s4-g2-2-corpus-locked-annotation/S4G2_2_CORPUS_LOCKED_EVIDENCE_REPORT.md` — Full scientific report detailing validator hardening, cycle detection terminology correction, candidate generation, and split integrity.
  - `tests/unit/test_s4g2_2_corpus_locked_annotation.py` — 40 adversarial and regression tests covering wrong chunks, wrong pages, approximate match rejection, punctuation-only rejection, empty text rejection, cycle fixtures, and candidate pool integrity.
- **Test Results:** **168/168** tests passing (40 new S4-G2.2 tests + 128 regression tests across S1–S4-G2.1).
- **Key Findings:**
  - Hardened provenance validator completely eliminates false positives by requiring exact document and linked chunk identity, setting `actual_chunk_id=None` when missing.
  - 24-item candidate pool generated entirely from frozen database passages (`okf_graph.db`).
  - Zero human judgments fabricated: all candidates remain `CANDIDATE_UNLABELED`.
  - TOC domain maintained as exploratory (`WITHIN_DOCUMENT_CHUNK_SPLIT`) until independent document is acquired.
- **Scientific Constraints Verified:** No modifications to `okf_graph.db` or gold fixtures; no AI-generated or synthetic text; human annotation columns blank; original 36 invalid S4-G2 items preserved unchanged; STOP maintained before human labeling or retrieval experiments.

### S4-G3 — Controlled Extraction Pipeline Repair & Blinded Annotation Handoff
- **Branch:** `research/s4-g3-extraction-repair`
- **Base Branch:** `research/s4-g2-2-corpus-locked-annotation`
- **Base Commit:** `0f78955bdc2e719d01be4aef5fa67d60f3420ac9`
- **Scientific Objective:** Repair the evidence-grounded academic concept-and-relation extraction pipeline across supported domains, eliminate spurious book-index explosions and prerequisite cycles, establish a blinded human annotation package, audit copyright/redistribution, and complete a controlled evaluation without modifying the production graph.
- **Implemented Changes:**
  - `okf/pilot/repaired_extractor.py` — New repaired extraction pipeline featuring:
    1. Automated document pre-screening: rejects book indices, bibliographies, sparse catalog records (`is_excluded_document`).
    2. Concept denoising: filters numeric tokens (`128KB`, `65B`, `48GB`), measurement units, figure/table references, and discourse markers while preserving canonical domain acronyms (`ANN`, `GNN`, `NIDS`, `LoRA`, `QLORA`, `LSTM`, `BERT`, `TLB`, `DFA`, `NFA`, `3NF`, `AST`, `CFG`) and compound terminology (`Virtual Memory`, `Page Table`, `Relational Algebra`).
    3. Clause-aware relation extraction: enforces syntactic binding within clauses/tight sentence scope ($\le 150$ chars) and preserves semantic direction for asymmetric `REQUIRES`, `PART_OF`, and `USES` relations.
    4. Prerequisite-specific DAG enforcement: implements reachability DFS cycle prevention specifically on prerequisite relations (`REQUIRES`, `INFERRED_REQUIRES`), allowing heterogeneous multi-relational graphs to retain natural non-prerequisite cyclic patterns.
  - `okf/eval/integrity_validators.py` — Updated with `strict_page_match=True` gate requiring exact page number agreement for strict admission.
  - `research/s4-g3-extraction-repair/annotation_package/` — Full annotation handoff:
    - `blinded/blinded_human_annotation_pool.csv` & `blinded_human_annotation_workbook.md`: 24 items with neutral IDs (`ANN-01` to `ANN-24`), blank judgment fields, and stripped hints.
    - `blinded/ANNOTATOR_INSTRUCTIONS.md`: Strict evidence-grounded guidelines.
    - `admin/selection_manifest.json`: Master cryptographic linkage with byte offsets and SHA-256 chunk fingerprints.
    - `admin/candidate_reconciliation_report.md`: Reconciles the 5 intermediate rejected specifications.
    - `public/candidate_metadata_index.csv`: Content-free public release index (zero verbatim text).
  - `research/s4-g3-extraction-repair/copyright_audit/source_redistribution_and_git_exposure_audit.md` — Legal audit establishing that Open Access $\neq$ unrestricted redistribution, detailing proprietary vs CC licenses, and providing Git history exposure review without destructive history rewrites.
  - `research/s4-g3-extraction-repair/scripts/run_s4g3_evaluation.py` — Controlled benchmark comparing baseline vs repaired extractor across 12 documents.
  - `research/s4-g3-extraction-repair/evaluation_results/` — `s4g3_controlled_comparison_results.json` and `comparison_metrics_table.csv`.
  - `research/s4-g3-extraction-repair/S4G3_EXTRACTION_REPAIR_REPORT.md` — Full scientific report.
  - `tests/unit/test_s4g3_extraction_repair.py` — 96 unit and adversarial tests covering pre-screening, denoising, clause relations, cycle prevention, blinded package integrity, and strict page verification.
- **Test Results:** **264/264** tests passing across S1–S4-G3 (96 new S4-G3 tests + 168 regression tests).
- **Key Findings:**
  - **Index Explosion Eliminated:** Baseline exploded into 39,435 edges taking 177s on `data_science_2019/Index_...`; repaired pipeline instantly excluded it (0 edges, 0.00s).
  - **Concept Noise Purged:** Noisy concept rate dropped from **33.8% average (up to 52.0%) to 0.0%**.
  - **Prerequisite Cycles Purged (208 $\to$ 0):** Baseline formed 208 prerequisite cycles across papers; repaired pipeline formed **0 prerequisite cycles**.
  - **Runtime Speedup:** Overall runtime reduced from **242.89s to 0.90s** (~270x faster).
  - **Safeguards Maintained:** Unsupported relation rate strictly reported as `NOT_MEASURED`; retrieval effectiveness strictly reported as `NOT_EVALUATED`.
- **STOP Confirmed:** S4-G3 is complete. Production graph untouched; gold fixtures untouched; zero human labels fabricated.

### S4-G4 — Final Extraction Validation & Retrieval Readiness
- **Branch:** `research/s4-g4-validation-readiness`
- **Base Branch:** `research/s4-g3-extraction-repair`
- **Base Commit:** `8ff96f22bf3cb39c37a7f59648f8c0872e9d6148`
- **Scientific Objective:** Validate the repaired extractor, protect annotation materials from public repository exposure, audit concept quality independently of extractor heuristics, analyze zero-edge documents, freeze extractor hyperparameters, construct and smoke-test the offline multi-hop retrieval comparison harness, and reconcile all test suite counts.
- **Implemented Changes:**
  - `PUBLIC_EXPOSURE_AND_REMEDIATION_AUDIT.md`: Complete audit of historical Git exposure across 10 commits and 11 documents. Documents proprietary copyright of Pearson textbooks, Elsevier journal, and OSTEP. Provides safe remediation playbook (`git-filter-repo`) for repository owners.
  - `.gitignore`: Updated with strict exclusion rules for `data/annotation_local/` and local annotation files.
  - `hydrate_local_annotation_pool.py`: Safe on-demand hydration script verifying 100% SHA-256 hashes against local `okf_graph.db` without tracking verbatim text in Git.
  - `candidate_metadata_index.csv`: Public metadata-only candidate index with accurate redistribution statuses (Pearson, Elsevier, OSTEP as `RESTRICTED_METADATA_ONLY`).
  - `build_concept_quality_audit.py`: Independent concept quality audit package sampling 54 candidates (27 retained, 27 rejected) across OS, AIML, and Networks. Emits public blinded pool with empty human fields. Reports 100% filter consistency and leaves semantic precision/recall as `NOT_MEASURED`.
  - `RELATION_COVERAGE_AND_ZERO_EDGE_AUDIT.md`: Detailed structural and syntactic root-cause analysis explaining zero edges in `08_Paging.pdf`, `doc_computer_networks_6_e`, `doc_fundamentals_of_database_system_7e`, and `doc_compilers_principles_techniques_and_tools`.
  - `okf/pilot/repaired_extractor_config.json`: Formally frozen extractor configuration (version `s4-g3-repaired-v1.0`).
  - `run_retrieval_smoke_test.py`: Offline multi-hop retrieval comparison harness executing BM25, Dense, Hybrid RRF, Baseline Graph, and Repaired Heterogeneous Graph retrieval on identical 764 passages.
  - `retrieval_smoke_test_report.json`: Technical sanity verdict `ALL_SYSTEMS_FUNCTIONAL` (0 schema errors, 0 crashes, sub-10ms latencies). Strictly enforces `retrieval_effectiveness = "NOT_EVALUATED"` pending independently judged gold query relevance labels.
  - `tests/unit/test_s4g4_validation_readiness.py`: 10 validation tests covering public exposure rules, metadata schemas, local hydration, concept quality audit, zero-edge behavior, retrieval smoke test, and test reconciliation.
- **Test Results:** **274/274** tests passing across S1–S4-G4 (10 new S4-G4 tests + 264 regression tests).
- **Test Reconciliation:** Resolved the 270 vs 264 discrepancy by identifying an erroneous entry in the S4-G3 report table where `test_s4e_graph_diagnosis.py` was listed as 12 items while actually containing exactly 6 ($270 - 6 = 264$).
- **STOP Confirmed:** S4-G4 is complete. All research objectives achieved. No further autonomous milestones initiated.

