# Archipelago D14 — Benchmark Isolation & Experimental Integrity Contract

- **Phase:** D14.0 (Baseline Freeze & Isolation Contract) → Enforced through D14.1–D14.7 → Executed in D14.8
- **Owner:** `d14-benchmark-integrity`
- **Companion Audit:** [`docs/reports/d14/D14_BENCHMARK_EXPOSURE_AUDIT.json`](./D14_BENCHMARK_EXPOSURE_AUDIT.json)
- **Target Venue:** ACM SIGIR 2027 Demonstrations Track
- **Leakage Policy:** Strict Non-Leaking — no held-out query text, gold answers, expected concepts, qrels grades, or passage texts appear in this contract or on the swarm board.

---

## 1. Executive Summary of Exposure Audit

An automated exact, normalized, content-token Jaccard, TF-IDF cosine, and expected-concept substring audit was run against the 50 held-out SIGIR benchmark queries (`research/d5_sigir_evaluation/queries_heldout_50.json`, present on `sigir/d12-recovery` @ `fe8887c` and `sigir/demo-2027` @ `71271ec`, absent on `main` @ `c0d90b8`):

| Query Set | Source Path | Queries | Exact / Norm Matches vs Heldout-50 | High Overlap (`TF-IDF ≥ 0.45` or `Jaccard ≥ 0.35`) | Held-out Concept Mentions | Verdict for D14.1–D14.7 |
|---|---|---:|---:|---:|---:|---|
| **D13 / D11-A / D10 36Q** | `docs/sigir/D10_S3_ANSWERING_BEFORE_AFTER_36Q.csv` | 36 (12 domains) | 0 / 0 | **0** (max TF-IDF `0.414`, max Jaccard `0.200`) | **0** | **APPROVED** exposed dev/regression set |
| **D10-S4 Preliminary 6Q** | `docs/reports/D10_S4_AUTHOR_TEST_WORKSHEET.csv` (`preliminary_regression_6q`) | 6 | 0 / 0 | **3** (incl. `S4-SPANNER` ↔ `Q39` at `1.000`, `S4-RAG` ↔ `Q05` at `0.699`) | **8** | **RESTRICTED — DO NOT TUNE** |
| **D5 Dev-15** | `research/d5_sigir_evaluation/queries_dev_15.json` | 15 | 0 / 0 | **6** (max TF-IDF `0.699`) | **8** | **RESTRICTED** — coarse sanity only |

All 36 query IDs in `outputs/d11-a-author-diagnostic/D11_A_AUTHOR_DIAGNOSTIC_WORKSHEET.xlsx` match `docs/sigir/D10_S3_ANSWERING_BEFORE_AFTER_36Q.csv` 100% (36/36).

---

## 2. Four-Tier File Quarantine Rules (Mandatory for D14.1–D14.7)

All SHA-256 checksums are recorded in `docs/reports/d14/D14_BENCHMARK_EXPOSURE_AUDIT.json` (45 inventoried files) and will be verified programmatically at the D14.8 gate.

### Tier 1 — HARD QUARANTINE (Strictly Off-Limits: Do NOT Read, Tune On, Reference, or Modify)

D14.1–D14.7 workers MUST NEVER open, inspect, tune hyperparameters against, or write to:

1. **Held-out 50 queries & qrels (`research/d5_sigir_evaluation/`):**
   - `research/d5_sigir_evaluation/queries_heldout_50.json`
   - `research/d5_sigir_evaluation/qrels.tsv` (445 lines)
   - `research/d5_sigir_evaluation/passage_qrels.json`
   - `research/d5_sigir_evaluation/unjudged_qrels.json`
2. **Sealed blinding key & blank 731-item human judgment pool (`research/d5_sigir_evaluation/`):**
   - `research/d5_sigir_evaluation/worksheets/pool_key_SEALED.json`
   - `research/d5_sigir_evaluation/human_annotation_worksheet.json` (731 items, 0/731 populated)
   - `research/d5_sigir_evaluation/worksheets/reviewer_A_worksheet.csv` (731 rows, 0/731 populated)
   - `research/d5_sigir_evaluation/worksheets/reviewer_B_worksheet.csv` (731 rows, 0/731 populated)
   - `research/d5_sigir_evaluation/worksheets/adjudication_worksheet.csv` (731 rows, 0/731 populated)
