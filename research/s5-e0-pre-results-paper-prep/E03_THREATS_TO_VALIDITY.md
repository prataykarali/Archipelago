# E0.3 Part B — Comprehensive Threats to Validity

**Phase:** S5-E0.3 Part B (Pre-Results Methodological Critique)  
**Repository:** `/home/pratay-karali/Desktop/archipelago/Archipelago`  
**Base Commit:** `6450585f60b3c1bea7bef2f411458800552cea0b`  
**Audit Date:** 2026-11-19  
**Cross-References:** [S5D0_LIMITATIONS_REGISTER.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/S5D0_LIMITATIONS_REGISTER.md), [E01_RESEARCH_GAPS.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_RESEARCH_GAPS.md), [E03_METHODS_AUDIT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E03_METHODS_AUDIT.md), [E03_RELATED_WORK.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E03_RELATED_WORK.md).

This document provides a structured internal, construct, conclusion, and external validity critique covering all **10 required methodological issues** of the Archipelago v2.1 retrieval pilot. Every threat is linked to verified frozen evidence and paired with its exact interpretation boundary.

---

## 1. Internal & Annotation Validity Threats

### Threat 1 — Two Non-Independent Reviewer Streams Due to Disclosed AI Assistance (`REV_B` 254/254)
- **Evidence:** [s5c2_audit_summary.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/s5c2_audit_summary.json) (`REV_B.ai_assisted_notes_count: 254`, `independence_status: UNVERIFIED_AI_ASSISTED_SUBMISSION_IN_REV_B`); [S5C2_ANNOTATION_VALIDATION_REPORT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/S5C2_ANNOTATION_VALIDATION_REPORT.md).
- **Methodological Impact:** Every item in Reviewer B's submission carries `AI-assisted proposed annotation; requires independent human confirmation`. Consequently, the two annotation streams are **not** verified independent human judgments. Pre-adjudication agreement (`203/254 = 79.92%`, quadratic weighted $\kappa = 0.7677$, unweighted $\kappa = 0.5972$) cannot be cited as inter-human reliability, and AI-assisted labels may exhibit systematic bias toward lexical/semantic surface cues that correlate differently with BM25, dense, and graph retrievers.
- **Mitigation / Boundary:** Strictly gated by S5-C3 (`GAP-B1`): requires documented independent human confirmation or independent human re-grading before S5-D1 metrics may be computed.

### Threat 2 — Unadjudicated Disagreements (`51 / 254`) and Workbook Source-Text Discrepancies (`5 / 254`)
- **Evidence:** [S5C2_INTER_ANNOTATOR_AGREEMENT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/S5C2_INTER_ANNOTATOR_AGREEMENT.md) (51 disagreements across the 7 answerable queries: `34` grade `0 vs 1`, `4` `1 vs 0`, `4` `1 vs 2`, `9` `2 vs 1`; 4–10 disagreements per answerable query); [s5c2_audit_summary.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/s5c2_audit_summary.json) (5 source-text diffs: `REV_A` `PAIR-189, 232`; `REV_B` `PAIR-091, 119, 134`).
- **Methodological Impact:** All 51 disagreements occur on the 7 answerable queries (representing `51 / 179 = 28.5%` of all answerable-query pairs), and 13 disagreements cross the strict relevance boundary (`grade 1 vs 2`). Computing retrieval metrics before third-party/investigator human adjudication would produce arbitrary rankings sensitive to tie-breaking between `REV_A` and `REV_B`.
- **Mitigation / Boundary:** Strictly blocked (`HOLD_FOR_DISAGREEMENT_ADJUDICATION_AND_REV_B_INDEPENDENCE_CHECK`); S5-C3 must adjudicate all 51 disagreements against verified frozen pool text (`GAP-B2`).

### Threat 3 — Negative-Control Ambiguity (`Q-S5B2-03`, `Q-S5B2-08`, `Q-S5B2-11`)
- **Evidence:** [S5C2_NEGATIVE_CONTROL_VERIFICATION.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/S5C2_NEGATIVE_CONTROL_VERIFICATION.md) (all human verification fields empty); [s5b2_negative_control_audit.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_negative_control_audit.json) (`human_inspection_status: NOT_YET_PERFORMED`).
- **Methodological Impact:** Three distinct risks arise: (a) automated regex/dense searches and 0-grade annotations on pooled Top-10 candidates do not alone prove corpus-wide unanswerability without independent human inspection of search-selected candidates; (b) `Q08` (LLaMA-3 405B electric utility bills) and `Q11` (2025 Cisco Catalyst 9300 CVE) contain unsupported/synthetic factual premises rather than purely out-of-corpus real facts; (c) in [evaluate_gold_labels_readonly.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/scripts/evaluate_gold_labels_readonly.py) (L274–306), only `NO_ANSWER_IN_FROZEN_CORPUS` is excluded from answerable denominators, so if a human verifier classifies `Q08` or `Q11` as `AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION` or `QUESTION_REQUIRING_REVISION`, it would unintentionally enter `precision_at_5`/`precision_at_10` averages with `0.0`.
- **Mitigation / Boundary:** Keep all three labeled `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_HUMAN_VERIFICATION` until S5-C3 completes verification (`GAP-B3`), and reconcile stratification handling for non-`NO_ANSWER_IN_FROZEN_CORPUS` labels before S5-D1.

