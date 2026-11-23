# Verified RBAC Matrix — Archipelago Campus Pilot

Every row below is verified directly against the repository's Flask route definitions, middleware guards, and Supabase SQL migrations at baseline `00f38b81351ebaeb5aff2fd36c5e64ea37319524`.

## 1. Institutional Role Hierarchy

Defined in `host_inference/hostapp/config.py:77-80`, `host_inference/hostapp/research_access.py:26-54`, and `supabase/migrations/20260916_000001_auth_roles.sql` + `003_add_faculty_role.sql`:

| Role | Set Membership | Chat Quota | Intended Campus Persona |
|---|---|---|---|
| `anonymous` | None (unauthenticated) | N/A | Public visitor / pre-login browser |
| `student` | `AUTH_ROLES` | **10 queries / rolling hour** (`security.py:57-58`, `chat.py:291-331`) | Enrolled UEM Kolkata student |
| `faculty` | `AUTH_ROLES`, `ELEVATED_ROLES`, `STAFF_ROLES` | Unrestricted (`chat.py:255-256`) | UEM Kolkata teaching & research faculty |
| `librarian` | `AUTH_ROLES`, `ELEVATED_ROLES`, `LIBRARIAN_ROLES`, `MANAGER_ROLES` | Unrestricted | Central Library staff |
| `administrator` | All sets (`allowed()` returns `True` for all `ResearchCapability`) | Unrestricted | Institutional system administrator |

> **Auth Mode Note:** `ARCHIPELAGO_AUTH_REQUIRED` defaults to `True` (`security.py:342-349`). All production campus deployments **must** keep `ARCHIPELAGO_AUTH_REQUIRED=1`.

---

## 2. Primary Hosted App (`host_inference` — `archipelago-blond.vercel.app`)

Legend: `ALLOW` = permitted, `401` = unauthorized, `403` = forbidden, `302` = redirect, `CRON` = requires `Bearer $CRON_SECRET`, `DEFECT` = verified security defect.

### 2.1 Public, Health, Auth & Static Routes

| Route | Method(s) | Guard Source | Anon | Student | Faculty | Librarian | Admin | Notes |
|---|---|---|---|---|---|---|---|---|
| `/`, `/landing`, `/library`, `/login` | GET | `pages.py:49-89` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | Public landing/catalogue/login shells |
| `/chat` | GET | `pages.py:33-47, 54-57` (`AUTH_GATED_PAGES`) | 302 `/login` | ALLOW | ALLOW | ALLOW | ALLOW | Gated when `ARCHIPELAGO_AUTH_REQUIRED=1` |
| `/graph` | GET | `pages.py:59-67` | 302 `/login` | 302 `/chat` | 302 `/academic/graph` | 302 `/academic/graph` | 302 `/academic/graph` | Enforces `ELEVATED_ROLES` |
| `/librarian`, `/analytics`, `/academic/graph`, `/academic-automation`, `/research`, `/index.html` | GET | `analytics.py:195-217`, `pages.py:69-78`, `static.py:98-113` | ALLOW (HTML shell) | ALLOW (HTML shell) | ALLOW | ALLOW | ALLOW | **P2-1**: HTML shells served without redirect; backing APIs enforce auth |
| `/health`, `/ready`, `/api/health`, `/api/readiness` | GET | `config.py:39-40`, `pages.py:91-147` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | Exposes corpus counts & config booleans (no secrets) |
| `/api/auth/config`, `/api/auth/logout` | GET / POST,DELETE | `config.py:34,36`, `routes/auth.py` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | Only publishable key returned |
| `/api/auth/session` | POST / DELETE | `config.py:35`, `routes/auth.py:113-152` | 401 (POST) / ALLOW (DEL) | ALLOW | ALLOW | ALLOW | ALLOW | Validates redirect target + rotates CSRF |
| `/api/auth/me` | GET | `middleware.py:256`, `routes/auth.py:229-252` | 401 | ALLOW | ALLOW | ALLOW | ALLOW | Returns principal + CSRF token |
| `/api/auth/handoff-ticket` | POST | `routes/auth.py:158-186` | 401 | 403 | ALLOW | ALLOW | ALLOW | Staff-only (`ELEVATED_ROLES`), origin-bound |
| `/api/auth/handoff-redeem` | POST | `config.py:37`, `routes/auth.py:188-227` | Ticket-gated | Ticket-gated | Ticket-gated | Ticket-gated | Ticket-gated | Single-use, 60s TTL (**P1-1**: in-memory only) |

### 2.2 Student Chat, Graph & Reader Routes

