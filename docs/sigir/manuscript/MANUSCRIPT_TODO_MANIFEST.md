# SIGIR 2027 Demonstrations Manuscript — Open TODO Manifest

Every `\todo{...}` or `[TODO: ...]` marker in [`sigir2027_demo.tex`](sigir2027_demo.tex) corresponds to
an item that **cannot** be fabricated by coding agents and requires human action or
independent external review before camera-ready submission.

## Open TODO Markers Requiring Human Action

| Marker ID | Location in `sigir2027_demo.tex` | Required Action | Owner | Blocks Submission? |
|---|---|---|---|---|
| `AFFILIATION` / `CITY` / `COUNTRY` / `EMAIL` / `ORCID` | Author block (lines 32–38) | Confirm and insert verified institutional affiliation, city, country, contact email, and ORCID | Primary Author | Yes |
| `VIDEO-URL` | Section 2 (`Reviewer Access & Screencast`) | Record the narrated 3–5 minute live screencast following [`../SIGIR_REVIEWER_REHEARSAL_AND_FALLBACK.md`](../SIGIR_REVIEWER_REHEARSAL_AND_FALLBACK.md) and insert persistent archival URL (e.g., Zenodo / unlisted YouTube) | Primary Author | Yes |
| `HUMAN-QRELS` | Section 4.2 (`Experiment B: Provisional Passage Ranking`) | Complete the re-blinded 731-item system-blinded pooled top-5 judging by 2 independent human annotators + 3rd adjudicator (keyed outside git); report $\kappa_w$, Krippendorff's $\alpha$, and human-adjudicated retrieval metrics | Independent Human Annotators + Adjudicator | Yes (blocks Scientific Evaluation GO) |
| `INDEPENDENT-AUDIT` | Section 4.3 (`Failure Taxonomy & Citation Grounding Audit`) | Complete independent human verification of the preliminary author-attributed 24-citation grounding audit (`citation_grounding_audit.json`) and 45-edge graph audit (`human_review_records.json`) | Independent Human Reviewer | Recommended (blocks independent audit claim) |

## Resolved Markers (Closed in D8 & D9)

| Former Marker ID | Resolution & Verified Artifact Provenance | Status |
|---|---|---|
| `LIVE-DEMO-VERIFY` | Closed by D8 authenticated live E2E verification (`6/6 PASS` across Student, Faculty, and Librarian roles on production deployment `dpl_8QiQvF79qZLQS9oj5xaobxurDarY`, code SHA `1785846a49db27d5931beb596cf64bbbae778f3c`, `graph_version: 9818ac0e8fd3`). Documented in [`../D8_AUTHENTICATED_E2E_REPORT.md`](../D8_AUTHENTICATED_E2E_REPORT.md). | **RESOLVED (D8)** |
| `FIG-1` (System Architecture) | Generated vector PDF/SVG and 300-DPI PNG architecture diagram (`figures/fig_f_system_architecture.{pdf,svg,png}`) via [`../../research/d5_sigir_evaluation/generate_d9_figures.py`](../../research/d5_sigir_evaluation/generate_d9_figures.py) and embedded as Figure 1 in `sigir2027_demo.tex`. | **RESOLVED (D9)** |
| `FIG-2` (Live Workspace Screenshot) | Embedded redacted live production screenshot [`../d8_evidence/j1_chat_transformer.png`](../d8_evidence/j1_chat_transformer.png) as Figure 2 alongside empirical Figures A–E (`figures/fig_a_concept_resolution.pdf` through `figures/fig_e_citation_audit.pdf`). | **RESOLVED (D8/D9)** |