---

## 2. Construct & Measurement Validity Threats

### Threat 4 — Short Retrieval Lists (`baseline_graph_1hop`: `69 / 100` Slots, `31` Missing)
- **Evidence:** [s5d0_technical_diagnostics.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_technical_diagnostics.json) (`baseline_graph_1hop` returns 6 passages on `Q02` and 1 passage each on `Q03, Q08, Q11`; all other 5 systems return `100/100`); [run_s5b1_retrieval_benchmark.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/scripts/run_s5b1_retrieval_benchmark.py) (L225–293).
- **Methodological Impact:** Because `baseline_graph_1hop` uses raw substring anchor matching (`"act"` inside `"exact"` on `Q03` and `Q11`) without partial-list backfill, it returns truncated lists (`< 10`). Under fixed-denominator `Precision@5` (`hits / 5.0`) and `Precision@10` (`hits / 10.0`) in `evaluate_gold_labels_readonly.py` (L245–246), short lists are structurally capped (e.g., `Q02` cannot exceed `P@10 = 0.6000`). Conversely, its sparse anchor coverage creates an asymmetric comparison against `repaired_graph_*`, which falls back cleanly to `corpus_bm25` on 4/10 queries (`Q01, Q02, Q03, Q11`).
- **Mitigation / Boundary:** Report returned-count shortfalls (`69/100`) and fallback stratification (`4/10` repaired graph fallbacks) alongside every Top-K effectiveness metric once S5-D1 runs.

### Threat 5 — Incomplete Judgment Coverage (Pre-v2.1 vs. v2.1 Complete Depth-10 Pool)
- **Evidence:** [S5B2_DATASET_AUDIT_REPORT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/S5B2_DATASET_AUDIT_REPORT.md) §5 (S5-B1.1 31-pair pool covered only 7.5%–13.3% of Top-10 outputs; 277 unique unjudged Top-10 pairs); [s5b2_1_topk_pool_coverage_refreshed.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_topk_pool_coverage_refreshed.json) (v2.1 254-pair pool achieves 100.0% Top-5 and Top-10 coverage across all 6 frozen systems).
- **Methodological Impact:** While v2.1 completely eliminates unjudged passages within Top-10 for the **six frozen systems**, judgment coverage remains incomplete beyond rank 10 (`k > 10`) and across the remaining `713 - |pool_q|` unpooled passages per query (682–700 unjudged passages per query).
- **Mitigation / Boundary:** Metrics are strictly restricted to depth $k \le 10$ on the six frozen systems; `evaluate_gold_labels_readonly.py` raises an explicit error if any unjudged passage appears in Top-10 rather than silently imputing grade `0`.

### Threat 6 — Judged-Pool nDCG and Recall Denominators (Pool-Relative vs. Full-Corpus Ideal)
- **Evidence:** [evaluate_gold_labels_readonly.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/scripts/evaluate_gold_labels_readonly.py) (L211–227: `relevant_in_pool` and `ideal_grades = sorted(query_qrels.values(), reverse=True)`).
- **Methodological Impact:** Both `Recall@k` (`hits_k / n_rel`) and `nDCG@k` (`DCG@k / IDCG@k`) normalize against the **judged 254-pair pool**, not an exhaustive 713-passage ground truth. If additional relevant passages exist outside the union of all 6 systems' Top-10 outputs plus the 25 investigator seeds, true corpus-wide Recall@k would be lower and true IDCG@k could be higher (inflating pool-relative Recall and nDCG).
- **Mitigation / Boundary:** Explicitly define all planned Recall@k and nDCG@k figures as **pool-relative** (computed over the complete depth-10 union of the 6 evaluated systems plus 25 investigator seeds).

