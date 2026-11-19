# An Auditable Pilot Evaluation of Lexical, Dense, Hybrid, and Graph-Based Passage Retrieval on a Technical Computer Science Corpus

**Document Status:** PRE-RESULTS VENUE-NEUTRAL MANUSCRIPT DRAFT  
**Template Independence:** Venue-neutral academic Markdown (no unselected conference or journal template applied)  
**Verified Bibliography:** `references.bib` (26/26 verified entries; see `BIBLIOGRAPHY_AUDIT.md`)  
**Incomplete-Section Manifest:** `MANUSCRIPT_TODO_MANIFEST.md` (`TODO-01` through `TODO-17`)  
**Scientific Integrity Gate:** All relevance-dependent effectiveness metrics, human-validated inter-annotator agreement claims, negative-control classifications, and post-results conclusions are **BLOCKED** pending completion of Stage S5-C3 (independent human annotation/adjudication and negative-control verification) and investigator-authorized Stage S5-D1 execution.

---

## 1. Title

**An Auditable Pilot Evaluation of Lexical, Dense, Hybrid, and Graph-Based Passage Retrieval on a Technical Computer Science Corpus**

**Authors:** `[TODO-00: Insert author names, affiliations, and contact emails prior to final compilation — Source: Human investigator decision]`

---

## 2. Abstract (Skeleton)

Retrieving grounding evidence from technical computer science corpora—comprising textbooks, lecture notes, and peer-reviewed research papers—challenges retrieval systems with exact domain terminology, mathematical identifiers, acronyms, and conceptual relationships. Practitioners increasingly choose among lexical matching (BM25), zero-shot dense bi-encoders, hybrid Reciprocal Rank Fusion (RRF), and knowledge-graph-assisted traversal, yet controlled comparisons across all four paradigms on the same frozen technical corpus remain scarce, and methodological lapses in corpus provenance, pooling completeness, or annotation independence can obscure genuine system behavior.

We present an auditable, corpus-scoped pilot evaluation of six frozen retrieval configurations (`bm25`, `dense_snowflake_arctic_768d`, `hybrid_rrf_e2e`, `baseline_graph_1hop`, `repaired_graph_1hop_ablation`, and `repaired_graph_2hop_full`) over a cryptographically locked 713-passage, 53-document computer science corpus (`s5a_eval_corpus_v1`) spanning Operating Systems, AI/ML, and Computer Networks. Prior to relevance scoring, a staged integrity audit placed 2 of 12 initial queries on hold due to corpus ingestion defects and refuted cross-document necessity on two further queries, leaving 10 active queries (7 answerable: 5 single-hop and 2 same-document two-hop; 3 provisional negative controls; 0 validated cross-document queries) and a complete depth-10 blinded union pool of 254 unique query–passage pairs (100.0% Top-5 and Top-10 coverage across all six systems). Relevance-agnostic technical diagnostics expose two structural mechanics that constrain cross-paradigm interpretation: (i) sparse domain coverage in the 146-edge repaired heterogeneous graph triggers deterministic BM25 fallback on 4/10 (40.0%) queries, mechanically inflating overall Top-10 Jaccard overlap with BM25 from 0.1333–0.1421 (non-fallback) to 0.4800–0.4852 (overall); and (ii) raw substring anchor matching (`"act"` inside `"exact"`) combined with no partial-list backfill yields 31/100 missing Top-10 slots and 65.2% (45/69) system-exclusive pairs in `baseline_graph_1hop`. Extending heterogeneous graph traversal from one hop to two hops activates hop-2 depth on 5/10 queries (all AI/ML), increasing traversed paths from 45 to 212 and altering Top-10 rank order on 5/5 and set membership on 4/5 queries.

`[TODO-01 — BLOCKED ON S5-C3 / S5-D1: Insert concise, strictly descriptive post-adjudication effectiveness summary (human-validated IAA/adjudication outcome, descriptive Recall@5/10, Precision@5/10, MRR@10, nDCG@5/10 across answerable queries, fallback-stratified graph behavior, and verified negative-control diagnostics) without statistical significance or superiority claims. Required artifacts: finalized human gold-label artifact + S5-D1 evaluation report JSON from s5_d1_evaluate.py.]`

---

## 3. Introduction

Retrieving grounding evidence from technical academic corpora—such as computer science textbooks, systems lectures, and peer-reviewed research papers—poses a persistent tension for information retrieval (IR) systems. Technical queries combine exact domain terminology, mathematical identifiers, and acronyms with conceptual relationships across definitions, mechanisms, and architectural tradeoffs. Practitioners and researchers increasingly choose among four retrieval paradigms for such corpora: probabilistic lexical matching (BM25), zero-shot dense bi-encoder embeddings, hybrid rank fusion, and knowledge-graph-assisted traversal. Yet controlled comparisons across all four paradigms on the same frozen technical corpus remain rare, and methodological lapses in corpus curation, corpus-scope parity, pooling completeness, or annotation provenance can easily obscure whether observed behavior reflects genuine retrieval properties or experimental artifacts.

Existing literature establishes well-characterized strengths and blind spots for each paradigm, leaving concrete diagnostic questions unresolved in small, heterogeneous technical collections. Probabilistic lexical models such as Okapi BM25 (`robertson1994some`, `robertson2009probabilistic`, `trotman2014improvements`) provide strong, zero-training exact-term matching and remain difficult to beat consistently in zero-shot technical search (`thakur2021beir`), but fail when relevant passages paraphrase query terminology. Siamese and dual-encoder dense retrievers (`reimers2019sentence`, `karpukhin2020dense`), including instruction-prefixed models such as Snowflake Arctic-Embed (`merrick2024arctic`), capture semantic similarity without lexical overlap, yet face fixed-dimensional representational limits on exact identifiers (`luan2021sparse`) and substantial CPU query-encoding latency relative to inverted indices. Hybrid fusion via parameter-free Reciprocal Rank Fusion (RRF; `cormack2009reciprocal`) mitigates score-scale incompatibility without calibration data, though recent analyses show that RRF discards score margins and remains sensitive to rank cutoffs (`bruch2023analysis`).

Knowledge-graph-assisted retrieval offers a structural complement by linking explicit concepts through typed relations (`xiong2017explicit`, `yasunaga2021qagnn`). Contemporary LLM-era graph frameworks target either global query-focused summarization over hierarchical community summaries (GraphRAG; `edge2024local`) or multi-hop associative recall via Personalized PageRank over extracted triples (HippoRAG; `gutierrez2024hipporag`). However, classical text-centric KG-IR research cautions that graph retrieval is highly vulnerable to entity-linking errors and incomplete graph coverage (`dietz2018utilizing`). Moreover, multi-hop evaluation studies demonstrate that surface compositional phrasing does not guarantee multi-hop necessity: benchmark audits have repeatedly uncovered single-hop shortcuts (`min2019compositional`) and motivated explicit reasoning-path and sub-question necessity verification (`yang2018hotpotqa`, `ho2020constructing`, `trivedi2022musique`). Finally, IR evaluation methodology underscores that incomplete judgment pools bias recall (`zobel1998reliable`, `buckley2004retrieval`), small query samples cannot support reliable statistical significance testing (`sakai2016statistical`), assessor disagreements require explicit modeling and adjudication (`cohen1968weighted`, `voorhees2000variations`), and AI-assisted relevance labels cannot be equated with independent human ground truth (`faggioli2023perspectives`).

These converging methodological risks motivate an **auditable, corpus-scoped pilot study** before scaling to a larger multi-domain benchmark. In this work, we examine six frozen retrieval configurations within the Archipelago testbed over a cryptographically locked technical corpus (`s5a_eval_corpus_v1`: 713 passages across 53 computer science documents spanning Operating Systems, AI/ML, and Computer Networks): (1) lexical `bm25` (`BM25Okapi`, $k_1=1.5, b=0.75$); (2) zero-shot dense bi-encoder `dense_snowflake_arctic_768d` (`Snowflake/snowflake-arctic-embed-m-v1.5`, 768-dim, CPU); (3) hybrid rank fusion `hybrid_rrf_e2e` (RRF, $k=60$ over top-50 lexical and dense lists); (4) corpus-scoped 1-hop Kùzu graph retrieval `baseline_graph_1hop` (1,526 verified edges across 451 eligible concepts); (5) repaired heterogeneous 1-hop graph retrieval `repaired_graph_1hop_ablation` (146 corpus-scoped typed edges); and (6) repaired heterogeneous 2-hop graph retrieval `repaired_graph_2hop_full` (identical 146-edge graph with multiplicative hop-2 decay `0.5`). All six systems operate under **corpus-scope information-access parity**: every system indexes and returns candidate passages exclusively from the identical 713-passage frozen corpus and corpus-scoped graph edges (excluding external and unscoped edges), using canonical `{doc_id}::{chunk_id}` identifiers, deterministic tie-breaking, and runtime SHA-256 verification. This enforces parity of accessible corpus evidence, though it does not imply unrestricted representational parity because the dense encoder relies on pretrained external weights while the lexical and graph retrievers rely on corpus-derived tokens and extracted concept graphs.

Rather than assuming benchmark validity or rushing to headline effectiveness numbers, we enforced a staged integrity audit prior to relevance scoring. Corpus and query-necessity auditing placed 2 of 12 original queries on `HOLD` due to truncated textbook stubs (`Q-S5A-09`) and constructed-card provenance (`Q-S5A-12`), and refuted cross-document labels on `Q-S5B2-06` and `Q-S5B2-07` (reclassifying both to `SINGLE_HOP`), leaving **10 active queries** (7 answerable: 5 `SINGLE_HOP` and 2 same-document `TWO_HOP`; plus 3 provisional negative controls) and **zero validated cross-document queries**. To eliminate pooling bias within Top-10 across the six systems, we expanded candidate assessment from a 25-pair seed set (7.0%–14.0% Top-10 coverage) to a complete depth-10 blinded union pool of **254 unique `(query_id, passage_id)` pairs** (100.0% Top-5 and Top-10 coverage). During pre-adjudication annotation auditing (Stage S5-C2), two initial annotation streams submitted 254/254 structurally valid annotations (203/254 exact agreements; 51 disagreements; descriptive pre-adjudication quadratic weighted $\kappa = 0.7677$), but Reviewer B disclosed AI-assisted proposed annotations on all 254 pairs and independent human negative-control verification remained incomplete. In accordance with governance standards for LLM-assisted judgments (`faggioli2023perspectives`), final relevance scoring was placed on `HOLD` pending genuinely independent human annotation/confirmation, human adjudication of all disagreements, and independent human verification of the three negative controls.

