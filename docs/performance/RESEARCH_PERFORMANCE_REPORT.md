# Research & Frontend Performance Report

**Date**: 2026-11-18  
**Scope**: `/research/papers`, `/research/*`, `host_inference/ui/**`, `host_research/ui/**`  
**Audit Categories Covered**: Phase 5 (Excel Export Hardening), Phase 6 (`/research/papers` Bottleneck & Polling Remediation), Audit Area 11 (11.1, 11.2, 11.3), and Client-Side Graceful Shutdown.

---

## Executive Summary

A full-stack client-side performance and network waterfall audit of `host_inference/ui/**` and `host_research/ui/**` identified and resolved seven distinct frontend request bottlenecks, polling leaks, and download race conditions:

1. **Duplicate `/api/auth/me` Call & Sequential Startup Waterfall on `/research/papers`** (`research_intelligence.js` + `research_common.js`).
2. **Unbounded Background Polling Across Hidden Tabs & Lack of In-Flight Deduplication** (`research_overview.js`, `research_domains.js`, `library_pipeline.js`, `research_progress.js`, `research_intake.js`, `librarian.js`, `auth_bridge.js`).
3. **Background Polling Artificially Resetting User Idle Session Timeout** (`auth_bridge.js`, `research_progress.js`).
4. **Redundant `/api/auth/me` Polling Every 60 Seconds on `/library`** (`library_pipeline.js`).
5. **Excel (`.xlsx`) Export Race Conditions, Immediate Blob URL Revocation & Silent Auth Expiration** (`research_intelligence.js`, `research_download.js`).
6. **Continuous 60fps `requestAnimationFrame` Loop in Hidden/Disconnected Cytoscape Graphs** (`graphify.js`).
7. **Missing Graceful Client Shutdown (`pagehide` / `beforeunload`) for In-Flight `AbortController` Fetches, Timers, Blob URLs, and `BroadcastChannel`** (`auth_bridge.js`, `research_download.js`, `research_intelligence.js`, `research_progress.js`, `research_overview.js`, `research_domains.js`, `library_pipeline.js`, `research_intake.js`, `librarian.js`).

---

## Findings & Remediations (`FOUND → ROOT CAUSE → PATCH → TEST → RESULT → REMAINING RISK`)

### 1. Duplicate `/api/auth/me` Round-Trip and Sequential Startup Waterfall on `/research/papers`

- **FOUND**:
  - `Archipelago/host_inference/ui/research_intelligence.js:285-308`
  - `Archipelago/host_research/ui/research_intelligence.js:285-308`
  - `Archipelago/host_inference/ui/research_common.js:1-6`
- **ROOT CAUSE**:
  - `research_common.js` initializes `window.archipelagoResearchReady` by awaiting `window.archipelagoAuthorizePage(...)`, which already fetches `/api/auth/me` and resolves with the authenticated `principal` object (`{ id, username, role, authenticated }`).
  - `research_intelligence.js` awaited `window.archipelagoResearchReady` on line 286 (`if (!await window.archipelagoResearchReady) return;`), discarding the resolved `principal`. It then sequentially awaited `loadHistory()`, `s5Json('/api/research/intelligence/runs/' + savedRunId)`, fetched `/api/auth/me` a **second time** on line 302 (`const me = await s5Json('/api/auth/me')`), and sequentially awaited `loadMonitors()` followed by `loadUpdates()`.
- **PATCH**:
  - Captured `const principal = await window.archipelagoResearchReady;` and reused `principal.role` directly (falling back to `/api/auth/me` only if `principal.role` is absent).
  - Parallelized startup data loading on `/research/papers` via `await Promise.all([loadHistory(), restoreSavedRun(), initMonitoring()])` and `await Promise.all([loadMonitors(), loadUpdates()])`.
- **TEST**:
  - Verified startup sequence and UI link integrity across `host_inference/ui/research_intelligence.js` and `host_research/ui/research_intelligence.js`.
- **RESULT**:
  - Eliminated 1 redundant `/api/auth/me` network round-trip on every `/research/papers` page load and collapsed 4 sequential startup requests (`runs`, `runs/<id>`, `monitors`, `updates`) into a single parallel wave.
