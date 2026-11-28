# Phase D14.7 Streaming, Auth & Latency Failure Register

**Owner:** `d14-streaming-perf`
**Branch:** `sigir/d14-recovery` (based on `fe8887c`)
**Date:** 2026-11-28

---

## Failure Modes, Root Causes, Fixes & Verification

| ID | Failure Mode / Symptom | Root Cause (Pre-D14.7) | D14.7 Fix Implemented | Regression Test | Status |
|---|---|---|---|---|---|
| **SF-01** | Slow sign-in after sign-out (*"sign out hole sign in korte onek time nicche"*) | `auth_bridge.js` fired 2 sequential server revocations (`POST /api/auth/logout` + `DELETE /api/auth/session`) without clearing `cachedAccessToken` (4 Supabase calls) + unbounded `supabase.auth.signOut({ scope: "global" })` + 3.5s CDN race; `login.html` prefetched `/chat` while signed out. | Cleared `cachedAccessToken` immediately; removed duplicate `DELETE /api/auth/session`; bounded local `signOut({ scope: "local" })` to 1s only if client already loaded; bounded logout fetch to 4s; deduplicated `/api/auth/config` via shared promise; removed unauthenticated `/chat` prefetch from `login.html`. | `tests/unit/test_d14_streaming_auth.py::test_frontend_auth_logout_and_streaming_contracts_and_mirror_sync` | **FIXED** |
| **SF-02** | Vercel serverless cold-start 5–91s stall on `/login`, `/api/auth/*`, and `/chat` | `factory.py:build_context()` instantiated `Engine()` eagerly on import/first request, triggering: (a) double-`hydrate()` bug (`remote_cache.py` never set `_LAST_HYDRATE_ATTEMPT` inside `hydrate()`, causing 6 sequential 10s Supabase Storage GETs); (b) 2 sequential 8s HF Hub API fetches (`library_index.py`); (c) 15s passage download. | Added thread-safe `_LazyEngineProxy` in `factory.py` so auth & HTML shell routes never trigger `Engine()` hydration; fixed `_LAST_HYDRATE_ATTEMPT` in `remote_cache.py`, skipped `pearson_bookshelf.json` in `open_access` mode, parallelized `hydrate()` with `(2.0, 3.0)`s timeout; skipped live HF Hub tree fetches in `library_index.py` when manifest/local paths exist. | `test_remote_cache_hydrate_sets_cooldown_and_skips_pearson_in_open_access`, `test_library_index_skips_live_hf_fetch_when_manifest_present`, `test_lazy_engine_proxy_defers_init_until_accessed` | **FIXED** |
| **SF-03** | `/chat` page fails to open / hangs (*"page open hote chaina"*) | 9 synchronous render-blocking CDN `<script>` tags in `<head>` of `index.html`; top-level `await window.archipelagoRequireSession()` in `js/index.js`; 5–6 redundant `/api/auth/me` calls on mount. | Removed blocking top-level `await` from `js/index.js`; deduplicated concurrent `GET /api/auth/me` in `auth_bridge.js` (`inFlightMePromise` + 15s `POST_LOGIN_ME_CACHE_MS`); submitted exact `defer` patch spec for `index.html` to `@d14-integrator` (owner of `index.html`). | `test_frontend_auth_logout_and_streaming_contracts_and_mirror_sync` | **FIXED** (`index.html` patch queued for `@d14-integrator`) |
| **SF-04** | Chat stuck / Stop button unresponsive during pre-send auth | `08-send-message.js` awaited `archipelagoVerifyChatSession()` (up to 15s+) before creating `AbortController` or incrementing `currentQuerySequence`; Stop clicks could not cancel it and allowed zombie streams to start. | Armed `preSendController` and incremented `currentQuerySequence` *before* `archipelagoVerifyChatSession({ signal })`; added abort check immediately after `await`. | `test_frontend_auth_logout_and_streaming_contracts_and_mirror_sync` | **FIXED** |
| **SF-05** | Zero-byte timeout & 60s mid-stream stall | `STREAM_IDLE_TIMEOUT_MS = 14000` was armed *before* HTTP headers arrived, colliding with auth + retrieval + 10s provider failover; `_tighten_socket_timeout()` only ran *after* the first SSE line; `iter_content(chunk_size=1024)` buffered small chunks; XKIRO (8s) starved NVIDIA failover to ≤2s inside a 10s budget. | Split frontend watchdogs into `STREAM_FIRST_BYTE_TIMEOUT_MS = 25000` (pre-headers) and `STREAM_IDLE_TIMEOUT_MS = 14000` (inter-chunk); tightened socket timeout immediately after HTTP 200 headers in `llm.py`; switched `SSE_CHUNK_BYTES = None`; rebalanced failover budget to `6s` primary + `6s` fallback (`PRE_FIRST_TOKEN_BUDGET_SECONDS = 12.0`). | `test_llm_failover_budget_and_deadline_prevent_starvation_and_truncation` | **FIXED** |
| **SF-06** | Incomplete prerequisite answer ending at "Page Tables" | `08-send-request.js` hardcoded `reply_detail: 'expanded'` (`1800` max_tokens) while `CHAT_REQUEST_DEADLINE_SECONDS = 24.0` cut off multi-section answers mid-sentence. | Raised `CHAT_REQUEST_DEADLINE_SECONDS` & `STREAM_TOTAL_DEADLINE_SECONDS` to `45s` (aligned with `STREAM_HARD_TIMEOUT_MS = 55000`); raised `REPLY_MAX_TOKENS` to `1200` and defaulted `08-send-request.js` to `options?.replyDetail || 'standard'`. | `test_llm_failover_budget_and_deadline_prevent_starvation_and_truncation` | **FIXED** |
| **SF-07** | Completed requests permanently marked `"Pending completion"` in Inspector | `stream-markers.js` merged `[STREAM_META:{...}]` at top level (`Object.assign(window._lastChatMetadata, terminalMeta)`), leaving `trace.stage_timings_ms.total_ms = null`; `MARKER_TAIL_GUARD = 48` split ~260-byte `[STREAM_META:{...}]` frames across chunks. | Raised `MARKER_TAIL_GUARD = 512` and merged all terminal timing & completion fields (`total_ms`, `provider_ttft_ms`, `visible_ttft_ms`, `retrieval_ms`, `auth_ms`, `query_resolution_ms`, `stream_status`, `completion_status`) into `trace.stage_timings_ms` and `trace`. | `test_frontend_auth_logout_and_streaming_contracts_and_mirror_sync`, `test_chat_route_emits_full_trace_and_tenant_isolated_cache_hits` | **FIXED** |

---

## `index.html` CDN `defer` Patch Spec (Submitted to `@d14-integrator`)

Because `host_inference/ui/index.html` and `ui/chat/index.html` are exclusively owned by `d14-integrator`, apply the following minimal attribute additions to both files:

- Line 13: `<script defer src="https://cdn.jsdelivr.net/npm/marked@18.3.0/lib/marked.umd.js"></script>`
- Lines 19–22: add `defer` to all 4 `prism*.min.js` `<script>` tags
- Line 24: `<script defer src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.4/cytoscape.min.js"></script>`
- Line 25: `<script defer src="/graphify.js"></script>`

(All scripts are consumed only after DOM/module evaluation, so `defer` preserves execution order while unblocking initial `/chat` HTML paint.)