---

## 4. Contributions and Research Questions

### 4.1 Research Questions

To maintain a strict boundary between verified relevance-agnostic diagnostics and blocked relevance effectiveness, this pilot addresses three research questions:

- **RQ1 (Cross-Paradigm Descriptive Effectiveness — Blocked Pending Human Gold Labels):** Under corpus-scope information-access parity over a frozen 713-passage computer science corpus, how do the six retrieval configurations compare in descriptive relevance effectiveness (pooled `Recall@5/10`, `Precision@5/10`, `MRR@10`, and graded `nDCG@5/10` per `jarvelin2002cumulated`) on verified answerable queries once independently validated human gold judgments become available, and how do they behave on verified negative controls?
- **RQ2 (Anchor Coverage, Substring Matching, and Fallback Mechanics — Diagnostics Verified; Effectiveness Stratification Blocked):** How do graph anchor coverage, raw substring matching, and deterministic `corpus_bm25` fallback shape observable retrieval behavior—specifically candidate overlap, system exclusivity, and Top-10 slot completeness—and what constraints do they impose on interpreting cross-paradigm comparisons?
- **RQ3 (One-Hop vs. Two-Hop Traversal Perturbation — Diagnostics Verified; Relevance Impact Blocked):** What measurable changes in observed traversal depth, traversed path counts, candidate set membership, and Top-K ranking order arise when extending deterministic heterogeneous graph retrieval from one hop (`repaired_graph_1hop_ablation`) to two hops (`repaired_graph_2hop_full`), independent of unverified relevance impact?

### 4.2 Scoped Contributions

Within the explicit boundaries of a 10-query exploratory pilot, this work makes the following contributions:

1. **C1 — Auditable, Corpus-Scoped Six-System Pilot Protocol (Verified):** We establish a cryptographically locked 713-passage corpus (`s5a_eval_corpus_v1`), a 4-tier passage provenance registry, corpus-scope graph parity (excluding 462 unscoped Kùzu edges and 2 external heterogeneous edges), complete depth-10 blinded pooling (254 pairs, 100.0% Top-5/Top-10 coverage), byte-identical fresh-clone workbook regeneration, and a gate-enforced read-only evaluation pipeline that refuses silent zero-imputation of unjudged passages (`buckley2004retrieval`).
2. **C2 — Empirical Relevance-Agnostic Characterization of Retrieval Mechanics (Verified):** Prior to gold-label scoring, we quantify candidate-set divergence (`bm25` vs. `dense_snowflake_arctic_768d` Top-10 Jaccard `0.4739`; `hybrid_rrf_e2e` bridging both with `0.6091`/`0.6480` Jaccard and `0.112–0.161 ms` fusion overhead vs. `95.4%–97.8%` dense CPU latency) and document two concrete graph-retrieval failure modes: (a) domain-concentrated graph sparsity causing **4/10 (40.0%)** `corpus_bm25` fallback in `repaired_graph_*` (inflating overall Top-10 Jaccard with `bm25` from `0.1333`/`0.1421` on non-fallback queries to `0.4800`/`0.4852` overall), and (b) raw substring anchor false positives (`"act"` inside `"exact"` on `Q-S5B2-03` and `Q-S5B2-11`) paired with no partial-list backfill, causing **31/100 missing Top-10 slots** and **65.2%** (`45/69`) exclusive pairs in `baseline_graph_1hop`.
3. **C3 — Exact Behavioral Isolation of 1-Hop vs. 2-Hop Heterogeneous Graph Traversal (Verified):** We demonstrate that extending deterministic heterogeneous graph traversal from 1 hop (`45` paths) to 2 hops (`212` paths: `45` hop-1 + `167` hop-2) activates observed hop depth 2 on **5/10** queries (all in AI/ML: `Q-S5B2-04`–`08`), altering Top-10 rank order on 5/5 and set membership on 4/5 (up to 5 passages replaced on `Q-S5B2-05`, Top-10 Jaccard `0.3333`), while leaving `Q-S5B2-10` (0 hop-2 edges) and all 4 fallback queries unchanged—explicitly without presuming relevance gain.
4. **C4 — Methodological Negative Findings on Multi-Hop Necessity and Annotation Governance (Verified):** Through explicit passage-necessity auditing (`min2019compositional`), we show that ostensibly cross-document queries in an initial pilot collapsed to single-hop evidence (leaving 0 validated cross-document queries), and we operationalize a reproducible governance gate that halts effectiveness reporting when AI-assisted annotation provenance (`faggioli2023perspectives`), unresolved disagreements, or unverified negative controls remain open.
5. **C5 — `[TODO-02 — BLOCKED ON S5-C3 / S5-D1]` Post-Adjudication Descriptive Pilot Effectiveness Profile:** *TODO: Once independent human annotation/confirmation, full human disagreement adjudication, independent human negative-control verification (`Q-S5B2-03`, `Q-S5B2-08`, `Q-S5B2-11`), and investigator-authorized S5-D1 evaluation complete, summarize the descriptive effectiveness findings (`Recall@5/10`, `Precision@5/10`, `MRR@10`, `nDCG@5/10`, fallback-stratified graph results, and negative-control diagnostics). Required artifact: S5-D1 evaluation report JSON from `s5_d1_evaluate.py`.*

### 4.3 Explicit Permanent Non-Claims

Even after Stage S5-D1 completes, five claims remain permanently unsupported by the frozen v2.1 pilot:
1. **No system superiority claims:** This pilot does not establish that graph retrieval outperforms lexical, dense, or hybrid retrieval (nor the reverse).
2. **No cross-document multi-hop retrieval claims:** Because **zero** validated cross-document queries exist, this study provides no evidence regarding cross-document multi-hop reasoning.
3. **No statistical significance or broad domain generalization claims:** With 10 active queries (7 answerable) across three computer science subfields, the pilot cannot support inferential hypothesis testing or cross-domain generalization (`sakai2016statistical`).
4. **No misrepresentation of pre-adjudication AI-assisted annotations:** Pre-adjudication S5-C2 agreement involving Reviewer B's AI-assisted stream is audit metadata only, never validated inter-human reliability.
5. **No production-scale efficiency claims:** CPU timings over 713 passages and 146 heterogeneous edges do not extrapolate to large-scale ($10^4$–$10^6$ passage) corpora or GPU/ANN deployments.

---

## 5. Related Work

### 5.1 Lexical Retrieval vs. Zero-Shot Dense Embeddings

Ad-hoc passage retrieval reflects an enduring tradeoff between exact lexical matching and learned dense semantic representations. Under the Probabilistic Relevance Framework, Robertson and Walker (`robertson1994some`) derived tractable approximations to the 2-Poisson term-eliteness model, formalized by Robertson and Zaragoza (`robertson2009probabilistic`) as Okapi BM25 with concave term-frequency saturation ($k_1$) and document-length normalization ($b$). Empirical re-examinations by Trotman, Puurula, and Burgess (`trotman2014improvements`) confirmed that standard BM25 remains a resilient zero-training baseline across minor scoring variants.

Dense passage retrieval addresses BM25's vocabulary-mismatch ceiling. Reimers and Gurevych (`reimers2019sentence`) showed that Siamese bi-encoders (Sentence-BERT) compress Transformer semantics into fixed-dimensional vectors amenable to fast inner-product search, and Karpukhin et al. (`karpukhin2020dense`) demonstrated strong in-domain gains for Dual-Encoder Dense Passage Retrieval (DPR) on open-domain QA. However, large-scale zero-shot evaluation on BEIR by Thakur et al. (`thakur2021beir`) revealed that **BM25 remains highly competitive—and frequently stronger—in zero-shot technical, scientific, and entity-heavy domains** dominated by exact terminology and rare identifiers. Recent embedding families such as Snowflake Arctic-Embed (`merrick2024arctic`) target this zero-shot gap via large-scale contrastive pretraining, hard-negative mining, and asymmetric query instruction prefixes. Archipelago directly contrasts standard `BM25Okapi` ($k_1=1.5, b=0.75$) against zero-shot `Snowflake/snowflake-arctic-embed-m-v1.5` (768-dim, CPU) on a technical CS corpus, where pre-results diagnostics already confirm low candidate overlap (mean Top-10 Jaccard `0.4739`) and substantial CPU latency asymmetry.

### 5.2 Hybrid Retrieval and Rank Fusion

Because lexical and dense retrievers exhibit complementary failure modes—exact-term sensitivity versus semantic paraphrasing—hybrid retrieval is a standard strong baseline. Luan et al. (`luan2021sparse`) demonstrated theoretically and empirically that fixed-dimensional dense encoders face representational capacity bottlenecks for long documents and exact lexical matches, motivating sparse–dense combination.

To combine uncalibrated score distributions without supervised training data, Cormack, Clarke, and Büttcher (`cormack2009reciprocal`) introduced Reciprocal Rank Fusion (RRF), $\text{RRF}(d) = \sum_r \frac{1}{k + \text{rank}_r(d)}$ ($k=60$). More recently, Bruch, Gai, and Ingber (`bruch2023analysis`) analyzed RRF against convex linear combinations of normalized scores, showing that RRF is a robust parameter-free zero-shot baseline when calibration splits are unavailable, but discards score-magnitude margins and remains sensitive to rank-cutoff depth. Archipelago adopts uncalibrated RRF ($k=60$, depth 50) because the 10-query zero-shot pilot lacks a validation split for learning convex weights, while explicitly refraining from testing score-aware fusion superiority.