3. **Protected manuscript directories (outside repo):**
   - `/home/pratay-karali/Desktop/sigit_manu/`
   - `/home/pratay-karali/Desktop/sigit_manu_d11_sync_v1/`

### Tier 2 — IMMUTABLE HISTORICAL RESULTS & GOLD GRAPHS (Read-Only; Never Overwrite)

Never overwrite, regenerate in place, or populate blank human fields in:

- `research/d5_sigir_evaluation/ranked_runs/*.run` (`bm25.run`, `feature_hashed_vector.run`, `snowflake_arctic_neural.run`, `archipelago_graph_assisted.run`)
- `research/d5_sigir_evaluation/d5_evaluation_results*.json`, `d5_1_evaluation_results*.json`, `citation_grounding_audit.json`, `reviewer_provenance.json`, `human_review_records.json`
- `research/d5_sigir_evaluation/d5_graph_slice.json`, `quarantined_edges.json`, `embedding_manifest.json`, `corpus_embeddings_snowflake.npy`, `concept_embeddings_snowflake.npy`
- `pilot_corpus/gold/gold_attention.json`, `gold_curriculum.json`, `gold_lora.json`, `pilot_corpus/gold_eval_results.json`
- `okf/gold/gold_attention.json`, `okf/gold/gold_lora.json`
- `research/d4-demo-graph-candidate/demo_graph_candidate.json`
- `docs/reports/D10_S4_CANDIDATE_PASSAGE_MANIFEST.json`
- Blank `human_*` columns in `docs/sigir/D10_S3_ANSWERING_BEFORE_AFTER_36Q.csv`, `docs/reports/D10_S4_AUTHOR_TEST_WORKSHEET.csv`, and `outputs/d11-a-author-diagnostic/D11_A_AUTHOR_DIAGNOSTIC_WORKSHEET.xlsx` (0/36 and 0/42 populated).

### Tier 3 — HIGH-EXPOSURE / CONTAMINATION-RISK QUERIES (No Tuning, No Overrides)

- **Do NOT tune on `preliminary_regression_6q`** in `docs/reports/D10_S4_AUTHOR_TEST_WORKSHEET.csv` (`S4-SPANNER`, `S4-RAG`, `S4-TRANSFORMER`, `S4-LORA`, etc.). `S4-SPANNER` has 1.000 content-token overlap with held-out `Q39`, and `S4-RAG` has 0.699 TF-IDF overlap with `Q05`. Adding concept overrides, domain boosts, or abstention rules driven by `S4-*` queries constitutes held-out leakage.
- **Do NOT tune per-concept overrides on `research/d5_sigir_evaluation/queries_dev_15.json`** (6 high-overlap pairs with `queries_heldout_50.json`). Permitted only for coarse pipeline smoke checks.

### Tier 4 — APPROVED EXPOSED DEVELOPMENT & REGRESSION QUERIES

- The **36 author-tested queries (`D10-*` across 12 academic domains)** in `docs/sigir/D10_S3_ANSWERING_BEFORE_AFTER_36Q.csv` are verified cleanly disjoint from `queries_heldout_50.json` and are approved as the D14.1–D14.7 development/regression suite.
- **Anti-overfitting rule:** Fixes MUST be systemic and domain-general (improved extraction, clean graph schema/edges, general NLU/retrieval scoring, citation provenance, math/synthesis reliability). Hardcoded query-string lookup tables, query-ID branches, or per-question canned answers are prohibited and will fail `d14-independent-verifier` and D14.8 review.

---

## 3. Corpus & Graph Versioning Requirements (Independent D14.8 Evaluation)

To guarantee that Phase D14.8 can evaluate **original vs. expanded corpus** and **original vs. repaired graph** independently without confounding effects, D14.1 (`d14-corpus-ingestion`) and D14.2 (`d14-okf-graph`) MUST follow strict side-by-side versioning:

