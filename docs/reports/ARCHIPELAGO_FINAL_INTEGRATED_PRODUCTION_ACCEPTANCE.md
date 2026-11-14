# ARCHIPELAGO — FINAL INTEGRATED INTELLIGENCE, LIVE UEM OPAC, USER QUOTAS & VERIFIED PRODUCTION ACCEPTANCE

**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Active Code Commit:** `9fe796d28355f1c9a63163564f316dc30c127c55`  
**Main Production Target:** `https://archipelago-blond.vercel.app/`  
**Active Main Production Deployment:** `https://vercel.com/archipelago-6383/archipelago/9PqvwqujfBb3brx1bcvJU2Zuoyvq` (promoted from `https://archipelago-ox3yxpgyb-archipelago-6383.vercel.app`)  
**Rollback Reference Deployment:** `https://vercel.com/archipelago-6383/archipelago/HB9cw6TonpwEQoLcifZwEMPuu24r` (prior `archipelago-lqs7nreqc` build)  
**Librarian Production Target:** `https://archipelago-librarian.vercel.app/` (separate Vercel team `shinaura`)  
**Supabase Project:** `spllaastejfwclllfndp`  

---

## 1. Executive Release Verdict

**Verdict: `ARCHIPELAGO CONDITIONALLY RELEASED`**

All code, database migration (`student_rolling_hour_quota`), RBAC, live UEM OPAC verification, Academic Chat routing, Academic Graph provenance, Quiz randomization/scoring, 14-sheet Excel cross-sheet integrity, mobile analytics layout, and 10-query rolling-hour Student Chat quota requirements are **implemented, verified live on `https://archipelago-blond.vercel.app/`, and passing (`107 passed` + `ruff check` clean)**.

**Reason for `CONDITIONALLY RELEASED` (two non-bypassable external boundaries):**
1. **`https://archipelago-librarian.vercel.app/` (`shinaura` team)**: Hosted on a separate Vercel team/project outside `archipelago-6383`. The hardened `host_research/app.py` role checks and responsive `host_research/ui/analytics.html` fixes are committed and pushed (`9fe796d`), awaiting deployment on `shinaura`.
2. **S4 Candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe`**: Intentionally kept **`BLOCKED`** (`publication_status: BLOCKED`, `decision: None`) pending independent human scientific sign-off on the local library workstation.

---

## 2. Deployment & Infrastructure Matrix (Phase 1)

- **Main Production (`https://archipelago-blond.vercel.app/`)**:
  - Deployment: `9PqvwqujfBb3brx1bcvJU2Zuoyvq` (built from `host_inference/` at `9fe796d`).
  - `/api/readiness`: `200 OK`, `mode: "inference-only"`, `concepts: 610`, `corpus: {"concepts": 610, "full": true, "source": "full"}`, `graph_version: "9818ac0e8fd3"`, `pearson_books: 40`, `cache: "supabase"`, `research_intelligence: {"durable_storage_configured": true, "runtime_packaged": true}`.
  - `/api/research/intelligence/readiness`: `200 {"ready": true}`.
  - `/api/library/data`: `91` shelf items (`40` Pearson e-books + `51` Hugging Face dataset items), `109` Koha holdings (`holdings_status: "koha_export"`).
- **Supabase Migrations (`spllaastejfwclllfndp`)**:
  - Baseline 19 migrations (`003_add_faculty_role.sql` through `20261114020000_s6_rpc_service_role_guc_fix.sql`) + new additive migration `20261114030000_student_rolling_hour_quota.sql` (`apply_migration` -> `{"success": true}`).
