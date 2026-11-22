# Archipelago Session & Authentication Architecture (`SESSION_ARCHITECTURE.md`)

**Date:** 2026-11-18  
**Applies To:** `host_inference` (`archipelago-blond.vercel.app`) & `host_research` (`archipelago-librarian.vercel.app`)

---

## 1. Architecture Overview

Archipelago operates across two Vercel deployments sharing a single Supabase Auth and PostgreSQL identity boundary:
1. **Primary Application (`host_inference` — `archipelago-blond.vercel.app`):** Hosts Academic Chat, Knowledge Graph, Library, and the S5 Research Intelligence backend.
2. **Research Transport & Librarian Space (`host_research` — `archipelago-librarian.vercel.app`):** Hosts the dedicated Research UI shell (`/research/papers`, `/research/topics`, `/research/progress`, `/research/paper`, `/research/topic`) and Librarian Space (`/librarian/*`).

### Core Security Principles
- **Server-Authoritative Identity:** Every protected API request resolves the caller's identity (`id`, `role`, `username`) on the server via `AuthGuard.principal()` (`host_inference`) or `storage.verify_user()` (`host_research`). Client-supplied `user_id` or role claims are never trusted.
- **HttpOnly Cookie + Bearer Dual Support:** Sessions are anchored by an `HttpOnly; Secure; SameSite=Lax` cookie (`archipelago_token`) set by `/api/auth/session` or `/api/auth/handoff-redeem`, alongside `Authorization: Bearer <access_token>` headers for API calls.
- **Zero `refresh_token` Cross-Window Exposure:** Cross-origin session handoff between the two Vercel origins uses a server-mediated, single-use, 60-second TTL ticket exchange (`POST /api/auth/handoff-ticket` → `POST /api/auth/handoff-redeem`). Raw Supabase `refresh_token` values are never transmitted over `window.postMessage`.

---

## 2. Server-Mediated Cross-Origin Session Handoff (Phase 2A)

```mermaid
sequenceDiagram
    participant R as host_research (/login)
    participant B as host_inference (/session-bridge.html)
    participant S as Server Auth API (/api/auth/handoff-*)

    R->>B: window.open("/session-bridge.html?target=https://archipelago-librarian.vercel.app&state=<48-hex-nonce>")
    B->>B: Validate window.opener, HTTPS protocol, allowlisted target origin, referrer match, and state format
    B->>S: POST /api/auth/handoff-ticket { target_origin, state }
    S->>S: Verify staff principal (faculty/librarian/administrator)<br/>Generate single-use opaque ticket (60s TTL, SHA-256 hashed at rest, bound to target_origin & state)
    S-->>B: { ticket, expires_in: 60 }
    B->>R: window.opener.postMessage({ type: "archipelago-session-v2", ticket, state }, targetOrigin)
    R->>R: Verify event.origin, event.source === activeHandoffPopup, and state === sessionStorage['archipelago_handoff_state']
    R->>S: POST /api/auth/handoff-redeem { ticket, target_origin, state }
    S->>S: Atomically consume ticket (single-use pop, TTL check, origin & state check)
    S-->>R: Set-Cookie: archipelago_token=...; HttpOnly; Secure; SameSite=Lax + { access_token, principal }
```

### Security Controls on Handoff Tickets
1. **Single-Use Enforcement:** Tickets are stored hashed/keyed in server state and immediately marked consumed upon the first `POST /api/auth/handoff-redeem` call. Any replay attempt returns `401 unauthorized`.
2. **Short TTL (60 Seconds):** Tickets expire automatically 60 seconds after issuance.
3. **Strict Origin & Audience Binding:** Both `/api/auth/handoff-ticket` and `/api/auth/handoff-redeem` validate that `target_origin` is an allowlisted HTTPS Archipelago origin (`https://archipelago-librarian.vercel.app`, `https://archipelago-blond.vercel.app`, or configured preview origin).
4. **No Refresh Token Exposure:** Only the opaque single-use `ticket` crosses `window.postMessage`; `refresh_token` never leaves its originating origin.