| Artifact Version ID | Scope | Canonical Location / Revision | Frozen SHA-256 Anchor | Mutability |
|---|---|---|---|---|
| `graph_v1_okf610` | 610 concepts, 1,988 edges (267 `requires`, 387 `unlocks`, 1,334 `related`), 775 embedded passages across 60 source docs | `host_inference/fixtures/okf_graph.json` (pinned HF `Prataykarali/graphier@86e29828`) | `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76` | **IMMUTABLE BASELINE** — preserve v1 snapshot before/alongside any D14.2 graph update |
| `corpus_v1_okf775` | 775 unique passages (`<canonical_source_doc>::<canonical_chunk_id>`) embedded in `okf_graph.json` | Embedded in `graph_v1_okf610`; embeddings in `research/d5_sigir_evaluation/corpus_embeddings_snowflake.npy` | `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76` | **IMMUTABLE BASELINE** — required for 731-item pool & D5 `qrels.tsv` compatibility |
| `corpus_v2_d10_3025` | 43 PDFs, 3,025 passages (D10–D13 runtime corpus) | Manifest: `docs/reports/D10_S4_CANDIDATE_PASSAGE_MANIFEST.json`; HF `Prataykarali/Library_books@b0561c76a4c5a7a8cb1fe3bd91b389280d504cbd`; JSONL stored outside Git | Manifest: see audit JSON; Passage JSONL: `93f6db39cb10d03beeb41c48469d138be27b62ed90aa59d20dd4c5107fbb2e52` | **IMMUTABLE BASELINE** — never overwrite `D10_S4_CANDIDATE_PASSAGE_MANIFEST.json` or its Supabase Storage object |
| `corpus_v3_d14` | D14.1 repaired + expanded OA corpus | New manifest: `docs/reports/d14/D14_CORPUS_V3_MANIFEST.json`; new versioned JSONL outside Git (e.g., `d14_candidate_passages_v3.jsonl`) | Computed at D14.1 gate | **VERSIONED NEW ARTIFACT** — must record `parent_manifest_sha256`, `parent_passage_index_sha256`, `added_doc_ids`, `reextracted_doc_ids`, and per-doc SHA-256 |
| `graph_v2_d14` | D14.2 cleaned + expanded OKF graph | Versioned artifact (e.g., `host_inference/fixtures/okf_graph_d14_v2.json` or explicitly archived `host_inference/fixtures/baselines/okf_graph_v1_610.json` with SHA `9818ac0e...2f76`) | Computed at D14.2 gate | **VERSIONED NEW ARTIFACT** — must record `schema_version`, `parent_graph_sha256`, and deterministic diff counts (`added_concepts`, `removed_concepts`, `repaired_edges`) |

### Runtime & Evaluation Switchability Requirement

- `host_inference` / retrieval & graph loaders MUST support selecting corpus and graph versions cleanly via environment variables or explicit loader arguments (e.g., `ARCHIPELAGO_GRAPH_PATH`, `ARCHIPELAGO_CANDIDATE_PASSAGES`, `ARCHIPELAGO_CANDIDATE_PASSAGES_SHA256`) without code edits.
- This enables Phase D14.8 to execute the **4-cell controlled ablation matrix**:
  1. **Cell A (D5 Frozen Benchmark):** `corpus_v1_okf775` + `graph_v1_okf610` → apples-to-apples against D5 baselines (`bm25`, `snowflake_arctic_neural`, `feature_hashed_vector`, `archipelago_graph_assisted`) and the 731-item pool.
  2. **Cell B (D10 Runtime Baseline):** `corpus_v2_d10_3025` + `graph_v1_okf610` → isolates D14.3–D14.7 retrieval, NLU, synthesis, citation, and streaming improvements on the exact D12/D13 corpus and graph.
  3. **Cell C (Graph-Only Upgrade):** `corpus_v2_d10_3025` + `graph_v2_d14` → isolates the effect of D14.2 graph cleanup/expansion.
  4. **Cell D (Full D14 System):** `corpus_v3_d14` + `graph_v2_d14` → measures end-to-end D14 recovery with new OA documents and repaired graph.

---

## 4. Compatibility Rules for the 731-Item Human Judgment Pool

