# E0.2 — Title Evaluation and Research Questions (Pre-Gold-Label)

**Phase:** S5-E0.2 (Scientific Framing and Introduction)  
**Base Commit:** `6450585f60b3c1bea7bef2f411458800552cea0b`  
**Date:** 2026-11-19  
**Ground Truth:** [E01_EVIDENCE_INVENTORY.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_EVIDENCE_INVENTORY.md), [E01_CLAIM_EVIDENCE_MATRIX.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_CLAIM_EVIDENCE_MATRIX.md), [S5D0_TECHNICAL_DIAGNOSTICS.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/S5D0_TECHNICAL_DIAGNOSTICS.md), [S5D0_LIMITATIONS_REGISTER.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/S5D0_LIMITATIONS_REGISTER.md)  
**Verified References:** [E03_VERIFIED_REFERENCES.bib](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E03_VERIFIED_REFERENCES.bib)

---

## 1. Critical Evaluation of the Provisional Title

**Provisional Title:**  
> *"An Auditable Pilot Evaluation of Lexical, Dense, Hybrid, and Graph-Based Retrieval for Academic Knowledge Discovery"*

### Component-by-Component Audit Against Frozen Evidence
| Title Phrase | Audit Verdict | Evidence-Based Assessment |
|---|---|---|
| *"An Auditable Pilot Evaluation"* | **Accurate** | Accurately reflects the small exploratory query sample (`N = 10` active queries, `7` answerable + `3` provisional negatives; `CLM-03`, `LIM-01`) and the cryptographic freeze/manifest discipline (`CLM-01`, `CLM-05`, `CLM-12`). |
| *"of Lexical, Dense, Hybrid, and Graph-Based Retrieval"* | **Accurate** | Matches the six frozen systems (`bm25`, `dense_snowflake_arctic_768d`, `hybrid_rrf_e2e`, `baseline_graph_1hop`, `repaired_graph_1hop_ablation`, `repaired_graph_2hop_full`; `CLM-06`). Specifying *"Passage Retrieval"* is slightly more precise than *"Retrieval"*, because all systems rank fixed passage chunks (`s5a_eval_corpus_v1`) rather than full documents or synthesized answers. |
| *"for Academic Knowledge Discovery"* | **Overbroad (Recommend Narrowing)** | *"Academic Knowledge Discovery"* implies end-to-end literature exploration, hypothesis synthesis, or multi-discipline academic search. In reality, `s5a_eval_corpus_v1` contains **713 passages across 53 computer-science documents** covering three CS subfields (Operating Systems, AI/ML, Computer Networks; `CLM-01`, `CLM-03`), with **0 validated cross-document queries** (`CLM-04`, `LIM-02`) and no downstream generation or discovery user study. |

### Recommended Revised Title
> **Recommended Title:** *"An Auditable Pilot Evaluation of Lexical, Dense, Hybrid, and Graph-Based Passage Retrieval on a Technical Computer Science Corpus"*

*(Rationale: Retaining *"Auditable Pilot Evaluation"* preserves methodological humility, *"Passage Retrieval"* accurately names the unit of evaluation, and *"on a Technical Computer Science Corpus"* removes the overbroad implication of general-purpose academic knowledge discovery while remaining faithful to the 3-domain CS benchmark.)*

---

## 2. Research Questions (Strictly Partitioned: Diagnostics vs. Effectiveness)

To prevent conflating **relevance-agnostic system behavior** (currently verified in S5-D0) with **relevance effectiveness** (strictly blocked on S5-C3 human adjudication and S5-D1 read-only scoring), the three research questions explicitly separate what is measurable now from what remains gated.

### RQ1 — Cross-Paradigm Descriptive Relevance Effectiveness *(BLOCKED — S5-C3 / S5-D1)*
> **RQ1:** *Under strict corpus and information-access parity over a frozen 713-passage computer science corpus, how do six retrieval configurations—lexical BM25, a zero-shot dense bi-encoder, Reciprocal Rank Fusion (RRF) hybrid retrieval, a corpus-scoped 1-hop Kùzu graph retriever, and repaired 1-hop and 2-hop heterogeneous graph retrievers—compare in descriptive relevance effectiveness once independently validated human relevance judgments become available?*

- **Current Evidence Status:** **`BLOCKED`** (`CLM-15`, `GAP-B1`–`GAP-B4`). No Recall@k, Precision@k, MRR@10, or nDCG@k values are computed prior to `ADJUDICATED_HUMAN_GOLD_FINAL`.
- **Planned Measurement Protocol (Post-S5-C3):** Read-only execution of [evaluate_gold_labels_readonly.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/scripts/evaluate_gold_labels_readonly.py) over the 254-pair depth-10 blinded pool (`100.0%` Top-10 coverage; `CLM-05`), reporting descriptive `Recall@5/10`, `Precision@5/10`, `MRR@10` at strict (`grade >= 2`) and lenient (`grade >= 1`) thresholds, and graded `nDCG@5/10` (`jarvelin2002cumulated`) on verified answerable queries only, with verified negative controls (`Q03, Q08, Q11`) reported separately (`CLM-17`).
- **Explicit Interpretive Boundary:** Because `N = 7` answerable queries is far below statistical-power thresholds (`sakai2016statistical`, `LIM-01`), RQ1 yields **descriptive pilot profiles only**—never statistical significance, system superiority (`CLM-18`, `CLM-20`), or cross-document multi-hop claims (`CLM-19`).

