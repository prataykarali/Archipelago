# Archipelago Research Security Audit Report (`RESEARCH_SECURITY_AUDIT.md`)

**Date:** 2026-11-18  
**Scope:** `/research/papers`, S5 Research Intelligence APIs & Exports, Cross-Origin Session Handoff (`host_inference` ↔ `host_research`), and Supabase PostgreSQL RLS / `SECURITY DEFINER` RPCs.  
**Research Preservation Gate:** **PASSED** — Zero modifications to scholarly search methodology, ranking formulas, OKF extraction logic, datasets, evaluation metrics, or paper payloads.

---

## 1. Executive Summary

This security audit evaluated the Archipelago Research Intelligence platform (`/research/papers` and supporting backend services across `host_inference` and `host_research`) across nine hardening phases:

1. **Cross-Origin Session Handoff (Phase 2A):** Replaced raw `refresh_token` transmission over `window.postMessage` with a server-mediated, single-use, short-lived (60s TTL), origin-bound ticket exchange (`POST /api/auth/handoff-ticket` → `POST /api/auth/handoff-redeem`).
2. **Cookie Session Authority, Idle/Absolute Expiry & Logout (Phases 2B & 2C):** Enforced server-authoritative idle and absolute session timeouts, prevented background job status polls (`X-Background-Poll: 1`) from artificially resetting user idle timers, and implemented cross-instance token revocation + cross-tab logout (`BroadcastChannel` / `storage` events + `Clear-Site-Data`).
3. **CSRF, CORS, Security Headers & Secret Redaction (Phases 2D & 3):** Enforced strict HTTPS CORS allowlists, Origin/Referer/CSRF validation on state-changing cookie mutations, DOM XSS sanitization, HSTS/CSP/Frame/Permissions headers, and log redaction of tokens/cookies/keys.
4. **Research API Authorization & Cross-Account Isolation (Phase 4):** Enforced server-derived principal ownership (`principal["id"]`) on all private S5 runs, dossiers, monitors, schedules, and exports.
5. **Excel Workbook Export Security & Reliability (Phase 5):** Enforced ownership checks, `Cache-Control: private, no-store, no-cache, must-revalidate`, spreadsheet formula injection neutralization (`=`, `+`, `-`, `@`, `\t`, `\r` prefix escaping on string cells while preserving all numeric metrics and schema contracts), and frontend `AbortController` / `URL.revokeObjectURL` cleanup.
6. **Supabase RLS & Privilege Hardening (Phase 4 / Database):** Added `supabase/migrations/20261118000000_prelaunch_rls_and_privilege_hardening.sql` to enable RLS on all cache and S6 analytics tables, lock down table privileges to `service_role`, harden `public.research_enqueue_job`, and support owner-scoped `delete_user_data`.

---

## 2. Detailed Security Findings (`FOUND → ROOT CAUSE → PATCH → TEST → RESULT → REMAINING RISK`)

### Finding SEC-01: Raw Supabase `refresh_token` Exposed via Cross-Window `postMessage` (HIGH)
- **FOUND:** `Archipelago/host_inference/ui/session-bridge.html:24` posted `{ type: 'archipelago-session-v1', access_token, refresh_token }` via `window.opener.postMessage`, and `Archipelago/host_research/ui/signin.js:65-68` consumed `refresh_token` directly from the message payload.
- **ROOT CAUSE:** Cross-deployment authentication between `archipelago-blond.vercel.app` and `archipelago-librarian.vercel.app` transferred long-lived refresh tokens across browser windows instead of using a server-mediated authorization code/ticket exchange.
- **PATCH:**
  - Added single-use, 60-second TTL, origin-bound handoff ticket issuance (`POST /api/auth/handoff-ticket`) and redemption (`POST /api/auth/handoff-redeem`) in `host_inference/hostapp/security.py`, `host_inference/hostapp/routes/auth.py`, and `host_research/app.py`.
  - Updated `host_inference/ui/session-bridge.html`, `host_inference/ui/auth_bridge.js`, `host_research/ui/auth_bridge.js`, and `host_research/ui/signin.js` to exchange opaque single-use tickets and validate exact origin, opener identity, and nonce/state without ever transmitting `refresh_token`.
