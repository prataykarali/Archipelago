# E0.2 — Scoped Contributions, Non-Claims, and Pilot Limitations (Pre-Gold-Label)

**Phase:** S5-E0.2 (Scientific Framing and Introduction)  
**Base Commit:** `6450585f60b3c1bea7bef2f411458800552cea0b`  
**Date:** 2026-11-19  
**Ground Truth:** [E01_CLAIM_EVIDENCE_MATRIX.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_CLAIM_EVIDENCE_MATRIX.md), [E01_RESEARCH_GAPS.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_RESEARCH_GAPS.md), [S5D0_LIMITATIONS_REGISTER.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/S5D0_LIMITATIONS_REGISTER.md)  
**Verified Bibliography:** [E03_VERIFIED_REFERENCES.bib](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E03_VERIFIED_REFERENCES.bib)

---

## 1. Permissible Pre-Results Contributions (Verified Now)

| ID | Contribution Statement (Manuscript-Safe Wording) | Evidence Basis (`E01` Claims & Artifacts) | Scope Qualifier |
|---|---|---|---|
| **C1** | **Parity-Enforced, Cryptographically Auditable Six-System Pilot Protocol:** Establishes strict 713-passage / 53-document information-access parity (`s5a_eval_corpus_v1`), canonical `{doc_id}::{chunk_id}` identifiers (0 collisions), runtime SHA-256 verification of the `(713, 768)` dense cache, exclusion of 462 unscoped Kùzu edges and 2 external heterogeneous edges, complete depth-10 blinded pooling (254 pairs, 100.0% Top-5/Top-10 coverage), and byte-identical fresh-clone workbook regeneration. | `CLM-01`, `CLM-02`, `CLM-05`, `CLM-06`, `CLM-12`; [s5b1_corpus_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/corpus/s5b1_corpus_manifest.json), [graph_information_access_audit.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/reports/graph_information_access_audit.json), [fresh_environment_reproducibility_report.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/reports/fresh_environment_reproducibility_report.json) | Pilot-scale protocol (`N = 10` queries, 713 passages); does not establish large-scale benchmark infrastructure. |
| **C2** | **Relevance-Agnostic Behavioral Characterization of Lexical, Dense, Hybrid, and Graph Retrievers:** Quantifies candidate-set divergence (`bm25` vs. `dense` Top-10 Jaccard `0.4739`; `hybrid_rrf_e2e` bridging both with `0.6091`/`0.6480` Jaccard and `0.112–0.161 ms` fusion cost vs. `95.4%–97.8%` dense CPU latency), domain-concentrated BM25 fallback in `repaired_graph_*` (**4/10 = 40.0%**, lowering non-fallback Jaccard with `bm25` from `0.4800`/`0.4852` to `0.1333`/`0.1421`), and `baseline_graph_1hop` substring false positives (`"act"` inside `"exact"` on `Q03`, `Q11`) plus **31/100 missing Top-10 slots** and **65.2%** (`45/69`) exclusive pairs. | `CLM-07`, `CLM-08`, `CLM-10`, `CLM-11`; [s5d0_technical_diagnostics.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_technical_diagnostics.json), [retrieval_timing_report.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/reports/retrieval_timing_report.json) | Strictly **relevance-agnostic** diagnostics; does not measure or imply retrieval effectiveness (`CLM-15`) or large-corpus latency scaling (`LIM-08`). |
| **C3** | **Exact Behavioral Isolation of 1-Hop vs. 2-Hop Heterogeneous Graph Expansion:** Demonstrates that extending traversal from 1 hop (`45` paths) to 2 hops (`212` paths: `45` hop-1 + `167` hop-2) reaches hop depth 2 on **5/10** queries (all AI/ML: `Q04`–`Q08`), modifying Top-10 rank order on 5/5 and set membership on 4/5 (up to 5 passages replaced on `Q05`, Top-10 Jaccard `0.3333`), while leaving `Q10` (`0` hop-2 edges) and all 4 fallback queries unchanged. | `CLM-09`; [s5d0_technical_diagnostics.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_technical_diagnostics.json) | Behavioral perturbation only; **does not** establish whether 2-hop expansion improves or degrades relevance (`CLM-16`). |
| **C4** | **Methodological Negative Findings on Multi-Hop Necessity & Annotation Governance:** Documents how passage-necessity auditing (`min2019compositional`) refuted cross-document tags on `Q06`/`Q07` (leaving **0 validated cross-document queries** and 2 held queries due to corpus defects), and operationalizes a reproducible pre-scoring governance gate (`evaluate_gold_labels_readonly.py`) that blocks effectiveness reporting when AI-assisted annotation provenance (`faggioli2023perspectives`; `REV_B` 254/254 pairs), 51/254 disagreements, and negative-control verifications remain unresolved. | `CLM-03`, `CLM-04`, `CLM-13`, `CLM-14`; [s5b2_1_passage_necessity_matrix.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_1_passage_necessity_matrix.json), [s5c2_audit_summary.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/s5c2_audit_summary.json), [evaluate_gold_labels_readonly.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/scripts/evaluate_gold_labels_readonly.py) | Pre-adjudication agreement (`79.92%`, $\kappa_w=0.7677$) is preliminary audit status only, never validated inter-human reliability (`CLM-21`). |