### RQ2 — Anchor Coverage, Substring Matching, and BM25 Fallback Effects *(VERIFIED Diagnostics; Effectiveness Stratification BLOCKED)*
> **RQ2:** *How do graph anchor coverage, raw substring matching, and deterministic BM25 fallback shape observable retrieval behavior—specifically candidate overlap, system exclusivity, and Top-10 slot completeness—and what constraints do they impose on interpreting cross-paradigm comparisons?*

- **Current Evidence Status:** **`VERIFIED` (Relevance-Agnostic Diagnostics)** via [s5d0_technical_diagnostics.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_technical_diagnostics.json) (`CLM-07`, `CLM-08`, `CLM-10`). Post-adjudication stratified effectiveness remains **`BLOCKED`**.
- **Verified Diagnostic Observables:**
  1. **Fallback inflation of lexical similarity:** Both repaired heterogeneous graph retrievers (`146` corpus-scoped edges) trigger deterministic `corpus_bm25` fallback on **4/10 (40.0%)** active queries (`Q01, Q02, Q03, Q11`) due to zero anchor matches, yielding exact `bm25` Top-10 copies (`CLM-07`). Removing fallback queries lowers mean Top-10 Jaccard with `bm25` from `0.4800`/`0.4852` to `0.1333`/`0.1421` (`CLM-08`).
  2. **Substring false positives and slot shortfalls:** In `baseline_graph_1hop`, raw substring matching (`c in query.lower()`) triggers false-positive anchor `"act"` inside `"exact"` on `Q03` and `Q11`, suppressing fallback while returning 1 passage each; without partial-list backfill, `baseline_graph_1hop` exhibits **31/100 missing Top-10 slots** and **65.2% (`45/69`)** exclusive pairs (`CLM-08`, `CLM-10`).
- **Methodological Implication:** Consistent with entity-linking and graph-incompleteness critiques (`dietz2018utilizing`), any future RQ1 comparison of `repaired_graph_*` must stratify **non-fallback (`6/10`) vs. fallback (`4/10`) queries**, and any comparison of `baseline_graph_1hop` must disclose its 31/100 slot shortfall (`LIM-07`).

### RQ3 — Behavioral Effects of 1-Hop vs. 2-Hop Heterogeneous Graph Traversal *(VERIFIED Diagnostics; Relevance Impact BLOCKED)*
> **RQ3:** *What measurable changes in observed traversal depth, path counts, candidate composition, and Top-K rank overlap arise when extending deterministic heterogeneous graph retrieval from one hop (`repaired_graph_1hop_ablation`) to two hops (`repaired_graph_2hop_full`), and how does this structural perturbation separate from unverified relevance impact?*

- **Current Evidence Status:** **`VERIFIED` (Relevance-Agnostic Diagnostics)** (`CLM-09`); whether 2-hop rank shifts improve or degrade relevance is **`BLOCKED`** (`CLM-16`).
- **Verified Diagnostic Observables:**
  1. **Domain-bounded hop activation:** `repaired_graph_2hop_full` reaches observed hop depth `2` on **5/10** active queries (all in AI/ML: `Q04`–`Q08`), increasing total traversed paths from `45` (1-hop) to `212` (`45` hop-1 + `167` hop-2). On `Q10` (Computer Networks), anchor `'nids'` has 0 hop-2 outgoing edges (`actual_hop_count = 1`), producing identical rankings; on the 4 fallback queries (`Q01, Q02, Q03, Q11`), both configurations revert identically to `bm25`.
  2. **Rank and set perturbation:** Across all 5 queries reaching hop 2, 2-hop decay scoring alters Top-10 rank order; on 4/5 queries (`Q04, Q05, Q06, Q08`), it alters Top-10 set membership (largest shift on `Q05`: +5/−5 passages replaced, Top-10 Jaccard `0.3333`, Top-5 Jaccard `0.2500`).
- **Explicit Interpretive Boundary:** Traversal expansion and rank perturbation are **purely behavioral diagnostics**, NOT evidence of retrieval improvement (`CLM-16`). Added hop-2 passages could be either relevant context or topical drift/distractors until evaluated against adjudicated human gold labels.

---

## 3. Summary Mapping of RQs to Evidence Layers

| RQ | Primary Focus | Relevance-Agnostic Status (Now) | Relevance-Effectiveness Status (Post-S5-C3/D1) | Prohibited Interpretations |
|---|---|---|---|---|
| **RQ1** | 6-system descriptive effectiveness comparison | N/A (Protocol & pool verified: `CLM-05`, `CLM-06`) | **`BLOCKED`** (`TODO`: S5-D1 `evaluate_gold_labels_readonly.py`) | No significance tests (`LIM-01`), no superiority (`CLM-18`), no cross-doc claims (`CLM-19`). |
| **RQ2** | Anchor coverage, substring matching & BM25 fallback | **`VERIFIED`** (`CLM-07`, `CLM-08`, `CLM-10`) | **`BLOCKED`** (`TODO`: fallback vs. non-fallback metric stratification) | Do not treat unstratified `repaired_graph_*` scores as pure graph retrieval (`LIM-07`). |
| **RQ3** | 1-hop vs. 2-hop traversal depth & candidate shift | **`VERIFIED`** (`CLM-09`) | **`BLOCKED`** (`TODO`: delta nDCG/Recall on 5 AI/ML queries) | Do not equate deeper traversal or rank shifts with relevance gain (`CLM-16`). |