- **TEST:** Covered by `tests/unit/test_prelaunch_security_matrix.py` (ticket issuance, single-use redemption, replay rejection, wrong-origin rejection, and zero `refresh_token` in bridge payload).
- **RESULT:** **FIXED (PARTIAL ACROSS COLD/MULTI-INSTANCE LAMBDAS)**.
- **REMAINING RISK:** Medium — Tickets are stored in process-local memory (`_SHARED_TICKETS_BY_SCOPE`), so cross-instance hops between separate Vercel lambdas require sticky routing or a shared store. `handoff-redeem` also returns `access_token` in JSON for Supabase JS compatibility alongside the `HttpOnly` cookie.

---

### Finding SEC-02: Missing RLS & Over-Permissive Grants on Cache & S6 Analytics Tables (CRITICAL)
- **FOUND:**
  - `Archipelago/supabase/migrations/20260930_000002_retrieval_cache.sql:5` (`public.retrieval_cache`) and `20260930_000003_graph_cache.sql:5` (`public.graph_cache`) did not enable Row Level Security (`ENABLE ROW LEVEL SECURITY`) or revoke default `anon`/`authenticated` privileges.
  - `Archipelago/supabase/migrations/20261114010000_s6_library_analytics_and_rpc_hardening.sql:5,41` (`research_intelligence.s6_library_events` and `research_intelligence.s6_analytics_audit_log`) did not enable RLS.
  - `public.archipelago_librarian_records` and `public.archipelago_runtime_quota` lacked explicit DDL + RLS migrations, and `public.research_enqueue_job` (`20261026110000_research_queue_admission.sql:4`) lacked a runtime `service_role` GUC check and `pg_catalog`-first `search_path`.
- **ROOT CAUSE:** Incremental schema migrations created internal cache and analytics tables without consistently applying RLS and `REVOKE ALL FROM PUBLIC, anon, authenticated`.
- **PATCH:** Created `Archipelago/supabase/migrations/20261118000000_prelaunch_rls_and_privilege_hardening.sql` to:
  - Enable RLS on `public.retrieval_cache`, `public.graph_cache`, `public.ai_response_cache`, `public.role_page_permissions`, `public.archipelago_librarian_records`, `public.archipelago_runtime_quota`, `research_intelligence.okf_paper_records`, `research_intelligence.s6_library_events`, and `research_intelligence.s6_analytics_audit_log`.
  - Revoke all privileges from `PUBLIC`, `anon`, and `authenticated` on all server-only tables and grant least-privilege access to `service_role`.
  - Harden `public.research_enqueue_job` with `SET search_path = pg_catalog, public, pg_temp` and runtime `service_role` verification.
  - Add owner-scoped `delete_user_data` operation to `public.s5_research_rpc`.
- **TEST:** Verified migration SQL completeness and RLS/privilege coverage across all tables and RPCs.
- **RESULT:** **FIXED**.
- **REMAINING RISK:** Low; ensure `supabase db push` is executed during deployment.

---

### Finding SEC-03: Background Polling Resets Idle Timeout & Logout Lacks Cross-Instance / Cross-Tab Invalidation (HIGH)
- **FOUND:**
  - `Archipelago/host_inference/hostapp/security.py:116-131` updated `_last_activity[token_id] = now` on every request, allowing background status polls on `/research/papers` and `/research/progress` to keep idle sessions alive indefinitely.
  - Logout (`DELETE /api/auth/session`) only cleared in-memory state on a single worker process, did not emit `Clear-Site-Data`, and did not notify other open browser tabs.
- **ROOT CAUSE:** Lack of distinction between user-initiated requests and background polling (`X-Background-Poll: 1`), combined with local-only logout handling.
- **PATCH:**
  - Updated `host_inference/hostapp/security.py` and `host_research/storage.py` to enforce both idle timeout and absolute session lifetime while ignoring background poll requests (`X-Background-Poll: 1` or status polling endpoints) when updating last-activity timestamps.
  - Added `POST /api/auth/logout` (alongside `DELETE /api/auth/session`) in `host_inference/hostapp/routes/auth.py` and `host_research/app.py` to record token revocation, clear `HttpOnly; Secure; SameSite=Lax` cookies, and return `Clear-Site-Data: "cookies", "storage"`.
  - Updated `host_inference/ui/auth_bridge.js` and `host_research/ui/auth_bridge.js` to broadcast logout across tabs via `BroadcastChannel` and `localStorage` events and clear all cached user state.
