# ARCHIPELAGO S6 — FINAL PLATFORM INTEGRATION, LIVE ANALYTICS, PRODUCTION AUDIT & RELEASE FREEZE

**Date:** 2026-11-14  
**Branch:** `feature/s6-final-platform-integration` (branched from verified S5 baseline `0d55a498d7bfeb345c9ac7f289d060c07ce4791b`)  
**Release Commit:** `a667b81` (+ this final acceptance report)  
**Target Applications:**
- Main Backend & Application: `https://archipelago-blond.vercel.app` (Vercel deployment `https://archipelago-4ylz59rto-archipelago-6383.vercel.app`, team `archipelago-6383`, project `prj_yVvxBExHYiLa67oqnABK2vW9FfCS`)
- Protected Preview Tested: `https://archipelago-ftw7igv2j-archipelago-6383.vercel.app`
- Librarian Application: `https://archipelago-librarian.vercel.app` (`host_research/`, owned by external `shinaura` Vercel team)
- Supabase Project: `spllaastejfwclllfndp`

---

## 1. Phase 0 — Verified Release Baseline Matrix

| Component | Verified Baseline | Notes |
| --- | --- | --- |
| **Git S5 Baseline** | `feature/s5-research-intelligence` (`0d55a498d7bfeb345c9ac7f289d060c07ce4791b`) | `main` and `session3-stable` were older baselines; `feature/s6-final-platform-integration` was branched directly from `0d55a498`. |
| **Main Production App** | `https://archipelago-blond.vercel.app` (`archipelago-6383/archipelago`) | Updated in S6 to `https://archipelago-4ylz59rto-archipelago-6383.vercel.app` (`Ready in 25s`). |
| **Librarian Production App** | `https://archipelago-librarian.vercel.app` (`shinaura` team) | `host_research/` code & UI updated in git, but CLI credentials only have access to `archipelago-6383` (`vercel teams ls`). See Section 2 for the exact `shinaura` release action. |
| **Supabase Database** | `spllaastejfwclllfndp` | Applied `20261114010000_s6_library_analytics_and_rpc_hardening.sql` and `20261114020000_s6_rpc_service_role_guc_fix.sql`. |
| **Canonical Knowledge Graph** | `okf_graph.json` (`610` concepts, `1,988` edges, SHA-256 `9818ac0e8fd3...`) | Synced to Supabase Storage (`archipelago-cache/okf_graph.json`, `6,489,729` bytes); verified on live `/api/readiness`. |
| **S4 Academic Staging** | Candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` | `publication_status: "BLOCKED"` awaiting independent human review. Preserved intact. |

---

## 2. Phase 1 — Main & Librarian Platform Integration

### Implemented Routes & UI Surfaces
- **Main Application (`host_inference`):**
  - `/` (Landing), `/login`, `/chat` (Academic & Research Chat), `/library` (Library Details & OPAC), `/academic/graph` (`host_inference/ui/academic_graph.html`), `/research` & `/research/*` (Research Intelligence & 9-sheet Excel export), `/analytics` & `/librarian/analytics` (`host_inference/ui/analytics.html`), `/academic-automation` (`host_inference/ui/academic_automation.html`), `/librarian` (`host_inference/ui/librarian.html`).
  - Backend API routes added in `host_inference/hostapp/routes/analytics.py`:
    - `GET /api/analytics/sources`
    - `GET /api/analytics/summary`
    - `POST /api/analytics/events`
    - `GET /api/academic-automation/status`
    - `GET /api/academic-automation/review/<job_id>`
    - `POST /api/academic-automation/review/<job_id>/decision`
    - `GET /api/library/koha`, `GET/POST /api/librarian/<record_type>`
- **Librarian Application (`host_research`):**
  - Updated `host_research/app.py` (395 lines) to serve `/analytics`, `/librarian/analytics`, `/academic-automation`, `/academic-automation.html` and proxy `/api/analytics/*` and `/api/academic-automation/*` with authenticated session forwarding to `ARCHIPELAGO_RESEARCH_ORIGIN`.
  - Synced UI shells (`analytics.html`, `academic_automation.html`, `librarian.html`) into `host_research/ui/`.

### Required `shinaura` Team Release Action (External Permission Gate)
`npx vercel teams ls` confirmed the current CLI token is authorized only for `archipelago-6383`. To update `https://archipelago-librarian.vercel.app/` with the S6 `host_research/` build, an authorized `shinaura` team member must run:
```bash
git checkout feature/s6-final-platform-integration
cd host_research
npx vercel deploy --prod --scope shinaura
```

---

## 3. Phase 2 — Real Library Analytics & Source Audit

### Institutional Source Audit
Every institutional feed is audited in `archipelago/scholarly/intelligence/analytics.py`:
- **Connected Sources:**
  - `circulation` (`koha_circulation_sync`): Connected via authorized Koha ODS export (`109` catalog titles, `904` total copies, `901` available copies, `3` checked out) + staff circulation notes.
  - `inventory_activity` (`inventory_audit`): Connected via Koha holdings, subject counts, and journal issues.
- **Unconnected Physical Sources (Honest Missing State):**
  - `physical_entry_exit` (`staff_manual_counter / qr_gate_adapter`): **`"Data source not connected"`**
  - `qr_attendance` (`qr_gate_adapter`): **`"Data source not connected"`**
  - `occupancy` (`staff_manual_counter`): **`"Data source not connected"`**
  - `academic_events` (`academic_event_log`): **`"Data source not connected"`** (until non-demo staff events are recorded)

### Privacy-Preserving Pipeline & Live Verification
- **Database Schema:** `research_intelligence.s6_library_events` and `research_intelligence.s6_analytics_audit_log` created in `spllaastejfwclllfndp` with `REVOKE ALL FROM PUBLIC, anon, authenticated`.
- **Live Verification (`https://archipelago-blond.vercel.app`):**
  - `GET /api/analytics/summary` returned `200`, `physical_footfall.status = "Data source not connected"`, `koha_catalog_titles = 109`, `koha_total_copies = 904`, `koha_available_copies = 901`.
  - **PII Rejection:** `POST /api/analytics/events` containing `student_id` returned `400` (`pii_field_forbidden:student_id`).
  - **Deduplication:** Posting a demo-isolated event (`is_demo: true`, `idempotency_key: s6-live-verify-...`) returned `201` (`inserted: true`, `event_id: 39634255-b677-4dd7-bc47-fff54c3a9c27`), and re-posting the identical key returned `200` (`deduplicated: true`, `inserted: false`).
  - **Demo Isolation:** Subsequent production `GET /api/analytics/summary` (default `include_demo=false`) continued to return `"Data source not connected"` without leaking the demo record.

---

## 4. Phase 3 — Academic Chat Experience (Live 10-Domain + OPAC + Multi-Turn)

Executed against `https://archipelago-blond.vercel.app/api/chat` with a verified student JWT (`12024002028038@student.iem.archipelago.invalid`):

| Domain / Test Case | Status | Latency (ms) | Response Length | Verified Behaviour |
| --- | --- | --- | --- | --- |
| **Operating Systems** | `200` | `4006.8` | `1,974` chars | Grounded definition + `[06_Address_Spaces.pdf — page 1]` source link |
| **DBMS** | `200` | `3385.4` | `2,133` chars | ACID & BCNF explanation with verified citations |
| **Computer Networks** | `200` | `3623.0` | `1,639` chars | Anchored on `tcp_congestion_control`, honest boundary on unindexed bridge |
| **DSA** | `200` | `3724.3` | `1,396` chars | Routed to `RESEARCH_EVIDENCE` with saved paper leads |
| **Compiler Design** | `200` | `2971.4` | `2,173` chars | Lexical analysis & LR parsing with textbook citation |
| **Mathematics** | `200` | `2576.4` | `2,388` chars | Multi-concept synthesis (`Eigenvalue`, `Eigenvector`, `Bayes' Theorem`) |
| **Artificial Intelligence** | `200` | `2822.3` | `1,549` chars | Honest unindexed boundary + research leads |
| **Machine Learning** | `200` | `3837.6` | `1,674` chars | Gradient Descent with `[papers/Hochreiter1997_LSTM.pdf, PDF p.13]` |
| **Software Engineering** | `200` | `3296.5` | `1,370` chars | Research evidence leads |
| **Distributed Systems** | `200` | `3200.1` | `1,406` chars | Research evidence leads |
| **Library OPAC** | `200` | `1296.5` | `106` chars | Clean catalog response + OPAC link, **0 MCQ noise** (`has_mcq_noise: false`) |
| **Multi-turn Follow-up** | `200` | `2763.9` | `639` chars | Contextualized follow-up (`thrashing`) with honest unindexed guard |

---

## 5. Phase 4 — Knowledge Graph Version Integrity & S4 Publication Gate

- **Local Canonical Verification:** `okf_graph.json` (`610` concepts, `1,988` edges, SHA-256 `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76`) matches local Kùzu `okf_graph.db` (`3ee305138a4a3661b505c30a1f782baeddd7e0779eef634720392821c0eb46ed`) with `0` self-loops and `0` orphan edges.
- **Supabase & Vercel Sync:** Uploaded canonical `okf_graph.json` (`6,489,729` bytes) and read-only `s4_academic_automation_snapshot.json` (`145,325` bytes) to private bucket `archipelago-cache`.
- **Live Vercel `/api/readiness`:** Confirmed `concepts: 610`, `corpus.source: "full"`, `graph_version: "9818ac0e8fd3"`, `ok: true`.
- **S4 Publication Gate (`bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe`):**
  - `GET /api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` returned `200` with `publication_status: "BLOCKED"` and `review_digest: "0fba3b14cc9e50fac0fd32fb960ac2a94fe9430f71b6fdbb10e640dd58fc9c77"`.
  - `POST .../decision` by student returned `403` (`forbidden`); `POST .../decision` by librarian with matching digest returned `409` (`workstation_required`), proving no hosted auto-approval or bypass is possible.

---

## 6. Phase 5 — S5 Research Intelligence & Author-Name Data-Quality Audit

- **Special Check (`Qing Wang,mying Li`):** Inspected the raw S5 acceptance payload (`hosted_acceptance_report.json`) and confirmed that the live API/PostgreSQL returned clean `Asela Hevapathige; Qing Wang` for Paper 1; `Qing Wang,mying Li` was a markdown typo in `s5_final_acceptance_report.md` (now corrected).
- **Hardening Added:** Implemented `_clean_author_name` normalization (comma-glued names, HTML entities, whitespace collapsing) and Crossref institutional `a.get("name")` fallback in `archipelago/scholarly/discovery/crossref_adapter.py` and `openalex_adapter.py`, synced to `host_inference/`.
- **No-Ranking Policy:** Preserved `collection_order` and 9-sheet Excel workbook generation (`Papers`, `Authors`, `Venues`, `References`, `Citation_Edges`, `Topic_Results`, `Sources_Provenance`, `Errors_Review`, `Run_Manifest`) with zero synthetic scores.

---

## 7. Phase 6 — Unattended Research Automation (`/api/internal/s5-monitor-tick`)

- **Configuration:** Added `{"path": "/api/internal/s5-monitor-tick", "schedule": "0 4 * * *"}` to `host_inference/vercel.json`; configured `ARCHIPELAGO_S5_SCHEDULER_ENABLED=1` and `CRON_SECRET` in Vercel Preview and Production.
- **Live Tick Proof (`https://archipelago-blond.vercel.app/api/internal/s5-monitor-tick`):**
  - Unauthenticated request: `401` (`unauthorized`).
  - Authorized `vercel-cron/1.0` Tick 1 (`2026-11-14T07:52:38.514131+00:00`): `200`, `trigger_source: "vercel_cron"`, `processed: 1`, `outcomes: ["updated"]`, `run_id: 571699aa-e2ab-42e0-93da-633b575a6ecf`.
  - Authorized `vercel-cron/1.0` Tick 2 (`2026-11-14T07:52:53.437764+00:00`): `200`, `processed: 1`, `monitor_id: a503cc2f-601f-45d8-80b9-a9bcd38338d8`, `run_id: 6c461690-71a3-4b02-b1d4-43e7f25940ab`.
  - Disabled Monitor Tick 3 (`2026-11-14T07:53:05.783529+00:00`): `200`, `processed: 0` (disabled monitors skipped cleanly).
  - Monitor history persisted (`GET /api/research/intelligence/monitors/<id>/history` returned `1` recorded run for the newly created monitor).

---

## 8. Phase 7 — Security Audit & RPC Hardening

- **Hardened `public.s5_research_rpc(text, jsonb)`:**
  - `SECURITY DEFINER` with locked `SET search_path = pg_catalog, research_intelligence, public`.
  - `REVOKE ALL FROM PUBLIC, anon, authenticated; GRANT EXECUTE TO service_role;`.
  - Runtime guard verifying `current_setting('role', true) = 'service_role'` (supporting `sb_secret_...` API keys), `request.jwt.claim.role = 'service_role'`, or `session_user IN ('postgres', 'service_role', 'supabase_admin')`.
  - `add_event` enforces monitor ownership (`EXISTS (SELECT 1 FROM s5_monitors m WHERE m.id = ... AND m.owner_id = ...)`).
- **Live Negative Security Tests:**
  - `s5_research_rpc` via `anon` key: `401`.
  - `s5_research_rpc` via `authenticated` user JWT: `403`.
  - `s5_research_rpc` with invalid `p_op`: `400` (`unsupported_s5_op`).
  - `GET /api/analytics/summary` unauthenticated: `401`.
  - `POST /api/analytics/events` as student: `403`; with PII (`student_id`): `400`.
  - `POST /api/academic-automation/review/.../decision` as student: `403`; as librarian: `409` (`workstation_required`).

---

## 9. Phase 8 & 9 — Browser UI & Performance Measurements

- **Live Page & API Latencies (`https://archipelago-blond.vercel.app`):**
  - `/api/readiness`: `494.2 ms`
  - `/library`: `434.5 ms`
  - `/research`: `446.4 ms`
  - `/analytics`: `411.5 ms`
  - `/academic-automation`: `392.7 ms`
  - `/api/graph/hubs`: `1850.7 ms`
  - `/api/graph/subgraph`: `1814.0 ms`
  - `/api/analytics/summary`: `5058.4 ms`
  - `/api/chat` (10 CS/Math/AI domains + OPAC): `1296.5 ms` – `4006.8 ms`
- **Playwright Screenshots Captured:** `desktop_analytics.png`, `desktop_academic_automation.png`, `desktop_academic_graph.png`, `desktop_research.png`, `desktop_chat.png`, `mobile_analytics.png`, `mobile_academic_automation.png` (under session `scratch/acceptance_results/browser_s6/`). Visual inspection of `/analytics` confirms clean rendering and explicit `"Data source not connected"` cards for physical footfall, occupancy, and peak window.

---

## 10. Phase 10 & 11 — Regression Gates & Rollback

- **Automated Checks Passed:**
  - `pytest` (`tests/unit/test_s6_platform_integration.py`, `test_host_inference_deployment.py`, `test_s5_research_intelligence.py`, `test_research_transport.py`, `tests/integration/test_s4_academic_dashboard.py`): **44 passed** in 14.74s.
  - `ruff check`: **0 errors**.
  - `mypy --strict --follow-imports=silent` on new/modified S6 modules: **0 errors**.
  - `source_size_gate.py`: All new/modified S6 files (`analytics.py` 331 lines, `routes/analytics.py` 349 lines, `host_research/app.py` 395 lines, `test_s6_platform_integration.py` 312 lines) are under the 400-line limit.
- **Rollback Procedure:**
  - Vercel production can be rolled back instantaneously via `npx vercel rollback --scope archipelago-6383` or by re-aliasing the previous S5 production deployment.
  - Database migrations (`20261114010000`, `20261114020000`) are additive and preserve all S4/S5 tables.

---

## 11. Subsystem Verdict Matrix & Final Release Decision

| Subsystem | Verdict | Evidence Summary |
| --- | --- | --- |
| **S1–S3 Academic Chat & Graph (`610` concepts)** | **PASS** | `10/10` CS/Math/AI domains + OPAC + multi-turn verified live (`200`, `1.3s–4.0s`, `0` MCQ noise); `/api/readiness` reports `610` concepts (`9818ac0e8fd3`). |
| **S4 Academic Automation Gate** | **PASS (Gate Preserved)** | Candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` remains `BLOCKED` pending independent human review (`403` student / `409` librarian). |
| **S5 Research Intelligence & Scheduled Cron** | **PASS** | 9-sheet Excel, no-ranking policy, author normalization, and live `/api/internal/s5-monitor-tick` (`vercel_cron`) verified end-to-end. |
| **S6 Library Analytics & Source Audit** | **PASS** | Honest `"Data source not connected"` for unlinked physical sensors; live Koha circulation (`109` titles / `904` copies), PII rejection (`400`), deduplication, and demo isolation verified. |
| **Security & `s5_research_rpc` Hardening** | **PASS** | `SECURITY DEFINER`, locked `search_path`, `REVOKE` from `anon`/`authenticated`, negative tests (`401`/`403`/`400`) verified. |
| **Librarian Production Promotion (`archipelago-librarian.vercel.app`)** | **PARTIAL / EXTERNAL GATE** | `host_research/` code & UI updated and synced in git; production promotion on Vercel requires an authorized `shinaura` team member (`vercel deploy --prod --scope shinaura`). |

### Final Release Verdict
**`ARCHIPELAGO CONDITIONALLY RELEASED — LISTED GATES OPEN`**

All engineering, integration, security, live inference, analytics, and unattended scheduler requirements on `https://archipelago-blond.vercel.app` and Supabase `spllaastejfwclllfndp` are **complete and verified**. Two external governance/permission gates remain open by design:
1. **Librarian Team Promotion:** Run `cd host_research && npx vercel deploy --prod --scope shinaura` with an authorized `shinaura` Vercel account.
2. **S4 Human Review Gate:** Complete independent human review on the local workstation for staged D2L candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` (`publication_status: "BLOCKED"`).