### 5.3 Knowledge-Graph-Assisted and Graph-Based IR

Graph-based IR spans classical entity-centric retrieval and contemporary LLM-era graph retrieval. Xiong, Power, and Callan (`xiong2017explicit`) showed in Explicit Semantic Ranking (ESR) that projecting academic queries and documents into a concept knowledge graph aids concept-heavy queries where lexical matching fails. Dietz, Kotov, and Meij (`dietz2018utilizing`) synthesized text-centric KG-IR and identified two persistent bottlenecks: **entity-linking / query-to-graph anchoring errors** and **incomplete graph coverage**.

In neural and LLM-era settings, Yasunaga et al. (`yasunaga2021qagnn`) combined language models and knowledge graphs via joint GNN message passing (QA-GNN). Edge et al. (`edge2024local`) introduced GraphRAG, pairing LLM-extracted entity graphs with Leiden community summaries for *global* query-focused summarization, whereas Jiménez Gutiérrez et al. (`gutierrez2024hipporag`) proposed HippoRAG, combining schemaless KG extraction with Personalized PageRank (PPR) for multi-hop associative passage retrieval. Archipelago's three graph retrievers occupy a lightweight, deterministic, local-passage-retrieval niche without GNN training, community summarization, or PPR—and its pre-results diagnostics empirically exhibit the exact anchoring and coverage bottlenecks identified by Dietz et al. (`dietz2018utilizing`).

### 5.4 Multi-Hop Retrieval and Benchmark Necessity Auditing

Multi-hop QA research demonstrates that surface compositional phrasing does not guarantee genuine multi-hop necessity. Following HotpotQA (`yang2018hotpotqa`), Min et al. (`min2019compositional`) showed that many ostensibly multi-hop questions could be answered via single-hop shortcuts without composing multiple passages. Subsequent benchmarks introduced explicit reasoning-path provenance (2WikiMultiHopQA; `ho2020constructing`) and bottom-up sub-question composition with disconnected-reasoning filters and unanswerable controls (MuSiQue; `trivedi2022musique`). Archipelago's Stage S5-B2.1 passage-necessity audit directly applies this discipline, refuting two putative cross-document labels (`Q-S5B2-06`, `Q-S5B2-07`) and documenting the resulting absence of validated cross-document queries rather than claiming unverified multi-hop gains.

### 5.5 Retrieval Evaluation Methodology, Pooling, Power, and AI-Assisted Labeling

Four methodological pillars govern Archipelago's evaluation design:
1. **Pooling completeness:** Zobel (`zobel1998reliable`) showed that incomplete pools overestimate absolute recall and can bias against unpooled runs, and Buckley and Voorhees (`buckley2004retrieval`) demonstrated metric distortion when unjudged documents are silently treated as non-relevant. Archipelago enforces 100.0% depth-10 union pooling across all six frozen systems (254 pairs) and raises a hard validation error on any unjudged Top-10 passage.
2. **Graded relevance and assessor agreement:** Järvelin and Kekäläinen (`jarvelin2002cumulated`) introduced DCG/nDCG for graded relevance with logarithmic rank discounting, and Cohen (`cohen1968weighted`) defined weighted kappa ($\kappa_w$) for ordinal agreement with partial credit. Voorhees (`voorhees2000variations`) showed that relative rankings can remain stable across assessor variations on large TREC query sets—an invariance that cannot be assumed on a 10-query pilot, making full human adjudication of disagreements essential.
3. **Sample size and statistical power:** Sakai (`sakai2016statistical`) systematically reviewed SIGIR and TOIS papers (2006–2015), demonstrating that underpowered query samples produce unreliable significance tests and inflated error rates. Because Archipelago's pilot has only 10 active queries (7 answerable), formal significance testing is excluded in favor of descriptive pilot reporting.
4. **LLM-assisted relevance judgments:** Faggioli et al. (`faggioli2023perspectives`) analyzed the validity risks, circularity, and anchoring bias of LLM-assisted relevance judgments when not validated by independent human assessment. This directly underpins Archipelago's governance gate holding effectiveness evaluation whenever AI-assisted annotations lack independent human verification or replacement.

---

## 6. System and Retrieval Methodology

All six evaluated configurations are frozen in `archipelago/eval/retrieval_baselines.py`, `research/s5-b1-integrity-repair/scripts/run_s5b1_retrieval_benchmark.py`, and `okf/pilot/repaired_extractor.py`. Every system returns up to `top_k = 10` ranked passages from the identical 713-passage eligible corpus (`s5a_eval_corpus_v1`) using canonical `{doc_id}::{chunk_id}` identifiers (0 collisions) and deterministic tie-breaking `(-score, passage_id)`.

### 6.1 Parity Scope Clarification

We enforce **corpus-scope information-access parity**: no retrieval configuration may access, traverse, or return passages or graph edges outside the frozen 713-passage eligible corpus (excluding 462 unscoped/external Kùzu edges and 2 external heterogeneous edges). This guarantees identical candidate passage scope across all six systems, while acknowledging that systems intentionally differ in internal representation (corpus-only term statistics for BM25, externally pretrained transformer weights for the zero-shot dense bi-encoder, and corpus-derived concept graphs for graph retrievers).

### 6.2 Frozen Retrieval Configurations

| System Identifier | Paradigm | Frozen Parameters, Scoring & Parity Enforcement | Fallback & Short-List Behavior |
|---|---|---|---|
| `bm25` | Lexical (`BM25Okapi`) | Lowercase alphanumeric tokenizer (`[a-z0-9]+`); $k_1 = 1.5$, $b = 0.75$; whitespace-normalized text. Uses non-negative shifted IDF $\ln\!\left(\frac{N - df + 0.5}{df + 0.5} + 1\right)$ and sums over query tokens with multiplicity. Always returns 10 passages (lexicographic tie-break even at score `0.0`). | None |
| `dense_snowflake_arctic_768d` | Zero-Shot Dense Bi-Encoder | `Snowflake/snowflake-arctic-embed-m-v1.5` (BERT-based, mean pooling, 768-dim, `max_seq_len = 512`, `float32`, CPU, local revision `f22f7b88939ba6d01306a445d48729fb5a2ff3f3`). Query prefix: `"Represent this sentence for searching relevant passages: "`; empty document prefix; L2-normalized dot product over runtime-SHA-256-verified `(713, 768)` cache (`ffb94053...`). Always returns 10 passages. | None |
| `hybrid_rrf_e2e` | Hybrid Rank Fusion | Reciprocal Rank Fusion (`cormack2009reciprocal`): $\text{RRF}(d) = \sum_{r} \frac{1}{60 + \text{rank}_r(d)}$ over top-50 deduplicated candidate lists from `bm25` and `dense_snowflake_arctic_768d`. End-to-end latency includes $T_{\text{BM25}} + T_{\text{Dense}} + T_{\text{Fusion}}$. | None |
| `baseline_graph_1hop` | Corpus-Scoped Kùzu 1-Hop Graph (`RepairedBaselineGraphRetriever`) | Restricts Kùzu `Concept` nodes strictly to the 713 eligible passages (**451/610** eligible concepts; excludes 56 external-only + 103 orphan concepts) and filters `REQUIRES`/`RELATED`/`UNLOCKS` edges via `_is_corpus_verified_kuzu_edge()` (**1,526/1,988** verified edges; excludes 462 = 23.24%). Raw substring anchor matching (`c in query.lower()`). Expands up to 5 alphabetically ordered 1-hop neighbors per anchor. Score: $+2.0$ per matched anchor, $+1.0$ per 1-hop neighbor. | `corpus_bm25` only when `matched_anchors` is empty; **no partial-list backfill** when `< 10` passages are linked. |
| `repaired_graph_1hop_ablation` | Heterogeneous Graph 1-Hop (`RepairedHeterogeneousGraphRetriever`, `max_hops=1`) | Built by `RepairedGraphExtractor` (clause-aware, denoised, prerequisite-DAG-enforced) restricted to the 713 eligible passages (**146/148** corpus-scoped edges; 2 external uploads removed). Typed edge weights: `REQUIRES=1.0`, `PART_OF=0.9`, `USES=0.8`, `CONTRASTS_WITH=0.7`, `RELATED=0.5`, multiplied by `edge.confidence` (undirected expansion for `CONTRASTS_WITH`/`RELATED`). Raw substring anchor matching against adjacency keys (concepts with $\ge 1$ outgoing edge, excluding pure directed sinks). Passages linked by edge provenance and raw substring mention (`c in p.text.lower()`). | `corpus_bm25` when `matched_anchors` is empty. |
| `repaired_graph_2hop_full` | Heterogeneous Graph 2-Hop (`RepairedHeterogeneousGraphRetriever`, `max_hops=2`) | Identical 146-edge corpus-scoped graph and edge weights as `repaired_graph_1hop_ablation`, extending traversal to hop 2 with multiplicative decay `0.5`: $\text{score}_2 = \text{score}_1 \times w_2 \times 0.5$ ($\max$ per visited concept). Logs observed hop depth (`0` fallback, `1` hop-1 only, `2` novel hop-2 concepts) and `paths_traversed`. | `corpus_bm25` when `matched_anchors` is empty. |

*(Note: A 64-dim deterministic token-hashing encoder documented in `s5b1_model_manifest.json` is strictly a CI/debugging baseline and is excluded from the six evaluated systems. Additionally, a minor prose typo on line 99 of `graph_information_access_audit.json` prints "1,686" whereas the authoritative structured fields and per-table sum `179 + 1019 + 328 = 1,526` confirm 1,526 verified Kùzu edges.)*

---

## 7. Dataset and Corpus Provenance

### 7.1 Frozen Eligible Corpus (`s5a_eval_corpus_v1`)

