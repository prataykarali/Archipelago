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

