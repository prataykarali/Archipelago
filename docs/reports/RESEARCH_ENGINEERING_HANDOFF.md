# Archipelago Research Engineering Handoff (`RESEARCH_ENGINEERING_HANDOFF.md`)

**Date:** 2026-11-18  
**Target Route & Systems:** `/research/papers`, `host_inference`, `host_research`, and `supabase/migrations`

---

## 1. Summary of Completed Work (Phases 1–9)

All findings across authentication, cross-origin session handoff, database RLS, API access control, Excel workbook export reliability, and frontend/backend request bottlenecks have been remediated using minimal, surgical diffs while strictly preserving Archipelago's scientific and research pipeline.

| Phase | Area | Key Changes | Status |
|---|---|---|---|
| **Phase 1** | Reconnaissance & Threat Model | Mapped all entrypoints across `host_inference`, `host_research`, and `supabase/migrations`; locked `AUDIT.md` into `.gitignore` and `.vercelignore`. | **COMPLETE** |
| **Phase 2A** | Cross-Origin Session Handoff | Replaced `postMessage` raw `refresh_token` transfer in `session-bridge.html` / `signin.js` with single-use, 60s TTL, origin-bound handoff tickets (`/api/auth/handoff-ticket` → `/api/auth/handoff-redeem`). | **COMPLETE** |
| **Phase 2B/2C** | Session Authority, Idle/Absolute Expiry & Logout | Enforced `HttpOnly; Secure; SameSite=Lax` cookies, server-side idle + absolute timeouts, non-touching background polls (`X-Background-Poll: 1`), cross-instance revocation, `Clear-Site-Data`, and multi-tab `BroadcastChannel` logout. | **COMPLETE** |
| **Phase 2D/3** | CSRF, CORS, XSS, Headers & Redaction | Enforced HTTPS CORS allowlists, CSRF Origin/header validation on state-changing cookie mutations, DOM XSS escaping, HSTS/CSP headers, and log redaction of tokens/cookies/keys. | **COMPLETE** |
| **Phase 4** | Research API Authorization & Supabase RLS | Enforced server-derived `principal["id"]` ownership across `/api/research/*`; added `20261118000000_prelaunch_rls_and_privilege_hardening.sql` enabling RLS and revoking `PUBLIC`/`anon`/`authenticated` grants on cache, librarian, quota, and S6 analytics tables. | **COMPLETE** |
| **Phase 5** | Excel Workbook Export Security & Reliability | Added ownership checks, `Cache-Control: private, no-store, no-cache, must-revalidate`, formula-prefix (`=`, `+`, `-`, `@`, `\t`, `\r`) neutralization on string cells, `Content-Disposition` forwarding in `host_research`, and frontend `AbortController` + `URL.revokeObjectURL`. | **COMPLETE** |
| **Phase 6** | `/research/papers` Performance Hardening | Deduplicated auth/config fetches, paused polling when `document.hidden`, added `X-Background-Poll: 1` on status polls, deferred non-critical scripts, and added bounded TTL caches in `host_research/storage.py` and `koha_snapshot.py`. | **COMPLETE** |
| **Phase 6B** | Graceful Shutdown & Resource Draining | Implemented `is_shutting_down()`, `initiate_shutdown()`, in-flight request draining (`503` + `Retry-After: 5`), safe `SIGTERM`/`SIGINT` + `atexit` registration, and frontend `pagehide`/`beforeunload` cleanup across `host_inference` and `host_research`. | **COMPLETE** |
| **Phase 7–9** | Documentation, Regression Matrix & Research Freeze Gate | Compiled `AUDIT.md`, `RESEARCH_SECURITY_AUDIT.md`, `SESSION_ARCHITECTURE.md`, `RESEARCH_PERFORMANCE_REPORT.md`, and verified all unit and regression tests pass with zero changes to research outputs. | **COMPLETE** |

---

## 2. Graceful Shutdown Lifecycle

Both backend services (`host_inference` and `host_research`) and frontend clients implement a coordinated graceful shutdown sequence:

