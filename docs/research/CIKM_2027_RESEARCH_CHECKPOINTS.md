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
