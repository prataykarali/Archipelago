# Archipelago D14.2 — OKF Graph Reconstruction & Semantic Audit

- **Baseline (Immutable):** `graph_v1_okf610` (`host_inference/fixtures/okf_graph.json`, SHA-256 `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76`)
- **Reconstructed Artifact:** `graph_v2_d14` (`host_inference/fixtures/okf_graph_v2_d14.json`, SHA-256 `33a6f7117acc9160e3a9dea99b04b159a355f8c2efa350c0b7d926d0da430774`)
- **Schema Version:** `2.0.0-d14`
- **Review Honesty Policy:** Zero machine-generated or newly curated edges are auto-promoted to `HUMAN_VERIFIED`; all carry explicit `PENDING_REVIEW` provenance pending human domain review.

## 1. Quantitative Comparison (`graph_v1_okf610` -> `graph_v2_d14`)

| Metric | `graph_v1_okf610` | `graph_v2_d14` |
|---|---:|---:|
| Concepts | 610 | 631 |
| Total Edges | 1,988 | 1944 |
| `REQUIRES` Edges | 267 | 264 |
| `ENABLES` / `UNLOCKS` Edges | 387 | 331 |
| `USES` Edges | (folded into RELATED) | 153 |
| `PART_OF` Edges | (folded into RELATED) | 176 |
| `RELATED_TO` Edges | (folded into RELATED) | 921 |
| `CONTRASTS_WITH` Edges | (folded into RELATED) | 99 |
| `REQUIRES` DAG Cycles | 0 | 0 |
| Combined Prerequisite (`REQUIRES` + inv `ENABLES`) Cycles | 7 SCCs | 0 |
| Empty Summaries | 55 | 0 |
| Placeholder Summaries | 26 | 0 |
| Malformed Artifact Nodes Removed | — | 5 |
| Duplicate Nodes Canonicalized | — | 5 |
| Curriculum Nodes Added | — | 31 |

## 2. Defect Register Resolution Summary

- **D14-DEF-003..008 (Resolution & Specificity):** Added canonical nodes & aliases for `Singular Value Decomposition (SVD)`, `Graph Attention Network (GAT)`, `Kullback-Leibler Divergence`, `Variational Inference`, `LALR Parsing`, `Denoising Diffusion Probabilistic Models (DDPM)`, `Page Table`, `TLB`, `Base-and-Bounds`, and multi-concept anchor extraction via `okf/graph/d14_concept_resolver.py`.
- **D14-DEF-009 (12-Domain Coverage):** Added source-backed curriculum nodes for Information Security (`RSA`, `TLS`, `Public-Key`, `Symmetric-Key`, `Cryptographic Hash`, `NIDS`), Automata (`Pumping Lemma`, `Regular Languages`, `Context-Free Languages`), Software Engineering (`Software Engineering`, `SDLC`, `SOLID`, `Unit Testing`, `Design Patterns`, `CI`, `VCS`), Computer Architecture (`CPU Architecture`, `ISA`, `Instruction Pipelining`, `Pipeline Hazards`, `Cache Memory`, `Cache Coherence`, `Branch Prediction`), and Algorithms (`Dijkstra's Algorithm`).
- **D14-DEF-010..018 (Invalid Edges):** Removed/re-typed all 9 invalid pedagogical and cross-domain contamination edges (`Neural Network -> MLE`, `DPO -> RL`, `Attention -> Neural Network`, `DFA/Regex -> Autonomous System`, `Probability -> Inheritance Hierarchy`, `PCA -> Web Traffic`, `Data Link Layer -> Bit Transmission`, `B+ Tree -> Clustered Index` re-typed to `USES`, `TCP -> Constitutional Principle`).
- **D14-DEF-019..020 (Hygiene):** Eliminated all 26 placeholder summaries, 55 empty summaries, 6 contaminated summaries, and 5 malformed artifact nodes (`Equation Only`, `Variable Compute Only`, `Flow Feature Name Description`, `Fast`, `Memory-Efficient`).
- **Interdisciplinary Preservation:** Preserved `PagedAttention -[USES]-> Paging` and `PagedAttention -[RELATED_TO]-> Virtual Memory` with accurate non-prerequisite typing.

## 3. 12-Domain Concept Coverage (`graph_v2_d14`)

| Academic Domain | Concept Count |
|---|---:|
| Mathematics for Computing | 23 |
| Probability & Statistics | 42 |
| AI & Machine Learning | 122 |
| Operating Systems | 27 |
| Data Structures & Algorithms | 10 |
| Database Systems | 15 |
| Computer Networks | 34 |
| Compilers & Languages | 12 |
| Automata & Computation | 15 |
| Information Security | 25 |
| Software Engineering | 9 |
| Computer Architecture | 11 |
