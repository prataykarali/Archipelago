# SIGIR 2027 Demonstrations Manuscript — Open TODO Manifest

Every `\todo{...}` marker in [`sigir2027_demo.tex`](sigir2027_demo.tex) corresponds to
an item that **cannot** be fabricated by coding agents and requires human action or
live authenticated capture before submission.

| Marker ID | Location | Required Action | Owner | Blocks Submission? |
|---|---|---|---|---|
| `AFFILIATION` / `CITY` / `COUNTRY` / `EMAIL` / `ORCID` | Author block | Insert verified institutional affiliation, city, country, contact email, and ORCID | Primary Author | Yes |
| `LIVE-DEMO-VERIFY` | Section 1 | Execute live authenticated browser walkthrough on hosted Vercel deployment (`chat`, PDF viewer, workbook export) | Primary Author / QA | Yes |
| `DEMO-VIDEO` | Section 1 | Record 3–5 minute live screencast and insert persistent archival URL | Primary Author | Yes |
| `FIG-1` | Section 2 | Export vector PDF architecture diagram matching verified runtime components | Primary Author / UI | Yes |
| `FIG-2` | Section 3 | Capture annotated high-DPI screenshot of authenticated workspace (Scenario 1 + Scenario 3 abstention) | Primary Author / UI | Yes |
| `HUMAN-QRELS` | Section 4.2 (Table 2) | Complete 731-item system-blinded pooled top-5 judging by 2 independent human annotators + 3rd adjudicator; report $\kappa_w$, Krippendorff's $\alpha$, and human-qrel retrieval metrics with significance tests | Independent Human Annotators + Adjudicator | Yes (blocks Scientific GO) |
| `INDEPENDENT-AUDIT` | Section 4.3 | Replicate 24-citation grounding audit and 45-edge audit with an independent human reviewer | Independent Human Reviewer | Recommended |