- **TEST:** Covered by `tests/unit/test_prelaunch_security_matrix.py` (idle expiry during background polling, absolute session expiry, immediate 401 after logout within process).
- **RESULT:** **FIXED (PROCESS-LOCAL REVOCATION)**.
- **REMAINING RISK:** Medium — Revocation state (`_SHARED_REVOKED_BY_SCOPE` / `_REVOKED_TOKENS`) is process-local in memory, not synchronized across separate Vercel serverless instances. True cross-instance revocation requires a shared store (Redis/Supabase).

---

### Finding SEC-04: Cross-Account Access & Ownership Verification on `/api/research/*` (HIGH)
- **FOUND:** Private S5 research routes (`host_inference/hostapp/routes/research_intelligence.py:21-51`, `routes/research_jobs.py:38-52`, `routes/research_intake.py:72-274`, `routes/research_graph.py:47-80`, `routes/research_projection.py:14-65`, `routes/research_schedule.py:49-56`, `routes/research_intelligence_schedule.py:22-28`, and `research_job_store.py:77-161`) required route-level principal fallback validation, strict PostgREST filter ID validation (`_validate_id`), and `Cache-Control: private, no-store, no-cache, must-revalidate` + `Vary: Authorization, Cookie` headers.
- **ROOT CAUSE:** Route handlers accessed `vars(request)["archipelago_principal"]` directly and did not validate IDs before PostgREST `eq.` filter construction.
- **PATCH:** Added `_resolve_principal()` and `@app.before_request` / `@app.after_request` guards across `research_intelligence.py:67-116`, `research_jobs.py:39-78`, `research_intake.py:47-81`, `research_graph.py:24-75`, and `research_projection.py:15-42`; added `_validate_id()` (`^[A-Za-z0-9_\-]{1,128}$`) in `research_job_store.py:39-43`; and enforced `Authorization: Bearer <CRON_SECRET>` via `secrets.compare_digest` in `research_schedule.py:51-57` and `research_intelligence_schedule.py:24-28`.
- **TEST:** Automated cross-account isolation tests (`test_s5_run_export_graph_and_monitor_are_owner_scoped`, `test_hosted_job_results_hide_another_faculty_job`, `test_complete_session_export_respects_job_access`).
- **RESULT:** **FIXED**.
- **REMAINING RISK:** None.

---

### Finding SEC-05: Spreadsheet Formula Injection & Missing Cache Headers on Excel Workbook Exports (HIGH)
- **FOUND:**
  - External scholarly metadata written into `.xlsx` exports in `host_inference/hostapp/routes/research_intelligence.py:31-65,198-222` checked `("=", "+", "-", "@")` at index 0 but missed tab/carriage-return prefixes (`\t`, `\r`) and leading whitespace before formula characters.
  - `host_research/app.py:_forward` did not forward `Content-Disposition` headers on proxied `.xlsx` downloads.
  - `host_inference/ui/research_download.js` and `host_research/ui/research_download.js` lacked single-flight download locking, ZIP magic-byte verification, and `URL.revokeObjectURL` cleanup on unload.
- **ROOT CAUSE:** Untrusted external strings with leading whitespace or control characters could be interpreted as formulas by spreadsheet software.
- **PATCH:**
  - Added `_safe_workbook_cell()` (`routes/research_intelligence.py:34-42`) escaping `("=", "+", "-", "@", "\t", "\r")` and leading-whitespace formula triggers while preserving 100% of numeric research metrics, column headers, and 14-sheet workbook structure; bounded exports with `_prepare_run_for_workbook()` (`MAX_EXPORT_PAPERS = 250`).
  - Set `Cache-Control: private, no-store, no-cache, must-revalidate`, `Pragma: no-cache`, `Vary: Authorization, Cookie`, `X-Content-Type-Options: nosniff`, and sanitized `Content-Disposition` (`_SAFE_FILENAME_RE`), and preserved `Content-Disposition` in `host_research/app.py:_forward`.
  - Updated `host_inference/ui/research_download.js` and `host_research/ui/research_download.js` with `AbortController`, single-flight locking, `0x50, 0x4B` ZIP header verification, 401/403 session-expiry feedback, and `URL.revokeObjectURL` cleanup.
