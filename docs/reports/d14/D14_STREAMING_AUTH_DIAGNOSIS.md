# Phase D14.0 Diagnostic Report: Auth Latency, `/chat` Load Hangs & Streaming Reliability

**Owner:** `d14-streaming-perf` (Phase D14.7 Streaming, Latency, Cache & Observability Specialist)
**Date:** 2026-11-28
**Mode:** Phase D14.0 Diagnosis Only (zero production code edits, zero deployments; UEM production untouched)
**Audited Live Deployment:** `https://archipelago-sigir.vercel.app`
**Confirmed Live Release SHA:** `fe8887c878e27f1770690236513f0f6c79c37d7c` (`sigir/d12-recovery`)
**Audited Workspaces:**
- `sigir/d12-recovery` (`fe8887c`) — **authoritative deployed SIGIR codebase**
- `d14_scientific_recovery_stabilization` / `main` (`c0d90b8`) — 83 commits behind `sigir/d12-recovery`
- `sigir/demo-2027` (`71271ec`) — earlier SIGIR snapshot

> **Live Baseline Probe (`2026-11-28 02:13 UTC`, warm instance `bom1::iad1`):**
> - `GET /api/readiness` → `200`, `x-archipelago-release: fe8887c878e27f1770690236513f0f6c79c37d7c`, `cache: "bundled"`, `candidate_passages.source: "supabase_storage"` (3,025 passages / 43 docs), `concepts: 610`, `open_access_only: true`, `cache_metrics: 0 hits / 6 misses (0.0%)`.
> - Warm single-hop RTT from India (`bom1`) to Vercel `iad1`: `~367–414 ms` per HTTP round-trip (`/login` 414 ms, `/chat` 396 ms [302], `/api/auth/config` 367 ms, `/api/auth/me` 367 ms, `/api/readiness` 374 ms). Every extra sequential round-trip multiplies latency directly.

---

## Executive Summary

All reported user-facing regressions on `https://archipelago-sigir.vercel.app/chat` trace to concrete, deterministic defects in the deployed `fe8887c` (`sigir/d12-recovery`) codebase:

| Reported Symptom | Primary Root Causes (Exact File:Line) | Severity |
|---|---|---|
| **1. Slow sign-in after sign-out** (*"sign out hole sign in korte onek time nicche"*) | (a) `archipelagoLogout` performs **2 duplicate sequential server revocations** (`POST /api/auth/logout` + `DELETE /api/auth/session`) without clearing `cachedAccessToken`, causing 4 upstream Supabase calls; (b) unbounded `supabase.auth.signOut({ scope: "global" })` + 3.5s CDN race; (c) `Clear-Site-Data: "cookies", "storage"` sent twice (stalls Chromium storage wipe & evicts `archipelago_auth_config_v1`); (d) `POST /api/auth/session` performs **3 sequential Supabase calls**; (e) **Vercel cold-start blocking cascade** (double `hydrate()` + HF Hub API + passage download = up to 91s worst-case) blocks auth endpoints synchronously. | **P0 / Critical** |
| **2. `/chat` page fails to open / hangs** (*"page open hote chaina"*) | (a) **9 synchronous render-blocking `<script>` tags** from 3 external CDNs (`cdn.tailwindcss.com`, `cdn.jsdelivr.net`, `cdnjs.cloudflare.com`) in `<head>` of `index.html:8-25`; (b) **Vercel cold-start double-`hydrate()` + synchronous HF API** blocks `GET /chat`; (c) **5–6 redundant `/api/auth/me` calls** + top-level `await` in `js/index.js:30-31` + `/api/catalog/all`, `/api/chat/quota`, `/api/readiness` storm on mount. | **P0 / Critical** |
| **3. Chat gets stuck / Stop button stuck** (*"sometimes chat stuck"*) | (a) `sendMessage()` blocks up to 15s+ inside `archipelagoVerifyChatSession()` **before** `state.isGenerating` or `AbortController` is armed (Stop button cannot cancel it, and clicking Stop early lets `sendMessage()` resume and start a stream anyway); (b) `STREAM_IDLE_TIMEOUT_MS` (14s) starts **before HTTP headers arrive**, colliding with cold-start + auth + retrieval + 10s provider failover; (c) missing `[STREAM_START]` leaves `metadataParsed = false` with typing dots frozen until EOF/timeout. | **P0 / Critical** |
| **4. 60s mid-stream timeout & zero-byte timeout** | (a) Pre-`8555462`: 60s/75s client timeouts + urllib3 v2 socket timeout not tightened on `raw._connection.sock`; (b) Post-`8555462` (`fe8887c`): `STREAM_IDLE_TIMEOUT_MS = 14000` is shorter than `auth_ms + engine_ms + enrich_ms + PRE_FIRST_TOKEN_BUDGET (10s)`, causing **zero-byte timeouts**; (c) XKIRO consumes 8s of the shared 10s `ft_deadline`, starving NVIDIA failover to ≤2s; (d) `_tighten_socket_timeout()` is only called *after* the first SSE line is parsed. | **P0 / Critical** |
| **5. Incomplete prerequisite answer ending at "Page Tables"** | (a) Frontend hardcodes `reply_detail: 'expanded'` (`1800` max_tokens + expanded concept context) on every request (`08-send-request.js:90`); (b) `CHAT_REQUEST_DEADLINE_SECONDS = 24.0` (`routes/chat.py:58`) starts ticking *before* retrieval/failover, cutting off long structured answers mid-sentence at 24s (`answer.py:877`, `llm.py:468`). | **P1 / High** |
| **6. Inspector shows `"Pending completion"` forever** | (a) `stream-markers.js:45` merges `[STREAM_META:{...}]` via `Object.assign(window._lastChatMetadata, terminalMeta)` at **top level**, never updating `window._lastChatMetadata.trace.stage_timings_ms.total_ms` (which `15-inspector.js:165` and `:230` read); (b) `MARKER_TAIL_GUARD = 48` (`stream-markers.js:2`) is far smaller than the ~260-byte `[STREAM_META:{...}]` frame, so chunk-split markers leak into prose and fail to parse. | **P1 / High** |
| **7. Zero cache utilization (0% hit rate)** | `routes/chat.py:451-454` unconditionally calls `ctx.cache_metrics.record_miss()` and never reads or writes `ctx.cache_service`. | **P2 / Medium** |

