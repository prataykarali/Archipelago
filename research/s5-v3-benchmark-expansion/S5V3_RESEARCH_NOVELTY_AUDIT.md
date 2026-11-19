# S5-v3 Module F — SIGIR-Level Research Contribution & Novelty Audit

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-benchmark-expansion`  
**Audit Standard:** SIGIR / ACM TOIS / ICTIR methodological & novelty bar (Evaluation, Reproducibility, Resource, and Retrieval tracks)  
**Verified Reference Base:** 26 verified entries in [E03_VERIFIED_REFERENCES.bib](file:///home/pratay-karali/Desktop/archipelago/research/s5-e0-pre-results-paper-prep/E03_VERIFIED_REFERENCES.bib) plus 2 newly verified references (`Nogueira & Cho, 2019`, arXiv:1901.04085; `Smucker, Allan, & Carterette, 2007`, CIKM '07, DOI: 10.1145/1321440.1321528). Zero unverified citations are used.

> [!IMPORTANT]
> **Epistemic & Non-Claim Boundary:** This audit does **not** manufacture novelty, claim system superiority, or predict/claim conference acceptance. Zero validated human gold relevance labels currently exist for either the frozen S5-v2.1 pilot (blocked at S5-C2/S5-C3 pending independent human confirmation and adjudication) or S5-v3 (all proposed queries and pools are pre-human-verification). Every assessment below separates **verified current evidence** from **missing human evidence**.

---

## 1. Executive Summary & Single Primary Recommendation

| Candidate Contribution | Current Evidence Strength | Missing Human Evidence | Incremental-Change Risk | Verdict |
|---|---|---|---|---|
| **A. Improved graph-anchor & fallback robustness** | Software-verified engineering controls only (no relevance evidence) | Full dual-human relevance labels across anchor regimes | **HIGH** — standard IR hygiene / bug fixes | **Secondary / Engineering Control Only** |
| **B. Reliable, provenance-aware multi-passage retrieval evaluation** | **STRONGEST** — verified across S5-B1/B2.1/C2/D0/v3 (parity audits, 462 unscoped edges caught, 25→254 pool repair, necessity refutations, AI-label governance gates) | Human-adjudicated S5-v3 gold labels + empirical sensitivity of rankings to parity/provenance/adjudication controls | **LOW–MODERATE** (Evaluation / Reproducibility / Resource framing) | **RECOMMENDED PRIMARY CONTRIBUTION** |
| **C. Effects of graph coverage & traversal depth on retrieval quality and cost** | Relevance-agnostic diagnostics only (hop depth, path counts, fallback rates, CPU latency) | Human relevance labels across sparse/rich graph coverage & 1-hop vs 2-hop vs reranker controls | **MODERATE–HIGH** (until paired with human quality data & strong neural controls) | **Secondary Empirical Study (Inside B)** |
| **D. Domain-specific IR benchmark construction & audit methodology** | Partial — deterministic OA pipeline & necessity audit exist, but local corpus is constrained to **4 OA docs** (OS/DB/Networks deferred) | Human verification of all queries, human NC audits, dual human grading, and multi-domain OA corpus expansion | **MODERATE** (too narrow at 4 docs to stand alone as a SIGIR Resource benchmark) | **Supporting Methodology (Subsumed by B)** |

### Recommended Primary Research Contribution: **Candidate B — Reliable, Provenance-Aware Multi-Passage Retrieval Evaluation**

**Why B (and only B) is supported strictly by current evidence:**
1. **Verified methodological findings already exist:** Archipelago's strongest non-fabricated empirical findings are *evaluation-validity diagnostics*: catching **462/1,988 (23.24%)** unscoped/external Kùzu edges that silently broke information-access parity; exposing **51/764** index/invalid-page corpus defects and **21** truncated textbook stubs ($\le 305$ chars); showing that an initial 25-pair seed pool covered only **7.0%–14.0%** of Top-10 outputs before depth-10 union pooling (`254` pairs, `100.0%` coverage); refuting `CROSS_DOCUMENT` labels on `Q-S5B2-06`/`07` via passage-necessity auditing (`0` validated cross-document queries in v2.1); and enforcing programmatic pre-scoring release gates that halt effectiveness reporting when AI-assisted labels (`254/254` Reviewer B pairs), `51` disagreements, or unverified negative controls remain open.
2. **Direct alignment with active SIGIR/ICTIR evaluation challenges:** Modern GraphRAG and hybrid retrieval evaluations routinely conflate graph leakage, single-passage shortcuts (`min2019compositional`), incomplete-pool zero-imputation (`buckley2004retrieval`), underpowered topic sets (`sakai2016statistical`), and unvalidated LLM-assisted judgments (`faggioli2023perspectives`). Unifying cryptographic parity enforcement, provenance-tier separation, necessity auditing, and hard governance gates into one executable, reproducible evaluation protocol directly addresses these documented community failure modes.
3. **Honest readiness boundary:** Recommending Candidate B does **not** mean a paper is ready to submit today. Before any external submission, Candidate B still requires (a) completed independent human annotation and adjudication on S5-v3 (or completed S5-C3/S5-D1 plus S5-v3), (b) empirical quantification of *how much* ranking conclusions change when each validity control (parity scoping, pool completeness, necessity filtering, AI-label gating) is toggled, and (c) multi-domain OA corpus expansion beyond the 4 currently available local documents.

---

## 2. Detailed SIGIR-Level Assessment of Candidate Contributions

### Candidate A — Improved Graph-Anchor and Fallback Robustness

- **Research Hypothesis:** Replacing raw substring concept matching (`c in query.lower()`) and unbackfilled graph retrieval with token-boundary-aware anchor matching, normalized concept aliases, corpus-grounded concept-to-passage indexing, deterministic zero-anchor BM25 fallback, partial-list lexical backfill, and coverage-aware routing eliminates false-positive anchor triggers and Top-K slot shortfalls without degrading retrieval effectiveness relative to lexical, dense, and hybrid controls.
- **Nearest Known Prior Work (Verified References Only):**
  - *Dietz, Kotov, & Meij (2018)* (`dietz2018utilizing`, SIGIR '18): Explicitly identified query-to-KG entity-linking errors and incomplete graph coverage as the two primary bottlenecks in text-centric KG-IR.
  - *Xiong, Power, & Callan (2017)* (`xiong2017explicit`, WWW '17): Explicit Semantic Ranking projecting queries/documents into KG concepts via entity linking and KG embeddings.
  - *Jiménez Gutiérrez et al. (2024)* (`gutierrez2024hipporag`, NeurIPS 2024): HippoRAG, using dense-to-KG node linking and Personalized PageRank rather than raw substring lookup.
  - *Cormack, Clarke, & Büttcher (2009)* (`cormack2009reciprocal`, SIGIR '09) and *Bruch, Gai, & Ingber (2023)* (`bruch2023analysis`, ACM TOIS): Rank and score fusion for combining complementary retrieval signals (the principled alternative to ad-hoc lexical fallback/backfill).
- **Distinguishing Technical Contribution:** Explicit per-rank provenance attribution (`graph` vs. `backfill` vs. `fallback`) coupled with deterministic coverage-aware routing that exposes fallback frequency as a first-class diagnostic variable rather than hiding lexical rescues inside aggregate graph scores.
- **Required Ablations:**
  1. Substring matching vs. token-boundary matching (isolating false-positive elimination).
  2. Without vs. with alias/acronym/hyphen normalization.
  3. Zero-anchor fallback ON vs. OFF; partial-list backfill ON vs. OFF (measuring short-list penalty vs. lexical dilution).
  4. Coverage-aware routing vs. fixed RRF (`graph + bm25`, `graph + dense`, `bm25 + dense`) and cross-encoder reranking (`Nogueira & Cho, 2019`, arXiv:1901.04085).
- **Supporting Evidence Currently Available:**
  - Verified defect diagnosis in v2.1 (`S5D0_TECHNICAL_DIAGNOSTICS.md`): `baseline_graph_1hop` triggered `"act"` inside `"exact"` on `Q03` and `Q11`, suffered `31/100` missing Top-10 slots, and `repaired_graph_*` fell back to BM25 on `4/10 (40.0%)` queries.
  - Software-verified unit tests and relevance-agnostic diagnostics in S5-v3 Module D (`S5V3_RETRIEVAL_ABLATION_PLAN.md`, `s5v3_retrieval_diagnostics.json` — synced in Section 3 below).
- **Missing Human Evidence:** **All relevance evidence.** Zero human-judged `nDCG@5/10`, `Recall@5/10`, or `MRR@10` data exists to test whether token-boundary anchoring, alias normalization, backfill, or coverage-aware routing actually improve retrieval quality or merely converge toward BM25.
- **Risk of Being Considered an Incremental Implementation Change:** **HIGH.** Token-boundary regex matching, case/plural/alias normalization, and lexical backfill are standard IR engineering fixes rather than algorithmic breakthroughs. Without a generalizable theoretical model of coverage-aware routing *and* strong human-evaluated gains over modern hybrid + cross-encoder baselines across multiple collections, SIGIR main-track reviewers would almost certainly classify Candidate A as incremental bug fixing.

---

### Candidate B — Reliable, Provenance-Aware Multi-Passage Retrieval Evaluation *(Recommended Primary)*

- **Research Hypothesis:** Multi-passage and graph-assisted retrieval evaluations frequently suffer from silent validity failures—specifically cross-corpus graph leakage, unverified passage/page provenance, single-passage shortcuts mislabeled as multi-hop, incomplete pooling with silent zero-imputation, and unvalidated AI-assisted relevance labels—and enforcing cryptographic parity checks, passage-necessity audits, complete depth-$k$ blinded pooling, and programmatic pre-scoring governance gates prevents invalid comparative conclusions.
- **Nearest Known Prior Work (Verified References Only):**
  - *Zobel (1998)* (`zobel1998reliable`, SIGIR '98) and *Buckley & Voorhees (2004)* (`buckley2004retrieval`, SIGIR '04): Pooling reliability, unpooled-system bias, and metric degradation when unjudged passages are silently treated as non-relevant.
  - *Voorhees (2000)* (`voorhees2000variations`, IP&M) and *Cohen (1968)* (`cohen1968weighted`, Psych. Bull.): Assessor disagreement stability and ordinal weighted kappa ($\kappa_w$).
  - *Järvelin & Kekäläinen (2002)* (`jarvelin2002cumulated`, ACM TOIS): Graded relevance evaluation (`nDCG`).
  - *Sakai (2016)* (`sakai2016statistical`, SIGIR '16) and *Smucker, Allan, & Carterette (2007)* (`CIKM '07`, DOI: `10.1145/1321440.1321528`): Statistical power, topic sample sizes, and paired randomization tests in IR.
  - *Min et al. (2019)* (`min2019compositional`, ACL '19) and *Trivedi et al. (2022)* (`trivedi2022musique`, TACL): Single-passage shortcut auditing and disconnected-reasoning / unanswerable-control discipline.
  - *Faggioli et al. (2023)* (`faggioli2023perspectives`, ICTIR '23): Validity risks, circularity, and anchoring bias of LLM-assisted relevance judgments without independent human validation.
- **Distinguishing Technical Contribution:** Integrates four usually siloed IR validity controls into a single, **executable, fail-closed evaluation pipeline** specifically tailored to heterogeneous graph + hybrid passage retrieval:
  1. *Graph-aware information-access parity* (auditing and excluding external/unscoped KG edges and orphan concepts against a SHA-256-locked eligible passage snapshot).
  2. *Tiered corpus & page-level provenance separation* (isolating PDF-extracted, markdown-OA, hand-authored, and truncated-stub passages so synthetic/truncated artifacts cannot silently corrupt benchmark queries).
  3. *Pre-annotation passage-necessity and shortcut auditing* (explicitly auditing minimum required evidence sets and negative-control corpus absence before human grading).
  4. *Fail-closed human-governance release gate* (`evaluate_gold_labels_readonly.py` + run manifest contracts that programmatically refuse to compute or publish effectiveness scores when AI-assisted labels lack independent human confirmation, disagreements remain unadjudicated, negative controls are unverified, or any Top-$k$ passage is unjudged).
- **Required Ablations:**
  1. *Parity ablation:* Unscoped Kùzu graph (1,988 edges) vs. corpus-scoped graph (1,526 edges) — measuring rank/metric distortion caused by external-edge leakage.
  2. *Pooling ablation:* Seed-only pool (`7%–14%` coverage) vs. depth-5 vs. depth-10 union pool (`100%` coverage) — quantifying recall/nDCG distortion and system rank flips under incomplete pools (`zobel1998reliable`, `buckley2004retrieval`).
  3. *Governance / provenance ablation:* Pre-adjudication AI-assisted labels (`REV_B`) vs. independently confirmed & adjudicated human gold labels — quantifying rank-order sensitivity (`Voorhees, 2000`; `Faggioli et al., 2023`).
  4. *Necessity-stratification ablation:* Aggregate metrics vs. stratified single-passage, same-document multi-passage, cross-document, and verified negative-control reporting.
- **Supporting Evidence Currently Available:**
  - Verified end-to-end artifacts across S5-B1, S5-B2.1, S5-C2, S5-D0, and S5-v3: `19/19` frozen v2.1 artifacts cryptographically preserved; `462/1,988` unscoped graph edges audited and excluded; `51/764` corpus defects excluded; `25 → 254` pool coverage repair; `2/12` queries held and `2/10` cross-doc tags refuted; `254/254` AI-assisted label gate triggered; local-only blinded annotation workbench, A-C adjudication tooling, and negative-control verifier unit-tested; deterministic S5-v3 corpus/query/run manifest contracts implemented.
- **Missing Human Evidence:**
  - Completed independent human annotation and adjudication on S5-v3 (and/or S5-C3) so the pooling, parity, and AI-vs-human governance ablations above can be quantified with real relevance metrics rather than structural diagnostics alone.
  - Independent human verification of proposed queries, passage-necessity tags, and negative-control corpus absence.
- **Risk of Being Considered an Incremental Implementation Change:** **LOW–MODERATE** for SIGIR Evaluation / Reproducibility / Resource tracks *once backed by human-annotated empirical sensitivity ablations*. **HIGH** if submitted without human gold labels (in which case it is a methodology/position draft rather than an empirical evaluation paper).

---

### Candidate C — Effects of Graph Coverage and Traversal Depth on Retrieval Quality and Cost

- **Research Hypothesis:** Graph-assisted passage retrieval exhibits a regime boundary governed by query-to-graph anchor coverage and traversal depth (1-hop vs. 2-hop): in anchor-rich regimes, controlled 2-hop traversal can surface non-lexical related evidence at low CPU cost, whereas in anchor-sparse regimes, graph retrieval either degrades into noisy short lists or collapses into lexical fallback, making fallback-stratified reporting mandatory.
- **Nearest Known Prior Work (Verified References Only):**
  - *Dietz, Kotov, & Meij (2018)* (`dietz2018utilizing`, SIGIR '18): Graph incompleteness and entity-linking bottlenecks.
  - *Xiong, Power, & Callan (2017)* (`xiong2017explicit`, WWW '17), *Yasunaga et al. (2021)* (`yasunaga2021qagnn`, NAACL '21), *Edge et al. (2024)* (`edge2024local`, arXiv:2404.16130), *Jiménez Gutiérrez et al. (2024)* (`gutierrez2024hipporag`, NeurIPS 2024): Modern KG-IR and GraphRAG traversal mechanisms (explicit ranking, GNN message passing, Leiden community summaries, Personalized PageRank).
  - *Luan et al. (2021)* (`luan2021sparse`, TACL) and *Thakur et al. (2021)* (`thakur2021beir`, NeurIPS 2021): Zero-shot lexical vs. dense capacity tradeoffs.
- **Distinguishing Technical Contribution:** Exact behavioral and cost isolation of 1-hop vs. 2-hop typed symbolic traversal (`REQUIRES`, `PART_OF`, `USES`, `CONTRASTS_WITH`, `RELATED`, decay `0.5`, fanout caps) stratified explicitly by anchor-coverage regime (`rich` vs. `sparse`) and fallback vs. non-fallback queries, alongside dense and neural-reranker cost controls.
- **Required Ablations:**
  1. Graph coverage sweep (e.g., 25%, 50%, 75%, 100% of extracted edges/concepts) measuring anchor hit rate, fallback rate, latency, memory, and human-judged `nDCG@10`/`Recall@10`.
  2. Traversal depth sweep (0-hop anchor-only vs. 1-hop vs. 2-hop) with controlled decay and degree/fanout caps.
  3. Non-fallback-only vs. aggregate effectiveness comparison against `bm25`, `dense`, `hybrid_rrf`, and a cross-encoder reranker.
- **Supporting Evidence Currently Available:**
  - Relevance-agnostic S5-D0 diagnostics: `repaired_graph_2hop_full` expanded `45` hop-1 paths to `212` total paths (`167` hop-2), reaching depth 2 on `5/10` queries (all AI/ML), changing Top-10 rank order on `5/5` and set membership on `4/5` (up to 5 passages replaced on `Q05`), while `4/10` queries fell back to BM25 (inflating overall Jaccard with BM25 from `0.1333`/`0.1421` to `0.4800`/`0.4852`).
  - S5-v3 Module D timing (`perf_counter_ns`), peak memory (`tracemalloc`), and coverage diagnostics (synced in Section 3).
- **Missing Human Evidence:** **Critical.** We currently have *zero* evidence on whether 2-hop expansion or higher graph coverage improves, leaves unchanged, or *hurts* retrieval relevance (e.g., topic drift). Without human relevance labels across both anchor-sparse and anchor-rich queries, the "retrieval quality" half of Candidate C is completely unmeasured.
- **Risk of Being Considered an Incremental Implementation Change:** **MODERATE–HIGH.** Studying 1-hop vs. 2-hop heuristic graph expansion over a small symbolic graph without strong neural graph/reranker baselines (`HippoRAG` PPR, cross-encoders) risks being viewed as a narrow system-specific ablation unless embedded inside a broader, human-validated evaluation study (Candidate B).

---

### Candidate D — Domain-Specific IR Benchmark Construction and Audit Methodology

- **Research Hypothesis:** Constructing a license-clean, page-provenance-locked academic CS/ML retrieval benchmark with programmatic passage-necessity checks, shortcut auditing, and independently verifiable negative controls yields a higher-validity evaluation resource than unverified synthetic or scraped multi-hop benchmarks.
- **Nearest Known Prior Work (Verified References Only):**
  - *Yang et al. (2018)* (`yang2018hotpotqa`, EMNLP '18), *Min et al. (2019)* (`min2019compositional`, ACL '19), *Ho et al. (2020)* (`ho2020constructing`, COLING '20), *Trivedi et al. (2022)* (`trivedi2022musique`, TACL): Multi-hop benchmark construction, shortcut critiques, reasoning-path provenance, and disconnected-reasoning / unanswerable filtering.
  - *Thakur et al. (2021)* (`thakur2021beir`, NeurIPS 2021): Heterogeneous zero-shot IR benchmark design.
  - *Sakai (2016)* (`sakai2016statistical`, SIGIR '16) and *Faggioli et al. (2023)* (`faggioli2023perspectives`, ICTIR '23): Sample-size planning and human-vs-LLM annotation governance.
- **Distinguishing Technical Contribution:** Strict separation of corpus provenance classes (`pdf_extracted`, `markdown_oa_extracted`, `hand_authored`, `derived`), automated truncation/malformation and exact/near-duplicate filtering, page-range SHA-256 verification for every query's supporting evidence, and explicit `AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION` quarantine prior to benchmark freezing.
- **Required Ablations:**
  1. Pre-audit vs. post-audit query retention and necessity-tag correction rates (e.g., how many candidate cross-document queries survive human shortcut auditing).
  2. Inter-annotator agreement ($\kappa$, $\kappa_w$) on dual human judgments across single-passage, multi-passage, and negative-control strata.
  3. Cross-domain difficulty and lexical-vs-dense divergence analysis once multi-domain OA sources are ingested.
- **Supporting Evidence Currently Available:**
  - S5-B2.1 necessity audit (`2/12` holds, `2/10` cross-doc refutations) and S5-v3 Module B/C deterministic OA extraction + programmatic query-evidence verification.
  - **Major structural blocker:** Local disk currently contains only **4 verified open-access documents** (ML/Math/NLP/Robotics); Operating Systems, Databases, Computer Networks, and Systems are `DEFERRED_PENDING_OA_SOURCE_INGESTION`.
- **Missing Human Evidence:**
  - Human verification of 100% of proposed S5-v3 queries (premise audit, shortcut check, minimum evidence set).
  - Independent human negative-control verification.
  - Dual independent human relevance grading + adjudication (~59–123 person-hours depending on query count and pool depth; see [S5V3_ANNOTATION_COST_ESTIMATE.md](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-benchmark-expansion/S5V3_ANNOTATION_COST_ESTIMATE.md)).
  - Multi-domain OA corpus expansion (e.g., OSTEP, OpenStax, arXiv systems/DB/networks papers) before claiming a multi-domain CS benchmark.
- **Risk of Being Considered an Incremental Implementation Change:** **MODERATE (currently HIGH as a standalone resource).** A 4-document, 48-query unannotated candidate set is far below SIGIR Resource Track expectations; however, its audit methodology is a strong supporting pillar of **Candidate B**.

---

## 3. Synced S5-v3 Artifact Evidence Snapshot

Synced from Modules B (`@corpus-v3`), C (`@benchmark-v3`), and D (`@retrieval-v3`):

- **Corpus v3 (`s5v3_corpus_manifest.json`, SHA-256 `77661622...`):** `858` total passages (`818` usable, `40` unusable, `138` quality-flagged, `3` exact duplicates, `1` near-duplicate) extracted deterministically from **`4` verified local OA documents** (`local_oa_001`–`local_oa_004`: ML, NLP/LLMs, Math for ML, Robotics/Control). Operating Systems, Databases, Computer Networks, and Distributed Systems remain `MISSING_LOCAL_OA_SOURCE`.
- **Proposed Benchmark v3 (`s5v3_query_benchmark_proposed.json`, SHA-256 `17914918...`):** **`48` proposed queries** (`16` `dev` [`13` pos + `3` NC], `32` `test` [`27` pos + `5` NC]; `12` single-passage, `10` same-doc multi-passage, `10` cross-doc multi-passage with `shortcut_found=false`, `8` terminology/paraphrase, `8` negative controls; `23` anchor-rich / `25` anchor-sparse; `0` dev/test overlap; `0` v2.1 reuse). All `48` queries remain quarantined under `AI_PROPOSED_CANDIDATE_REQUIRES_HUMAN_VERIFICATION`.
- **Retrieval v3 Relevance-Agnostic Diagnostics (`s5v3_retrieval_diagnostics.json`, SHA-256 `54b021e0...`):** Across all `6` S5-v3 variants (`11/11` unit tests passing), corpus-grounded graph coverage on Corpus v3 is **`139/610` concepts (`22.79%`)** and **`270/1,988` edges (`13.58%`)**; token-boundary anchoring + deterministic fallback reduces zero-result queries from `3` (`v3_graph_naive_substring_ablation`) to `0` (`v3_graph_1hop_backfill` / `v3_graph_2hop_backfill`); and `v3_graph_2hop_coverage_routed` routes `17/48` queries to `lexical_only`, `30/48` to `balanced_hybrid`, and only `1/48` to `graph_heavy` (mean query anchor coverage `0.1910`).
- **Implication for Primary Contribution Verdict:** These synced diagnostics directly reinforce recommending **Candidate B** (*Reliable, Provenance-Aware Multi-Passage Retrieval Evaluation*): sparse corpus-grounded graph coverage (`22.79%` concepts / `13.58%` edges) and heavy `lexical_only` routing (`17/48` queries) confirm why fallback-stratified, provenance-aware evaluation methodology is essential—while the `4`-document corpus ceiling and `0` human relevance labels confirm that neither Candidate C nor Candidate D can stand alone without human annotation and multi-domain OA expansion.