Inspection of `research/d5_sigir_evaluation/human_annotation_worksheet.json` and `worksheets/*.csv` confirms:
- **Size & Status:** 731 `(query_id, blinded_candidate_id)` items across all 50 held-out queries (`pool_depth_k = 5`, 4 pooled systems), currently `PENDING_HUMAN_ANNOTATION` with **0/731** human judgments completed.
- **Identifier Schema:** Every item is keyed to `passage_id` of the form `<canonical_source_doc>::<canonical_chunk_id>` (353 unique `passage_id`s across 51 `canonical_source_doc`s), sourced exclusively from `corpus_v1_okf775` (`okf_graph.json`, SHA-256 `9818ac0e...2f76`).
- **Mismatch with `corpus_v2_d10_3025`:** Only 26 of the 51 canonical documents in the 731-item pool share a filename basename with the 43 PDFs in `corpus_v2_d10_3025`, and `corpus_v2_d10_3025` uses a different chunking/passage-ID scheme (`build_d10_candidate_passages.py`, 1,600-char page-confined chunks).

Therefore, the following **4 hard compatibility rules** apply:

1. **Zero Synthetic Population:** No agent, script, or LLM may fill `reviewer_assessment`, `relevance_grade`, `claim_supported`, `adjudicated_relevance_grade`, or `adjudicated_claim_supported` in any of the 731-item worksheets or in `D10_S3` / `D10_S4` / `D11_A` human columns.
2. **Exact-ID Evaluation Only on `corpus_v1_okf775`:** Any D14.8 evaluation computing retrieval metrics (`NDCG@5`, `MRR`, `MAP`, `Recall@5`) against `qrels.tsv` / `passage_qrels.json` or checking coverage against the 731-item pool MUST run on `corpus_v1_okf775` using exact `<canonical_source_doc>::<canonical_chunk_id>` IDs and MUST report `judged_rate@5` and `unjudged_rate@5`.
3. **No Cross-Corpus Qrels Remapping:** Passage IDs produced on `corpus_v2_d10_3025` or `corpus_v3_d14` MUST NOT be heuristically mapped onto `corpus_v1_okf775` passage-level qrels to claim apples-to-apples passage-level NDCG/MAP gains.
4. **Separate Supplemental Pool for New Candidates:** If D14.8 introduces unjudged top-5 candidates on `queries_heldout_50.json` (either from improved ranking on `corpus_v1_okf775` or from `corpus_v3_d14`), those new candidates MUST be exported to a **separate** supplemental blinded file under `research/d14_evaluation/` with its own sealed key — leaving `research/d5_sigir_evaluation/human_annotation_worksheet.json` and `worksheets/*.csv` byte-identical.

---

## 5. D14.8 Integrity Verification Gate (Pre-Merge Requirement)

Before Phase D14.8 results are accepted or any D14 branch is merged/released, `d14-benchmark-integrity` will verify:
1. **Checksum Integrity:** All Tier 1 and Tier 2 files in `D14_BENCHMARK_EXPOSURE_AUDIT.json` match their frozen SHA-256 hashes (100% byte-identical).
2. **Blank Human Fields Intact:** All 731 rows in `reviewer_A_worksheet.csv`, `reviewer_B_worksheet.csv`, `adjudication_worksheet.csv`, and `human_annotation_worksheet.json` remain unpopulated (`0/731`), and all `human_*` columns in `D10_S3` / `D10_S4` remain unpopulated (`0/36`, `0/42`).
3. **Protected Manuscript Directories Untouched:** Zero modifications to `/home/pratay-karali/Desktop/sigit_manu/` or `/home/pratay-karali/Desktop/sigit_manu_d11_sync_v1/`.
4. **No Hardcoded Query Overfitting:** Code diff audit confirms zero held-out query strings, zero `Q01..Q50` branches, and zero `S4-*` or `D10-*` query-string lookup hacks in production retrieval/NLU/synthesis code.
5. **Independent Versioned Reporting:** D14.8 reports metrics separately for frozen baselines (`corpus_v1_okf775` / `corpus_v2_d10_3025` / `graph_v1_okf610`) vs. expanded D14 artifacts (`corpus_v3_d14` / `graph_v2_d14`).
