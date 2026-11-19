# S5-D0 — Paper Methods and Experimental Setup (Verified Draft)

**Base Commit:** `6450585f60b3c1bea7bef2f411458800552cea0b`  
**Date:** 2026-11-19  
**Status:** PRE-GOLD-LABEL DRAFT — FOR INVESTIGATOR REVIEW  

> [!IMPORTANT]
> This draft documents verified implementation details, frozen configurations, corpus provenance, and evaluation protocols for the Archipelago retrieval pilot. **No relevance-based effectiveness results are included**, no Reviewer A/B submissions are represented as validated independent human judgments, and no superiority, statistical significance, or publication-readiness claims are made.

---

## 1. Corpus Construction and Provenance (`s5a_eval_corpus_v1`)

The evaluation corpus is a frozen, deduplicated snapshot extracted from the local Kùzu graph database (`okf_graph.db`) via `build_fixed_corpus_from_kuzu()` in [retrieval_baselines.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/archipelago/eval/retrieval_baselines.py) and filtered by `load_s5b1_corpus()` in [run_s5b1_retrieval_benchmark.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/scripts/run_s5b1_retrieval_benchmark.py).

- **Database vs. Eligible Scope:** `okf_graph.db` contains 79 documents and 786 total chunks. Starting from the S3 baseline (`s3_fixed_corpus_v1`: 764 passages across 59 documents), 51 passages were excluded under deterministic audit rules ([s5b1_corpus_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/corpus/s5b1_corpus_manifest.json)):
  - **50 index/frontmatter passages** matched by `_is_index_only_passage()` (author lists, book indices, dense page-number lists).
  - **1 invalid-page passage** (`doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4`, page 612 exceeding book length 500).
- **Frozen Eligible Corpus (`s5a_eval_corpus_v1`):** Exactly **713 passages** across **53 documents**, cryptographically locked at runtime:
  - `corpus_passage_id_sha256`: `f7fe70031781b005d712a7a9a4aa2452a8b17d7353531305b39b09d88eeecd98`
  - `corpus_text_sha256`: `8464acaea13cbfae0f345ea29ce1cf707dc39e76832c7729fca33fbd763bc68c`
  - `corpus_sha256`: `6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7`
- **Four-Tier Provenance Registry:** Audited in [s5b2_1_corpus_provenance_registry.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_corpus_provenance_registry.json) without altering the frozen 713-passage corpus:
  1. `source_verified_constructed_pilot_card`: **1** passage (`pilot/silberschatz_3nf_card.txt::third_normal_form_seed_001`, inline hand-authored card in `seed_soference_catalog.py` with `"pdfs": []`).
  2. `source_verified_truncated_textbook_stub`: **21** passages (`doc_*` entries truncated at ≤305 characters).
  3. `convention_inferred_seed_chunk`: **16** passages (`*_seed_*` chunks from OSTEP chapters, QLoRA, and vLLM; raw PDF page alignment not independently re-verified during S5-B2.1).
  4. `convention_inferred_paper_or_upload_chunk`: **675** passages (`papers/*.pdf` and `upload_*` chunks).

---

## 2. Evaluated Retrieval Systems (Frozen Configurations)

All six systems operate under **strict information-access parity** over the identical 713-passage corpus (`s5a_eval_corpus_v1`), returning up to `top_k = 10` ranked passages per query with deterministic tie-breaking `(-score, passage_id)`. Implementations are frozen in [retrieval_baselines.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/archipelago/eval/retrieval_baselines.py), [run_s5b1_retrieval_benchmark.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/scripts/run_s5b1_retrieval_benchmark.py), and [repaired_extractor.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/okf/pilot/repaired_extractor.py).