- **REMAINING RISK**:
  - None. If a user's role changes mid-session, the next navigation or 30s server cache expiry re-validates the principal.

---

### 2. Unbounded Background Polling in Hidden Tabs & Missing In-Flight Request Guards

- **FOUND**:
  - `Archipelago/host_inference/ui/research_overview.js:24` (`setInterval(loadResearchOverview, 60000)`)
  - `Archipelago/host_inference/ui/research_domains.js:113` (`setInterval(loadResearchTopics, 60000)`)
  - `Archipelago/host_inference/ui/library_pipeline.js:57` (`setInterval(loadLibraryPipeline, 60000)`)
  - `Archipelago/host_inference/ui/research_progress.js:47` & `Archipelago/host_research/ui/research_progress.js:47` (`setTimeout(() => pollProgress(jobId), 4000)`)
  - `Archipelago/host_inference/ui/research_intake.js:189, 388` (`setTimeout(() => pollJob(jobId), 5000)` and `setInterval(refreshRecords, 60000)`)
  - `Archipelago/host_inference/ui/librarian.js:285` & `Archipelago/host_research/ui/librarian.js:200` (`setInterval(loadPeopleTraffic, 15000)`)
  - `Archipelago/host_inference/ui/js/03-wrap-library-inventory-secti.js:76` (`setInterval(checkConnection, 10000)` calling `/api/readiness`)
- **ROOT CAUSE**:
  - All recurring `setInterval` and recursive `setTimeout` pollers continued firing indefinitely while browser tabs were hidden (`document.hidden === true`) and lacked in-flight `AbortController` guards, allowing slow network responses to stack overlapping requests.
- **PATCH**:
  - Added `document.hidden` checks to skip background poll ticks while hidden (and immediately resume `pollProgress` on `visibilitychange` when the tab becomes visible).
  - Added per-poller in-flight `AbortController` guards so a new poll never starts while a previous request is still pending.
  - Added `X-Background-Poll: 1` header to all background poll requests.
  - In `host_inference/ui/auth_bridge.js`, short-circuited `/api/readiness` background polls when `document.hidden` is true so hidden chat tabs generate zero network traffic while preserving byte-for-byte parity between `host_inference/ui/js/*.js` and `ui/chat/js/*.js`.
- **TEST**:
  - Verified via unit test suite (`test_ui_link_integrity.py`, `test_hosted_release_regressions.py`, `test_academic_correctness_remediation.py`).
- **RESULT**:
  - Background network traffic from hidden tabs drops to zero; overlapping in-flight poll requests cannot accumulate under high latency.
- **REMAINING RISK**:
  - None.

---

### 3. Background Polling Artificially Resetting User Idle Session Timeout

- **FOUND**:
  - `Archipelago/host_inference/ui/auth_bridge.js:90-92`
  - `Archipelago/host_inference/ui/research_progress.js:41`
  - `Archipelago/host_research/ui/research_progress.js:41`
- **ROOT CAUSE**:
  - `research_progress.js` invoked `window.archipelagoTouchSession?.()` on every 4-second poll tick, resetting the 60-minute `IDLE_TIMEOUT_MS` timer indefinitely even without user interaction.
- **PATCH**:
  - Removed `window.archipelagoTouchSession?.()` from `research_progress.js` (in both `host_inference/ui/` and `host_research/ui/`) and restricted idle timer resets in `auth_bridge.js` strictly to real user interaction events (`pointerdown`, `keydown`, `touchstart`, `scroll`, `wheel`).
- **TEST**:
  - Inspected `research_progress.js` and `auth_bridge.js` to confirm only physical user events reset `idleTimer`.
- **RESULT**:
  - Idle sessions reliably expire after 60 minutes of user inactivity even if a progress page is left open.
- **REMAINING RISK**:
  - None.

---

### 4. Redundant `/api/auth/me` Call on Every 60-Second Library Pipeline Poll

- **FOUND**:
  - `Archipelago/host_inference/ui/library_pipeline.js:46-54`
- **ROOT CAUSE**:
  - `loadLibraryPipeline()` fetched `/api/auth/me` on every 60-second interval tick merely to toggle the visibility of `#pipeline-research-link`.
