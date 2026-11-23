# D8 Authenticated Live SIGIR E2E Verification Report

**Verdict:** **HOSTED DEMO GO** (`6/6 PASS`, `0 FAIL`, `0 BLOCKED`)  
**Target Origin:** `https://archipelago-blond.vercel.app`  
**Secondary Origin:** `https://archipelago-librarian.vercel.app`  
**Verified Production Deployment:** `dpl_8QiQvF79qZLQS9oj5xaobxurDarY`  
**Verified Deployed Commit SHA (`X-Archipelago-Release`):** `1785846a49db27d5931beb596cf64bbbae778f3c`  
**Graph Export Fingerprint (`graph_version`):** `9818ac0e8fd3` (explicitly distinct from code SHA)  
**Verification Date (UTC):** `2026-11-23`  
**Execution Method:** Real headless Chromium (Playwright) browser sign-in through `/login` (Supabase Auth + `POST /api/auth/session`) for three separately authorized roles (`student`, `faculty`, `librarian`), plus authenticated session byte verification (`%PDF-`, `openpyxl` `.xlsx`). Zero credentials, cookies, JWTs, or Authorization headers were logged, screenshotted, or committed.

---

## 1. Deployment Readiness & Revision Separation

| Check | Endpoint | HTTP | Observed Value |
|-------|----------|------|----------------|
| Inference Readiness | `GET /api/readiness` | `200` | `ok: true`, `concepts: 610`, `corpus.source: "full"`, `pearson_books: 40` |
| Deployed Code SHA | Header `X-Archipelago-Release` | `200` | `1785846a49db27d5931beb596cf64bbbae778f3c` |
| Graph Fingerprint | Body `graph_version` | `200` | `9818ac0e8fd3` (distinct from code revision) |
| Librarian Readiness | `GET https://archipelago-librarian.vercel.app/api/readiness` | `200` | `ready: true` |

---

## 2. Authenticated Journey Verification Matrix (J1–J6)

| ID | Journey | Verdict | Original Source Opened? | Key Network / Byte Evidence | Redacted Evidence |
|----|---------|---------|-------------------------|-----------------------------|-------------------|
| **J1** | **Chat, Graph & Original PDF** (`What is a Transformer?`) | **PASS** | **Yes** (`Vaswani2017` p.2/15) | `POST /api/chat` -> `200`, `citations=3`, `render_graph=true`, `provenance_status="provenance_verified"`, `claim_support_status="not_assessed"`. Clicked citation -> `/read?doc=papers%2FVaswani2017_Attention_Is_All_You_Need.pdf&page=2` (`200`). Authenticated `/api/page-view` -> `200`; PDF bytes verified: **`2,215,244` bytes**, `%PDF-` magic, `%%EOF`, **15 pages**, page 2 in range. | [j1_chat_transformer.png](d8_evidence/j1_chat_transformer.png), [j1_pdf_viewer.png](d8_evidence/j1_pdf_viewer.png) |
| **J2** | **Research Discovery** (`Dense Passage Retrieval`) | **PASS** | **Yes** (DOI `302` -> SpringerOpen) | `/research` UI search persisted run `2468332d-f971-46d5-a9c9-dfd794aff51c` (**30 papers**, provider `openalex`). `GET /api/research/intelligence/runs/<id>/dossier` -> `200` (**186,193 bytes**). Primary DOI `https://doi.org/10.1186/s40537-025-01257-9` resolved `HTTP 302` -> `https://journalofbigdata.springeropen.com/articles/10.1186/s40537-025-01257-9`. | [j2_research_results.png](d8_evidence/j2_research_results.png), [j2_research_dossier.png](d8_evidence/j2_research_dossier.png) |
| **J3** | **Research Persistence & Export** (`.xlsx`) | **PASS** | **Yes** (valid OOXML workbook) | Reloaded browser -> `GET /api/research/intelligence/runs` -> `200` (run persisted). Reopened `GET /runs/<id>` -> `200` (30 papers). `GET /runs/<id>/xlsx?mode=standard` -> `200` (**26,511 bytes**). `openpyxl` verified **4 sheets** (`Start Here`, `Papers` 31 rows, `Authors` 81 rows, `Sources` 74 rows) with real paper titles and **103 live hyperlinks** (30 in `Papers`, 73 in `Sources`). | [j3_saved_run_reopened.png](d8_evidence/j3_saved_run_reopened.png) |
| **J4** | **Library & OPAC** (`/library` + Koha) | **PASS** | **Yes** (Koha `biblionumber=1910`) | `/library` loaded (`200`) and interactive search (`Algorithms`) worked. `GET /api/library/data` -> `200` (`91` e-books, `109` Koha holdings, explicit freshness disclosure `koha_stale: true`, `koha_source_updated_at: 2026-11-11T15:24:20.794016+00:00`). Institutional Koha OPAC record `biblionumber=1910` (*Journal of human resource management*) opened live (`HTTP 200`) on `uemk-opac.l2c2.co.in`. | [j4_library_opac.png](d8_evidence/j4_library_opac.png), [j4_koha_record.png](d8_evidence/j4_koha_record.png) |
| **J5** | **Unsupported-Topic Integrity** (`What is Spanner TrueTime?`) | **PASS** | N/A (abstention) | `POST /api/chat` -> `200` (`GUARDRAIL_INTERCEPT`, `0.02s`). **`0` citations**, **`0` graph nodes**, **`0` graph edges**, `render_graph: false`, `grounding_status: "unmatched"`, `provenance_status: "none"`. Honest scope abstention preserved with zero fabricated graph edges or citations. | [j5_unsupported_abstention.png](d8_evidence/j5_unsupported_abstention.png) |
| **J6** | **Role-Based Security & P0-2 Isolation** | **PASS** | N/A (security boundary) | **Student -> Librarian negative (5/5 `HTTP 403`):** `POST /api/library/import`, `POST /api/auth/handoff-ticket`, `GET /api/analytics/sources`, `GET /api/analytics/summary`, `GET /api/librarian/catalog`. **P0-2 Bidirectional Cross-User Isolation (6/6 `HTTP 404`):** Faculty cannot read Student's run/dossier/xlsx (`404`/`404`/`404`); Faculty created own run (`200`), and Student cannot read Faculty's run/dossier/xlsx (`404`/`404`/`404`). **Librarian positive (3/3 `HTTP 200`):** `GET /api/analytics/sources`, `GET /api/analytics/summary`, `GET /api/librarian/catalog`. | [j6_librarian_session.png](d8_evidence/j6_librarian_session.png) |