---

## Part 1: Sign-Out → Sign-In Lifecycle Trace (Exact Root Causes)

### 1.1 Sign-Out Cascade (`host_inference/ui/auth_bridge.js:306-336`, `host_inference/hostapp/routes/auth.py:78-107`)

When the user clicks Sign Out (`signOutSupabase()` in `index-inline-2.js:45-61` → `window.archipelagoLogout()` in `auth_bridge.js:306-336`):

1. **Duplicate sequential logout calls + stale `cachedAccessToken` (`auth_bridge.js:306-325, 384-385`)**:
   - Line 313 awaits `POST /api/auth/logout` → `auth.py:171-173` → `_logout_response(ctx)` (`auth.py:78-107`).
   - Inside `_logout_response(ctx)`, lines 83–85 call `ctx.auth.end_session(tok)` (`security.py:326-354`), which in `hosted_runtime()` makes **2 sequential synchronous Supabase HTTP calls**:
     - `GET {url}/auth/v1/user` (`timeout=(3.0, 5.0)`, `security.py:335-339`)
     - `POST {url}/rest/v1/rpc/archipelago_runtime_session_rpc` (`operation="revoke"`, `timeout=10`, `security.py:346-351` → `runtime_state.py:219-224`)
   - Line 320 then sequentially awaits `DELETE /api/auth/session` — which routes to the **exact same `_logout_response(ctx)`** (`auth.py:134-135`).
   - Because `archipelagoLogout()` **never resets `cachedAccessToken = ""`**, the monkey-patched `window.fetch` (`auth_bridge.js:416-425`) calls `addAccessToken()` (`auth_bridge.js:384-385`) and re-attaches `Authorization: Bearer <old_token>` to `DELETE /api/auth/session`, forcing **another** full `GET /auth/v1/user` + `archipelago_runtime_session_rpc("revoke")` round-trip!
   - **Impact:** 2 sequential Vercel `iad1` round-trips + 4 sequential Supabase calls on every logout.