| Route | Method(s) | Guard Source | Anon | Student | Faculty | Librarian | Admin | Notes |
|---|---|---|---|---|---|---|---|---|
| `/api/chat` | POST | `middleware.py:256`, `routes/chat.py:268-499` | 401 | ALLOW (10/hr) | ALLOW | ALLOW | ALLOW | Research-run enrichment restricted to `_RESEARCH_STAFF_ROLES` (`chat.py:136, 354`) |
| `/api/chat/quota` | GET | `middleware.py:256`, `routes/chat.py:250-261` | 401 | ALLOW | ALLOW | ALLOW | ALLOW | Non-students receive `{"unrestricted": true}` |
| `/api/chat/history` | DELETE, POST | `middleware.py:256`, `routes/chat.py:546-569` | 401 | ALLOW (self) | ALLOW (self) | ALLOW (self) | ALLOW (self) | **P1-2**: Clears single-instance RAM + SQLite only |
| `/api/chat/diagnostic-mcqs`, `/api/chat/adaptive-step`, `/api/chat/telemetry`, `/api/roadmap`, `/api/quiz` | GET / POST | `middleware.py:256`, `routes/chat.py` | 401 | ALLOW | ALLOW | ALLOW | ALLOW | Protected by `_is_protected_api` |
| `/api/graph/hubs`, `/api/graph/page`, `/api/graph/subgraph`, `/api/metrics/cache` | GET | `middleware.py:256`, `routes/graph.py`, `pages.py:149` | 401 | ALLOW | ALLOW | ALLOW | ALLOW | Protected by `_is_protected_api` |
| `/api/library/data`, `/api/library/koha`, `/api/reply-templates` | GET | `config.py:41-43`, `routes/library.py`, `analytics.py:218` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | Public catalogue/OPAC snapshot metadata |
| `/api/library/paper-evidence/<key>`, `/api/catalog/all`, `/api/page-view`, `/api/reader/info` | GET / POST | `middleware.py:256`, `routes/library.py`, `reader.py` | 401 | ALLOW | ALLOW | ALLOW | ALLOW | Protected by `_is_protected_api` |
| `/open/<book_id>`, `/papers/<doc_path>`, `/read` | GET | `middleware.py:257`, `routes/reader.py` | 401 | ALLOW | ALLOW | ALLOW | ALLOW | Pearson handoff & HF PDF streaming |
| **`/pdfs/<doc_path>`** | **GET** | **`reader.py:177` (MISSING in `middleware.py:257`)** | **DEFECT (ALLOW)** | ALLOW | ALLOW | ALLOW | ALLOW | **P0-1**: Unauthenticated & un-rate-limited private HF PDF stream |
| **`/read/<subpath>`** | **GET** | **`reader.py:117` (MISSING in `middleware.py:257`)** | **DEFECT (ALLOW)** | ALLOW | ALLOW | ALLOW | ALLOW | **P0-1**: Bypasses `path == "/read"` check |

### 2.3 Librarian, Analytics, Ingestion & Automation Routes

| Route | Method(s) | Guard Source | Anon | Student | Faculty | Librarian | Admin | Notes |
|---|---|---|---|---|---|---|---|---|
| `/api/ingest/capabilities` | GET | `config.py:38`, `ingest.py:44-55` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | Read-only capability flags |
| `/api/ingest`, `/api/ingest/<job_id>`, `/api/ingest/index` | GET, POST | `middleware.py:243-253`, `ingest.py` | 401 | 403 | 403 | ALLOW | ALLOW | Enforces `LIBRARIAN_ROLES`; upload disabled unless `ARCHIPELAGO_INGESTION_ENABLED=1` |
| `/api/library/import` | POST | `middleware.py:256`, `library.py:140-150` | 401 | 403 | 403 | ALLOW | ALLOW | CSV holdings import (`LIBRARIAN_ROLES`) |
| `/api/librarian/<record_type>` | GET / POST | `analytics.py:225-245` | 401 | 403 | GET only (POST 403) | ALLOW | ALLOW | `GET`: `ELEVATED_ROLES`; `POST`: `LIBRARIAN_ROLES` |
| `/api/analytics/sources`, `/api/analytics/summary`, `/api/academic-automation/status` | GET | `analytics.py:247-319` | 401 | 403 | ALLOW | ALLOW | ALLOW | `ELEVATED_ROLES` |
| `/api/analytics/events` | POST | `analytics.py:293-307` | 401 | 403 | 403 | ALLOW | ALLOW | `LIBRARIAN_ROLES` |
| `/api/academic-automation/review/<job_id>` & `/decision` | GET / POST | `analytics.py:321-372` | 401 | 403 | 403 | ALLOW (`409` on POST) | ALLOW (`409` on POST) | Rejects `local-dev-token`; `POST` returns `409 workstation_required` |

### 2.4 Research Intelligence, Intake, Graph & Jobs Routes

