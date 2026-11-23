# Archipelago D9 — Scientific Reproducibility & Methodological Audit Report (Issue #21)

**Date:** 2026-11-23
**Target Venue:** ACM SIGIR 2027 Demonstrations Track
**Evaluated Baseline Commit:** `6eaa91ccd1ffa0cee24aff9e04a25af2acd8c7ad`
**Authoritative Result Artifact:** [`d5_1_evaluation_results_v2.json`](research/d5_sigir_evaluation/d5_1_evaluation_results_v2.json)
**Statistical & Table Pipeline:** [`d9_statistical_and_table_pipeline.py`](research/d5_sigir_evaluation/d9_statistical_and_table_pipeline.py)

---

## 1. Executive Summary & Gate Verdicts

This report presents the D9 Phase 1 scientific reproducibility verification and methodological audit of the Archipelago evaluation benchmark, baselines, frozen artifacts, and manuscript claims. Every frozen dataset, cached embedding array, TREC run file, and runtime evaluation path was re-verified bit-for-bit against the repository state at commit `6eaa91ccd1ffa0cee24aff9e04a25af2acd8c7ad`.

> [!IMPORTANT]
> **Separation of Technical Reproducibility vs. Independent Human Evaluation Readiness:**
> - **Deterministic Code & Artifact Reproducibility:** **`PASS (VERIFIED)`** — All 11 frozen artifact SHA-256 locks, model revision pins (`Snowflake/snowflake-arctic-embed-m` @ `fc74610d18462d218e312aa986ec5c8a75a98152`), 50 held-out query outcomes, TREC run scores, and statistical tests reproduce deterministically.
> - **Independent Human Evaluation Gate:** **`HOLD (PENDING HUMAN REVIEWERS)`** — All 445 positive passage relevance labels in [`passage_qrels.json`](research/d5_sigir_evaluation/passage_qrels.json) remain algorithmic candidates (`human_reviewed: false`), the 24-citation grounding audit ([`citation_grounding_audit.json`](research/d5_sigir_evaluation/citation_grounding_audit.json)) and 45-edge graph audit ([`human_review_records.json`](research/d5_sigir_evaluation/human_review_records.json)) are legacy-record-attributed (unconfirmed) (`independent_peer_review: false`), and the 731-item re-blinded annotation pool awaits independent human annotators.

---

## 2. Frozen Artifact SHA-256 Revalidation & Provenance Audit

