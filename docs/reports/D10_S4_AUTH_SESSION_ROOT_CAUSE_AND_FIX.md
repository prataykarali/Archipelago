# D10-S4 authentication session root cause and fix

Candidate base: `bcb4989cbd72f47e66785e40cc76a8815c9e4668` (`d10-s3-candidate-runtime`). This report covers candidate code revision `722b0c58c7fc4d4432da7ada515a7270fba463b3`.

## Code-confirmed cause

- The hosted backend has a 300-second idle timeout and 3,600-second maximum lifetime. The chat client had a 3,600,000-millisecond idle timer, and the login page stated 60 minutes of inactivity. Thus the browser could keep showing a Librarian identity after the backend had expired the session.
- `auth_bridge.js` accepted an identity cached in session storage for up to 120 seconds before contacting `/api/auth/me`. It could render role navigation from the cached value.
- Chat cleared the input before the request, and its stream error path treated a 401 as a generation failure. The server returned the same hardcoded five-minute inactivity message for idle expiration, absolute expiration, and revocation.
- The client could request a chat response without first checking the authoritative session state.

The exact production request path has **not** been established with authenticated browser/network evidence. No Librarian credentials or redacted HAR were available. The observed message is consistent with the backend code path, but it does not prove which Vercel instance or token handled the author's request.

## Candidate changes

- The chat send path checks `/api/auth/me` with `no-store` and a passive request header before clearing the question. A 401 stops the chat POST, presents one sign-in prompt, and stores the draft in tab session storage. After a verified sign-in and return to `/chat`, the draft is restored without resubmission.
- A 401 race from `/api/chat` follows the same draft-preserving path. An upstream verification error keeps the draft and asks the user to retry.
- Role navigation and protected-page authorization now verify `/api/auth/me` rather than accepting the cached principal as authority. The independent browser idle timer was removed so an inactive tab cannot log out a session still active in another tab; the shared backend tracker decides expiry. The login privacy text no longer states an inaccurate fixed idle duration.
- `/api/auth/me` and protected API 401 responses carry stable `reason` codes: `idle_expired`, `absolute_expired`, `jwt_expired`, `revoked_credentials`, `missing_session`, `invalid_credentials`, or `upstream_unavailable`. An upstream identity verification outage returns 503 from `/api/auth/me`. JWT `exp` is used only to reject already expired tokens; it is never used to authenticate one.

## Shared hosted-session state

The candidate now adds `supabase/migrations/20261124000000_d10_s4_durable_sessions.sql` and a server-only RPC adapter. On Vercel, every authorized request verifies the Supabase identity and atomically checks a row keyed by the signed JWT's `session_id` and verified user ID. The RPC checks that the corresponding `auth.sessions` row still exists, then enforces idle and absolute expiry using the database clock. Logout records revocation in that same row. A refreshed JWT from the same valid Supabase session keeps the existing idle/absolute timeline. Expired, revoked and missing sessions cannot be registered again. The process-local principal cache is bypassed for hosted requests.

The RPC is restricted to `service_role`; the table has RLS enabled and no `anon` or `authenticated` grants. Hosted CSRF tokens require a shared server-side `ARCHIPELAGO_CSRF_SECRET`, so different instances derive the same token. When the RPC or required secret is unavailable, hosted authorization fails closed. Supabase documents the JWT `session_id` claim and its relationship to `auth.sessions` in [User sessions](https://supabase.com/docs/guides/auth/sessions).

The migration was **not applied**, per the no-deployment instruction. This means the current deployed Vercel app cannot use the new shared store yet. Apply it only in an approved staging deployment with the required server-only key and shared CSRF secret, then run two-instance live tests before author re-testing. Cross-instance behavior has been simulated in unit tests; it has not been verified against a live Supabase database.

If shared revocation storage is unavailable during logout, the server returns 503 instead of reporting a successful revocation. Protected hosted requests remain denied while the store is unavailable. A live outage/recovery test is still needed to confirm the complete logout flow with Supabase's global sign-out.

Refresh is limited to Supabase's existing valid refresh-token flow in the browser. This candidate does not force refresh after an idle, absolute, or revoked-session response.

## Verification

- `python3 -m pytest tests/unit/test_host_auth_session_reasons.py -q`: 7 passed, including cross-instance mock RPC, refresh continuity, non-resurrection, shared CSRF and fail-closed outage.
- `python3 -m pytest tests/unit/test_prelaunch_security_matrix.py -q -k 'session or logout or token'`: 9 passed.
- `node --check` on `auth_bridge.js`, `08-send-message.js`, and `08-send-request.js`: passed.
- `python3 scripts/quality_gate.py`: fails on existing repository-wide lint, format, type, banned-pattern and file-size baselines; this focused change did not clear those baselines.
- The broader auth/security test selection had 65 passes and two unrelated failures: the existing Excel sheet schema assertion and an ingestion-file immutability assertion against concurrent D10-S4 ingestion edits. A later focused auth selection had 16 passes.

Authenticated browser re-testing remains required for idle and active sessions, refresh, reload, logout, role changes, simultaneous tabs, and simultaneous Vercel instances. No production deployment was made.