| Route | Method(s) | Guard Source | Anon | Student | Faculty | Librarian | Admin | Notes |
|---|---|---|---|---|---|---|---|---|
| `/api/research/intake/metrics`, `/api/research/intake/activity` | GET | `config.py:44-45`, `research_intake.py:39-45` | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | Public aggregate counts & recent titles |
| `/api/research/intake/scheduled`, `/api/internal/s5-monitor-tick` | GET | `research_schedule.py:49-58`, `research_intelligence_schedule.py:22-30` | CRON | CRON | CRON | CRON | CRON | Requires `Bearer $CRON_SECRET` (`compare_digest`) |
| `/api/scholarly/snapshot` | GET | `middleware.py:221`, `scholarly.py:73-79` | 401 | 403 | ALLOW | ALLOW | ALLOW | `ResearchCapability.SEARCH` (`STAFF_ROLES`) |
| `/api/research/intake/topics`, `/records`, `/reply`, `/paper-okf/<k>`, `/topic-overview`, `/discover`, `/papers` | GET / POST | `middleware.py:219-242`, `research_intake.py:70-82` | 401 | 403 | ALLOW | ALLOW | ALLOW | `POST /papers` also requires `Authorization: Bearer` |
| `/api/research/intake/college` | POST | `research_intake.py:287-293` | 401 | 403 | 403 | ALLOW | ALLOW | `MANAGER_ROLES` + Bearer required |
| `/api/research/graph/full`, `/subgraph`, `/ingested`, `/papers`, `/export` | GET | `middleware.py:219-242`, `research_projection.py:20-36` | 401 | 403 | ALLOW | ALLOW | ALLOW | `STAFF_ROLES` |
| `/api/research/graph/annotation` | GET / POST | `middleware.py:96-97`, `research_graph.py:59-99` | 401 | 403 | GET only (POST 403) | ALLOW | ALLOW | `POST` requires `EDITOR_ROLES` + Bearer |
| `/api/research/jobs`, `/worker`, `/latest`, `/<id>`, `/<id>/papers`, `/<id>/export` | GET / POST | `middleware.py:114-115`, `research_jobs.py:57-77` | 401 | 403 | ALLOW (own jobs) | ALLOW (all jobs) | ALLOW (all jobs) | Owner-scoped for faculty; manager override for librarian/admin |
| `/api/research/intelligence/search`, `/runs`, `/runs/<id>`, `/graph`, `/xlsx`, `/preview`, `/import` | GET / POST | `middleware.py:229-234`, `research_intelligence.py:144-173` | 401 | ALLOW (own runs) | ALLOW (own runs) | ALLOW (all runs) | ALLOW (all runs) | Students explicitly allowed metadata search & own runs |
| **`/api/research/intelligence/runs/<id>/dossier`** | **GET** | **`research_intelligence.py:336-351`** | 401 | **DEFECT (ANY RUN)** | **DEFECT (ANY RUN)** | ALLOW | ALLOW | **P0-2**: Falls back to `manager=True`, bypassing owner scoping |
| `/api/research/intelligence/monitors*`, `/updates` | GET/POST/PATCH/DEL | `middleware.py:110-111`, `research_intelligence.py:162-166` | 401 | 403 | ALLOW (own) | ALLOW (own) | ALLOW (own) | `MONITOR_ROLES` (`STAFF_ROLES`) |

---

## 3. Secondary Hosted App (`host_research` — `archipelago-librarian.vercel.app`)

Verified against `host_research/app.py:324-550`:
- **Public**: `/`, `/login`, `/api/readiness`, `/api/auth/config`, `/api/auth/logout`, `/api/auth/handoff-redeem`, `/api/library/koha`, static UI shells (`/research*`, `/librarian*`, `/analytics`, `/academic/graph`), and `CRON_SECRET`-gated `/api/research/intake/scheduled`, `/api/library/koha/scheduled`.
- **Authenticated (`verify_user`)**: `/api/auth/me`, `/api/auth/session`, `/api/auth/handoff-ticket`, `/api/graph/*`, `/api/research/*`, `/api/analytics/*`, `/api/academic-automation/*`.
- **Role-gated**: `/api/library/opac/live` (`faculty`, `librarian`, `administrator`, line 508); `/api/librarian/<record_type>` (`GET`: `faculty`/`librarian`/`administrator`; `POST`: `librarian`/`administrator`, lines 458-464).

---

## 4. Supabase Database RLS & RPC Boundary

Verified against `supabase/migrations/20261118000000_prelaunch_rls_and_privilege_hardening.sql`:
- **RLS enabled** on `profiles`, `credential_import_permissions`, `credential_import_audits`, `retrieval_cache`, `graph_cache`, `ai_response_cache`, `role_page_permissions`, `archipelago_librarian_records`, `archipelago_runtime_quota`, `research_intelligence.*`.
- **`PUBLIC` / `anon` / `authenticated` revoked** from all server-only tables and the entire `research_intelligence` schema (`lines 81-145`).
- **`SECURITY DEFINER` RPCs** (`research_enqueue_job`, `s5_research_rpc`) enforce `SET search_path = pg_catalog, ...` and runtime `service_role` verification (`lines 157-169, 219-239`).
