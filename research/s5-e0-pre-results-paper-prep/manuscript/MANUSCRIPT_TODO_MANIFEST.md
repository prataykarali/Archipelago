# Manuscript TODO Manifest (`manuscript_draft.md`)

**Manuscript File:** `research/s5-e0-pre-results-paper-prep/manuscript/manuscript_draft.md`  
**Total `TODO` Markers:** 18 (`TODO-00` through `TODO-17`)  
**Policy:** No `TODO` marker may be filled using synthetic test outputs, unadjudicated labels, or unverified estimates. Every effectiveness and adjudication `TODO` requires finalized human evidence from Stage S5-C3 and investigator-authorized Stage S5-D1 execution.

---

## Complete Checklist Mapping Every `TODO` to Its Required Source Artifact

| TODO ID | Manuscript Section | Content Blocked | Required Stage / Gate | Exact Required Source Artifact(s) | Completed? |
|---|---|---|---|---|---|
| `TODO-00` | §1 Title | Author names, affiliations, and contact emails | Human Review | Investigator authorship decision | [ ] |
| `TODO-01` | §2 Abstract (Skeleton) | Concise descriptive post-adjudication effectiveness summary (IAA outcome, answerable metrics, fallback-stratified graph behavior, negative controls) | S5-C3 + S5-D1 | Finalized human gold-label JSON + S5-D1 evaluation report JSON (`s5_d1_evaluate.py`) | [ ] |
| `TODO-02` | §4.2 Scoped Contributions (C5) | Post-adjudication descriptive pilot effectiveness profile | S5-C3 + S5-D1 | S5-D1 evaluation report JSON (`s5_d1_evaluate.py`) | [ ] |
| `TODO-03` | §9.3 Annotation & Human Evaluation Protocol | Finalized independent human IAA (exact agreement, unweighted $\kappa$, quadratic weighted $\kappa$, confusion matrix), total disagreement count, and human adjudication summary | S5-C3 | S5-C3 A/C comparison & adjudication summary report + finalized human gold-label JSON | [ ] |
| `TODO-04` | §9.3 Annotation & Human Evaluation Protocol | Finalized independent human negative-control classifications, checked passage counts, and rationales for `Q-S5B2-03`, `Q-S5B2-08`, `Q-S5B2-11` | S5-C3 | Finalized S5-C3 human negative-control verification JSON (`s5_negative_control_verifier.py`) | [ ] |
| `TODO-05` | §11.1 Results (Table R1) | Per-system descriptive effectiveness summary (`Precision@5/10`, `Pooled Recall@5/10`, `MRR@10`, `nDCG@5/10`, strict `grade == 2` and lenient `grade >= 1`) | S5-D1 (Authorized) | `s5_d1_tables_figures.py` real-run `system_effectiveness_summary.{md,tex,csv}` | [ ] |
| `TODO-06` | §11.2 Results (Table R2) | Query-level descriptive effectiveness breakdown across verified answerable queries by domain and hop type | S5-D1 (Authorized) | `s5_d1_evaluate.py` real-run `query_level_metrics` in `REAL_D1_REPORT_JSON` | [ ] |
| `TODO-07` | §11.3 Results (Table R3) | Fallback vs. non-fallback stratified graph effectiveness & short-list accounting compared with `bm25` | S5-D1 (Authorized) | `s5_d1_tables_figures.py` real-run `fallback_and_shortlist_accounting.{md,tex,csv}` | [ ] |
| `TODO-08` | §11.4 Results (Table R4) | 1-hop vs. 2-hop descriptive metric deltas on the 5 AI/ML queries reaching hop depth 2 (`Q-S5B2-04`–`08`) | S5-D1 (Authorized) | `s5_d1_tables_figures.py` real-run `one_hop_vs_two_hop_comparison.{md,tex,csv}` | [ ] |
| `TODO-09` | §11.5 Results (Table R5) | Negative-control diagnostics for `Q-S5B2-03`, `Q-S5B2-08`, `Q-S5B2-11` (verified classification, returned counts, fallback flags, max gold grade, reclassification effect) | S5-D1 (Authorized) | `s5_d1_evaluate.py` real-run `negative_control_behavior` in `REAL_D1_REPORT_JSON` | [ ] |
| `TODO-10` | §11.6 Results (Short-List) | Short-list ceiling sensitivity for `baseline_graph_1hop` (`69/100` slots, fixed-denominator `P@5/10` ceilings) | S5-D1 (Authorized) | `s5_d1_tables_figures.py` real-run `fallback_and_shortlist_accounting.{md,tex,csv}` + `short_list_accounting` in `REAL_D1_REPORT_JSON` | [ ] |
| `TODO-11` | §11.7 Results (Figures F1–F2) | Real (non-synthetic) SVG figures: `fig1_system_effectiveness.svg` and `fig2_fallback_vs_nonfallback.svg` | S5-D1 (Authorized) | `s5_d1_tables_figures.py` real-run SVG outputs (verify ZERO `SYNTHETIC_` prefix or watermark) | [ ] |
| `TODO-12` | §12.2 Discussion (RQ1) | Descriptive cross-paradigm effectiveness interpretation across the six frozen systems (strictly pilot-scoped; no significance/superiority claims) | S5-D1 + Human Review | S5-D1 evaluation report JSON (`s5_d1_evaluate.py`) + human investigator synthesis | [ ] |
| `TODO-13` | §12.2 Discussion (RQ2) | Interaction between fallback/substring mechanics and observed effectiveness (including `baseline_graph_1hop` short-list effects) | S5-D1 + Human Review | S5-D1 fallback-stratified & short-list tables + human investigator synthesis | [ ] |
| `TODO-14` | §12.2 Discussion (RQ3) | Relevance impact of 2-hop traversal on the 5 AI/ML queries (relevant context vs. topical drift) | S5-D1 + Human Review | S5-D1 1-hop vs. 2-hop comparison table + human investigator synthesis | [ ] |
| `TODO-15` | §14 Limitations | Update `LIM-04`, `LIM-05`, and `LIM-06` status from `Blocking (S5-C3)` to resolved with provenance; retain permanent `LIM-01`, `02`, `03`, `07`, `08`, `09` | S5-C3 + S5-D1 | Finalized S5-C3 gold/negative-control artifacts + S5-D1 preflight pass log | [ ] |
| `TODO-16` | §15 Conclusions (Skeleton) | Concise post-adjudication descriptive conclusions and v3 future-work directions preserving all permanent non-claims | S5-D1 + Human Review | S5-D1 evaluation report JSON + human investigator review | [ ] |
| `TODO-17` | §16.1 Reproducibility Disclosures | Record SHA-256 hashes of finalized human gold-label JSON, negative-control verification JSON, investigator authorization artifact, and final S5-D1 report JSON | S5-C3 + S5-D1 | S5-C3 export logs + S5-D1 preflight/evaluation manifest (never commit private passage text) | [ ] |

---

## Pre-Publication Verification Gate

Before removing `[PRE-RESULTS]` status or compiling the final paper:
1. Confirm every `TODO-00` through `TODO-17` above is checked `[x]` using **real, investigator-authorized** outputs (zero `SYNTHETIC`-marked files).
2. Confirm permanent non-claims (§4.3) remain intact: no statistical significance tests, no system superiority claims, no cross-document multi-hop claims, and no large-corpus/GPU scaling claims.
3. Re-audit `BIBLIOGRAPHY_AUDIT.md` flagged preprints (`merrick2024arctic`, `edge2024local`) for archival venue updates if desired.