| System Identifier | Retrieval Paradigm | Frozen Parameters & Provenance Enforcement | Fallback Behavior |
|---|---|---|---|
| `bm25` | Lexical (`BM25Okapi`) | Lowercase alphanumeric tokenizer (`[a-z0-9]+`); `k1 = 1.5`, `b = 0.75`; whitespace-normalized text. | None |
| `dense_snowflake_arctic_768d` | Neural Dense Bi-Encoder | `Snowflake/snowflake-arctic-embed-m-v1.5` (BERT-based, mean pooling, 768-dim, `max_seq_len = 512`, `float32`, CPU, local revision `f22f7b88939ba6d01306a445d48729fb5a2ff3f3`). Query prefix: `"Represent this sentence for searching relevant passages: "`; empty document prefix; L2-normalized dot product. Precomputed `(713, 768)` cache verified at runtime (`SHA-256: ffb94053fa66471d14758771253c8c5404bb4adf2e7b14d2c9e4c30b2cbd4ee2`). | None |
| `hybrid_rrf_e2e` | Hybrid Rank Fusion | Reciprocal Rank Fusion (Cormack et al., 2009): $\text{RRF}(d) = \sum_{r} \frac{1}{k + \text{rank}_r(d)}$ with `k = 60` over top-50 candidates from `bm25` and `dense_snowflake_arctic_768d`. End-to-end latency accounts for $T_{\text{BM25}} + T_{\text{Dense}} + T_{\text{Fusion}}$. | None |
| `baseline_graph_1hop` | Corpus-Scoped Kùzu 1-Hop Graph (`RepairedBaselineGraphRetriever`) | Maps Kùzu `Concept` nodes strictly to the 713 eligible passages (**451** eligible concepts out of 610; excludes 56 external-only + 103 orphan concepts). Filters `REQUIRES`/`RELATED`/`UNLOCKS` edges via `_is_corpus_verified_kuzu_edge()` (**1,526** verified edges out of 1,988; excludes 462 external/unscoped/null-source edges). Anchor matching: `c in query.lower()`. Expands up to 5 alphabetically ordered 1-hop neighbors per anchor. Passage score: $+2.0$ per matched anchor, $+1.0$ per 1-hop neighbor. | `corpus_bm25` only when `matched_anchors` is empty (no partial-list backfill). |
| `repaired_graph_1hop_ablation` | Heterogeneous Graph 1-Hop (`RepairedHeterogeneousGraphRetriever`, `max_hops=1`) | Built by `RepairedGraphExtractor` (S4-G3 clause-aware, denoised, prerequisite-DAG-enforced extractor) restricted to the 713 eligible passages (**146** corpus-scoped edges vs. 148 unconstrained). Edge weights: `REQUIRES = 1.0`, `PART_OF = 0.9`, `USES = 0.8`, `CONTRASTS_WITH = 0.7`, `RELATED = 0.5`, multiplied by `edge.confidence`. Undirected expansion for `CONTRASTS_WITH` and `RELATED`. Anchor weight `1.0`; hop-1 score $1.0 \times w$. Passage score sums concept weights over passages linked by edge provenance or substring mention. | `corpus_bm25` when `matched_anchors` is empty. |
| `repaired_graph_2hop_full` | Heterogeneous Graph 2-Hop (`RepairedHeterogeneousGraphRetriever`, `max_hops=2`) | Identical 146-edge corpus-scoped graph and edge weights as `repaired_graph_1hop_ablation`, extending traversal to hop 2 with multiplicative decay `0.5`: $\text{score}_2 = \text{score}_1 \times w_2 \times 0.5$, taking $\max$ per visited concept. Reports observed hop depth (`0` fallback, `1` hop-1 only, `2` novel hop-2 concepts reached) and full `paths_traversed`. | `corpus_bm25` when `matched_anchors` is empty. |

*(Note: A 64-dim deterministic token-hashing encoder is also documented in [s5b1_model_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/models/s5b1_model_manifest.json) strictly as a CI/debugging baseline and is excluded from the six evaluated retrieval systems.)*

---

## 3. Query Benchmark Evolution and Provenance

The initial 12-query S5-A/S5-B1 pilot underwent an evidence-sufficiency and provenance audit in S5-B2 / S5-B2.1 ([S5B2_DATASET_AUDIT_REPORT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/S5B2_DATASET_AUDIT_REPORT.md), [S5B2_1_APPROVAL_GATE_REPORT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/S5B2_1_APPROVAL_GATE_REPORT.md)):

- **Held / Excluded Queries (2 of 12):**
  - `Q-S5A-09` (OSI Reference Model layers): **HOLD** — sole textbook chunk (`doc_computer_networks_6_e_p42_1`) is truncated at 285 characters after Layer 2; Layers 3–7 do not exist in `okf_graph.db`.
  - `Q-S5A-12` (Third Normal Form / 3NF): **HOLD** — sole passage mentioning 3NF (`pilot/silberschatz_3nf_card.txt`) is a source-verified constructed pilot card rather than PDF-extracted evidence.
- **Active Queries (10 of 12, `s5b2_proposed_blinded_query_specs.json`):**
  - **Domains:** Operating Systems (3: `Q-S5B2-01`, `02`, `03`), AI & Machine Learning (5: `Q-S5B2-04`, `05`, `06`, `07`, `08`), Computer Networks (2: `Q-S5B2-10`, `11`).
  - **Revisions Applied:** `Q-S5B2-02` was revised to match extracted LDE/address-translation text in `07_address_translation.pdf` (base-and-bounds pages were absent); `Q-S5B2-10` was revised to reflect proposed D-MAGIC/SAGA mechanisms without claiming experimentally verified latency reductions; `Q-S5B2-04` and `05` had missing corpus formula chunks added to the seed candidates; `Q-S5B2-06` and `07` were reclassified from `CROSS_DOCUMENT` to `SINGLE_HOP`.
  - **Hop-Necessity Classification ([s5b2_1_passage_necessity_matrix.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_passage_necessity_matrix.json)):** **Zero** validated cross-document queries remain. Two queries (`Q-S5B2-02`, `Q-S5B2-10`) are classified as same-document `TWO_HOP`; five (`Q-S5B2-01`, `04`, `05`, `06`, `07`) are `SINGLE_HOP`; three (`Q-S5B2-03`, `08`, `11`) are provisional negative controls (`PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_HUMAN_VERIFICATION`).