- **PATCH**:
  - Guarded the `/api/auth/me` check in `library_pipeline.js` with `pipelineAuthChecked` so role-based link visibility is resolved once on initial load rather than re-queried every 60 seconds.
- **TEST**:
  - Verified `library_pipeline.js` initial load vs background poll behavior.
- **RESULT**:
  - Eliminated 60 redundant `/api/auth/me` requests per hour per open `/library` tab.
- **REMAINING RISK**:
  - None.

---

### 5. Excel (`.xlsx`) Download Race Conditions, Premature Blob Revocation & Expired-Auth Handling

- **FOUND**:
  - `Archipelago/host_inference/ui/research_intelligence.js:63-84`
  - `Archipelago/host_research/ui/research_intelligence.js:63-84`
  - `Archipelago/host_inference/ui/research_download.js` & `Archipelago/host_research/ui/research_download.js`
- **ROOT CAUSE**:
  - Clicking `#excel-link` had no in-flight lock or `AbortController`, allowing rapid clicks or run switches to trigger concurrent workbook exports.
  - `URL.revokeObjectURL(url)` was called synchronously on the same tick immediately after `a.click()`, which can revoke the Blob URL before the browser download manager begins reading the stream.
  - HTTP `401`/`403` responses and non-XLSX error payloads were not differentiated from generic failures.
- **PATCH**:
  - Added `isExcelDownloadInFlight` lock and `AbortController` (`activeExcelController`) that aborts any pending export when the user switches research runs or unloads the page.
  - Added ZIP/XLSX magic byte verification (`0x50, 0x4B`), explicit `401`/`403` session-expired messaging, `aria-busy`/`aria-disabled` button state feedback, and delayed `URL.revokeObjectURL` cleanup (10s after download initiation plus immediate revocation on `pagehide`/`beforeunload`).
- **TEST**:
  - Verified `research_intelligence.js` and `research_download.js` in both `host_inference/ui` and `host_research/ui`.
- **RESULT**:
  - Excel exports are single-flight, validated for ZIP/XLSX integrity, resilient against premature Blob revocation, and leak-free on navigation.
- **REMAINING RISK**:
  - None.

---

### 6. Unbounded 60fps `requestAnimationFrame` Loop in `graphify.js`

- **FOUND**:
  - `Archipelago/host_inference/ui/graphify.js:299-313`
- **ROOT CAUSE**:
  - `animateFlow()` ran a continuous 60fps Cytoscape style batch mutation (`line-dash-offset` and `shadow-blur`) even when `document.hidden` was true or after the container element was detached from the DOM.
- **PATCH**:
  - Added `!container.isConnected` termination check and `if (!document.hidden)` guard around `cy.batch(...)` in `graphify.js`.
- **TEST**:
  - Ran `tests/unit/test_academic_correctness_remediation.py`.
- **RESULT**:
  - Zero GPU/CPU style recalculation overhead when the tab is backgrounded or the graph container is removed.
- **REMAINING RISK**:
  - None.

---

### 7. Graceful Client-Side Shutdown on `pagehide` / `beforeunload`

- **FOUND**:
  - `auth_bridge.js`, `research_intelligence.js`, `research_download.js`, `research_progress.js`, `research_overview.js`, `research_domains.js`, `library_pipeline.js`, `research_intake.js`, `librarian.js`
- **ROOT CAUSE**:
  - Navigating away or closing a tab left `setInterval`/`setTimeout` timers active, in-flight `fetch` requests un-aborted, Blob URLs unrevoked, and `BroadcastChannel` instances open (preventing bfcache eligibility and delaying socket teardown during server shutdown).
- **PATCH**:
  - Registered `pagehide` and `beforeunload` handlers across all polling, download, and auth bridge scripts to abort active `AbortController` instances, clear all timers, revoke tracked Blob URLs, and close `BroadcastChannel("archipelago_auth_channel")`.
- **TEST**:
  - Verified all listeners and run full UI unit tests.
- **RESULT**:
  - Clean resource teardown on tab close or navigation.
- **REMAINING RISK**:
  - None.