The corpus is a frozen, deduplicated snapshot extracted from `okf_graph.db` via `build_fixed_corpus_from_kuzu()` (collapsing whitespace, deduplicating on `exact_normalized_sha256` after deterministic sorting on `(doc_id, page_number, chunk_id, raw_text)`, and rejecting orphan chunks lacking `Document -[:HAS_CHUNK]-> Chunk` edges) and filtered by `load_s5b1_corpus()`:

- **Database scope:** `okf_graph.db` contains 79 documents and 786 total chunks.
- **S3 baseline (`s3_fixed_corpus_v1`):** 764 passages across 59 documents.
- **Deterministic S5-A/S5-B1 exclusions (51 passages):** **50** index/frontmatter passages matched by `_is_index_only_passage()` plus **1** invalid-page passage (`doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4`, page 612 exceeding book length 500).
- **Frozen eligible corpus (`s5a_eval_corpus_v1`):** Exactly **713 passages** across **53 documents**, cryptographically locked at runtime:
  - `corpus_passage_id_sha256`: `f7fe70031781b005d712a7a9a4aa2452a8b17d7353531305b39b09d88eeecd98`
  - `corpus_text_sha256`: `8464acaea13cbfae0f345ea29ce1cf707dc39e76832c7729fca33fbd763bc68c`
  - `corpus_sha256`: `6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7`

### 7.2 Four-Tier Passage Provenance Registry

Auditing `s5a_eval_corpus_v1` without altering the frozen 713 passages (`s5b2_1_corpus_provenance_registry.json`) classifies every passage into four provenance tiers:
1. `source_verified_constructed_pilot_card`: **1** passage (`pilot/silberschatz_3nf_card.txt::third_normal_form_seed_001`, inline hand-authored card in `seed_soference_catalog.py` with `"pdfs": []`).
2. `source_verified_truncated_textbook_stub`: **21** passages (`doc_*` entries truncated at $\le 305$ characters).
3. `convention_inferred_seed_chunk`: **16** passages (`*_seed_*` chunks from OSTEP chapters, QLoRA, and vLLM; raw PDF page alignment not independently re-verified during S5-B2.1).
4. `convention_inferred_paper_or_upload_chunk`: **675** passages (`papers/*.pdf` and `upload_*` chunks).

### 7.3 Query Benchmark Evolution and Passage-Necessity Audit

Starting from 12 initial pilot queries, the Stage S5-B2 / S5-B2.1 audit (`s5b2_proposed_blinded_query_specs.json`, `s5b2_1_passage_necessity_matrix.json`) produced the frozen v2.1 benchmark:

- **Held / Excluded Queries (2 of 12):**
  - `Q-S5A-09` (OSI Reference Model layers): placed on `HOLD` because the sole textbook chunk (`doc_computer_networks_6_e_p42_1`) is truncated at 285 characters after Layer 2.
  - `Q-S5A-12` (Third Normal Form / 3NF): placed on `HOLD` because the sole passage mentioning 3NF is the constructed pilot card (`silberschatz_3nf_card.txt`).
- **Active Queries (10 of 12):**
  - **Domain distribution:** Operating Systems (3: `Q-S5B2-01`, `02`, `03`), AI & Machine Learning (5: `Q-S5B2-04`, `05`, `06`, `07`, `08`), Computer Networks (2: `Q-S5B2-10`, `11`).
  - **Query revisions:** `Q-S5B2-02` was revised to align with extracted LDE/address-translation text in `07_address_translation.pdf`; `Q-S5B2-10` was revised to reflect proposed D-MAGIC/SAGA mechanisms without claiming experimentally verified latency reductions; `Q-S5B2-04` and `Q-S5B2-05` had missing corpus formula chunks added to seed candidates.
  - **Hop-necessity classification:** **Zero (0)** validated cross-document queries remain (`Q-S5B2-06` and `Q-S5B2-07` were refuted and reclassified from `CROSS_DOCUMENT` to `SINGLE_HOP`). Five queries (`Q-S5B2-01`, `04`, `05`, `06`, `07`) are `SINGLE_HOP`; two (`Q-S5B2-02`, `10`) are same-document `TWO_HOP`; three (`Q-S5B2-03`, `08`, `11`) are provisional negative controls (`PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_HUMAN_VERIFICATION`), with `Q-S5B2-08` and `Q-S5B2-11` also carrying unsupported/synthetic factual premises (`s5b2_negative_control_audit.json`).

---

## 8. Experimental Setup

### 8.1 Depth-10 Union Pooling and Blinding

To eliminate incomplete-pool bias within Top-10 (`zobel1998reliable`, `buckley2004retrieval`), S5-B2.1 expanded the 25-pair investigator seed pool (which covered only 7.0%–14.0% of Top-10 outputs) to the deduplicated union of Top-10 outputs across all six frozen systems plus the 25 investigator seeds. Duplicates across systems (e.g., identical BM25 fallback lists or overlapping Top-10 candidates) are collapsed to unique `(query_id, passage_id)` keys before shuffling, yielding **254 unique pairs** (`244` retrieved union + `10` seed-only) and **100.0% Top-5 and Top-10 pool coverage** across all six systems (`s5b2_1_topk_pool_coverage_refreshed.json`).

Candidate passages per query are stored in neutral lexicographical order and deterministically shuffled (`random.Random(20261119)`) before assigning neutral IDs `S5B21-PAIR-001` through `S5B21-PAIR-254`. All reviewer-facing artifacts (`retrieval_query_pool_blinded.json`, `SHA-256: 2d134546...`) strip system identities, retrieval ranks, investigator judgments, and answerability/category hints.

### 8.2 Planned Post-Adjudication Evaluation Protocol (Stage S5-D1)

Once independent human gold labels and human negative-control verifications pass preflight and receive explicit investigator authorization, read-only descriptive evaluation computes:

- **Thresholds:** Strict binary relevance (`grade == 2`) and lenient binary relevance (`grade >= 1`).
- **Answerable-query metrics:** `Precision@5` and `Precision@10` (fixed denominators `5.0` and `10.0`, which explicitly penalize short lists such as `baseline_graph_1hop`), **pooled** `Recall@5` and `Recall@10` (denominated over total pooled relevant passages for that query at the given threshold, not the full 713-passage corpus), `MRR@10`, and graded `nDCG@5` and `nDCG@10` (`jarvelin2002cumulated`) with exponential gain $2^g - 1$, logarithmic discount $1/\log_2(\text{rank}+1)$, and `IDCG` computed over the judged 254-pair pool.
- **Unjudged-passage policy:** Unjudged Top-10 passages are explicitly counted and raise a hard validation error rather than being silently imputed as grade `0`.
- **Stratified diagnostics:** Separate reporting of (a) fallback (`4/10`) vs. non-fallback (`6/10`) graph queries, (b) short-list accounting (`baseline_graph_1hop`: `69/100` slots), (c) 1-hop vs. 2-hop descriptive comparison on the 5 AI/ML queries reaching hop 2, and (d) verified negative-control behavior (excluded from Recall/MRR/nDCG denominators; any negative control reclassified by human verifiers is handled explicitly in stratification).
- **Latency protocol:** Cold-start initialization is separated from first-query and warm per-query distributions (5 warm repetitions per query on CPU, recorded in S5-B1.1).

---

## 9. Annotation and Human Evaluation Protocol

### 9.1 Grading Rubric and Blinding Rules

Reviewers grade each blinded `(query_id, passage_id)` pair on a discrete 3-level ordinal scale (`RETRIEVAL_ANNOTATION_PROTOCOL.md`):
- **`0` (Irrelevant / Distractor):** Passage does not answer or provide useful grounding context for the query; supporting quotation must remain empty.
- **`1` (Partially Relevant / Background Context):** Passage provides partial facts, definitions, or background context but is insufficient on its own; requires a verbatim supporting quotation copied from the passage.
- **`2` (Highly Relevant / Grounding Evidence):** Passage directly provides core grounding evidence answering the query (or a necessary component for same-document two-hop queries); requires a verbatim supporting quotation.

Reviewers also record confidence (`HIGH`, `MEDIUM`, `LOW`), optional notes, and a truthful human provenance declaration (reviewer ID, human attestation, and explicit AI-assistance/exposure disclosure). All blinded reviewer workbooks and local annotation tools enforce zero AI relevance suggestions, zero prior-reviewer leakage, and zero auto-signed provenance declarations.

### 9.2 Pre-Adjudication Audit Status (Stage S5-C2 — Preliminary Only)

In Stage S5-C2 (`s5c2_audit_summary.json`), two initial annotation streams (`REV_A` and `REV_B`) were audited:
- Both streams submitted 254/254 structurally valid pairs (0 missing, 0 duplicate, 0 verbatim quote mismatches; 5 minor workbook source-text discrepancies against the frozen pool: `REV_A` `PAIR-189, 232`; `REV_B` `PAIR-091, 119, 134`).
- Pre-adjudication descriptive agreement was 203/254 (79.92% exact agreement; unweighted $\kappa = 0.5972$; quadratic weighted $\kappa = 0.7677$, `cohen1968weighted`), with **51 disagreements** (all on the 7 answerable queries: 34 `0 vs 1`, 4 `1 vs 0`, 4 `1 vs 2`, 9 `2 vs 1`). Both streams assigned grade `0` to all pooled pairs on `Q-S5B2-03` (25/25), `Q-S5B2-08` (27/27), and `Q-S5B2-11` (23/23).
- **Governance Hold:** Reviewer B disclosed `AI-assisted proposed annotation; requires independent human confirmation` on all `254/254` pairs, and independent human negative-control verification remained unperformed (`NOT_YET_PERFORMED`). S5-C2 therefore issued `HOLD_FOR_DISAGREEMENT_ADJUDICATION_AND_REV_B_INDEPENDENCE_CHECK`. These pre-adjudication numbers are **preliminary audit status only** and must never be cited as validated inter-human reliability.

