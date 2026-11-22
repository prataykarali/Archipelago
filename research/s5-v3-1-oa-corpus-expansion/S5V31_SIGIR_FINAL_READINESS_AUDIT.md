# Archipelago S5-v3.1 — Final SIGIR Research-Readiness Audit

**Date:** 2026-11-19  
**Audit Mode:** **READ-ONLY SCIENTIFIC AUDIT** (zero code, dataset, benchmark, model, workbook, or manuscript edits; baseline commit `eca75b6846efc9a7159c2692555cd6c897182315` on `research/s5-v3-1-oa-corpus-expansion-canonical`)  
**Auditors:** `@eval-design-v3` (Audits A, D, E), `@benchmark-v3` (Audit B), `@retrieval-v3` (Audit C), `@verifier` (independent spot-checks & consolidation)

---

## 1. Decision Verdict: `GO` / `HOLD` Split

| Phase | Verdict | Rationale |
|---|---|---|
| **Stage 1 — Human Query Validation** (`72` proposed queries + `8` NCs via `data/annotation_local/s5v3_1/query_audit/`) | **`GO`** | Programmatic benchmark integrity is clean (`0` broken passage/SHA-256 refs, `0` dev/test leakage, `0` v2.1 reuse, `0` fabricated page numbers), and the fresh blinded 72-query human audit workbook is ready (`7.20 hr` all-72 or `4.80 hr` test-only). Human reviewers **must** actively `REVISE`/`REJECT` the flagged items in Section 2.1. |
| **Stage 2 — Downstream v3.1 Pooling, Dual Human Annotation & D1 Scoring** | **`HOLD`** | Strictly blocked by **hardcoded S5-v2.1 incompatibilities** across `d1_pipeline/`, `s5_gold_label_ac_v2.schema.json`, `annotation_workbench/`, `ac_adjudication/`, and `neg_control/` (including a **silent negative-control bypass hazard** at `d1_pipeline/preflight_checks.py:L200-202`), plus unresolved pre-pooling experimental design decisions (cross-encoder reranker and unscoped-vs-scoped graph ablation). |
| **SIGIR 2027 Full-Paper Submission Readiness (Today)** | **`NO-GO` (until post-human + v3.1 rewrite)** | `0` human gold labels exist, and `manuscript_draft.md` is still 100% anchored to the obsolete 10-query S5-v2.1 pilot (`okf_graph.db` missing). |

---

## 2. Exact Blocking Issues (Distinguished by Phase)

### 2.1 Blockers to Starting Stage 1 Human Query Validation: **NONE** (Attention Items Flagged for Human `REVISE`/`REJECT`)
Human query validation can begin immediately, but reviewers should expect substantive revisions on four empirically audited issues in `s5v31_query_benchmark_proposed.json` (`72` queries):
1. **Explicit source-title/author lexical cueing (`35/72` queries overall; `10/14` cross-document):** All `10` retained ML/Math/NLP/Robotics cross-doc queries (`Q-S5V31-08, 09, 10, 30, 31, 32, 33, 34, 35, 36`) explicitly name both books/authors in `query_text`, creating a BM25 title-matching shortcut. Flagged for human `REVISE` de-cueing.
2. **Weak/artificial cross-document juxtaposition bridges (`6/14` cross-doc):** `Q-S5V31-34` (CFG Python syntax vs. METATRON coding agent), `Q-S5V31-36` (ERM vs. LLM next-token logits), `Q-S5V31-53` (Go-Back-N vs. Two Generals), `Q-S5V31-67` (OS memory hierarchy vs. file-based DB coupling), `Q-S5V31-68` (primary-key entity integrity vs. 2PC/2PL), and `Q-S5V31-69` (quorum linearizability vs. single-site DBMS). Remaining `8` (`08, 09, 10, 30, 31, 32, 33, 35`) have genuine conceptual overlap once de-cued.
3. **Adjacent-chunk & single-passage shortcut risk (`10/19` same-doc multi-passage):** `Q-S5V31-05, 06, 07, 23, 46, 48, 59, 62, 63, 65` cite chunks within distance `<= 2` (`62` and `63` are on the same page); five queries show `>= 0.69` single-passage lexical coverage (`Q-S5V31-06` `0.90`, `05` `0.71`, `26` `0.71`, `48` `0.70`, `63` `0.69`). Additionally, `13` cited passages across `11` retained v3 queries (`02, 07, 10, 16, 24, 29, 33, 34, 36, 40, 41`) carry `MID_SENTENCE_TRUNCATION_START/END` flags; two `test`/`dev` pairs have `0.47–0.54` Jaccard overlap (`Q-S5V31-18/19` vs. `Q-S5V31-03`).
4. **Negative-control near-miss risk (`1/8` high-priority):** `Q-S5V31-71` (Spanner TrueTime GPS/atomic-clock $\epsilon$) has `0` hits for `spanner`/`truetime`, but `oa_ds_001` (`c0062`, `c0070`) discusses GPS and atomic clocks; human verifier must confirm no partial answer. (`Q-S5V31-54` eBPF XDP and `Q-S5V31-72` RocksDB LSM-tree are low-risk domain near-misses; `Q-S5V31-14, 42, 43, 44, 70` have `0` near-misses.)