---

## 2. Deferred / Blocked Contribution (`TODO` Pending S5-C3 & S5-D1)

- **C5 (`BLOCKED` — `TODO`):** *Descriptive Post-Adjudication Effectiveness Profile Across Six Frozen Systems.* Strictly blocked on `GAP-B1`–`GAP-B4` (Reviewer B independent human confirmation, human adjudication of 51 disagreements + 5 text-diff pairs, independent human verification of negative controls `Q03, Q08, Q11`, and read-only execution of `evaluate_gold_labels_readonly.py` on `ADJUDICATED_HUMAN_GOLD_FINAL`). Once unlocked, this will provide descriptive `Recall@5/10`, `Precision@5/10`, `MRR@10`, `nDCG@5/10` (`jarvelin2002cumulated`), fallback-stratified graph summaries, and negative-control abstention diagnostics—never significance tests or superiority claims.

---

## 3. Explicit Non-Claims (Permanent Disclaimers for v2.1 Pilot)

To prevent misinterpretation by reviewers or readers, the manuscript must explicitly disclaim five claims that are permanently unsupported by the frozen v2.1 pilot (`E01_CLAIM_EVIDENCE_MATRIX.md` §5):
1. **No system superiority claims (`CLM-18`):** This study does not claim that graph-based retrieval outperforms BM25, dense bi-encoders, or hybrid RRF (nor the reverse).
2. **No cross-document multi-hop reasoning claims (`CLM-19`):** Because 0 validated cross-document queries exist (`LIM-02`), this study provides zero evidence regarding cross-document multi-hop retrieval.
3. **No statistical significance or domain generalization claims (`CLM-20`):** With 10 active queries (7 answerable) across 3 CS domains, the pilot is severely underpowered for inferential testing (`sakai2016statistical`, `LIM-01`).
4. **No claim of validated independent double-blind human gold labels (`CLM-21`):** Reviewer B's 254/254 AI-assistance disclosure and 51 unadjudicated disagreements remain active blockers (`LIM-05`, `LIM-06`).
5. **No production-scale efficiency claims (`CLM-22`):** CPU timings over 713 passages and 146 heterogeneous edges do not extrapolate to 10k–1M passage corpora or GPU deployments (`LIM-08`).

---

## 4. Structured Pilot Limitations Summary

| Limitation Group | IDs | Concise Impact on Manuscript Scope |
|---|---|---|
| **Blocking (S5-C3 / S5-D1)** | `LIM-04`, `LIM-05`, `LIM-06` (`GAP-B1`–`GAP-B4`) | Final effectiveness metrics, negative-control stratification, and inter-human reliability claims remain strictly blocked until human confirmation, adjudication of 51 disagreements, and negative-control verification complete. |
| **Permanent v2.1 Pilot Scope** | `LIM-01`, `LIM-02`, `LIM-03`, `LIM-08` (`GAP-P1`–`GAP-P4`) | `N = 10` (7 answerable) limits study to descriptive pilot diagnostics; 0 validated cross-document queries; 21 truncated textbook stubs ($\le 305$ chars) + 1 constructed pilot card + sparse OSTEP extraction remain frozen in `s5a_eval_corpus_v1`; warm multi-rep CPU timing reflects pre-revision S5-B1.1 12-query set. |
| **Algorithmic & Governance Constraints** | `LIM-07`, `LIM-09` (`GAP-F1`–`GAP-F4`) | 40% BM25 fallback in `repaired_graph_*` and `"act"`-in-`"exact"` substring false positives + 31/100 missing slots in `baseline_graph_1hop` require stratified interpretation; historical Git packfile exposure requires isolated local reviewer workbooks outside Git access. |