- **Environment Variable Scope (presence only, no secret values)**:
  - Vercel `archipelago-6383/archipelago` (Production & Preview): `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `ARCHIPELAGO_AUTH_REQUIRED`, `ARCHIPELAGO_ENV`, `ARCHIPELAGO_INGESTION_ENABLED`, `ARCHIPELAGO_RESEARCH_DATABASE_URL`, `ARCHIPELAGO_S5_SCHEDULER_ENABLED`, `CRON_SECRET`, `HF_TOKEN`, `HF_DATASET_REPO`, `XKIRO_API_KEY`, `NVIDIA_API_KEY`, `NARA_API_KEY`.
- **Data Flow**:
  `Browser -> host_inference (archipelago-blond.vercel.app) -> Supabase Auth (/auth/v1/user) & PostgREST/RPC (profiles, quota_events, s5_research_rpc) + HF/Pearson + LLM (XKIRO/NVIDIA/NARA) <-> host_research (archipelago-librarian.vercel.app) -> UEMK OPAC (https://uemk-opac.l2c2.co.in/)`.

---

## 3. Live UEM Kolkata OPAC Verification (Phase 2)

Tested directly against `https://uemk-opac.l2c2.co.in/` via `host_research/opac_live.py` on `2026-11-14T12:03:29Z–12:04:06Z` (all 5 queries succeeded with live HTML parsing, zero fabricated fields):

1. **Operating Systems** (`13` page-1 results):
   - `biblionumber=576` | `OPERATING SYSTEMS` | `NUTT, NEOGY` | `Pearson` | Call `005.43 NEO` | `Department of CSE Library`, `UEM Kolkata Central Library` | `2/2` `Available` (barcodes `7976`, `7977`) | `https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber=576`
   - `biblionumber=583` | `OPERATING SYSTEMS` | `WILLIAM STALLINGS` | `Pearson` | Call `005 STA` | `UEM Kolkata Central Library` (`Available`, `8105`), `Department of CSE (IOT, CYS, BCT) Library` (`Not For Loan`, `8106`) | `1/2` `Available`
2. **Database Management Systems** (`5` results):
   - `biblionumber=1116` | `Database management systems` | `R.Pannerselvam` | `PHI Learning Pvt. Ltd.` | Call `004 PAN` | `UEM Kolkata Central Library` | `Not For Loan` (`0/1` Available, `10343`)
   - `biblionumber=3678` | `Introduction to Database Management Systems` | ISBN `9788131700785` | `Pearson` | Call `005.74 KAH` | `UEM Kolkata Central Library` | `Not For Loan` (`0/2` Available, `34816`, `34817`)
3. **Machine Learning** (`20` page-1 results):
   - `biblionumber=4131` | `Statistics for Machine Learning...` | `Singh, Himanshu` | ISBN `9789388511971` | `BPB Publications` | `2024` | Call `006.37 SIN` | `UEM Kolkata Central Library` | `3 Available` (`38121`–`38123`), `1 Not For Loan` (`38124`)
   - `biblionumber=1591` | `Machine learning` | `Clarence chio` | `Shroff Publishers` | `2018` | `Department of CSE (AIML) Library` | `1/1` `Available` (`23001`)
4. **Computer Networks** (`17` results):
   - `biblionumber=2122` | `Computer Networks` | `Tanenbrum,A.S` | Call `004.6 TAN` | `Department of CST, CSIT Library` | `Not For Loan` (`0/1`, `GIFT295`)
   - `biblionumber=1434` | `Computer Networking A Top-Down approach` | `Kurose, James F` | ISBN `9789356061316` | `Pearson` | `2025` | Call `004 KUR` | `0/5` Available (`2 Checked out`, `3 Not For Loan`)
5. **Data Structures** (`20` page-1 results):
   - `biblionumber=4048` | `A practical approach to data structures and algorithms` | `Pahuja, Sanjay` | ISBN `9788122428049` | `2018` | Call `005 PAH` | `Not For Loan` (`0/1`, `GIFT892`)
   - `biblionumber=4535` | `Data Structures and Algorithms Using C` | `Salaria, R.S` | ISBN `9789392549205` | Call `005.73 SAL` | `1/1` `Available` (`GIFT1009`)

### Live-vs-Snapshot Usage Matrix

| Surface | Source Mode | Notes |
|---|---|---|
| 1. Library Details (`/library`, `/api/library/data`) | `KOHA_EXPORT_SNAPSHOT` / CSV Import | `koha_export` (`109` rows) + `91` e-books |
| 2. Academic Chat (`/api/chat`) | `INDEXED_ACADEMIC_DOCUMENT` + `CATALOG_SHELF_ROUTING` | No unnecessary live OPAC scraping per chat turn |
| 3. Faculty/Librarian Dashboard (`/librarian`) | `LIVE_OPAC` with `KOHA_EXPORT_SNAPSHOT` fallback | Calls `/api/library/opac/live` (`403` for students) |
| 4. Academic Source Discovery (`discovery.py`) | `LIVE_OPAC` | Reconciles `opac_live:<biblionumber>` |
| 5. Academic Ingestion Proposals (`ingest_proposals.py`) | Advisory Queue (No Live OPAC) | `toc_only` default, no auto-mutation |
| 6. Academic Concept Graph References (`/academic/graph`) | Hybrid (`KOHA_EXPORT_SNAPSHOT` + `LIVE_OPAC`) | Snapshot via `/api/library/koha`; live search for staff |
| 7. Search Results / Holdings | Split | Public table = Snapshot; Staff live lookup = `LIVE_OPAC` |
| 8. Analytics / Inventory Summaries | `KOHA_EXPORT_SNAPSHOT` | `load_koha_snapshot()` + staff records + events |

---

## 4. Academic Chat, Graph, Quiz & Personalized Learning (Phases 3, 4, 5)

- **Library Routing Fixes (`host_inference/engine/route_logic.py`)**:
  - Verified live on `https://archipelago-blond.vercel.app/`:
    - `"Is Operating System Concepts available in the UEM library?"` -> `200`, `route: CATALOG_SHELF_ROUTING` (previously `GUARDRAIL_INTERCEPT`).
    - `"Do you have books about machine learning?"` -> `200`, `route: CATALOG_SHELF_ROUTING` (previously `GRAPH_SYNTHESIS`).
    - `"Explain deadlock and show relevant library resources."` -> `200`, `GRAPH_SYNTHESIS` with `Bankers Algorithm` related concept (previously `MULTI_CONCEPT` treating `"show relevant library resources"` as an unindexed concept).
    - Follow-up `"What is the call number of this book?"` resolves prior topic from `(Earlier user topics: ...)` into `CATALOG_SHELF_ROUTING`.
  - No fictional rack numbers, copy counts, or synthetic fallback graph edges emitted.
- **Academic Graph Provenance (`host_inference/hostapp/routes/graph.py`)**:
  - Verified live: `GET /api/graph/subgraph?q=deadlock` returns `11/11` edges with `source_ref` populated.
- **Quiz Randomization & Scoring (`host_inference/engine/diagnostics.py`, `15-submit-adaptive-answer.js`)**:
  - Verified live: `GET /api/chat/diagnostic-mcqs?concept=deadlock` returns `['D', 'D']` (deterministic SHA-256 option placement instead of hardcoded `'A'`).
  - Frontend fallback `passed` (`correctCount >= 3`) and `full_score` (`correctCount === asked`) aligned with backend `diagnostics.py`.
  - Personalized quiz progress (`3/4`, `passed: true`) verified isolated per student `principal["id"]`.

---

## 5. Student 10-Query Rolling-Hour Chat Quota & Unlimited Staff Quotas (Phase 6)

Implemented across `supabase/migrations/20261114030000_student_rolling_hour_quota.sql`, `host_inference/hostapp/security.py`, `host_inference/hostapp/routes/chat.py`, `ui/chat/`, and `host_inference/ui/js/`:

- **Live Production Test (`https://archipelago-blond.vercel.app/`, ephemeral student accounts)**:
  - Queries `1..10`: All `10` returned `200 OK` with `X-Queries-Used: 1..10` and `X-Queries-Remaining: 9..0`.
  - Query `11`: Returned **`429`** with JSON:
    `{"detail": "Hourly chat limit reached (10/10). You can ask another question after 13:20 UTC.", "error": "query_limit", "limit": 10, "remaining": 0, "reset_at": "2026-11-14T13:20:26.944822+00:00", "retry_after": 3567, "used": 10}`.
  - Independent Student 2: Returned `200 OK`, `X-Queries-Used: 1`.
  - Replayed `request_id`: Returned **`409 duplicate_request`** without double-charging.
  - Faculty / Librarian / Administrator: Unlimited per-account chat quota (`200 OK`), while global IP burst rate limits (`429`) remain active.
  - Automated Quota + UI Link Tests: `21 passed in 1.61s` (including 15-thread concurrency and 3600s window recovery).

---

## 6. S4 Academic Ingestion & Approval Boundary (Phase 7)

- 10-step S4 workflow verified end-to-end (`tests/integration/test_s4_academic_dashboard.py` + `test_s6_platform_integration.py`: `9 passed`).
- Candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` (`opac_live:4150`, `rights: open_permitted`) remains `status: review_ready`, `decision: None`, **`publication_status: BLOCKED`**.
- Hosted `POST /api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe/decision` rejects anonymous (`401`), student/faculty (`403`), `local-dev-token` (`401`/`403`), and returns `409 workstation_required` / `publication_status: BLOCKED` for verified librarians.

---

## 7. Research Intelligence, Graph & 14-Sheet Excel Validity (Phase 8)

- Validated `Archipelago_Edge_SLM_Research_Report_FINAL.xlsx` (`22` papers, `14` sheets): `22/22` unique Paper IDs, `99/99` unique Author IDs, `17/17` unique Venue IDs, `20/20` valid DOIs, `22/22` populated URLs, `74` `Research_Claims` with `Exact Evidence`, `394/394` numeric `Metric_Observations`, and explicit sparsity codes (`NOT_FOUND_IN_AVAILABLE_EVIDENCE`, `IDENTITY_UNRESOLVED`, `LICENSE_RESTRICTED`, `PROVIDER_FIELD_ABSENT`).
- Fixed 2 cross-sheet defects in `archipelago/scholarly/intelligence/workbook_extra.py`: `Institutions_Affiliations` now includes `author["institutions"]` (`29/29` matching `Run_Manifest`) and formats `Linked Author IDs` as `author:<short_id>` matching `Authors[Author ID]`.
- Live Research Intelligence on `https://archipelago-blond.vercel.app/`: `POST /api/research/intelligence/search` (`"graph neural networks"`, `top_k=5`) -> `200` (`run_id=414e5c2e-7c7e-4e23-abd9-87e8dc377a27`), `GET .../graph` -> `schema=archipelago.scholarly_graph.v1` with `0` `REQUIRES`/`UNLOCKS` edges, `GET .../xlsx` -> `200` (`36293` bytes), Research Chat -> `200` (`route=RESEARCH_EVIDENCE`, `graph_mode=research`).

---

## 8. Security, Performance, Regression & Browser Acceptance (Phases 10–12)

- **Security & Roles**: 5-role matrix verified (`anon`, `student`, `faculty`, `librarian`, `administrator`), tampered/`alg:none` JWTs rejected (`401`/`403`), all 6 Supabase RPCs reject `anon`/`student` (`401`/`403`/`404`), CORS rejects `evil.example.com`, CSP updated with `font-src 'self' data: ...`, and `host_research/app.py` hardened with `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy`.
- **Latencies (`https://archipelago-blond.vercel.app/`)**: `/api/readiness` p50 `588.7 ms` / p95 `9492.2 ms` (cold-start tail), `/api/graph/hubs` p50 `2934.1 ms` / p95 `13017.8 ms`, `/api/research/intelligence/runs` p50 `3391.7 ms` / p95 `3560.6 ms`, `/api/chat` p50 `2904.7 ms` / p95 `4024.2 ms`.
- **Integrated Regression Suite**: `ruff check` **All checks passed**; `pytest` across 14 unit/integration files: **107 passed in 28.48s**.
- **Playwright (`1440×960` & `390×844`)**: Fixed mobile `/analytics` horizontal overflow (`scrollWidth: 390 == innerWidth: 390`, `overflowX: false`); refreshed `artifacts/validation/final-ui-audit/Archipelago_Final_UI_Audit.zip`.