### 2.2 Hard Blockers to Downstream v3.1 Pooling, Annotation & D1 Evaluation (EXACT `file:line`)
All existing S5-C3 / S5-D1 evaluation and annotation tools hardcode S5-v2.1 constants (`254` pairs, `713` passages, `Q-S5B2-03/08/11`, `okf_graph.db`) and **MUST NOT** be run on S5-v3.1 without versioned v3.1 adapters/schemas:

| Component | Exact `file:line` | Incompatibility / Hazard |
|---|---|---|
| **D1 Preflight (CRITICAL SILENT-BYPASS HAZARD)** | `research/s5-d0-experimental-analysis-prep/scripts/d1_pipeline/constants.py:L88` & `preflight_checks.py:L200-202` | Hardcodes `PROVISIONAL_NEG_CONTROL_IDS = ("Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11")`. Because `L200-202` returns early when none of those 3 IDs appear in `pool_query_ids`, v3.1 query IDs would **silently skip ALL 8 v3.1 negative-control checks** and mix NCs into answerable metrics. |
| **D1 Metrics & Rankings Loader** | `research/s5-d0-experimental-analysis-prep/scripts/d1_pipeline/constants.py:L9-22, L114-116` & `metrics.py:L61, L235-237, L270-282` | Hardcodes `s5b2_1_frozen_ranked_results.json`, v2.1 system names (`repaired_graph_1hop_ablation`, `repaired_graph_2hop_full`, `baseline_graph_1hop`), v2.1 JSON schema (`systems[s]["queries"][i]["ranked_top10"]`), and fail-closed `unjudged_at_10 > 0` (rejects `@5`-only pools unless a `@5` mode is added). |
| **Legacy D1 Readonly Evaluator** | `research/s5-d0-experimental-analysis-prep/scripts/evaluate_gold_labels_readonly.py:L31-36, L50, L60-64, L119` | Hardcodes v2.1 paths, `Q-S5B2-03/08/11`, `pool_sha256="2d134546..."`, and `reviewer_b_independence_confirmed`. |
| **Gold Label v2 Schema** | `research/s5-c3-human-adjudication-prep/schemas/s5_gold_label_ac_v2.schema.json:L32, L41-42, L61, L100-156, L198-211` | Hardcodes `pool_version="s5b2_1_proposed_pooled_v2.1_pending_approval"`, `const: 254` / `minItems: 254` / `maxItems: 254`, `Q-S5B2-03/08/11`, and historical `REV_A`/`REV_C`/`REV_B` provenance. |
| **Annotation Workbench** | `research/s5-c3-human-adjudication-prep/scripts/annotation_workbench/constants.py:L9-43`, `loader.py:L106-121`, `ui_template.py:L173` | Hardcodes `EXPECTED_PAIR_COUNT=254`, `EXPECTED_QUERY_COUNT=10`, `okf_graph.db`, v2.1 markdown workbook hydration (cannot read `s5v31_corpus_passages.jsonl`), and `0 / 254 completed`. |
| **A/C Adjudication Tooling** | `research/s5-c3-human-adjudication-prep/scripts/ac_adjudication/constants.py:L9-25, L67` | Hardcodes v2.1 pool, `s5_gold_label_ac_v2.schema.json`, `EXPECTED_PAIR_COUNT=254`, and `Q-S5B2-03/08/11`. |
| **Negative-Control Verifier** | `research/s5-c3-human-adjudication-prep/scripts/neg_control/constants.py:L9-19, L171-186` & `schema.py:L23-49` | Hardcodes `EXPECTED_CORPUS_PASSAGE_COUNT=713`, `53` docs, `6435bf44...`, `okf_graph.db`, and the 3 v2.1 NC specs. |