Machine-readable redacted evidence: [`docs/sigir/d8_evidence/d8_authenticated_e2e_results.json`](d8_evidence/d8_authenticated_e2e_results.json).

---

## 3. Operational Observations & Non-Blocking Notes (No P0/P1 Defects Reproduced)

No P0 or P1 functional or security defects were reproduced on production SHA `1785846a49db27d5931beb596cf64bbbae778f3c`. Four operational behaviors were observed and documented for SIGIR live demo execution:

1. **Research Search Latency (30-paper default):** Full 30-paper scholarly discovery + Excel structuring takes ~55–65 seconds on Vercel serverless cold starts. For the 5-minute SIGIR demo, pre-save a `Dense Passage Retrieval` run (or select a smaller paper count) so the live beat stays well within the 75-second budget.
2. **Per-Account `/api/chat` Rate Limiting:** Rapid back-to-back automated chat runs against the same account can trigger `HTTP 429` within the rate-limit window (verified working as an abuse-protection control). During live rehearsal, avoid spamming automated probes on the presenter account immediately before going on stage.
3. **Research Dossier Hydration Delay:** Navigating directly to `/research/topic?run=<uuid>` shows the `Loading topic...` skeleton briefly while `/api/research/intelligence/runs/<uuid>/dossier` (~186 KB) hydrates; allow 4–8 seconds after cold start.
4. **CSRF Same-Origin Protection Verified:** Cookie-authenticated `POST` endpoints (`/api/research/intelligence/search`, `/api/auth/handoff-ticket`, `/api/library/import`) enforce same-origin `Origin` header validation (`403` when absent), confirming active CSRF protection in production.

---

## 4. Hosted Demo Verdict

**GO — Ready for SIGIR 2027 Live Demo & Video Recording.**

All 6 authenticated journeys pass end-to-end on live production (`1785846a49db27d5931beb596cf64bbbae778f3c`):
- Original PDF bytes (`Vaswani2017`, 2.2 MB, page 2/15) open cleanly from verified citations.
- Real scholarly discovery, durable reload persistence, and `openpyxl`-verified `.xlsx` export (4 sheets, 103 hyperlinks) operate end-to-end.
- Institutional Koha OPAC freshness (`koha_stale: true`) and live `biblionumber` handoff work cleanly.
- Out-of-corpus abstention (`Spanner TrueTime`) produces zero citations and zero fabricated graph edges.
- P0-2 cross-user research isolation (`404` bidirectionally) and RBAC boundaries (`403` student / `200` librarian) are enforced live.