1. **Signal & Process Exit Registration:**
   - Main-thread `SIGTERM` and `SIGINT` handlers (guarded for non-main WSGI threads and serverless cold starts) and `atexit` hooks invoke `initiate_shutdown(drain_timeout)`.
2. **Draining Guard & Readiness Probe Reporting:**
   - Once `is_shutting_down()` transitions to `True`:
     - `/api/readiness` returns `503 Service Unavailable` with `{"ready": false, "status": "shutting_down"}` and `Retry-After: 5` so load balancers stop routing new traffic.
     - New incoming requests receive `503 Service Unavailable` (`{"error": "service_shutting_down", "status": "shutting_down"}`) with `Retry-After: 5`.
     - Active in-flight requests tracked by middleware (`in_flight_requests()`) are allowed to complete up to `drain_timeout` before teardown hooks run.
3. **Resource Cleanup Callbacks:**
   - Registered shutdown callbacks flush buffered traffic/telemetry events, close shared `requests.Session` pools, clear in-memory caches, and safely close SQLite/cache connections (`close_storage_resources()` in `host_research/storage.py` and `runtime_state` callbacks in `host_inference`).
4. **Frontend Page Unload Cleanup (`pagehide` / `beforeunload`):**
   - Browser clients abort in-flight `AbortController` fetches, clear active polling timers, revoke temporary Blob URLs (`URL.revokeObjectURL`), and close `BroadcastChannel` instances.

---

## 3. Non-Negotiable Research Preservation Verification

- **Research Pipeline & Ranking Logic:** Untouched (`archipelago/scholarly/**`, ranking formulas, OKF extraction, and evaluation metrics have zero behavioral changes).
- **Datasets, Fixtures & Annotations:** Untouched (`host_inference/fixtures/okf_graph.json`, S3/S4/S5 evaluation artifacts, and paper records are 100% unchanged).
- **Excel Export Schema & Numeric Metrics:** All worksheet names, column headers, row ordering, and numeric values remain identical; only untrusted string cells starting with spreadsheet formula characters (`=`, `+`, `-`, `@`, `\t`, `\r`) are prefixed with a safe apostrophe (`'`) to prevent formula execution in Excel.

---

## 3. Deployment & Operations Checklist

1. **Apply Supabase Hardening Migration:**
   ```bash
   supabase db push
   # Applies supabase/migrations/20261118000000_prelaunch_rls_and_privilege_hardening.sql
   ```
2. **Verify Environment Variables on Both Vercel Projects (`archipelago-blond` & `archipelago-librarian`):**
   - `ARCHIPELAGO_ENV=production`
   - `ARCHIPELAGO_AUTH_REQUIRED=1`
   - `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_SECRET_KEY` (server-only)
   - `CRON_SECRET` (matching across Vercel Cron configuration)
   - `ARCHIPELAGO_FRONTEND_ORIGIN=https://archipelago-librarian.vercel.app` (on `host_inference` and `host_research`)
3. **Rotate Local Development Keys Before Public Launch:**
   - Rotate any API keys stored in local developer `.env` files (`XKIRO_API_KEY`, `NVIDIA_API_KEY`, `NARA_API_KEY`, `GEMINI_API_KEY`, `HF_TOKEN`, `APIFY_TOKEN`) via their respective cloud consoles if those keys were ever shared outside the local workstation.

---

## 4. Reference Documentation Index

- Pre-Launch 85-Check Audit (local-only, gitignored): `Archipelago/AUDIT.md`
- Security Audit Report (Deliverable #1): `Archipelago/docs/security/RESEARCH_SECURITY_AUDIT.md`
- Session & Auth Architecture (Deliverable #2): `Archipelago/docs/security/SESSION_ARCHITECTURE.md`
- Research Page Performance Report (Deliverable #3): `Archipelago/docs/performance/RESEARCH_PERFORMANCE_REPORT.md`
- Engineering Handoff (Deliverable #4): `Archipelago/docs/reports/RESEARCH_ENGINEERING_HANDOFF.md`