### 9.3 Stage S5-C3 Independent Human Adjudication and Negative-Control Verification

To clear the governance hold without weakening provenance standards, Stage S5-C3 supports genuinely independent double-blind human annotation (Reviewer A and Reviewer C under versioned schema `s5_gold_label_ac_v2`, while preserving the legacy Reviewer B provenance contract untouched), full human adjudication of every disagreement with written rationales, independent corpus-wide human verification of `Q-S5B2-03`, `Q-S5B2-08`, and `Q-S5B2-11`, and explicit investigator sign-off.

- `[TODO-03 — BLOCKED ON S5-C3: Insert finalized independent human inter-annotator agreement (exact agreement, unweighted kappa, quadratic weighted kappa, confusion matrix), total disagreement count, and human adjudication summary. Required artifact: finalized S5-C3 A/C comparison and adjudication report + finalized human gold-label JSON.]`
- `[TODO-04 — BLOCKED ON S5-C3: Insert finalized independent human negative-control verification classifications, checked passage counts, and rationales for Q-S5B2-03, Q-S5B2-08, and Q-S5B2-11. Required artifact: finalized S5-C3 human negative-control verification JSON.]`

---

## 10. Verified Relevance-Agnostic Technical Diagnostics

All figures in this section are strictly **relevance-agnostic behavioral diagnostics** verified directly from `research/s5-d0-experimental-analysis-prep/reports/s5d0_technical_diagnostics.json` (`relevance_metrics_computed: false`, SHA-256 `f502e035...`) and `s5b2_1_frozen_ranked_results.json` (`e20a9f64...`). They characterize candidate overlap, graph traversal, fallback frequency, slot completeness, and recorded CPU latency without evaluating or implying retrieval effectiveness.

### 10.1 Pairwise Top-10 and Top-5 Candidate Overlap

Table 1 reports mean pairwise Top-10 Jaccard similarity (with mean Top-5 Jaccard in parentheses) across all 10 active queries:

| System | `bm25` | `dense` | `hybrid_rrf` | `baseline_graph_1hop` | `repaired_1hop` | `repaired_2hop` |
|---|---:|---:|---:|---:|---:|---:|
| **`bm25`** | 1.0000 (1.0000) | 0.4739 (0.4869) | 0.6091 (0.7440) | 0.1466 (0.1222) | 0.4800 (0.4472) | 0.4852 (0.4583) |
| **`dense_snowflake_arctic_768d`** | 0.4739 (0.4869) | 1.0000 (1.0000) | 0.6480 (0.5663) | 0.1088 (0.1000) | 0.2106 (0.1540) | 0.2159 (0.1651) |
| **`hybrid_rrf_e2e`** | 0.6091 (0.7440) | 0.6480 (0.5663) | 1.0000 (1.0000) | 0.1216 (0.1333) | 0.2742 (0.3262) | 0.2795 (0.3373) |
| **`baseline_graph_1hop`** | 0.1466 (0.1222) | 0.1088 (0.1000) | 0.1216 (0.1333) | 1.0000 (1.0000) | 0.1164 (0.1222) | 0.1216 (0.1222) |
| **`repaired_graph_1hop_ablation`** | 0.4800 (0.4472) | 0.2106 (0.1540) | 0.2742 (0.3262) | 0.1164 (0.1222) | 1.0000 (1.0000) | 0.8636 (0.8250) |
| **`repaired_graph_2hop_full`** | 0.4852 (0.4583) | 0.2159 (0.1651) | 0.2795 (0.3373) | 0.1216 (0.1222) | 0.8636 (0.8250) | 1.0000 (1.0000) |

`bm25` and `dense_snowflake_arctic_768d` share a mean Top-10 Jaccard of `0.4739` and agree at Rank 1 on only `5/10` queries. `hybrid_rrf_e2e` bridges both lists, sharing an average of `7.4` Top-10 passages with `bm25` and `7.5` with `dense` (matching `dense` at Rank 1 on `8/10` queries and `bm25` on `5/10`).

### 10.2 Fallback-Adjusted Lexical Overlap and System Exclusivity

Overall Top-10 Jaccard between `repaired_graph_*` and `bm25` (`0.4800`/`0.4852`) is mechanically inflated by `corpus_bm25` fallback on `4/10` queries (where Jaccard = `1.0000`). Excluding fallback queries yields substantially lower lexical overlap:

| Graph System | Non-Fallback Queries | Mean Top-10 Jaccard vs. `bm25` (Non-Fallback) | Mean Shared Top-10 Passages vs. `bm25` (Non-Fallback) |
|---|---:|---:|---:|
| `baseline_graph_1hop` | 9 / 10 | **0.0518** | 0.89 / 10 |
| `repaired_graph_1hop_ablation` | 6 / 10 | **0.1333** | 2.17 / 10 |
| `repaired_graph_2hop_full` | 6 / 10 | **0.1421** | 2.33 / 10 |

Across all 10 queries, Top-10 exclusivity reveals that `baseline_graph_1hop` produces the most disjoint candidate set:

| System | Total Top-10 Pairs Retrieved | Exclusive to This System | Shared with $\ge 1$ Other System | Rank-1 Agreement with `bm25` / `dense` |
|---|---:|---:|---:|---:|
| `bm25` | 100 | 9 (9.0%) | 91 | 10 / 5 |
| `dense_snowflake_arctic_768d` | 100 | 21 (21.0%) | 79 | 5 / 10 |
| `hybrid_rrf_e2e` | 100 | 8 (8.0%) | 92 | 5 / 8 |
| `baseline_graph_1hop` | 69 | **45 (65.2%)** | 24 | 1 / 1 |
| `repaired_graph_1hop_ablation` | 100 | 7 (7.0%) | 93 | 4 / 1 |
| `repaired_graph_2hop_full` | 100 | 6 (6.0%) | 94 | 4 / 1 |

### 10.3 One-Hop vs. Two-Hop Graph Traversal Behavior

| Query ID | Domain | `baseline_1hop` Anchors / Paths / Hop | `repaired_1hop` Anchors / Concepts / Paths / Hop | `repaired_2hop` Concepts / Paths (H1+H2) / Hop | `1-hop` vs `2-hop` Top-5 / Top-10 Jaccard | `2-hop` Top-10 Set Diff & Rank Shifts |
|---|---|---|---|---|---:|---|
| `Q-S5B2-01` | OS | `[]` / 0 / 0 (FB) | `[]` / 0 / 0 / 0 (FB) | 0 / 0 (0+0) / 0 (FB) | 1.0000 / 1.0000 | Identical (BM25 fallback) |
| `Q-S5B2-02` | OS | `['translation']` / 2 / 1 | `[]` / 0 / 0 / 0 (FB) | 0 / 0 (0+0) / 0 (FB) | 1.0000 / 1.0000 | Identical (BM25 fallback) |
| `Q-S5B2-03` | OS | `['act']` / 0 / 0 | `[]` / 0 / 0 / 0 (FB) | 0 / 0 (0+0) / 0 (FB) | 1.0000 / 1.0000 | Identical (BM25 fallback) |
| `Q-S5B2-04` | AI/ML | `['transformer']` / 5 / 1 | `['attention', 'the transformer', 'transformer']` / 13 / 21 / 1 | 33 / 96 (21+75) / **2** | 1.0000 / 0.6667 | +2 / −2 passages; 2 shared rank shifts |
| `Q-S5B2-05` | AI/ML | `['multi-head attention']` / 5 / 1 | `['attention']` / 3 / 2 / 1 | 5 / 4 (2+2) / **2** | **0.2500 / 0.3333** | +5 / −5 passages; 5 shared rank shifts |
| `Q-S5B2-06` | AI/ML | `['low-rank adaptation', 'transformer']` / 9 / 1 | `['low-rank adaptation', 'transformer']` / 13 / 12 / 1 | 34 / 68 (12+56) / **2** | 0.6667 / 0.8182 | +1 / −1 passage; 8 shared rank shifts |
| `Q-S5B2-07` | AI/ML | `['adapter', 'fine-tuning', 'qlora', 'quantization']` / 12 / 1 | `['gpu', 'qlora']` / 6 / 4 / 1 | 17 / 21 (4+17) / **2** | 0.6667 / 1.0000 | +0 / −0 passages; 9 shared rank shifts |
| `Q-S5B2-08` | AI/ML | `['llama']` / 0 / 0 | `['gpu']` / 4 / 3 / 1 | 15 / 20 (3+17) / **2** | 0.6667 / 0.8182 | +1 / −1 passage; 8 shared rank shifts |
| `Q-S5B2-10` | Net | 6 anchors / 24 / 1 | `['nids']` / 4 / 3 / 1 | 4 / 3 (3+0) / 1 | 1.0000 / 1.0000 | Identical (0 hop-2 outgoing edges) |
| `Q-S5B2-11` | Net | `['act']` / 0 / 0 | `[]` / 0 / 0 / 0 (FB) | 0 / 0 (0+0) / 0 (FB) | 1.0000 / 1.0000 | Identical (BM25 fallback) |

`repaired_graph_1hop_ablation` traversed **45** hop-1 paths across 6 non-fallback queries; `repaired_graph_2hop_full` traversed **212** paths (**45** hop-1 + **167** hop-2), reaching observed hop depth 2 on **5/10** queries (all AI/ML: `Q-S5B2-04`–`08`), altering Top-10 rank order on `5/5` and set membership on `4/5` (largest shift on `Q-S5B2-05`: +5/−5 passages, Top-10 Jaccard `0.3333`). `baseline_graph_1hop` traversed **57** 1-hop Kùzu paths with `0` traversal errors.

### 10.4 BM25 Fallback Frequency, Substring Anchor False Positives, and Missing Slots