- **TEST:** Automated workbook export tests (`test_filters_and_workbook_are_real_typed_cells`, `test_options_and_untrusted_spreadsheet_text`).
- **RESULT:** **FIXED**.
- **REMAINING RISK:** None.

---

### Finding SEC-06: DOM XSS, Open Redirects, Stream Marker Injection & SSRF Hardening (HIGH)
- **FOUND:**
  - Unescaped `innerHTML` interpolations in `host_inference/ui/user_management_modal.js:22,138-155,261-275`, `library-inline-1.js:284-330`, `graphify.js:188-214`, and `performance.html:175`, plus unvalidated URL schemes on dynamic links in `library-inline-1.js`, `academic_koha.js`, `library_pipeline.js`, `research_intake.js`, and `research_home.js`.
  - Unstripped `[STREAM_START]` / `[STREAM_DONE]` control tokens in external paper metadata in `host_inference/hostapp/research_chat.py:303-318`.
  - Missing loopback/private/link-local IP rejection on `source_url` in `host_inference/hostapp/routes/analytics.py:99-112` and redirect validation in `pages.py`, `routes/auth.py`, `landing.html`, `reader.js`, and `pearson-handoff.js`.
- **ROOT CAUSE:** Untrusted strings and URLs rendered or followed without strict escaping/allowlisting.
- **PATCH:** Escaped all dynamic HTML interpolations with `escapeHtml()`, enforced `/^https?:\/\//i` scheme validation, stripped stream control markers in `research_chat.py:305-316`, blocked private/loopback IPs via `ipaddress.ip_address` in `routes/analytics.py:99-112`, enforced `is_safe_redirect_target()` (`security.py:87-117`), and deleted dead backup `host_inference/ui/index.html.stripped_backup_20260729`.
- **TEST:** Verified via unit and UI security tests.
- **RESULT:** **FIXED**.
- **REMAINING RISK:** None.

---

### Finding SEC-07: CSRF, CORS, Security Headers, Rate Limiting & Log Redaction (HIGH)
- **FOUND:**
  - State-changing cookie-authenticated requests lacked strict Origin/Referer/CSRF validation in `host_inference/hostapp/middleware.py:125-215` and `host_research/app.py`.
  - `CLIENT_IP_HEADERS` in `host_inference/hostapp/security.py:38` included non-Vercel headers (`CF-Connecting-IP`, `Fly-Client-IP`), and `user_traffic.py` read the first hop of `X-Forwarded-For`.
  - `host_inference/hostapp/log_redaction.py:36-76` did not scrub `Cookie:` / `Set-Cookie:` headers or `record.exc_text`, and `runtime_rpc()` in `runtime_state.py` allowed raw `requests.HTTPError` exceptions to propagate.
- **PATCH:**
  - Added `_check_csrf()` in `host_inference/hostapp/middleware.py:114-168` and CSRF Origin validation in `host_research/app.py`.
  - Restricted `CLIENT_IP_HEADERS = ("X-Vercel-Forwarded-For", "X-Real-IP")` with rightmost `X-Forwarded-For` fallback across `security.py`, `user_traffic.py`, and `host_research/app.py`, and added `RateLimiter.check_auth()` (`security.py:659-670`).
  - Extended `log_redaction.py` with `_COOKIE_HEADER_RE`, `record.exc_text` scrubbing, and `mask_secret()` (`xxxx••••`), and suppressed raw upstream exception chaining in `runtime_state.py:185-194`.
- **TEST:** Verified via unit tests across `host_inference` and `host_research`.
- **RESULT:** **FIXED**.
- **REMAINING RISK:** None.