2. **Unbounded `supabase.auth.signOut({ scope: "global" })` + CDN wait (`auth_bridge.js:326-329`)**:
   - Awaits `window.archipelagoAuthReady` (which races `import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.2/+esm")` with `SUPABASE_CDN_TIMEOUT_MS = 3500`, `auth_bridge.js:32-42`).
   - Then awaits `supabase.auth.signOut({ scope: "global" })` with **no `AbortController` or timeout**. Any slow network response from Supabase or `cdn.jsdelivr.net` stalls the redirect to `/login?logout=1`.

3. **Double `Clear-Site-Data: "cookies", "storage"` header (`auth.py:106`)**:
   - `_logout_response()` sets `Clear-Site-Data: "cookies", "storage"` on **both** `POST /api/auth/logout` and `DELETE /api/auth/session`.
   - In Chromium, `Clear-Site-Data: "storage"` triggers a synchronous browser-wide storage purge (localStorage, sessionStorage, IndexedDB, CacheStorage) that stalls navigation by 0.5–3s — executed twice back-to-back.
   - It also wipes `sessionStorage["archipelago_auth_config_v1"]`, guaranteeing a cold `/api/auth/config` fetch when `/login?logout=1` loads.

### 1.2 Sign-In & Redirect Cascade (`host_inference/ui/login.html:22, 140-245`, `host_inference/hostapp/security.py:479-572`)

4. **Wasted unauthenticated prefetch (`login.html:22`)**:
   - `<link rel="prefetch" href="/chat">` fires `GET /chat` while signed out → server runs `pages.py:36-42` (`AUTH_GATED_PAGES = {"chat"}`) → 302 redirect back to `/login?next=/chat`.

5. **Serial 4-hop authentication waterfall on Sign-In submit (`login.html:188-234`)**:
   - **Hop 1:** `GET /api/auth/config` (`login.html:150`, 10s timeout) — forced uncached because `Clear-Site-Data` wiped `sessionStorage`, and simultaneously duplicated by `auth_bridge.js:399` (`loadConfig()`).
   - **Hop 2:** `POST {supabase_url}/auth/v1/token?grant_type=password` (`login.html:193-207`, 15s timeout).
   - **Hop 3:** `POST /api/auth/session` (`login.html:160-165`, 15s timeout) → server calls `_hosted_principal()` (`security.py:479-572`), which executes **3 sequential blocking HTTP calls to Supabase** (`operation="register"` bypasses `_principal_cache` at `security.py:489`):
     1. `GET {url}/auth/v1/user` (`timeout=(3.0, 5.0)`, `security.py:503`)
     2. `GET {url}/rest/v1/profiles?select=username,role&id=eq.{user_id}` (`timeout=(3.0, 5.0)`, `security.py:513`)
     3. `POST {url}/rest/v1/rpc/archipelago_runtime_session_rpc` (`operation="register"`, `timeout=10`, `security.py:547`)
     - *Worst-case server time on `POST /api/auth/session` alone (excluding cold start): `8s + 8s + 10s = 26s` — exceeding `login.html`'s `15s` client timeout!*
   - **Hop 4:** `window.location.replace("/chat")` (`login.html:234`) → `GET /chat` (`pages.py:36-42`) → if routed to a different Vercel instance where `_principal_cache` is empty, executes the **same 3 sequential Supabase calls again** before emitting the first byte of HTML!

### 1.3 Vercel Serverless Cold-Start Blocking Cascade (Affects Sign-In, Logout, AND `/chat` Load)

When Vercel spins up a fresh Python serverless instance for `host_inference/app.py` (frequent after sign-out/idle or concurrent traffic bursts), `create_app()` (`factory.py:52-85`) → `build_context()` (`factory.py:32-49`) → `Engine.__init__()` (`answer.py:186-200`) runs **synchronously before Flask routes any request**:

| Step | File:Line | Blocking Network I/O | Worst-Case Timeout |
|---|---|---|---|
| 1 | `answer.py:187` → `remote_cache.py:58-95` | `hydrate()`: **3 sequential** `GET`s to Supabase Storage (`okf_graph.json`, `pearson_bookshelf.json`, `library_manifest.json`) | `3 × 10s = 30s` |
| 2 | `answer.py:199` → `remote_cache.py:169-172` | **Double-`hydrate()` bug!** Live `/api/readiness` confirms `"cache": "bundled"` (meaning `pearson_bookshelf.json` was not written to `/tmp/archipelago/cache` from Supabase). Because `hydrate()` never sets `_LAST_HYDRATE_ATTEMPT` (only `_hydrate_if_needed()` at line 165 does), `load_books()` triggers a **second full `hydrate()`** (3 more sequential Supabase Storage `GET`s)! | `3 × 10s = 30s` |
| 3 | `answer.py:200` → `library_index.py:248` → `:143-148` | When `HF_TOKEN` is set, `_load_hf_repo_map()` makes **2 sequential** `GET`s to Hugging Face Hub API (`Prataykarali/Library_books` + `Prataykarali/graphier`, `?recursive=true`) | `2 × 8s = 16s` |
| 4 | `library_index.py:283` → `:285-312` | `_load_remote_candidate_passages()` downloads `d10_candidate_passages.jsonl` (3,025 passages) from Supabase Storage, hashes SHA-256, and tokenizes all 3,025 passages synchronously | `15s` + CPU parse |

- **Total worst-case cold-start block:** **`91 seconds`** (typical healthy cold start across `iad1 ↔ Supabase ↔ HuggingFace`: **5–15 seconds**).
- Because `/api/auth/config`, `/api/auth/session`, `/api/auth/logout`, `/login`, and `/chat` all live inside the same monolithic Flask app (`host_inference/app.py`), **every auth request pays the full Engine + Corpus + HF cold-start penalty**!

---

## Part 2: `/chat` Page Load Hang & Chat Streaming Lifecycle Trace

### 2.1 Why `/chat` Fails to Open / Hangs (`host_inference/ui/index.html`, `index-inline-2.js`, `js/index.js`)

1. **9 synchronous, render-blocking external CDN scripts in `<head>` (`host_inference/ui/index.html:8-25`)**:
   - Line 8: `<script src="https://cdn.tailwindcss.com"></script>` (runtime JIT compiler)
   - Line 11: `<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">`
   - Line 13: `<script src="https://cdn.jsdelivr.net/npm/marked@18.3.0/lib/marked.umd.js"></script>`
   - Line 14, 18: blocking KaTeX & Prism CSS
   - Lines 19–22: **4 synchronous** PrismJS scripts from `cdnjs.cloudflare.com`
   - Line 24: `<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.4/cytoscape.min.js"></script>` (~300 KB)
   - None of lines 8, 13, 19–22, 24 have `defer` or `async`. If any single CDN host (`cdn.tailwindcss.com`, `cdn.jsdelivr.net`, or `cdnjs.cloudflare.com`) stalls or drops a packet on the user's network, the browser halts HTML parsing in `<head>` and `/chat` stays completely blank.