- **Repaired heterogeneous graph fallback (`4/10 = 40.0%`):** Both `repaired_graph_1hop_ablation` and `repaired_graph_2hop_full` trigger deterministic `corpus_bm25` fallback on all three Operating Systems queries (`Q-S5B2-01`, `02`, `03`) plus Networks negative control `Q-S5B2-11` due to zero anchor matches in the 146-edge graph, yielding exact Top-10 ID and score matches to `bm25` (`4/4`).
- **Baseline Kùzu graph substring false positives and slot shortfalls:** `baseline_graph_1hop` falls back on only `1/10` (`Q-S5B2-01`), because raw substring matching (`c in q_low`) falsely matched concept `"act"` inside the word `"exact"` on `Q-S5B2-03` and `Q-S5B2-11`, suppressing fallback while returning 1 passage each. Without partial-list backfill, `baseline_graph_1hop` returns **69/100** Top-10 slots (**31 missing slots**: `Q-S5B2-02` returns 6; `Q-S5B2-03`, `08`, `11` return 1 each), whereas all other five systems return `100/100` slots.
- **Pool completeness:** Across all 10 queries, the six systems produce **244** unique Top-10 pairs plus **10** seed-only pairs = **254** pooled pairs (`0` unpooled Top-10 pairs; `100.0%` coverage).

### 10.5 Recorded CPU Latency Diagnostics and Separated Hypotheses

Multi-repetition CPU latency was profiled in Stage S5-B1.1 (`retrieval_timing_report.json`) across **12 pre-revision queries** $\times$ **5 warm repetitions** on CPU; Stage S5-B2.1 recorded single-pass component timing for `hybrid_rrf_e2e` across the 10 active queries (`s5b2_1_frozen_ranked_results.json`).

**Cold-Start Initialization (S5-B1.1):** `dense_model_load_ms` = `7,630.455 ms`; `corpus_scoped_graph_build_ms` = `2,458.478 ms`; `bm25_index_build_ms` = `407.279 ms`; `corpus_load_ms` = `400.246 ms`; `dense_embedding_cache_load_ms` = `21.353 ms`.

**Per-Query Latency Distributions (S5-B1.1, 12 Queries $\times$ 5 Warm Repetitions, CPU):**