### 2.3 Scientific / Experimental Blockers Before Pooling
1. **Unscoped vs. Corpus-Scoped Graph Ablation Missing:** `okf_graph.json` (`610` concepts, `1,988` edges) is already grounded via Corpus v3.1; testing the primary hypothesis (*"enforcing corpus-scoped graph parity materially alters comparative system conclusions"*) requires adding an explicit unguarded/unscoped graph control before pooling.
2. **No Cross-Encoder Reranker in Pool:** Only 1 dense encoder (`snowflake-arctic-embed-m-v1.5`) is pooled; if a neural reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2` or `bge-reranker-base`, both feasible on local RTX 2050 4 GiB VRAM) is desired for SIGIR competitiveness, it **must** be cached, pinned, and included **before** freezing the blinded depth-$k$ pool (post-hoc pooling introduces unjudged-passage bias).
3. **Graph-Anchor Regime Confounded with Domain:** `okf_graph.json` grounds `183/610` (`30.00%`) concepts and `341/1,988` (`17.15%`) edges in Corpus v3.1, producing **`0` `rich` queries** in OS (`0/5`), Networks (`0/5`), Distributed Systems (`0/5`), and Robotics (`0/6`), with `40–80%` deterministic BM25 fallback on CS Systems (`80%` on Distributed Systems vs. `0%` on Math for ML). All future evaluations **must** stratify by domain and fallback/non-fallback status.

---

## 3. Prioritized Human-Research Checklist

1. **[NOW — `GO`] Execute Stage 1 Human Query Audit (`4.80–7.20 hr`):** Complete `data/annotation_local/s5v3_1/query_audit/s5v31_query_audit_workbook.{md,json,csv}` for all `72` proposed queries (or locked `48` `test` queries first). De-cue title-named queries (`35/72`), `REVISE`/`REJECT` weak cross-doc bridges (`Q-S5V31-34, 36, 53, 67, 68, 69`), verify truncated-chunk evidence (`11` queries), verify adjacent-chunk shortcuts (`10/19`), and check `Q-S5V31-71` near-miss.
2. **[PRE-POOLING ENGINEERING — SEPARATE PR]** Build versioned **S5-v3.1** adapters/schemas (`s5_gold_label_v31.schema.json`, v3.1 workbench loader reading `s5v31_corpus_passages.jsonl`, v3.1 negative-control verifier over `1,958` passages / `8` NCs, and v3.1 D1 preflight/metrics with explicit dynamic NC list and `@5`-only option) while keeping v2.1 untouched.
3. **[PRE-POOLING DECISION]** Decide whether to include a pinned cross-encoder reranker (`ms-marco-MiniLM-L-6-v2` or `bge-reranker-base`) and an unscoped-graph ablation before locking the blinded depth-$k$ pool.
4. **[CALIBRATION]** Run a `10`-query calibration round across domain-paired human assessors (2 ML/Math/NLP/Robotics + 2 CS Systems + 1 adjudicator per track) and verify inter-annotator agreement before full `test` grading.
5. **[HUMAN ANNOTATION & ADJUDICATION]** Execute dual blind human relevance grading (`test_only_depth_10`: `1,238` pairs, `80.03 hr`, or `test_only_depth_5` fallback: `675` pairs, `47.18 hr`), independent negative-control verification (`6` test NCs, `3.00 hr`), and third-human adjudication of all disagreements (`<= 50 pairs / 75 min` per session).
6. **[INVESTIGATOR-AUTHORIZED D1]** Pass v3.1 preflight, sign the two-factor Investigator-Authorization artifact with exact SHA-256 digests, run read-only v3.1 evaluation, and rewrite `manuscript_draft.md` around S5-v3.1.

---

## 4. Final Experiment Specification (S5-v3.1)

- **Eligible Corpus (`s5v31_corpus_passages.jsonl`, SHA-256 `63664771...`):** `1,958` passages across `8` verified OA sources (`local_oa_001` D2L Ch.3 `26`, `local_oa_002` arXiv:2307.09702v2 `23`, `local_oa_003` MML `719`, `local_oa_004` METATRON `50`, `oa_os_001` OS `112`, `oa_db_001` DB `208`, `oa_net_001` CNP3 `600`, `oa_ds_001` DS `220`); **0** dependence on missing `okf_graph.db`. *(Corpus skew disclosure: MML `36.72%` + CNP3 `30.64%` = `67.36%` of passages.)*
- **Systems (Identical `1,958`-Passage Scope, `8/8` Deterministic):**
  - Controls (3): `v31_lexical_bm25`, `v31_dense_snowflake` (`Snowflake/snowflake-arctic-embed-m-v1.5`, rev `e58a8f75...`, Apache-2.0, `11/11` SHA-256 verified, cache `c02f817f...`), `v31_hybrid_rrf_bm25_dense`.
  - Graph v3 Variants (5): `v31_graph_naive_substring`, `v31_graph_1hop_no_backfill`, `v31_graph_1hop_backfill`, `v31_graph_2hop_backfill`, `v31_graph_2hop_coverage_routed` (using canonical `okf_graph.json`, `610` concepts / `1,988` edges; `183` grounded concepts = `30.00%`).
  - *Recommended Pre-Pooling Additions:* `1` pinned cross-encoder reranker + `1` unscoped-graph ablation (if targeting SIGIR Full/Resource Track).
- **Splits & Leakage Guard:** `24` `dev` (`22` pos + `2` NC) vs. `48` `test` (`42` pos + `6` NC). Zero hyperparameter tuning on `test`; any routing/weight adjustment locked on `dev` prior to `test` pooling.
- **Metrics & Fail-Closed Rules (`d1_pipeline/metrics.py`):**
  - `Precision@5`, `Precision@10` (fixed denominators `5.0`/`10.0`; no short-list inflation).
  - `Pooled Recall@5`, `Pooled Recall@10` (denominator = pooled relevant count `n_rel`, explicitly reported as pooled recall, never full-corpus recall; `None` if `n_rel == 0`).
  - `nDCG@5`, `nDCG@10` (exponential gain `(2**grade - 1)/log2(rank + 1)` over ideal pooled grades); `MRR@10` (or `MRR@5` in `@5`-only mode).
  - Both **Strict (`grade == 2`)** and **Lenient (`grade >= 1`)** thresholds; mandatory per-domain and fallback vs. non-fallback stratification; fail-closed on unjudged Top-$K$.
  - **Statistical Inference (Post-Human Only):** Paired randomization test (`Smucker et al. 2007`) + paired bootstrap 95% CIs + Holm-Bonferroni correction, explicitly disclosing `N_test = 42` answerable queries (`< 50` Sakai 2016 benchmark-power heuristic).

---

## 5. Estimated Human Effort (`s5v31_cost_estimate.json`)

Measured from actual 8-system v3.1 unique pools (`1,001` pairs @ `k=5`; `1,855` pairs @ `k=10`), central `90 s/pair`, `2×` blind humans, `20%` S5-C2-calibrated disagreement @ `2.5 min/adj`, `0.50 hr/NC`, `0.10 hr/QV`:

| Scenario | Queries (`Pos / NC`) | Unique Pairs | Per Reviewer | Dual Grading (`2×`) | Query Audit (`QV`) | NC Review | Adjudication (3rd Human) | **Total Person-Hours** | Indicative Cost (`$25–$50/hr`) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `dev_only_depth_5` | `24` (`22/2`) | `326` | `8.15 hr` | `16.30 hr` | `2.40 hr` | `1.00 hr` | `2.71 hr` (`65` pairs) | **`22.41 hr`** | `$560–$1,120` |
| **`test_only_depth_5`** *(Fallback)* | `48` (`42/6`) | `675` | `16.88 hr` | `33.76 hr` | `4.80 hr` | `3.00 hr` | `5.62 hr` (`135` pairs) | **`47.18 hr`** | `$1,180–$2,359` |
| **`test_only_depth_10`** *(Recommended)* | `48` (`42/6`) | `1,238` | `30.95 hr` | `61.90 hr` | `4.80 hr` | `3.00 hr` | `10.33 hr` (`248` pairs) | **`80.03 hr`** | `$2,001–$4,002` |
| `full_72_depth_10` | `72` (`64/8`) | `1,855` | `46.38 hr` | `92.75 hr` | `7.20 hr` | `4.00 hr` | `15.46 hr` (`371` pairs) | **`119.42 hr`** | `$2,986–$5,971` |

- **Assessor Staffing & Fatigue Risk:** Two generalist assessors across **8 disparate CS subfields** (`30.95 hr` each at `k=10`) are **NOT sufficient** due to domain-competency error and fatigue drift. Use **2 domain-paired teams** (2 ML/Math/NLP/Robotics + 2 CS Systems + 1 adjudicator per track), cap sessions at `<= 50 pairs / 75 min`, and run a `10`-query calibration pass first.
- **Note on NC Pool Share:** The `6` test NCs generate `200/1,238` (`16.2%`) of the `k=10` test pool because diverse systems scatter on unanswerable queries.
- **Smaller-Scope Fallback:** `test_only_depth_5` (`47.18 hr`, strictly `@5` metrics, zero silent imputation of ranks `6–10`) OR a 4-domain CS-Systems/ML-Core track (`~24–30` test queries @ `k=10`, `~40–50 hr`).

---

## 6. Manuscript Evidence Gaps (`manuscript_draft.md`)

**CRITICAL STRUCTURAL GAP:** `research/s5-e0-pre-results-paper-prep/manuscript/manuscript_draft.md` (`458` lines) is **100% anchored to the obsolete S5-v2.1 10-query / 713-passage pilot** (`okf_graph.db` missing, `0` cross-doc queries, `254` pairs, `18` blocked TODOs `TODO-00..TODO-17`) and contains **ZERO** S5-v3 or S5-v3.1 content.

| Section (`manuscript_draft.md`) | Existing Evidence | Missing Evidence | Required Experiment | Human Dependency | Publication Risk |
|---|---|---|---|---|---|
| **§1–2 Title & Abstract** (`L11–26`) | v2.1 pilot framing only | S5-v3.1 scope + all results (`TODO-00, 01`) | Full S5-v3.1 eval | Authorship + human gold | **CRITICAL** (wrong benchmark version) |
| **§3–4 Intro, RQs, Contribs** (`L29–71`) | Verified v2.1 C1–C4 + non-claims | S5-v3.1 falsifiable hypothesis + C5 (`TODO-02`) | Parity/pooling/AI-gate ablations | Human gold + query audit | **HIGH** (10-query pilot != SIGIR full paper) |
| **§5 Related Work & §17 Bib** (`L74–105, 429–458`) | `26/26` verified refs (`BIBLIOGRAPHY_AUDIT.md`; 2 preprints flagged) | `Nogueira & Cho 2019`, `Smucker et al. 2007`, 2025–2026 GraphRAG/IR-eval updates | Literature update only | None | **LOW–MEDIUM** |
| **§6–7 Systems & Corpus** (`L108–164`) | Frozen v2.1 6 systems & `713`-passage corpus | S5-v3.1 `1,958`-passage 8-domain OA corpus, `8` v3.1 systems, optional reranker | Rewrite for v3.1 + add reranker if pooled | Human query verification (`72` q) | **CRITICAL** (v2.1 `okf_graph.db` missing) |
| **§8–9 Setup & Annotation** (`L167–211`) | v2.1 `254`-pair pool + preliminary S5-C2 audit (AI-assisted `REV_B`) | v3.1 pool protocol + real inter-human IAA + NC verifications (`TODO-03, 04`) | Dual blind human annotation + adjudication | **100% HUMAN-BLOCKED** (`47–80+ hr`) | **CRITICAL** |
| **§10 Tech Diagnostics** (`L214–301`) | Verified v2.1 diagnostics | v3.1 8-system diagnostics (`1,001`/`1,855` pools, `30.0%` concept / `17.15%` edge grounding, `29.2%` fallback) | Port verified Stage C diagnostics | None | **MEDIUM** (data exists; not yet in draft) |
| **§11 Results** (`L304–335`) | **0% populated** (`TODO-05..11`) | All effectiveness metrics, domain/fallback/hop stratifications, CIs/significance | Execute v3.1 D1 scoring after human gold | **100% HUMAN-BLOCKED** | **CRITICAL** |
| **§12–15 Disc, Threats, Lims, Concl** (`L338–402`) | Pre-results v2.1 takeaways + `LIM-01..09` | Post-results RQ1–RQ3 synthesis (`TODO-12..16`), v3.1 limitations (MML/CNP3 skew, `page_start=None` on OS/DB/DS) | Post-results error & ablation analysis | Investigator synthesis | **HIGH** |
| **§16 Repro & Ethics** (`L405–426`) | v2.1 SHA-256s + copyright/packfile disclosures | v3.1 SHA-256s + finalized human gold hashes (`TODO-17`) | Record post-human hashes | Investigator sign-off | **MEDIUM** |

---

## 7. SIGIR 2027 Full-Paper Viability Assessment

### 7.1 Audit A — Contribution Decomposition (`"Reliable, Provenance-Aware Multi-Passage Retrieval Evaluation"`)
- **Genuinely New (Narrow Scope):** Integrating four usually siloed validity controls into one executable, fail-closed pipeline for heterogeneous graph + hybrid passage retrieval: (a) graph-aware information-access parity via SHA-256 corpus lock, (b) tiered passage/page provenance separation, (c) pre-annotation passage-necessity & shortcut auditing with verified negative controls, and (d) programmatic pre-scoring gates blocking unconfirmed AI-assisted labels, unadjudicated disagreements, and silent zero-imputation of unjudged passages.
- **Established Prior Work (NOT New):** Pooling bias (`zobel1998reliable`, `buckley2004retrieval`), assessor IAA & weighted $\kappa$ (`voorhees2000variations`, `cohen1968weighted`, `jarvelin2002cumulated`), power/randomization tests (`sakai2016statistical`, `Smucker et al. 2007`), multi-hop shortcut auditing (`min2019compositional`, `ho2020constructing`, `trivedi2022musique`), LLM-as-judge warnings (`faggioli2023perspectives`), KG-IR/GraphRAG (`dietz2018utilizing`, `xiong2017explicit`, `edge2024local`, `gutierrez2024hipporag`).
- **Engineering-Only (NOT Novelty):** Token-boundary anchor matching, alias normalization, BM25 fallback, partial-list backfill, SHA-256 hashing, `tracemalloc`, and local annotation UI.
- **Falsifiable Primary Hypothesis:** *Enforcing corpus-scoped graph parity, passage-necessity auditing, complete depth-$k$ pooling, and independent human-adjudicated labels materially alters comparative system conclusions relative to unguarded evaluations.* **Testability today:** **PARTIAL / BLOCKED** until human gold labels, unscoped-vs-scoped graph ablation, and optional reranker baseline are added.

### 7.2 Separate 4-Axis Assessment (SIGIR 2027 Full Paper)
- **Research Strength:** **LOW today** (`0` human gold labels; manuscript still on 10-query v2.1); **MODERATE** after v3.1 human annotation + parity/pooling ablations.
- **Novelty:** **MODERATE** for **SIGIR Resource / Reproducibility Track**; **LOW** for **SIGIR Main Retrieval Algorithms Track** (graph changes are engineering hygiene, not a new retrieval algorithm).
- **Methodological Validity:** **HIGH** on engineering/provenance rigor (fail-closed gates, zero fabricated labels, exact SHA-256s); **BLOCKED** empirically until human validation completes and v3.1 D1/C3 adapters replace hardcoded v2.1 constants.
- **Expected Limitations:** `N_test = 42` answerable queries (`< 50`-topic Sakai 2016 heuristic), MML+CNP3 corpus skew (`67.36%`), `okf_graph.json` CS-Systems sparsity (`40–80%` fallback), `page_start=None` on EPUB/HTML/LaTeX sources, single dense encoder unless reranker is added pre-pooling, and permanently `BLOCKED` historical v2.1 `okf_graph.db` / Reviewer A `70049fa8...`.

---

## 8. Short-Paper / Workshop / Resource-Track Fallback Recommendation

| Target Venue / Track | Required Scope | Viability |
|---|---|---|
| **SIGIR 2027 Resource Track or Reproducibility Track** *(Primary Recommended Target)* | Complete `test_only_depth_10` (`80.03 hr`) + v3.1 D1/C3 adapters + unscoped-vs-scoped graph & pooling/AI-gate ablations + public OA corpus/code/gold release + full v3.1 manuscript rewrite. | **HIGH (Post-Human)** |
| **SIGIR 2027 Short Paper (4 pp)** *(Bounded-Budget Target)* | Complete `test_only_depth_5` (`47.18 hr`, strictly `@5` metrics) + v3.1 D1/C3 adapters + pooling/fallback/AI-gate empirical findings. | **MODERATE–HIGH (Post-Human)** |
| **SIGIR / ICTIR / EVIA / Eval4NLP Workshop Paper** *(Near-Term / Low-Budget Fallback)* | Methodology & audit paper on fail-closed provenance-aware evaluation using verified v2.1 + v3.1 structural/necessity/pooling diagnostics + optional `dev_only_depth_5` human pilot (`22.41 hr`), without claiming full-benchmark effectiveness. | **HIGH (Near-Term)** |

---

## 9. Clear Stop Conditions

Halt and escalate to the Principal Investigator before spending further annotation hours if **any** of the following trigger:
1. **Query Audit Attrition (`> 25%` rejection):** If Stage 1 human query validation rejects `> 12` of the `48` `test` queries (leaving `< 36` `test` queries or `< 6` verified cross-doc queries), **STOP** and replenish/re-audit queries before pooling.
2. **Low Calibration Agreement (`\kappa_w < 0.60`):** If the `10`-query human calibration round yields quadratic weighted $\kappa_w < 0.60$ or exact agreement `< 70%`, **STOP** full annotation and refine rubric definitions / domain-team pairing.
3. **Unfixed v2.1 Tooling Hardcoding:** **NEVER** run S5-v3.1 gold labels through `d1_pipeline/`, `s5_gold_label_ac_v2.schema.json`, `annotation_workbench/`, `ac_adjudication/`, or `neg_control/` until v3.1 adapters eliminate the `preflight_checks.py:L200-202` silent NC bypass and `254`-pair hardcoding.
4. **Post-Pooling System Additions:** Once the blinded depth-$k$ pool is frozen and human grading begins, **STOP** any attempt to add a new retrieval system (e.g., cross-encoder reranker) without funding incremental pooling for all unjudged Top-$K$ passages.
5. **Budget / Staffing Shortfall (`< 47 hr` available):** If `< 47.18 hr` of qualified domain-paired human assessor time is committed, **STOP** SIGIR Full/Resource-Track execution and pivot cleanly to the Workshop Paper (`dev_only_depth_5` `22.41 hr` or methodology-only) rather than producing under-audited or AI-substituted labels.