---

## 3. Cookie Session Authority, Idle Expiry & Absolute Lifetime (Phase 2B)

### Cookie Attributes
| Attribute | Value | Purpose |
|---|---|---|
| Name | `archipelago_token` | Server session cookie |
| `HttpOnly` | `true` | Prevents JavaScript (`document.cookie`) access under XSS |
| `Secure` | `true` (in `production`/`prod`) | Restricts transmission to HTTPS |
| `SameSite` | `Lax` | Protects against cross-site request forgery on top-level/subresource requests |
| `Path` | `/` | Available to all `/api/*` and page routes on the origin |
| `Max-Age` | `SESSION_COOKIE_MAX_AGE` (3600s) | Bounded cookie lifetime |

### Idle Timeout vs. Background Polling
- **Server-Side Idle Timeout (`IDLE_TIMEOUT_SECONDS = 300`):** Tracked per token digest (`sha256(token)`) in `AuthGuard._last_activity`.
- **Server-Side Absolute Session Lifetime (`ABSOLUTE_TIMEOUT_SECONDS`):** Tracked from initial session establishment (`_first_seen[token_id]`) so a session cannot be extended indefinitely beyond its maximum lifetime.
- **Non-Interactive Polling Rule (`X-Background-Poll: 1`):**
  - Background polling requests (such as job progress polling on `/api/research/jobs/*` or requests carrying `X-Background-Poll: 1`) still require a valid, non-expired session to succeed, **but do NOT update `_last_activity[token_id]`**.
  - This ensures an unattended browser tab polling in the background still expires cleanly after the idle window.

---

## 4. Cross-Instance & Multi-Tab Logout (Phase 2C)

When a user clicks **Sign out** or an idle timeout triggers:
1. **Server-Side Revocation (`POST /api/auth/logout` or `DELETE /api/auth/session`):**
   - Computes `sha256(token)` and records it in the process-local revocation registry (`AuthGuard._expired` / `_SHARED_REVOKED_BY_SCOPE` in `host_inference` and `storage.revoke_token()` in `host_research`), evicting any cached principal entry immediately. *(Remaining risk: in-memory revocation is process-local, not synchronized across separate Vercel serverless instances without a shared store.)*
   - Deletes `archipelago_token`, `archipelago_access_token`, and `sb-access-token` cookies with matching `Path=/` and `SameSite=Lax`.
   - Emits `Clear-Site-Data: "cookies", "storage"` to instruct the browser to purge origin storage.
2. **Client-Side Storage Purge & Cross-Tab Broadcast:**
   - Clears `localStorage` and `sessionStorage` keys (`archipelago_local_user`, cached research state, and Supabase session tokens).
   - Broadcasts a `logout` event over `BroadcastChannel("archipelago_auth_channel")` and a `localStorage` event key (`archipelago_logout_broadcast`) so every open tab on the same origin immediately clears in-memory state and redirects to `/login`.

---

## 5. CSRF, CORS & Caching Defenses (Phase 2D)

- **CSRF Protection on Cookie-Authenticated Mutations:**
  - All state-changing methods (`POST`, `PUT`, `PATCH`, `DELETE`) verify that `Origin` (or `Referer`) matches the host origin or an explicitly allowlisted HTTPS Archipelago origin, and validate custom request headers (`X-CSRF-Token` / `X-Requested-With` / `Content-Type: application/json`).
- **CORS Allowlist:**
  - `Access-Control-Allow-Origin` is emitted only when `Origin` exactly matches an allowlisted HTTPS origin (`ARCHIPELAGO_FRONTEND_ORIGIN` / `archipelago-blond.vercel.app` / `archipelago-librarian.vercel.app`), never `*`.
- **Private Response Caching:**
  - All authenticated API responses and `/api/research/*` exports set `Cache-Control: private, no-store` (and `Vary: Authorization, Cookie` on user-scoped endpoints) so CDN/browser caches never store sensitive data across accounts.