| System | First-Query Mean (ms) | First-Query Max (ms) | Warm Mean (ms) | Warm Median (ms) | Warm Std (ms) | Warm Min / Max (ms) | Warm P95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bm25` | 4.798 | 6.383 | 4.344 | 4.353 | 0.888 | 2.445 / 6.230 | 5.979 |
| `dense_snowflake_arctic_768d` | 164.950 | 361.618 | 148.281 | 142.261 | 17.325 | 125.764 / 205.963 | 178.982 |
| `hybrid_rrf_e2e` | 156.402 | 196.444 | 153.233 | 149.064 | 15.487 | 132.627 / 194.791 | 183.876 |
| `baseline_graph_1hop` | 21.953 | 61.523 | 20.077 | 8.261 | 20.864 | 4.439 / 70.009 | 60.184 |
| `repaired_graph_1hop_ablation` | 2.561 | 5.564 | 2.317 | 1.530 | 2.127 | 0.132 / 5.576 | 5.312 |
| `repaired_graph_2hop_full` | 2.452 | 5.240 | 2.188 | 1.673 | 1.937 | 0.130 / 5.007 | 4.933 |

In S5-B2.1 single-pass `hybrid_rrf_e2e` profiling (10 active queries), `dense_ms` accounted for **95.4%–97.8%** of total latency (`138.401–229.783 ms`), `bm25_ms` ranged from `3.601–9.819 ms`, and `fusion_ms` ranged from `0.112–0.161 ms` (`total_e2e_ms`: `143.674–239.714 ms`). In S5-B1.1, `repaired_graph_*` exhibited bimodal warm means (`0.149–0.656 ms` on 6 non-fallback queries vs. `3.009–5.019 ms` on 6 fallback queries), and `baseline_graph_1hop` ranged from `4.848 ms` (fallback) to `51.431–61.989 ms` (multi-anchor queries).

**Mechanistic Hypotheses (Explicitly Separated from Measurements):**
- **H1:** The ~0.13 ms lower overall warm mean of `repaired_graph_2hop_full` (`2.188 ms`) vs. `repaired_graph_1hop_ablation` (`2.317 ms`) is hypothesized to reflect CPU scheduling/cache variance on fallback queries masking sub-millisecond hop-2 traversal cost (`+0.008` to `+0.206 ms`).
- **H2:** Multi-anchor latency spikes (~51–62 ms) in `baseline_graph_1hop` are hypothesized to stem from per-anchor Kùzu Cypher queries versus in-memory Python adjacency traversal in `repaired_graph_*`.
- **H3:** Dense CPU latency (~138–230 ms) is hypothesized to be dominated by transformer forward-pass query encoding rather than the `(713, 768) @ (768,)` dot product.
- **H4:** Measured latencies at 713 passages / 146 edges do not establish scaling behavior on larger ($10^4$–$10^6$ passage) corpora.

---

## 11. Results (Placeholders — Blocked Pending Stage S5-C3 and Investigator-Authorized Stage S5-D1)

> **STRICT GOVERNANCE NOTICE:** No effectiveness values are populated in this pre-results manuscript. Every table and figure placeholder below maps 1-to-1 to the reproducible outputs generated by the Stage S5-D1 reporting pipeline (`s5_d1_evaluate.py` and `s5_d1_tables_figures.py`) **only** after real human evidence passes preflight and receives explicit investigator authorization.

### 11.1 Overall Descriptive Effectiveness Across Six Frozen Systems (Answerable Queries)

`[TODO-05 — BLOCKED ON S5-D1: Insert Table R1 (Per-System Descriptive Summary: Precision@5, Precision@10, Pooled Recall@5, Pooled Recall@10, MRR@10, nDCG@5, nDCG@10 at both strict grade == 2 and lenient grade >= 1 thresholds across verified answerable queries, explicitly noting pooled denominators and zero significance testing). Source: s5_d1_tables_figures.py -> system_effectiveness_summary.{md,tex,csv} (label tab:s5d1_system_summary).]`

### 11.2 Per-Query Descriptive Effectiveness Breakdown

`[TODO-06 — BLOCKED ON S5-D1: Insert Table R2 (Query-Level Metrics across all verified answerable queries by domain and hop type: SINGLE_HOP vs. same-document TWO_HOP). Source: s5_d1_evaluate.py -> query_level_metrics in REAL_D1_REPORT_JSON.]`

### 11.3 Fallback vs. Non-Fallback Stratified Graph Analysis & Short-List Accounting

`[TODO-07 — BLOCKED ON S5-D1: Insert Table R3 (Stratified Effectiveness for repaired_graph_1hop_ablation, repaired_graph_2hop_full, and baseline_graph_1hop partitioned into fallback vs. non-fallback queries alongside bm25, combined with short-list slot accounting). Source: s5_d1_tables_figures.py -> fallback_and_shortlist_accounting.{md,tex,csv} (label tab:s5d1_fallback_shortlist).]`

### 11.4 One-Hop vs. Two-Hop Heterogeneous Graph Comparison

`[TODO-08 — BLOCKED ON S5-D1: Insert Table R4 (Descriptive delta in Precision@k, Pooled Recall@k, MRR@10, and nDCG@k between repaired_graph_1hop_ablation and repaired_graph_2hop_full on the 5 AI/ML queries reaching hop depth 2: Q-S5B2-04 through Q-S5B2-08, distinguishing answerable queries from Q-S5B2-08 negative-control status). Source: s5_d1_tables_figures.py -> one_hop_vs_two_hop_comparison.{md,tex,csv} (label tab:s5d1_hop_comparison).]`

### 11.5 Negative-Control Behavior and Reclassification Accounting

`[TODO-09 — BLOCKED ON S5-D1: Insert Table R5 (Negative-Control Diagnostics for Q-S5B2-03, Q-S5B2-08, and Q-S5B2-11: verified human classification, returned passage counts, fallback flags, max observed gold grade, and any reclassification effect on answerable denominators). Source: s5_d1_evaluate.py -> negative_control_behavior in REAL_D1_REPORT_JSON.]`

### 11.6 Short-List Accounting Sensitivity (`baseline_graph_1hop`)

`[TODO-10 — BLOCKED ON S5-D1: Insert short-list ceiling sensitivity commentary detailing returned slots vs. 10-slot cap (69/100 slots) and fixed-denominator Precision@5/10 ceilings on Q-S5B2-02 and negative controls. Source: s5_d1_tables_figures.py -> fallback_and_shortlist_accounting.{md,tex,csv} + short_list_accounting in REAL_D1_REPORT_JSON.]`

### 11.7 Planned Figures

`[TODO-11 — BLOCKED ON S5-D1: Embed real post-S5-D1 SVG figures generated by s5_d1_tables_figures.py (NEVER SYNTHETIC-prefixed/watermarked figures): (a) Figure F1 — Per-system descriptive effectiveness profile (fig1_system_effectiveness.svg); (b) Figure F2 — Fallback vs. non-fallback graph effectiveness stratification (fig2_fallback_vs_nonfallback.svg). Source: s5_d1_tables_figures.py real-run SVG outputs.]`

---

## 12. Discussion (Skeleton)

### 12.1 Verified Methodological Takeaways (Available Pre-Results)

Even prior to gold-label effectiveness scoring, three verified methodological insights emerge from the frozen pilot:
1. **Unstratified graph evaluation obscures fallback mechanics:** Because `repaired_graph_*` falls back to `bm25` on 40.0% of active queries, unstratified aggregate metrics blend graph traversal with lexical retrieval. Stratified reporting (`fallback` vs. `non-fallback`) is mandatory for transparent interpretation.
2. **Naive substring entity linking introduces silent structural failure:** Raw substring matching (`"act"` inside `"exact"`) suppresses fallback while starving result lists (`baseline_graph_1hop`: 31/100 missing slots), reinforcing classical KG-IR warnings (`dietz2018utilizing`) and motivating token-boundary or semantic entity linking in future system versions.
3. **Evidence-necessity auditing prevents premature multi-hop claims:** Auditing passage necessity (`min2019compositional`) revealed that putative cross-document queries were answerable from single passages, preventing unsupported cross-document claims.

### 12.2 Blocked Effectiveness Discussion Placeholders

- `[TODO-12 — BLOCKED ON S5-D1: Discuss RQ1 descriptive effectiveness patterns across bm25, dense_snowflake_arctic_768d, hybrid_rrf_e2e, and graph systems on verified answerable queries, maintaining strict pilot-scope framing (no significance or superiority claims). Source: s5_d1_evaluate.py report JSON.]`
- `[TODO-13 — BLOCKED ON S5-D1: Discuss RQ2 interaction between fallback/substring mechanics and observed descriptive effectiveness, including fixed-denominator Precision@k effects on baseline_graph_1hop. Source: s5_d1_evaluate.py fallback & short-list tables.]`
- `[TODO-14 — BLOCKED ON S5-D1: Discuss RQ3 relevance impact of 2-hop traversal on the 5 AI/ML queries—specifically whether the +5/−5 passage replacement on Q-S5B2-05 and rank shifts on Q-S5B2-04/06/07/08 introduced relevant context or topical drift. Source: s5_d1_evaluate.py 1-hop vs. 2-hop comparison.]`

---

## 13. Threats to Validity

We organize methodological threats across internal, construct, conclusion, and external validity (`E03_THREATS_TO_VALIDITY.md`):

### 13.1 Internal and Annotation Validity
1. **Non-independent initial annotation stream (`REV_B` 254/254 AI disclosure):** Reviewer B's initial submission carried an AI-assistance disclosure on all 254 pairs, precluding its use as independent human ground truth (`faggioli2023perspectives`). *Mitigation:* S5-C3 enforces independent human annotation/confirmation and refuses gold export without verified human provenance.
2. **Unadjudicated disagreements (`51/254`) and workbook source-text discrepancies (`5/254`):** In S5-C2, 51 disagreements occurred across the 7 answerable queries (28.5% of answerable pairs), alongside 5 minor workbook source-text diffs. *Mitigation:* All disagreements must be adjudicated by humans against verified frozen pool text before S5-D1 execution.
3. **Negative-control ambiguity (`Q-S5B2-03`, `Q-S5B2-08`, `Q-S5B2-11`):** Automated corpus searches and 0-grade pooled labels do not alone establish corpus-wide unanswerability, and `Q-S5B2-08`/`11` contain unsupported/synthetic factual premises. *Mitigation:* Independent corpus-wide human verification and explicit stratification handling for any reclassified negative control in S5-D1 preflight.

### 13.2 Construct and Measurement Validity
4. **Short retrieval lists (`baseline_graph_1hop`: `69/100` slots):** Under fixed-denominator `Precision@5` and `Precision@10`, truncated lists face structural score ceilings (e.g., `Q-S5B2-02` cannot exceed `P@10 = 0.6000`). *Mitigation:* Report returned-slot counts and short-list accounting alongside every Top-K metric.
5. **Incomplete judgment coverage beyond Top-10:** While depth-10 pooling achieves 100.0% Top-5/Top-10 coverage for the six frozen systems, 682–700 corpus passages per query remain unpooled. *Mitigation:* Restrict all metrics to $k \le 10$ on the six frozen systems and raise a hard error on any unjudged Top-10 passage.
6. **Pool-relative Recall and nDCG denominators:** `Recall@k` and `nDCG@k` normalize against relevant passages found in the 254-pair judged pool rather than an exhaustive 713-passage ground truth. *Mitigation:* Explicitly label Recall and nDCG as pool-relative.
7. **Pooling bias for future/external systems:** Any seventh retrieval system evaluated later against the frozen 254-pair qrels would be disadvantaged by unjudged novel passages (`zobel1998reliable`, `buckley2004retrieval`). *Mitigation:* Restrict v2.1 qrels strictly to the six contributing frozen systems.

### 13.3 Conclusion and External Validity
8. **Small exploratory sample size (`N = 10` active; `7` answerable):** A single query shift changes macro-averaged metrics by up to 14.3 percentage points (`1/7`), precluding formal significance testing (`sakai2016statistical`). *Mitigation:* Descriptive pilot reporting only; permanent prohibition on significance or superiority claims.
9. **Absence of validated cross-document multi-hop queries (`0` validated):** Only 2 same-document `TWO_HOP` queries exist (`Q-S5B2-02`, `Q-S5B2-10`), and `repaired_graph_*` falls back on `Q-S5B2-02` and reaches only hop-1 on `Q-S5B2-10`. *Mitigation:* Permanent prohibition on cross-document multi-hop claims.
10. **Limited corpus, domain, and hardware generalizability:** The frozen corpus covers 713 passages across 3 CS subfields with documented ingestion defects (21 truncated stubs, 1 constructed card, sparse OSTEP pages) and 146 AI/ML-concentrated heterogeneous edges; warm multi-repetition latency reflects CPU profiling on 12 pre-revision queries. *Mitigation:* Scope all findings strictly to the 713-passage CPU pilot and defer large-scale/GPU benchmarking to v3.

---

## 14. Limitations

Table 2 summarizes the nine formally tracked pilot limitations (`S5D0_LIMITATIONS_REGISTER.md`):

| ID | Category | Summary of Limitation | Current Status | Claim Boundary |
|---|---|---|---|---|
| **LIM-01** | Sample Size | 10 active queries (7 answerable + 3 provisional negatives across 3 CS domains; 2 held) | Permanent for v2.1 | Descriptive pilot only; no significance or superiority claims. |
| **LIM-02** | Multi-Hop Scope | 0 validated cross-document queries (5 `SINGLE_HOP`, 2 same-doc `TWO_HOP`) | Permanent for v2.1 | No cross-document multi-hop claims permitted. |
| **LIM-03** | Corpus Provenance | 21 truncated textbook stubs ($\le 305$ chars), 1 constructed pilot card, sparse OSTEP extraction, 16 unverified seed chunks | Frozen unaltered | Forced HOLD on `Q-S5A-09`/`12`; corpus repair requires a new versioned manifest. |
| **LIM-04** | Negative Controls | `Q-S5B2-03`, `08`, `11` pending independent human corpus-wide verification | Blocking (S5-C3) | Cannot be reported as verified unanswerable until S5-C3 completes. |
| **LIM-05** | Annotation Independence | Initial `REV_B` submission carries AI-assistance disclosure on `254/254` pairs | Blocking (S5-C3) | Pre-adjudication agreement is not validated inter-human reliability. |
| **LIM-06** | Adjudication | 51 initial disagreements + 5 minor workbook source-text discrepancies | Blocking (S5-C3) | Effectiveness scoring strictly blocked until human adjudication completes. |
| **LIM-07** | Graph Mechanics | 40% BM25 fallback in `repaired_graph_*`; `"act"`-in-`"exact"` false positives + 31/100 missing slots in `baseline_graph_1hop` | Frozen for v2.1 | Mandatory fallback stratification and slot-shortfall disclosure. |
| **LIM-08** | Latency Scope | S5-B1.1 5-rep warm timing covers 12 pre-revision queries on CPU (713 passages); S5-B2.1 single-pass timing covers `hybrid_rrf_e2e` only | Documented | No extrapolation to large-corpus or GPU/ANN latency. |
| **LIM-09** | Governance | Historical Git packfiles (`788976d`, `78d3f2f`, S4 commits) retain earlier metadata/excerpts | Mitigated in HEAD | Human annotators/adjudicators must work exclusively on isolated local workbooks outside Git access. |

`[TODO-15 — BLOCKED ON S5-C3 / S5-D1: Update status of LIM-04, LIM-05, and LIM-06 from "Blocking" to "Resolved in S5-C3" with exact human verification/adjudication provenance once S5-C3 and S5-D1 complete. Permanent limitations LIM-01, LIM-02, LIM-03, LIM-07, LIM-08, and LIM-09 remain active.]`

---

## 15. Conclusions (Skeleton)

This pilot demonstrates the value of enforcing cryptographic artifact freezing, corpus-scope information-access parity, passage-necessity auditing, complete depth-10 pooling, and strict human-provenance governance prior to computing retrieval effectiveness scores. Relevance-agnostic diagnostics alone surfaced critical operational constraints—including 40.0% domain-concentrated BM25 fallback in the 146-edge heterogeneous graph, raw substring anchor false positives and 31/100 missing slots in the Kùzu 1-hop graph, and domain-bounded 2-hop rank perturbation on 5/10 AI/ML queries—that must inform any fair interpretation of cross-paradigm retrieval behavior.

`[TODO-16 — BLOCKED ON S5-C3 / S5-D1: Insert concise post-adjudication descriptive conclusions summarizing what the verified human gold labels revealed across RQ1–RQ3, strictly preserving all permanent pilot boundaries (no significance claims, no superiority claims, no cross-document gains) and outlining concrete v3 future work (larger multi-domain query set, repaired corpus ingestion, token-boundary/semantic entity linking, and controlled GPU/ANN latency profiling). Source: S5-D1 evaluation report JSON + human investigator review.]`

---

## 16. Reproducibility and Ethical/Provenance Disclosures

### 16.1 Cryptographic Artifact Fingerprints

All frozen experimental artifacts are anchored by SHA-256 digests verified against `s5d0_preservation_manifest.json`:
- `s5a_eval_corpus_v1` (`corpus_sha256`): `6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7` (`713` passages, `53` documents)
- Dense embedding cache `(713, 768)` `float32`: `ffb94053fa66471d14758771253c8c5404bb4adf2e7b14d2c9e4c30b2cbd4ee2` (`Snowflake/snowflake-arctic-embed-m-v1.5`, rev `f22f7b88939ba6d01306a445d48729fb5a2ff3f3`)
- Blinded 254-pair JSON pool (`retrieval_query_pool_blinded.json`): `2d13454655dda965304ac4aabddbeef5e39b77bc6927393bebfdaa94235fb037`
- Blinded 254-pair CSV pool (`retrieval_query_candidate_pool_blinded.csv`): `4c9cb0e58f9f6d32c59eb12804f032be32a6a52c1eeb75055fb5148600f9acd7`
- Frozen six-system rankings (`s5b2_1_frozen_ranked_results.json`): `e20a9f64272c1afa42d62ea7474cb3d9db8e9472c5cf97b639f680e4942eba86`
- S5-D0 technical diagnostics (`s5d0_technical_diagnostics.json`): `f502e0356e39239198a3c792d012b9c51d62b32a7de678900014d85fcd8a1c48`

Isolated fresh-clone verification in `/tmp` (`fresh_environment_reproducibility_report.json`) regenerated 5/5 blinded package and workbook files byte-identically and passed 34/34 applicable tests (310/310 in the full local research suite).

`[TODO-17 — BLOCKED ON S5-C3 / S5-D1: Record SHA-256 hashes of the finalized human gold-label JSON, finalized negative-control verification JSON, investigator authorization artifact, and final S5-D1 evaluation report JSON (never commit private passage text or private reviewer workbooks to Git). Source: S5-C3 exports + S5-D1 preflight/evaluation logs.]`

### 16.2 Ethical, Copyright, Privacy, and AI-Provenance Disclosures

- **Copyright & source-text hygiene:** Source textbook and paper excerpts remain stored exclusively in local Git-ignored paths and are never redistributed in public repository commits or manuscript appendices.
- **Historical Git packfile disclosure (`LIM-09`):** Earlier repository commits (`788976d`, `78d3f2f`, and S4 commits `8ff96f2`, `0f78955`, `2147ece`, `abad203`, `e3af789`) retain earlier admin metadata/excerpts in Git packfile history pending repository-owner decision on history scrubbing or private visibility. Accordingly, all human annotators and adjudicators work strictly on isolated local workbooks outside Git access.
- **AI-assistance provenance disclosure:** Initial Reviewer B annotations disclosed AI-assisted proposals on all 254/254 pairs (`s5c2_audit_summary.json`). In compliance with methodological transparency (`faggioli2023perspectives`), those labels are explicitly quarantined from validated human ground truth, and no AI-generated judgments are permitted in finalized gold labels.

---

## 17. Verified Bibliography

All 26 references below correspond 1-to-1 with `references.bib` (audited in `BIBLIOGRAPHY_AUDIT.md`; 0 unverified or invented citations):

1. `[bruch2023analysis]` Bruch, S., Gai, S., & Ingber, A. (2023). An Analysis of Fusion Functions for Hybrid Retrieval. *ACM Transactions on Information Systems (TOIS)*, 42(1), Article 20. DOI: `10.1145/3596512`.
2. `[buckley2004retrieval]` Buckley, C., & Voorhees, E. M. (2004). Retrieval Evaluation with Incomplete Information. *Proceedings of SIGIR '04*, pp. 25–32. DOI: `10.1145/1008992.1009000`.
3. `[cohen1968weighted]` Cohen, J. (1968). Weighted kappa: Nominal scale agreement provision for scaled disagreement or partial credit. *Psychological Bulletin*, 70(4), 213–220. DOI: `10.1037/h0026256`.
4. `[cormack2009reciprocal]` Cormack, G. V., Clarke, C. L. A., & Büttcher, S. (2009). Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods. *Proceedings of SIGIR '09*, pp. 758–759. DOI: `10.1145/1571941.1572114`.
5. `[dietz2018utilizing]` Dietz, L., Kotov, A., & Meij, E. (2018). Utilizing Knowledge Graphs for Text-Centric Information Retrieval. *Proceedings of SIGIR '18*, pp. 1387–1390. DOI: `10.1145/3209978.3210187`.
6. `[edge2024local]` Edge, D., Trinh, H., Cheng, N., Bradley, J., Chao, A., Mody, A., Truitt, S., Metropolitansky, D., Ness, R. O., & Larson, J. (2024). From Local to Global: A Graph RAG Approach to Query-Focused Summarization. *arXiv preprint* `arXiv:2404.16130`.
7. `[faggioli2023perspectives]` Faggioli, G., Dietz, L., Clarke, C. L. A., Demartini, G., Hagen, M., Hauff, C., Kando, N., Kanoulas, E., Potthast, M., Stein, B., & Wachsmuth, H. (2023). Perspectives on Large Language Models for Relevance Judgment. *Proceedings of ICTIR '23*, pp. 39–50. DOI: `10.1145/3578337.3605136`.
8. `[gutierrez2024hipporag]` Jiménez Gutiérrez, B., Shu, Y., Gu, Y., Yasunaga, M., & Su, Y. (2024). HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models. *Advances in Neural Information Processing Systems (NeurIPS 2024)*. `arXiv:2405.14831`.
9. `[ho2020constructing]` Ho, X., Nguyen, A.-K. D., Sugawara, S., & Aizawa, A. (2020). Constructing A Multi-hop QA Dataset for Comprehensive Evaluation of Reasoning Steps. *Proceedings of COLING 2020*, pp. 6609–6625. DOI: `10.18653/v1/2020.coling-main.580`.
10. `[jarvelin2002cumulated]` Järvelin, K., & Kekäläinen, J. (2002). Cumulated Gain-Based Evaluation of IR Techniques. *ACM Transactions on Information Systems (TOIS)*, 20(4), 422–446. DOI: `10.1145/582415.582418`.
11. `[karpukhin2020dense]` Karpukhin, V., Oğuz, B., Min, S., Lewis, P., Wu, L., Edunov, S., Chen, D., & Yih, W.-t. (2020). Dense Passage Retrieval for Open-Domain Question Answering. *Proceedings of EMNLP 2020*, pp. 6769–6781. DOI: `10.18653/v1/2020.emnlp-main.550`.
12. `[luan2021sparse]` Luan, Y., Eisenstein, J., Toutanova, K., & Collins, M. (2021). Sparse, Dense, and Attentional Representations for Text Retrieval. *Transactions of the Association for Computational Linguistics (TACL)*, 9, 329–345. DOI: `10.1162/tacl_a_00369`.
13. `[merrick2024arctic]` Merrick, L., Xu, D., Nuti, G., & Campos, D. (2024). Arctic-Embed: Scalable, Efficient, and Accurate Text Embedding Models. *arXiv preprint* `arXiv:2405.05374`.
14. `[min2019compositional]` Min, S., Wallace, E., Singh, S., Gardner, M., Hajishirzi, H., & Zettlemoyer, L. (2019). Compositional Questions Do Not Necessitate Multi-hop Reasoning. *Proceedings of ACL 2019*, pp. 4249–4257. DOI: `10.18653/v1/P19-1416`.
15. `[reimers2019sentence]` Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *Proceedings of EMNLP-IJCNLP 2019*, pp. 3982–3992. DOI: `10.18653/v1/D19-1410`.
16. `[robertson1994some]` Robertson, S. E., & Walker, S. (1994). Some Simple Effective Approximations to the 2-Poisson Model for Probabilistic Weighted Retrieval. *Proceedings of SIGIR '94*, pp. 345–354. DOI: `10.1007/978-1-4471-2099-5_24`.
17. `[robertson2009probabilistic]` Robertson, S., & Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond. *Foundations and Trends in Information Retrieval*, 3(4), 333–389. DOI: `10.1561/1500000019`.
18. `[sakai2016statistical]` Sakai, T. (2016). Statistical Significance, Power, and Sample Sizes: A Systematic Review of SIGIR and TOIS, 2006–2015. *Proceedings of SIGIR '16*, pp. 5–14. DOI: `10.1145/2911451.2911492`.
19. `[thakur2021beir]` Thakur, N., Reimers, N., Rücklé, A., Srivastava, A., & Gurevych, I. (2021). BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models. *NeurIPS 2021 Datasets and Benchmarks Track*. `arXiv:2104.08663`.
20. `[trivedi2022musique]` Trivedi, H., Balasubramanian, N., Khot, T., & Sabharwal, A. (2022). MuSiQue: Multihop Questions via Single-hop Question Composition. *Transactions of the Association for Computational Linguistics (TACL)*, 10, 539–554. DOI: `10.1162/tacl_a_00475`.
21. `[trotman2014improvements]` Trotman, A., Puurula, A., & Burgess, B. (2014). Improvements to BM25 and Language Models Examined. *Proceedings of ADCS '14*, pp. 58–65. DOI: `10.1145/2682862.2682863`.
22. `[voorhees2000variations]` Voorhees, E. M. (2000). Variations in Relevance Judgments and the Measurement of Retrieval Effectiveness. *Information Processing & Management*, 36(5), 697–716. DOI: `10.1016/S0306-4573(00)00010-8`.
23. `[xiong2017explicit]` Xiong, C., Power, R., & Callan, J. (2017). Explicit Semantic Ranking for Academic Search via Knowledge Graph Embedding. *Proceedings of WWW '17*, pp. 1271–1279. DOI: `10.1145/3038912.3052558`.
24. `[yang2018hotpotqa]` Yang, Z., Qi, P., Zhang, S., Bengio, Y., Cohen, W. W., Salakhutdinov, R., & Manning, C. D. (2018). HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering. *Proceedings of EMNLP 2018*, pp. 2369–2380. DOI: `10.18653/v1/D18-1259`.
25. `[yasunaga2021qagnn]` Yasunaga, M., Ren, H., Bosselut, A., Liang, P., & Leskovec, J. (2021). QA-GNN: Reasoning with Language Models and Knowledge Graphs for Question Answering. *Proceedings of NAACL-HLT 2021*, pp. 535–546. DOI: `10.18653/v1/2021.naacl-main.45`.
26. `[zobel1998reliable]` Zobel, J. (1998). How Reliable Are the Results of Large-Scale Information Retrieval Experiments? *Proceedings of SIGIR '98*, pp. 307–314. DOI: `10.1145/290941.291014`.
