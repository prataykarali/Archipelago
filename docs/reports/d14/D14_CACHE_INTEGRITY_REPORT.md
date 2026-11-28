# Phase D14.7 Cache Integrity & Observability Report

**Owner:** `d14-streaming-perf`
**Branch:** `sigir/d14-recovery` (based on `fe8887c`)
**Date:** 2026-11-28

---

## 1. Cache Key Versioning & Tenant Isolation

Prior to D14.7, `host_inference/hostapp/routes/chat.py:451-454` bypassed `ctx.cache_service` completely (`0.0%` live hit rate on `/api/readiness`). D14.7 wires `CacheService.build_versioned_key()` (`host_inference/cache_service.py`) into `POST /api/chat` with strict isolation guarantees:

| Key Component | Purpose | Isolation Guarantee |
|---|---|---|
| `norm_query` | Normalized query text (preserves `+`, `*` for `B+ Tree`, `C++`, `A*`) | Equivalent phrasing maps cleanly without conflating distinct technical terms |
| `tenant_scope` | `user:<id>:role:<role>` (or `open:<access_profile>` when auth disabled) | **Strict per-user & per-role tenant isolation** — Student/Faculty/Librarian responses never cross-contaminate |
| `access_profile` | `open_access` vs `institutional` | Guarantees SIGIR open-access answers never leak UEM institutional/Pearson payloads |
| `graph_version` | Live `ctx.engine.graph.graph_version` | Automatic cache invalidation when `graph_v1_okf610` → `graph_v2_d14` changes |
| `corpus_version` | Live `candidate_passages_info.sha256[:12]` (or `corpus_source`) | Automatic cache invalidation when `corpus_v2_d10_3025` → `corpus_v3_d14` changes |
| `release_sha` | `runtime_release_sha()` | Automatic cache invalidation on every release deployment |
| `model_version` + `prompt_version` | Active synthesis model & prompt revision | Prevents stale prose across prompt/model upgrades |
| `reply_detail` + `template_id` | `standard`/`expanded` + template ID | Separates distinct formatting contracts |

### Safety Invariants
1. **Stateful / conversational turns bypassed:** When `history` is non-empty, caching is bypassed (`cache_status: "bypass_history"`) to prevent cross-turn context contamination.
2. **Incomplete / errored streams never cached:** Only responses with `terminal_stream_status == "complete"` and non-empty prose are written to cache.
3. **Withdrawal re-check on replay:** `_withdrawn_notice(cached_citations)` is evaluated on both write and replay; withdrawn sources are never served from cache.
4. **Honest `cache_status` telemetry:** Reports `"hit"`, `"miss"`, `"bypass_history"`, or `"miss_no_reuse"` accurately in both `[STREAM_START]` and `[STREAM_META]`.

---

## 2. Full Observability Trace Contract

Every `POST /api/chat` response emits a complete, honest trace object in `[STREAM_START]` and finalizes terminal timings in `[STREAM_META:{...}]`:

- **Identity & Provenance:** `request_id` (UUID), `release_sha`, `graph_version` (`graph_revision`), `corpus_version`, `retrieval_mode`, `generation_mode` (`synthesis_mode`), `provider`, `model`, `cache_status`, `completion_status` (`stream_status`).
- **Stage Timings (`stage_timings_ms`):** `auth_ms`, `query_resolution_ms`, `retrieval_ms` (`evidence_retrieval_ms`), `reranking_ms`, `provider_ttft_ms`, `visible_ttft_ms` (`ttft_visible_ms`), `provider_stream_ms`, `total_ms`.
- **Missing-Value Honesty:** Any stage that was not executed or not separately instrumented is explicitly emitted as **`null`** (`None` in Python) — never fabricated as `0`.

---

## 3. Verification Evidence

- Verified via `tests/unit/test_d14_streaming_auth.py`:
  - `test_versioned_cache_keys_isolate_tenants_profiles_and_versions` — verifies 5 distinct keys across users, access profiles, graph versions, and corpus versions, plus tenant-isolated hit/miss behavior.
  - `test_chat_route_emits_full_trace_and_tenant_isolated_cache_hits` — verifies full trace schema, `null` for unmeasured timings (`reranking_ms`, `auth_ms`), and second-turn `cache_status == "hit"` without invoking `stream_chat` a second time.