---

## 4. Candidate Pooling, Blinding, and Annotation Protocol

- **Complete Depth-10 Pooling:** In S5-B2.1, the 25-pair investigator seed pool (which covered only 7.0%–14.0% of Top-10 outputs) was expanded to the deduplicated union of Top-10 outputs across all 6 frozen systems plus the 25 investigator-selected seed pairs, yielding **254 unique `(query_id, passage_id)` pairs** (`244` retrieved union + `10` seed-only pairs), achieving **100.0% Top-5 and Top-10 pool coverage** across all 6 systems.
- **Blinding & Randomization:** Candidate passages per query are stored in neutral lexicographical order and deterministically shuffled (`random.Random(20261119)`) before assigning neutral IDs `S5B21-PAIR-001` through `S5B21-PAIR-254`. Reviewer-facing files ([retrieval_query_candidate_pool_blinded.csv](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package_v2_1/retrieval_query_candidate_pool_blinded.csv), [RETRIEVAL_ANNOTATION_PROTOCOL.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/proposed_package_v2_1/RETRIEVAL_ANNOTATION_PROTOCOL.md), and local Git-ignored workbooks) contain zero system identities, rankings, investigator judgments, or answerability/category hints.
- **Grading Scale:** Discrete 3-level relevance scale: `0` (Irrelevant / Distractor), `1` (Partially Relevant / Background Context), `2` (Highly Relevant / Grounding Evidence), with mandatory verbatim supporting quotes for grades `1` and `2` and empty quotes for grade `0`, plus confidence (`HIGH`, `MEDIUM`, `LOW`).
- **S5-C2 Pre-Adjudication Audit Status ([s5c2_audit_summary.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/s5c2_audit_summary.json)):** Both Reviewer A and Reviewer B submitted 254/254 structurally valid pairs (0 missing, 0 duplicate, 0 quote mismatches). Descriptive pre-adjudication agreement is 203/254 (79.92%; quadratic weighted $\kappa = 0.7677$; unweighted $\kappa = 0.5972$) with **51 disagreements**. However, Reviewer B disclosed `AI-assisted proposed annotation; requires independent human confirmation` on all 254 pairs, and human negative-control verification (`Q03`, `Q08`, `Q11`) remains uncompleted. Accordingly, S5-C2 issued `HOLD_FOR_DISAGREEMENT_ADJUDICATION_AND_REV_B_INDEPENDENCE_CHECK`.

---

## 5. Planned Post-Adjudication Evaluation Protocol (Read-Only Pipeline)

Once independent human confirmation of Reviewer B's labels, third-party/investigator adjudication of all 51 disagreements, and human verification of the 3 negative controls are completed, final descriptive pilot metrics will be computed using the read-only pipeline [evaluate_gold_labels_readonly.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/scripts/evaluate_gold_labels_readonly.py):

- **Gate Enforcement:** The script refuses to run unless the gold-label file explicitly declares `status == "ADJUDICATED_HUMAN_GOLD_FINAL"`, `reviewer_b_independence_confirmed == True`, `all_disagreements_adjudicated == True`, verified human classifications for `Q-S5B2-03`, `Q-S5B2-08`, and `Q-S5B2-11`, and exact 254-pair alignment with `retrieval_query_pool_blinded.json` (`SHA-256: 2d134546...`).
- **Metrics (Answerable Queries Only):** Reported at both strict (`grade >= 2`) and lenient (`grade >= 1`) binary thresholds for `Recall@5`, `Recall@10`, `Precision@5`, `Precision@10`, `MRR@10`, plus graded `nDCG@5` and `nDCG@10` using exponential gain $2^g - 1$ and logarithmic discount $1 / \log_2(\text{rank} + 1)$.
- **Unjudged Passage Policy:** Unjudged passages are explicitly counted and **never** silently treated as irrelevant (the pipeline raises a validation error if any Top-10 passage lacks a gold judgment).
- **Negative-Control Stratification:** Verified corpus-unanswerable queries are excluded from Recall/MRR/nDCG denominators and reported separately (returned count, fallback flag, max observed grade).
- **Latency Measurement Protocol:** Cold-start initialization is separated from first-query and warm per-query distributions (5 warm repetitions per query on CPU, as executed in S5-B1.1).

---

## 6. Summary of Scope Boundaries and Limitations

All limitations restricting interpretation of this pilot are formally tracked in [S5D0_LIMITATIONS_REGISTER.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/S5D0_LIMITATIONS_REGISTER.md), including the 10-query pilot sample size, absence of validated cross-document queries, truncated textbook stubs and sparse OSTEP coverage, unresolved negative controls, Reviewer B's AI-assistance disclosure, historical Git exposure of earlier S4/S5-A/S5-B1 artifacts, and pre-revision S5-B1.1 latency profiling scope.