### Threat 7 — Unjudged Passages and Pooling Bias for Future / External Systems
- **Evidence:** [retrieval_query_pool_blinded.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package_v2_1/retrieval_query_pool_blinded.json) (254 pairs = 244 retrieved by the 6 frozen systems + 10 seed-only).
- **Methodological Impact:** Following Zobel (1998) and Buckley & Voorhees (2004), pooling bias disadvantages any **new, seventh retrieval system** (or any post-hoc modification of the six systems) evaluated later against the frozen 254-pair qrels, because novel passages it surfaces will be unjudged. Additionally, the 10 seed-only passages reflect investigator selection rather than purely system-agnostic sampling.
- **Mitigation / Boundary:** Restrict the v2.1 254-pair qrels strictly to the six frozen systems that contributed to the depth-10 pool; any new system requires fresh pooling or condensed-list evaluation (e.g., `bpref`) with explicit unjudged-passage accounting.

---

## 3. Conclusion & External Validity Threats

### Threat 8 — Small Sample Size (`N = 10` Active Queries: `7` Answerable + `3` Provisional Negatives)
- **Evidence:** [s5b2_proposed_blinded_query_specs.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/corpus/s5b2_proposed_blinded_query_specs.json) (`LIM-01`).
- **Methodological Impact:** With only 7 answerable queries (and 2 held out of 12), statistical power is near zero: a single query shift changes macro-averaged metrics by up to `14.3` percentage points (`1/7`). Formal hypothesis tests (paired $t$-test, Wilcoxon, randomization tests) cannot reliably separate signal from query-sampling variance.
- **Mitigation / Boundary:** Permanently prohibit statistical significance claims, superiority claims, or leaderboard rankings from v2.1; report per-query descriptive diagnostics and macro averages strictly as an exploratory pilot.

### Threat 9 — Absence of Validated Cross-Document Multi-Hop Queries (`0` Validated)
- **Evidence:** [s5b2_1_passage_necessity_matrix.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_passage_necessity_matrix.json) (`LIM-02`); [S5B2_DATASET_AUDIT_REPORT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/S5B2_DATASET_AUDIT_REPORT.md).
- **Methodological Impact:** Although the overarching research motivation asks whether provenance-aware graph retrieval aids multi-hop academic retrieval, evidence-necessity auditing refuted the two putative cross-document queries (`Q06`, `Q07` $\to$ `SINGLE_HOP`), leaving **0** cross-document queries and only **2** same-document two-passage queries (`Q02`, `Q10`). Moreover, `repaired_graph_*` falls back to `bm25` on `Q02` and achieves only hop-1 (`0` hop-2 edges) on `Q10`. Thus, v2.1 **cannot** empirically test cross-document multi-hop reasoning.
- **Mitigation / Boundary:** Explicitly state `0` validated cross-document queries in Introduction, Methods, and Limitations; prohibit any claim of cross-document multi-hop gains.

### Threat 10 — Limited Generalizability (3 CS Domains, 713 Passages, CPU-Only Pre-Revision Timing)
- **Evidence:** [s5b1_corpus_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/corpus/s5b1_corpus_manifest.json) (713 passages / 53 docs); [s5b2_1_corpus_provenance_registry.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_corpus_provenance_registry.json) (21 truncated stubs, 1 constructed card, sparse OSTEP extraction); [retrieval_timing_report.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/reports/retrieval_timing_report.json) (`LIM-03`, `LIM-08`).
- **Methodological Impact:**
  1. **Domain & corpus scope:** Active queries span only 3 computer science subfields (OS, AI/ML, Computer Networks; DBMS dropped after `Q12` HOLD) over a small 713-passage corpus with known ingestion defects (truncated textbook stubs, sparse OSTEP chunks) and only 146 heterogeneous graph edges concentrated in AI/ML.
  2. **Hardware & timing scope:** Multi-repetition warm latency (5 reps) was measured in S5-B1.1 on CPU over 12 pre-revision queries (not re-profiled after S5-B2.1 query edits; S5-B2.1 recorded single-pass component timing only for `hybrid_rrf_e2e`). Small-scale CPU latencies (713 passages, brute-force numpy dot product, Python adjacency dict) do not generalize to GPU inference, ANN vector indices, or corpora of $10^4$–$10^6$ passages (`H4`).
  3. **Governance/blinding hygiene:** Historical Git packfiles (`788976d`, `78d3f2f`, and S4 commits) retain earlier admin metadata/snippets (`LIM-09`), requiring isolated local workbook distribution outside Git access for all human annotators and adjudicators.
- **Mitigation / Boundary:** Scope all conclusions strictly to the 713-passage CS pilot on CPU; frame larger multi-domain corpora, repaired ingestion (`v2`), and controlled GPU/ANN latency profiling as future work.