All frozen benchmark inputs and outputs were re-hashed and verified against [`tests/unit/test_d5_evaluator_and_protocol.py`](file:///home/pratay-karali/.gemini/antigravity/worktrees/ef53cb24-6e31-4ad2-861f-263e5c31b7dd/swarm-d9-stats-repro-de221142/tests/unit/test_d5_evaluator_and_protocol.py) and [`REPRODUCIBILITY.md`](research/d5_sigir_evaluation/REPRODUCIBILITY.md):

| Artifact | Path | Records / Shape | Verified SHA-256 | Provenance Classification |
|---|---|---|---:|---|
| Development Query Split | `research/d5_sigir_evaluation/queries_dev_15.json` | 15 queries (12 supp, 3 OOD) | `43893328d55fc5cb0b6f583ee7a20ab0eb36c95e686122db75703d6e6dadbd5b` | Frozen dev split |
| Held-Out Query Split | `research/d5_sigir_evaluation/queries_heldout_50.json` | 50 queries (20 core, 18 rel, 12 OOD) | `9e39430942b4f00d34911848cbe61a96532c29ffaee76f0d82ce69496f71103a` | Frozen test split |
| Runtime Graph & Corpus Fixture | `host_inference/fixtures/okf_graph.json` | 610 concepts, 1,988 edges, 775 passages ($\ge 40$ chars) | `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76` | Frozen runtime knowledge base |
| Curated Graph Audit Slice | `research/d5_sigir_evaluation/d5_graph_slice.json` | 40 verified edges (from 45 audited) | `55140e114dcf192cde59d95271a4cb81f1d099fb4de44b0135c6d95f3e455590` | Author-reviewed (`independent_peer_review=false`) |
| Algorithmic Candidate QRels | `research/d5_sigir_evaluation/passage_qrels.json` | 445 positive labels across 37/50 queries | `b3e55ab147907940c6cd90ea5273284558037363066c4cfdd199efa0743bc8a2` | Provisional algorithmic (`human_reviewed=false`) |
| Cached Corpus Embeddings | `research/d5_sigir_evaluation/corpus_embeddings_snowflake.npy` | `(775, 768)` `float32` | `f2fe942e6c07d95337ec22b1bcaaa1e0666e33ee47012518db7a302be7ea26c2` | Pinned `snowflake-arctic-embed-m` (`fc74610d...`) |
| Cached Concept Embeddings | `research/d5_sigir_evaluation/concept_embeddings_snowflake.npy` | `(610, 768)` `float32` | `db7a019a684b343c92c1a76aac7ebe2f1208362e560c9fffb8b91eec3818a3f3` | Pinned `snowflake-arctic-embed-m` (`fc74610d...`) |
| BM25 Ranked Run | `research/d5_sigir_evaluation/ranked_runs/bm25.run` | 50 queries $\times$ top-5 | `1df0d3a0ab8dbfec01b89b044b167097e31cc919da8cb6a184e57575f5908446` | Frozen TREC run (`k1=1.5, b=0.75`) |
| Snowflake-Arctic Ranked Run | `research/d5_sigir_evaluation/ranked_runs/snowflake_arctic_neural.run` | 50 queries $\times$ top-5 | `b92152490a46aa3c43d1588267f3ae81ad4de20c361e098d4d63df5239a4a0fd` | Frozen TREC run (cosine similarity) |
| Feature-Hashed Ranked Run | `research/d5_sigir_evaluation/ranked_runs/feature_hashed_vector.run` | 50 queries $\times$ top-5 | `7d0681efee7f35445a2307fbbc07856add2a94f9f1e873bfa4b3a7ab4956a9d0` | Frozen TREC run (BLAKE2b 384-d) |
| Archipelago Ranked Run | `research/d5_sigir_evaluation/ranked_runs/archipelago_graph_assisted.run` | 143 rows across 50 queries | `61e425fa7add8d97375efc1417cb3585514cfd9efaa41fbc010f57bb4444fabe` | Frozen D5.3-A heuristic citation run |

### 2.1 Embedding & Corpus Ordering Fingerprint Verification

- **Corpus Passage Traversal Order:** Deduplicating passages $\ge 40$ characters in first-seen traversal order over `okf_graph.json` produces exactly **775** unique `doc_id::chunk_id` identifiers with `sha256("\n".join(passage_ids))` = `b0c921f7e9a2120c605565e16e3534f6b917115190462fa97c4e05345f4bcca9`, matching `embedding_manifest.json` (`passage_id_order_fingerprint`).
- **Concept Node Ordering:** Sorting the 610 keys of `okf_graph.json["concepts"]` in ascending lexicographical order matches the 610 rows of `concept_embeddings_snowflake.npy`.
- **Metric Implementation Verification:** `reciprocal_rank`, `ndcg_at_k`, `recall_at_k`, and `precision_at_k` in [`archipelago/eval/retrieval_baselines.py`](archipelago/eval/retrieval_baselines.py) were verified against analytical ground truth and reproduce `d5_1_evaluation_results_v2.json` to 4 decimal places across all 4 systems.

---

## 3. Methodological Examination of the Five Core Scientific Questions

### Question 1: Output-Space Equivalence in Experiment A (Concept Resolution)

**Finding:** All four systems in Experiment A ([`scripts/benchmarks/d5_1_evaluation_suite.py`](scripts/benchmarks/d5_1_evaluation_suite.py#L123-L238)) predict over the **exact same discrete output space**: $\mathcal{C} \cup \{\varnothing\}$, where $\mathcal{C}$ is the set of 610 canonical concept IDs in `okf_graph.json` and $\varnothing$ (`None`) represents abstention.

- **Candidate Representation for Baselines:** Each $c \in \mathcal{C}$ is represented by the descriptor string `"{label}: {summary}"` extracted from `okf_graph.json["concepts"][c]`.
  - **BM25 Lexical (`bm25_lexical`):** Ranks the 610 concept descriptors using `BM25Okapi(k1=1.5, b=0.75)` and predicts the top-1 `cid` if $\text{score} > 2.0$, else `None`.
  - **Feature-Hashed Vector (`feature_hashed_vector`):** Embeds query and 610 concept descriptors via 384-dim BLAKE2b token projection (`host_inference/engine/text.py`), predicting the top-1 `cid` by cosine similarity if $\cos > 0.35$, else `None`.
  - **Snowflake-Arctic Neural (`snowflake_arctic_neural`):** Embeds query (with prefix `"Represent this sentence for searching relevant passages: "`) and 610 concept descriptors using `Snowflake/snowflake-arctic-embed-m` (`fc74610d...`), predicting top-1 `cid` if $\cos > 0.45$, else `None`.
  - **Archipelago Concept Resolver (`archipelago_resolver`):** Executes `Engine().answer(query)` and extracts `payload["anchor_concept"]["id"]` ($\in \mathcal{C} \cup \{\varnothing\}$).
- **Structural Difference Disclosed:** While the output space $\mathcal{C} \cup \{\varnothing\}$ and scoring rule (`pred_cid == expected_concept or pred_cid in gold_relevant_concepts`) are identical across all four systems, Archipelago's resolver incorporates curated alias tables (`ALIASES` in `host_inference/engine/constants.py`, 57 entries), morphological normalization (`_normalize_query_for_graph`), domain-incompatibility guards (`_is_domain_incompatible`), and route-level graph-suppression rules (`route_logic.py`), whereas the three baselines perform unassisted text similarity over `"label: summary"` strings. Thus, Experiment A evaluates an **engineered concept-grounding pipeline against zero-shot lexical and embedding matchers over concept descriptors**, not two identically parameterized classifiers.

### Question 2: Abstention Threshold Fairness Across Baselines

**Finding:** In `d5_1_evaluation_suite.py`, the baseline abstention cutoffs (`BM25 > 2.0`, `Feature-Hashed > 0.35`, `Snowflake-Arctic > 0.45`) are fixed heuristic constants rather than thresholds calibrated on a held-out validation curve.
- **Why Uncalibrated BM25 (`> 2.0`) Achieves 0/12 Abstention:** On the 610-concept descriptor collection, any multi-word English query sharing common function or technical tokens (e.g., `"Explain"`, `"What"`, `"is"`, `"in"`, `"system"`, `"equations"`, `"theory"`) with concept summaries achieves a BM25 score between `2.13` (`Q48`) and `12.62` (`Q47`), exceeding the `2.0` cutoff on all 12 out-of-corpus queries.
- **Dev-Only Calibration Sensitivity Check (`queries_dev_15.json`):** Any threshold calibration must use **development data only** (`queries_dev_15.json`: 12 supported `DEV01`–`DEV12`, 3 unsupported `DEV13`–`DEV15`). On `queries_dev_15.json`, the maximum BM25 score across unsupported queries (`DEV13`–`DEV15`) is `7.153` (`DEV13` and `DEV15`), while supported dev queries range from `7.153` to `21.465`.
  - Applying the dev-calibrated threshold $\tau_{\text{BM25,dev}} = 7.153$ to the frozen held-out split (`queries_heldout_50.json`) raises BM25 abstention accuracy from **0/12 (0.00%)** to **5/12 (41.67%)** while changing supported concept-resolution accuracy from **16/38 (42.11%)** to **15/38 (39.47%)** (overall 20/50 = 40.00%).
  - Even under dev-calibrated thresholding, BM25 fails to abstain on 7/12 out-of-domain queries (`Q40` 9.29, `Q41` 10.07, `Q44` 9.62, `Q45` 8.95, `Q46` 10.51, `Q47` 12.62, `Q49` 9.52) because lexical IDF over short concept summaries cannot distinguish domain-specific technical terms from incidental word matches.
  - Conversely, `Snowflake-Arctic-Embed-M` at its threshold `0.45` already achieves **12/12 (100.00%)** abstention on the held-out set, matching Archipelago's 12/12 concept-level abstention while still trailing Archipelago by **+31.58 percentage points** on supported concept resolution (26/38 vs. 14/38, exact McNemar $p = 0.000488$).

### Question 3: Separation of Concept-Level Resolution vs. Passage-Level Ranking Metrics

**Finding:** The evaluation suite strictly decouples **Experiment A (Concept Resolution & Abstention)** from **Experiment B (Passage Retrieval)**:
1. **Different Tasks & Units of Retrieval:** Experiment A evaluates whether a query is anchored to its canonical ontology node $c^* \in \mathcal{C}$ (610 concepts) or cleanly abstained ($\varnothing$). Experiment B evaluates top-5 ranked retrieval of verbatim document chunks $p \in \mathcal{P}$ (775 passages, `doc_id::chunk_id`).
2. **Opposite Empirical Outcomes Disclosed Candidly:** Archipelago leads Experiment A (68.42% supported concept resolution, 100% abstention), whereas standard flat retrievers (`BM25Okapi` and `Snowflake-Arctic-Embed-M`, both MRR `0.7500`, nDCG@5 `0.6415` / `0.6524`) outperform Archipelago's graph-assisted heuristic passage ordering (`MRR 0.4865`, `nDCG@5 0.2253`, paired randomization $p = 0.0156$ for MRR and $p = 0.0001$ for nDCG@5) on the provisional algorithmic passage qrels.
3. **Historical Frozen Run vs. Post-Issue #11 Live Runtime Citation Selection:** The frozen TREC run `ranked_runs/archipelago_graph_assisted.run` (143 entries across 50 queries) captures the D5.3-A baseline heuristic citation-order decay ranking. Subsequent runtime evidence-selection hardening (`host_inference/engine/evidence_selection.py`) caps and filters live chat citations for provenance precision without altering the frozen D5.3-A TREC run lock (`61e425fa...`). Both are verified separately in `test_d5_evaluator_and_protocol.py`.

### Question 4: Impact of Missing QRels, Predicate-Schema Mismatches, and Dev/Test Semantic Overlap

1. **Missing QRels (`37/50` Evaluated Queries in Experiment B):**
   - `passage_qrels.json` contains 445 positive relevance labels across **37** of the 50 held-out queries.
   - The 13 excluded queries are explicitly cataloged in [`unjudged_qrels.json`](research/d5_sigir_evaluation/unjudged_qrels.json): 12 are out-of-corpus abstention queries (`Q39`–`Q50`) that intentionally have zero relevant corpus passages, and **1 supported query (`Q19`: `"What is Cross-Encoder re-ranking?"`)** received zero algorithmic candidate labels because no passage in the 775-passage corpus matched its keyword/document substring threshold (`papers/Nogueira2019_Passage_Reranking.pdf` is not ingested in `okf_graph.json`).
   - **Impact:** Excluding `Q19` from Experiment B inflates apparent passage-retrieval averages by $38/37 \approx 1.027\times$ relative to a penalizing all-38-supported denominator. If `Q19` is included with score `0.0` across all systems ($N=38$ supported denominator), MRR scales by $37/38$: BM25 `0.7303`, Snowflake-Arctic `0.7303`, Archipelago `0.4737`, Feature-Hashed `0.2732`. Furthermore, because the 445 labels were generated by keyword-density heuristics (`ALGORITHMIC_RULE_BASED_CANDIDATE`), lexical rankers (`BM25`) enjoy a structural circularity advantage until replaced by the 731-item human-judged qrels.
2. **Predicate-Schema Mismatches (`13/18` Relational Queries in Experiment C):**
   - `queries_heldout_50.json` defines `expected_relation` triples for 18 relational queries (`Q21`–`Q38`) using four predicates: `USES` (11 queries), `REQUIRES` (4 queries), `CONTRASTS_WITH` (2 queries), and `APPLIES_TO` (1 query).
   - However, `okf_graph.json` stores only **three** edge predicates in runtime memory: `RELATED` (1,334 edges), `REQUIRES` (267 edges), and `UNLOCKS` (387 edges).
   - Consequently, **14 of 18** relational queries expect a predicate (`USES`, `CONTRASTS_WITH`, `APPLIES_TO`) that does not exist in `okf_graph.json`. In [`scripts/benchmarks/d5_relationship_eval.py`](scripts/benchmarks/d5_relationship_eval.py), `no_anchor_resolved` is checked first (`Q29` and `Q30` on `REQUIRES`, plus `Q34` on `USES`), leaving **13 anchor-resolved queries** classified as `PREDICATE_ABSENT_IN_GRAPH` and only **2 assessable queries** (`Q22` and `Q37`, both expecting `REQUIRES`). Neither `Q22` (anchored on `attention_mechanism` instead of `self_attention`) nor `Q37` (where `dense_passage_retrieval` is absent from `okf_graph.json`) surfaces the exact expected triple, yielding **0/18 exact triple matches (`TP = 0, F1 = 0.0`)**.
3. **Dev/Test Semantic Overlap (`2` High-Jaccard Query Pairs, `7` Shared Target Concepts):**
   - Zero query IDs (`DEV01`–`DEV15` vs. `Q01`–`Q50`) and zero normalized query strings overlap between `queries_dev_15.json` and `queries_heldout_50.json`.
   - Two dev/test query pairs exhibit content-token Jaccard similarity $\ge 0.40$:
     1. `DEV10` (*"Explain Leiden community detection in GraphRAG"*) vs. `Q34` (*"What role does community detection play in GraphRAG?"*): **Jaccard = 0.50** (notably, Archipelago misses `Q34` on the held-out set, confirming no overfitting to `DEV10`).
     2. `DEV03` (*"What is LoRA rank r?"*) vs. `Q06` (*"Explain Low-Rank Adaptation (LoRA)"*): **Jaccard = 0.40**.
   - **7 target concepts** (`bert`, `bm25`, `graph_rag`, `low_rank_adaptation`, `qlora`, `rag`, `retrieval`) appear as `expected_concept` in both splits, affecting **14/38** supported held-out queries. While no automatic prompt or weight tuning was performed on held-out queries, `host_inference/engine/constants.py` contains hand-crafted `ALIASES` entries for 6 of those 7 concepts (`lora`, `qlora`, `bert`, `rag`, `graph rag`). Stratified performance on held-out queries targeting the 7 shared concepts is **12/14 (85.71%)** vs. **14/24 (58.33%)** on the 24 held-out queries targeting non-shared concepts (Fisher exact two-sided $p = 0.1485$). This difference must be disclosed as a finite-ontology domain-overlap limitation.

### Question 5: Provenance Status of `citation_grounding_audit.json` and `human_review_records.json`

**Finding:** Both files are explicitly classified as **Author-Attributed / Preliminary Unverified Audits** (`independent_peer_review: false`):
- **`citation_grounding_audit.json` (24 live citations across 5 queries: `Q01=10`, `Q08=6`, `Q21=2`, `Q23=6`, `Q39=0`):**
  - `auditor`: `"Pratay Karali (Lead Author)"`
  - `annotation_method`: `"AUTHOR_REVIEW_SINGLE_ANNOTATOR"`
  - `independent_peer_review`: `false`
  - **Breakdown:** `7/24 (29.17%)` `FULLY_SUPPORTED`, `6/24 (25.00%)` `PARTIALLY_SUPPORTED`, `1/24 (4.17%)` `UNSUPPORTED`, `9/24 (37.50%)` `IRRELEVANT_OR_SPURIOUS` (neighborhood citation dilution), `1/24 (4.17%)` `UNASSESSABLE_NO_TEXT` (`upload_17869808`). Strict precision = `29.17%`; lenient precision = `54.17%`.
- **`human_review_records.json` & `reviewer_provenance.json` (45 graph edges in `d5_graph_slice.json` + `quarantined_edges.json`):**
  - `auditor_role`: `"Pratay Karali (Lead Author and System Architect)"`
  - `review_type`: `"AUTHOR_SELF_REVIEW"`
  - `independent_peer_review`: `false` (`independently_peer_reviewed: 0`)
  - **Breakdown:** `40/45 (88.89%)` marked valid in legacy records (`35` explicit in paper, `5` pedagogical consensus), `5/45 (11.11%)` marked quarantined in legacy records (`self_attention -> transformer REQUIRES` inverted dependency; `anomaly_detection -> federated_learning REQUIRES`; `anomaly_detection -> dynamic_clustering REQUIRES`; `graph_neural_network -> graph_convolutional_network REQUIRES`; `transformer -> linear_algebra REQUIRES`).
  - **Critical Schema Note:** The 40 marked valid in legacy records edges in `human_review_records.json` and `d5_graph_slice.json` are a curated offline evaluation slice using predicates `{USES, REQUIRES, CONTRASTS_WITH, APPLIES_TO}`, whereas the live runtime graph (`okf_graph.json`, 1,988 edges) uses `{RELATED, REQUIRES, UNLOCKS}` and still contains the unquarantined edge `(self_attention, REQUIRES, transformer)`.
- **Required Governance Action:** Neither file may be cited as "independently verified" or "peer-reviewed human evaluation." Both require (a) explicit first-person primary-author sign-off confirming the single-annotator grades, and (b) independent multi-annotator human replication prior to claiming human-verified grounding precision.
