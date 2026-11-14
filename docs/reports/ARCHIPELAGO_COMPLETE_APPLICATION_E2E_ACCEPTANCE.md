# Archipelago — Complete Application End-to-End Acceptance & Release Report

**Date:** 2026-11-14  
**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Base Release Code Audited:** `aaa15b83db96f82d9c4a475f3d7f494381259bf5`  
**E2E Fixes Committed:** `1d61c75baad1c91ce63c9606123a17c46142272b` + `_inventory_answer` multi-turn context strip in `host_inference/hostapp/research_chat.py`  
**Protected Vercel Preview (`archipelago-6383`):** [`https://archipelago-6bbuz5wf5-archipelago-6383.vercel.app`](https://archipelago-6bbuz5wf5-archipelago-6383.vercel.app) (Deployment ID: `9TcimwYbxLLpZY8KjSDpGAgD5vcZ`; prior preview: `2FNRhCDAidr5vEwK7yoV9mgScTtG`)  
**Current Production Domain (`https://archipelago-blond.vercel.app/`):** `5FjVNLvksWfJGzhyj7FNWTgDJM8z` (`200 OK`, `610` concepts, graph `9818ac0e8fd3`; pre-patch commit `4b19d30`, awaiting authorized promotion)  
**Librarian Application (`https://archipelago-librarian.vercel.app/`):** `200 OK` (`{"ready":true,"service":"research_transport"}`; `shinaura` promotion remains external gate)  
**Overall Verdict:** **`ARCHIPELAGO CONDITIONALLY RELEASED`**

---

## 1. Component Acceptance Matrix

| Component | Verdict | Evidence Summary |
|---|---|---|
| Release Candidate & 15-Paper Reconciliation | **PASS** | `aaa15b8` + `1d61c75`; papers 1–10 reconciled in 22-paper Topic A workbook, papers 11–15 reconciled in 8-paper Topic B run |
| Academic Chat (10 Questions + 4-Turn) | **PARTIAL** | Q2, Q3, Q4, Q6, Q8, Q10 grounded in indexed PDFs/Kùzu; Q1 missed SJF example; Q7 returned tautological fallback; Q5/Q9/multi-turn research hijacking fixed in `1d61c75` + `_inventory_answer` strip |
| Research Chat (10 Questions, Preview) | **PASS** | All 10 questions `200 OK` on `9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3` including R8 provider provenance & R10 monitoring changes (`9TcimwYbxLLpZY8KjSDpGAgD5vcZ`) |
| Academic Pipeline, OPAC & 610-Concept Graph | **PASS** | `/api/graph/hubs` (`610` concepts, `68` docs, `1988` edges), `/api/graph/subgraph?q=virtual+memory` (`REQUIRES`/`UNLOCKS`), Koha `109` holdings / `1212` journal issues |
| Academic Automation (S4 Review Gate) | **PASS / GATED** | `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` remains `job_review_ready` / protected; student receives `403` |
| Research Intelligence & 14-Sheet Excel | **PASS** | Topic A `22` papers, Topic B `8` papers, `115,401`-byte 14-sheet `.xlsx` (`42` hyperlinks, `fk_claims_valid=True`) |
| UI Pages & Visual Acceptance (1440×960 & 390×844) | **PARTIAL** | `17/18` screenshots `PASS` (`200`, `ov=False`); `14e_mobile_analytics.png` `FAIL` (`ov=True` horizontal overflow at `390px`) |
| Library Analytics & Unavailable Turnstiles | **PASS** | `/api/analytics/sources` & `/summary` `200` for librarian, `403` for student; turnstiles & QR gates explicitly report `"Data source not connected"` |
| Security, Role Isolation & Cron Auth | **PASS** | Unauth/bad JWT `401`; student on staff endpoints `403`; cross-user run/xlsx `404`; cron endpoints `401` without `CRON_SECRET` |
| Production Vercel Release | **BLOCKED (Operator Gate)** | `npx vercel --prod --yes` blocked by pre-tool security hook; requires authorized `archipelago-6383` promotion + `shinaura` librarian promotion |

---

## 2. Phase 1 — Release Candidate & 15-Paper External Audit Reconciliation

- **Workbook (`Archipelago_Edge_SLM_Research_Report_FINAL.xlsx`):** `22` unique Topic A papers (`115,401` bytes, `14` sheets).
- **Reconciliation of the 15-Paper External Audit:**
  - **Papers 1–10** (`10.21203/rs.3.rs-11378808/v1` through `10.23939/acps2025.02.233`): all `10/10` matched directly by `Paper ID` and `DOI` inside the 22-paper Topic A workbook (`in_wb=True`).
  - **Papers 11–15** (`10.14419/nb420z19`, `10.1016/j.jmps.2025.106152`, `10.1137/23m1609786`, `10.1002/mgea.50`, `10.1016/j.jcp.2023.112537`): all `5/5` belong to **Topic B** (`Graph Neural Networks for Scientific Machine Learning`, 8-paper collection) rather than the Topic A-only workbook, explaining why they were absent from the Topic A workbook while matching `crossref_rest_api` `title`, `year`, and `authors_count` (`15/15` verified externally: `13/15` `VERIFIED`, `2/15` `PARTIAL`).

---

## 3. Phase 2 — Real Chat UI Transcripts & Quality Assessment

### Academic Chat (10 Questions via `/chat`, Desktop `1440×900`, Student Session)
| # | Prompt | HTTP / Latency | Quality Assessment |
|---:|---|---|---|
| 1 | Explain FCFS vs SJF CPU scheduling, with an example. | `200` / `6,703 ms` | **PARTIAL** — Defined `CPU Scheduling` (`operating_system_concepts_silberschatz.pdf` p.185) but parsed `"Explain FCFS"` as unindexed and omitted SJF example. |
| 2 | Explain virtual memory and page replacement. | `200` / `5,509 ms` | **PARTIAL** — Accurately defined `Virtual Memory` (`06_Address_Spaces.pdf` p.1) but omitted page replacement. |
| 3 | Explain ACID properties and database normalization. | `200` / `8,426 ms` | **PARTIAL** — Accurately defined `ACID Properties` (`database_system_concepts_silberschatz.pdf` p.630) but omitted normalization. |
| 4 | Explain TCP congestion control. | `200` / `4,908 ms` | **PASS** — Accurate Slow Start / Congestion Avoidance / Fast Retransmit / Fast Recovery (`computer_networks_tanenbaum.pdf` p.545). |
| 5 | Explain Dijkstra's algorithm and its limitations. | `200` / `5,372 ms` | **FAIL (Pre-fix) → FIXED** — Initially substituted unrelated saved papers (`Wombat Optimization`). After `1d61c75`, returns clean out-of-corpus scope guardrail on preview `9TcimwYbxLLpZY8KjSDpGAgD5vcZ`. |
| 6 | Explain lexical analysis and LR parsing. | `200` / `5,001 ms` | **PARTIAL** — Accurately defined `Lexical Analysis` (`compilers_principles_techniques_tools_aho.pdf` p.109) but omitted LR parsing. |
| 7 | Explain eigenvalues and eigenvectors. | `200` / `4,696 ms` | **FAIL** — Returned tautological 1-liner (`"Eigenvalues And Eigenvectors is a fundamental concept. Source 1 · page unverified"`). |
| 8 | Explain gradient descent and backpropagation. | `200` / `4,972 ms` | **PARTIAL** — Defined `Gradient Descent` (`Index_2019_Data-Science.pdf` p.4), omitted backpropagation, appended research citations. |
| 9 | Explain distributed systems consistency models. | `200` / `4,979 ms` | **FAIL (Pre-fix) → FIXED** — Initially substituted saved papers (`Calvin`, `Young tableaux`). Fixed by `1d61c75` guardrail isolation. |
| 10 | What is the difference between supervised and reinforcement learning? | `200` / `6,660 ms` | **PASS** — Reported `Reinforcement Learning` prerequisites/unlocks + `Rafailov2023_DPO.pdf` p.2 and honestly refused to invent a bridge to unindexed `supervised`. |

### Multi-turn Academic Chat (`M1–M4`)
- `M1` (`"Explain virtual memory."`) → **PASS** (`07_Address_Translation.pdf` p.2).
- `M2–M4` (`"What causes thrashing?"` → `"How does the working-set model help?"` → `"Give me a simple example."`) → Initial run lost context and triggered `research_chat.py` / `_inventory_answer()`. Fixed via `conversation.py` (`FOLLOW_UP` expansion) and `research_chat.py` (`_inventory_answer` stripping `(Earlier user topics: ...)` + `RESEARCH_SOURCE_REQUEST` guard).

### Research Chat (10 Questions on `9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3`, Protected Preview)
- `R1` (`Show the collected papers.`) → `200` (`8,882 ms`), `22` papers ordered `publication_date_desc`.
- `R2` (`Which papers discuss quantization?`) → `200` (`8,613 ms`), `7/22` papers with exact/synonym snippets.
- `R3` (`Which discuss low-memory inference?`) → `200` (`8,814 ms`), `3/22` papers (`memory footprint`, `memory-efficient`, `ram`).
- `R4` (`What datasets are explicitly mentioned?`) → `200` (`8,106 ms`), literal methods/metrics (`none stated in the available abstract` when absent).
- `R5` (`Who authored the first paper?`) → `200` (`8,826 ms`), `PRIYANKA AGAVAN (Sanjivani University)` + DOI link.
- `R6` (`What verified author metrics are available?`) → `200` (`8,013 ms`), honestly reports h-index unavailable without provider-linked ID.
- `R7` (`Which papers cite other papers in this collection?`) → `200` (`9,228 ms`), `[7] cites [22]`, `[14] cites [22]`, `[14] cites [21]` (`openalex`).
- `R8` (`Which providers contributed these results?`) → Fixed in `1d61c75`; verified `200` on `9TcimwYbxLLpZY8KjSDpGAgD5vcZ` listing `openalex (33)`, `semantic_scholar (rate_limited 429)`, `arxiv (25)`, `dblp (blocked_bot_challenge 202)`, `crossref (48)`.
- `R9` (`Export this collection to Excel.`) → `200` (`9,091 ms`), `/api/research/intelligence/runs/9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3/xlsx (22 papers)`.
- `R10` (`What changed in monitoring?`) → Fixed in `1d61c75`; verified `200` on `9TcimwYbxLLpZY8KjSDpGAgD5vcZ` listing newly indexed papers from `2026-11-14T09:13:43Z–44Z`.

---

## 4. Visual Evidence Index & Delivered Screenshots

- **Screenshot Directory:** `artifacts/validation/final-full-app/browser/`
- **Visual Evidence Index:** [`visual_evidence_index.json`](file:///home/pratay-karali/Desktop/archipelago/Archipelago/artifacts/validation/final-full-app/visual_evidence_index.json)
- **Screenshot ZIP Archive (`6,997,954` bytes):** [`archipelago_browser_screenshots.zip`](file:///home/pratay-karali/Desktop/archipelago/Archipelago/artifacts/validation/final-full-app/archipelago_browser_screenshots.zip) (Artifact copy: [`archipelago_browser_screenshots.zip`](file:///home/pratay-karali/.gemini/antigravity/brain/b239371b-36c1-4fa5-bf52-2d4b7a7e35b9/archipelago_browser_screenshots.zip))
- **Summary:** `17/18` captured views `PASS` (`HTTP 200`, `horizontal_overflow=False` across `1440×960` desktop and `390×844` mobile); `1/18` (`14e_mobile_analytics.png`) `FAIL` (`horizontal_overflow=True` at `390×844`).

---

## 5. Security, Analytics, Cron & Regression Results

- **Security & Role Isolation (Protected Preview):**
  - Unauthenticated `/api/auth/me`: `401` | Invalid JWT: `401`
  - Unauthenticated `/api/research/intelligence/search`: `401`
  - Student on `/api/analytics/summary`: `403` | Student on `/api/academic-automation/status`: `403` | Student on `/api/research/intelligence/monitors`: `403`
  - Cross-user isolation (Student querying Librarian `run_id` `9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3` and `/xlsx`): `404` on both
  - Cron endpoints without `CRON_SECRET` (`/api/internal/s5-monitor-tick`, `/api/research/intake/scheduled`): `401 {"error":"unauthorized"}`
- **Analytics & Koha:** `/api/analytics/sources` (`200`, `demo_isolated: true`, physical entry/exit & QR attendance `"Data source not connected"`); Koha snapshot (`109` holdings, `1212` journal issues).
- **Cron Schedule (`host_inference/vercel.json`):** `0 3 * * *` (`/api/research/intake/scheduled`) and `0 4 * * *` (`/api/internal/s5-monitor-tick`); persisted monitor history shows live event execution at `2026-11-14T09:13:44Z`.
- **Automated Regression Suite (post-final edit):** `ruff check` → `All checks passed!`; `pytest` across 6 suites → **`53 passed in 14.14s`**.

---

## 6. Issue Register & Rollback Reference

- **Resolved in `1d61c75` + final `_inventory_answer` fix:**
  - **P1:** Academic `GUARDRAIL_INTERCEPT` queries (`Q5`, `Q9`) hijacked into unrelated saved papers (`research_chat.py`).
  - **P1:** Multi-turn follow-up regex (`conversation.py`) & `(Earlier user topics: ...)` triggering `_inventory_answer()` (`research_chat.py`).
  - **P1:** Research Chat `R8` (provider provenance) & `R10` (monitoring changes) (`research_run_chat.py`).
  - **P2:** FontAwesome CSP `font-src` console errors (`middleware.py`).
- **Open / Outstanding Issues:**
  - **P1:** Academic Q7 (`"Explain eigenvalues and eigenvectors."`) returns tautological 1-liner; Q1/Q2/Q3/Q6/Q8 multi-part questions only answer the first indexed concept.
  - **P2:** `14e_mobile_analytics.png` still exhibits `horizontal_overflow=True` at `390px` width.
  - **External Gates:** Production promotion to `https://archipelago-blond.vercel.app/` (operator command: `npx vercel promote https://archipelago-6bbuz5wf5-archipelago-6383.vercel.app --yes`), `shinaura` librarian promotion, and S4 independent human review of `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe`.
- **Rollback Reference:** Current active production deployment `5FjVNLvksWfJGzhyj7FNWTgDJM8z` (`4b19d30`).