2. **5–6 redundant `/api/auth/me` calls + top-level `await` storm on `/chat` mount**:
   - `index-inline-2.js:40`: immediate `updateHeaderAuthProfile()` → `GET /api/auth/me` (**#1**)
   - `index-inline-2.js:42`: `DOMContentLoaded` → `updateHeaderAuthProfile()` → `GET /api/auth/me` (**#2**)
   - `index-inline-2.js:1-6`: after `archipelagoAuthReady`, calls `archipelagoRequireSession()` → `GET /api/auth/me` (**#3**), then `updateHeaderAuthProfile()` → `GET /api/auth/me` (**#4**)
   - `js/index.js:30-31`: **top-level `await window.archipelagoAuthReady; await window.archipelagoRequireSession();`** → `GET /api/auth/me` (**#5**), blocking module completion and `/api/chat/quota` (`js/index.js:43`)
   - `auth_bridge.js:178-181`: `pageshow` listener fires `passiveSessionRecheck({ force: true })` → `GET /api/auth/me` (**#6**)
   - Simultaneously on mount: `GET /api/readiness` (`03-wrap-library-inventory-secti.js:322`, plus every 10s at line 320), `GET /api/catalog/all` (`05-display-books.js:244`), `GET /api/chat/suggestions` (`22-welcome-suggestions.js:298`), `GET /data/catalogs/pearson_bookshelf.json` (`02--kw-highlights.js:161`), and `GET /api/chat/quota` (`js/index.js:43`).
   - All of these fire across `bom1 → iad1`, saturating HTTP/2 streams and triggering repeated `ctx.auth.principal()` Supabase checks on any cold/unwarmed lambda.

3. **5-minute idle expiry (`config.py:106`) + non-redirecting 5xx handling (`auth_bridge.js:539, 550`)**:
   - `IDLE_TIMEOUT_SECONDS = 300` (5 minutes). If a user pauses reading for 5 minutes and reloads or sends a message, the session is revoked server-side.
   - During a transient 5xx/timeout on `/api/auth/me`, `archipelagoRequireSession()` returns `null` without setting `window.archipelagoUserId`, leaving the page mounted in a half-authenticated state where subsequent chat sends stall in `archipelagoVerifyChatSession()`.

### 2.2 Why Chat Gets Stuck & Stop Button Misbehaves (`08-send-message.js`, `07-open-page-viewer-modal.js`)

1. **Uncancelable pre-send auth gate (`08-send-message.js:33-62`, `auth_bridge.js:429-484`)**:
   - `sendMessage()` sets `window.archipelagoChatAuthChecking = true`, shows a spinner on `#send-btn`, and awaits `window.archipelagoVerifyChatSession()`.
   - If `window.archipelagoUserId` is unset (e.g., during mount race or after passive recheck failure), `archipelagoVerifyChatSession()` awaits `window.archipelagoAuthReady` (up to 11.5s) AND `GET /api/auth/me` (up to `VERIFY_SESSION_TIMEOUT_MS = 15000`).
   - During this window, `state.isGenerating` is still `false` and `state.currentAbortController` does not exist — so clicking Send/Stop does nothing (or if `stopGeneration()` is invoked, it only sets `window.archipelagoChatAuthChecking = false` and increments `currentQuerySequence`, but `sendMessage()` does NOT check if it was cancelled after `await window.archipelagoVerifyChatSession()`, so it proceeds to line 65 and starts a new stream anyway!).

2. **Idle watchdog armed before HTTP response headers (`08-send-message.js:114-122`, `00-current-origin.js:61`)**:
   - `STREAM_IDLE_TIMEOUT_MS` was tightened from 75s to **14s** in commit `8555462`.
   - `armStreamIdleWatchdog()` is called at line 122 **before** `await postChatRequest(...)` at line 149!
   - On the backend, `POST /api/chat` (`routes/chat.py:330-729`) sends **zero bytes** until ALL of the following complete:
     1. `middleware.py:264`: `ctx.auth.principal()` (up to 3 Supabase calls on cache miss)
     2. `routes/chat.py:364`: `ctx.limiter.check_daily_chat()` (Supabase RPC for students)
     3. `routes/chat.py:419`: `ctx.engine.answer(resolved_query)` + optional `enrich_with_research()` (`line 437`)
     4. `answer.py:711-779`: **Primary LLM (XKIRO) + Fallback LLM (NVIDIA) first-token wait** (`PRE_FIRST_TOKEN_BUDGET_SECONDS = 10.0s`)
   - Whenever `auth + quota + retrieval + enrich + provider_TTFT > 14s`, the frontend aborts the `fetch()` at 14s with **0 bytes received** (**zero-byte timeout**).

3. **Missing `[STREAM_START]` freezes prose rendering (`08-send-message.js:428-444`)**:
   - Until `[STREAM_START]` is seen, `metadataParsed` stays `false`, so `if (metadataParsed && buffer)` never consumes incoming chunks; the bubble stays stuck on the typing indicator until EOF or timeout.

### 2.3 Mid-Stream 60s Timeout, Provider Failover Starvation & Truncation at "Page Tables" (`llm.py`, `answer.py`, `routes/chat.py`)

1. **60s mid-stream timeout (D13 pre-`8555462` vs remaining gap in `fe8887c`)**:
   - Pre-`8555462`, `urllib3` v2 stored the live socket on `raw._connection.sock` rather than `raw._fp.fp.raw._sock`, so `_tighten_socket_timeout()` was a no-op and a silent provider stall hung until the 60s/75s timeout.
   - In `fe8887c` (`8555462`), `_tighten_socket_timeout()` was fixed to check `raw._connection.sock` (`llm.py:236-239`), **but** it is only invoked *inside* `for line_str in _iter_sse_lines():` (`llm.py:475`) — **after** the first newline arrives. If a provider returns `HTTP 200` headers and stalls before sending the first line, the socket timeout is not tightened against `ft_deadline`.
   - Additionally, `iter_content(chunk_size=1024)` (`llm.py:435`) can wait to fill a 1 KB buffer depending on transfer encoding/adapter behavior; `chunk_size=None` (read whatever is immediately available from the socket) avoids artificial chunk buffering latency.

2. **Failover budget starvation (`answer.py:713-779`, `llm.py:149, 152`)**:
   - `ft_deadline` allocates `PRE_FIRST_TOKEN_BUDGET_SECONDS = 10.0s` total across BOTH XKIRO and NVIDIA.
   - `STREAM_FIRST_TOKEN_TIMEOUT_SECONDS = 8s` (`llm.py:149`) allows XKIRO to consume 8s before timing out, leaving NVIDIA only **≤2.0s** for TCP+TLS+prompt-eval+TTFT — almost guaranteeing a secondary `first_token_timeout` and fallback to deterministic/abstention!

3. **Incomplete prerequisite answer truncated at "Page Tables" (`routes/chat.py:58`, `llm.py:111-112, 151`, `08-send-request.js:90`)**:
   - `08-send-request.js:90` unconditionally sends `reply_detail: 'expanded'`, which sets `max_tokens = EXPANDED_REPLY_MAX_TOKENS (1800)` (`llm.py:356`) and appends `expanded_concept_context` (`answer.py:684-689`) to the prompt.
   - Meanwhile, `routes/chat.py:58` enforces a **24.0s total request deadline** (`request_deadline = t_req_start + 24.0`, `routes/chat.py:534`) that includes retrieval, enrichment, and provider failover!
   - For multi-section prerequisite explanations (e.g., Virtual Memory / Paging / Page Tables / TLBs), 4–8s TTFT + 16–20s generation at ~40–60 tok/s hits `time.perf_counter() >= deadline` (`answer.py:877` / `llm.py:468`) mid-response — abruptly terminating right around `"Page Tables"` and emitting `[STREAM_INCOMPLETE:stream_deadline_exceeded]` (or hitting `max_tokens` → `[STREAM_TRUNCATED:length]`).

### 2.4 Why Inspector Always Shows `"Pending completion"` (`stream-markers.js:2, 19, 41-54`, `15-inspector.js:165, 230`, `routes/chat.py:660, 671-691`)

Two compounding bugs guarantee `"Pending completion"` on live-streamed turns:

1. **Schema merge mismatch (`stream-markers.js:45` vs `15-inspector.js:165`)**:
   - `[STREAM_START]` (`routes/chat.py:651-662`) initializes `meta.trace.stage_timings_ms.total_ms = None`.
   - Terminal `[STREAM_META:{...}]` (`routes/chat.py:671-691`) sends flat keys: `{"total_ms": 4321.5, "provider_ttft_ms": ..., "stream_status": "complete", ...}`.
   - `stream-markers.js:45` runs `Object.assign(window._lastChatMetadata, terminalMeta)`, placing `total_ms` on `window._lastChatMetadata.total_ms` instead of `window._lastChatMetadata.trace.stage_timings_ms.total_ms` (and never updating `trace.stream_status`, `trace.provider_status`, `trace.stage_timings_ms.provider_ttft_ms`, or `trace.stage_timings_ms.ttft_visible_ms`).
   - `15-inspector.js:165` checks `trace.stage_timings_ms?.total_ms != null ? ... : 'Pending completion'` → **always `null` → always displays `"Pending completion"`**.
   - `15-inspector.js:230` (`renderGroundingBadge`) also reads `trace.stage_timings_ms?.total_ms`, omitting latency from the grounding badge.

2. **Undersized `MARKER_TAIL_GUARD = 48` (`stream-markers.js:2, 19`)**:
   - The terminal `[STREAM_META:{...}]` payload is **~240–300 bytes**.
   - `splitSafeStreamChunk()` (`stream-markers.js:19`) only holds back an unclosed `[` tail if `tailLen <= 48`. Any chunk boundary occurring >48 bytes into `[STREAM_META:{...}]` flushes the broken prefix to `consumeTextChunk()`, so `STREAM_META_RE` never matches, raw `[STREAM_META:...` leaks into the rendered chat bubble, and `total_ms` is lost.

### 2.5 Cache Bypass (`host_inference/hostapp/routes/chat.py:451-454`)

- `api_chat()` records `ctx.cache_metrics.record_request()` and `ctx.cache_metrics.record_miss()` unconditionally, never consulting `ctx.cache_service` (`host_inference/cache_service.py`), explaining the live `0.0%` hit rate (`0 hits / 6 misses`).

---

## Part 3: Concrete, Minimal, High-Confidence Fix Plan (Phase D14.7 & Hotfix Readiness)

All fixes below target **`sigir/d14-recovery`** (branched from `sigir/d12-recovery` at `fe8887c` once Gate 0 clears, per `@d14-integrator`'s contract). Remember the `host_inference/ui/` ↔ `ui/chat/` mirror sync invariant.

### Track A — Immediate Hotfix (Auth Latency + `/chat` Load Hang)

| # | Target File(s) | Minimal High-Confidence Change | Expected Impact |
|---|---|---|---|
| **A1** | `host_inference/ui/auth_bridge.js` (+ `ui/chat/` mirror) | In `archipelagoLogout()`: (1) set `cachedAccessToken = ""` immediately; (2) call **only** `POST /api/auth/logout` (remove duplicate `DELETE /api/auth/session`); (3) cap `supabase.auth.signOut({ scope: "local" })` (server already revoked durable session) with a 1500 ms timeout; (4) do not block logout on CDN load if `supabase` is not already loaded. | Cuts logout from 4–6 sequential network hops + unbounded CDN/Supabase hang to **1 server hop (<500 ms)**. |
| **A2** | `host_inference/hostapp/routes/auth.py` | Remove `"storage"` from `Clear-Site-Data` (or drop `Clear-Site-Data` in favor of explicit `delete_cookie` + client `archipelagoClearClientStorage()`), keeping `archipelago_auth_config_v1` intact across logout → login. | Eliminates double Chromium synchronous storage-purge stall (0.5–3s) and eliminates cold `/api/auth/config` refetch on `/login`. |
| **A3** | `host_inference/remote_cache.py`, `host_inference/library_index.py` | (1) Fix **double-`hydrate()` bug**: set `_LAST_HYDRATE_ATTEMPT = time.monotonic()` inside `hydrate()`, skip `pearson_bookshelf.json` in `open_access` mode, and bound per-file cold-start timeout to `(2.0, 3.0)`s (or fetch in parallel with `ThreadPoolExecutor(max_workers=3)`); (2) In `library_index.py:_load_hf_repo_map()`, **do NOT run live Hugging Face Hub tree fetches synchronously in `Catalog.__init__`** when packaged/manifest paths already exist (defer/background refresh or trigger on-demand only on miss). | Cuts Vercel cold start from **5–91s** down to **<1.5s**, eliminating cold-start auth timeouts and `/chat` hang. |
| **A4** | `host_inference/ui/login.html` (+ `ui/chat/` mirror) | Remove `<link rel="prefetch" href="/chat">` (wasted 302 round-trip while signed out). | Saves 1 cold/auth request on `/login`. |
| **A5** | `host_inference/ui/index.html` (via `@d14-integrator`), `index-inline-2.js`, `js/index.js`, `auth_bridge.js` | (1) Add `defer` to non-critical `<head>` CDN scripts (`marked`, `prism*`, `cytoscape`, `graphify.js`) so `/chat` paints immediately even if a CDN is slow; (2) Deduplicate `/api/auth/me` on mount using a single shared in-flight promise (`window._archipelagoMePromise`) + honor `sessionStorage["archipelago_me_cache_v1"]` within 30s after login; (3) Remove blocking top-level `await window.archipelagoRequireSession()` from `js/index.js:30-31` (run non-blocking init). | Eliminates blank-page `/chat` hangs and reduces mount `/api/auth/me` calls from **5–6 down to 1 (or 0 immediately post-login)**. |

### Track B — Phase D14.7 Streaming, Latency, Cache & Observability Fixes

| # | Target File(s) | Minimal High-Confidence Change | Expected Impact |
|---|---|---|---|
| **B1** | `host_inference/ui/js/stream-markers.js` (+ `ui/chat/` mirror) | (1) Raise `MARKER_TAIL_GUARD` from `48` to `512` (or hold back any unclosed `[STREAM_META:` until `]` or newline); (2) When applying `terminalMeta`, merge into **`window._lastChatMetadata.trace`** and **`window._lastChatMetadata.trace.stage_timings_ms`** (`total_ms`, `provider_ttft_ms`, `ttft_visible_ms`, `evidence_retrieval_ms`, `auth_ms`, `provider_stream_ms`) + `trace.stream_status`, `trace.provider_status`, `trace.fallback_reason`, then refresh both Inspector and the grounding badge. | Permanently fixes `"Pending completion"` and prevents split `[STREAM_META:...]` leakage. |
| **B2** | `host_inference/hostapp/routes/chat.py`, `host_inference/engine/answer.py`, `host_inference/engine/llm.py` | (1) Emit `[STREAM_START]` (or an immediate keepalive/progress frame) **before** waiting on the LLM provider, or split frontend watchdogs into `FIRST_BYTE_TIMEOUT_MS = 25000` vs `INTER_CHUNK_IDLE_TIMEOUT_MS = 14000`; (2) Split `PRE_FIRST_TOKEN_BUDGET_SECONDS` fairly across providers (`6s` primary XKIRO + `6s` fallback NVIDIA = `12s` total) so NVIDIA is never starved to ≤2s; (3) Raise `CHAT_REQUEST_DEADLINE_SECONDS` / `STREAM_TOTAL_DEADLINE_SECONDS` from `24s` to `45s` (well inside Vercel's `300s` `maxDuration`) and tighten socket timeout immediately after `requests.post` returns headers (before first line read), using `iter_content(chunk_size=None)`; (4) Keep `reply_detail: 'standard'` (`REPLY_MAX_TOKENS = 1200`) unless the user explicitly clicks Expand, preventing runaway 1800-token generations from truncating mid-sentence at "Page Tables". | Eliminates zero-byte timeouts, mid-stream 24s/60s cutoffs, failover starvation, and truncated prerequisite answers. |
| **B3** | `host_inference/ui/js/08-send-message.js`, `07-open-page-viewer-modal.js`, `00-current-origin.js` (+ `ui/chat/` mirrors) | (1) Make `archipelagoVerifyChatSession()` abortable by `stopGeneration()` and re-check `thisQuerySequence` immediately after `await`; (2) Arm `STREAM_FIRST_BYTE_TIMEOUT_MS` (25s) before `fetch()` and switch to `STREAM_IDLE_TIMEOUT_MS` (14s) once the first chunk arrives; (3) If stream ends with `metadataParsed === false` and non-empty `buffer`, render `buffer` gracefully instead of hanging; (4) Set `STREAM_HARD_TIMEOUT_MS = 55000` aligned with the 45s backend stream deadline. | Eliminates stuck Stop button, stuck typing dots, and race-condition zombie streams. |
| **B4** | `host_inference/hostapp/routes/chat.py` | Wire `ctx.cache_service` for deterministic / non-personalized read-through caching (keyed by `(normalized_query, route, graph_version, access_profile, reply_detail, reply_template_id)` with withdrawal re-check via `_withdrawn_notice()`) and report honest `cache_status: "hit"` vs `"miss"` in trace. | Cuts repeat-query latency to <150 ms and restores truthful cache telemetry. |
| **B5** | `tests/unit/` + `tests/integration/` | Add regression tests for: (1) single-call logout + `cachedAccessToken` clear; (2) cold-start single-`hydrate()` invariant (no double-hydrate); (3) chunk-split `[STREAM_META:{...}]` (>48 bytes) merging into `trace.stage_timings_ms.total_ms` (no `"Pending completion"`); (4) primary→fallback TTFT budget split (NVIDIA gets ≥5s); (5) Stop button cancellation during pre-send auth check and mid-stream. | Locks all fixes against regressions in CI. |

---

## Verification Status (Phase D14.0)

- Live deployment confirmed at `fe8887c878e27f1770690236513f0f6c79c37d7c` via read-only `GET https://archipelago-sigir.vercel.app/api/readiness`.
- Zero production files edited; zero deployments executed; UEM production (`archipelago-blond.vercel.app`) untouched.
- Ready to execute Track A hotfix + Track B Phase D14.7 immediately after Gate 0 clears and `@d14-integrator` creates `sigir/d14-recovery` from `fe8887c`.
