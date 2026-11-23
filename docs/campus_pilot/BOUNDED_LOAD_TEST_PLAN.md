# Bounded Load Test Plan — UEM Kolkata Campus Pilot

> **PLAN ONLY — DO NOT EXECUTE AGAINST LIVE INFRASTRUCTURE WITHOUT WRITTEN AUTHORIZATION.**  
> No load tests were executed during this assessment. This plan defines safe, bounded capacity validation to be run **only** against an approved staging environment (or scheduled maintenance window) after P0/P1 fixes and UEM IT / Koha consent are in place.

---

## 1. System Constraints & Serverless Budgets (Verified from Repo)

| Component | Verified Limit / Configuration | Source |
|---|---|---|
| Vercel Function Duration (`host_inference`, `host_research`) | `maxDuration: 300` seconds | `host_inference/vercel.json:5`, `host_research/vercel.json:3` |
| Max Request Payload | 5 MiB (`host_inference`), 2 MiB (`host_research`) | `config.py:27`, `host_research/app.py:37` |
| Student Rolling Chat Quota | **10 queries / 3600s** per student (Supabase RPC) | `security.py:57-58`, `20261114030000_student_rolling_hour_quota.sql` |
| Per-Instance Rate Limits (`host_inference`) | Chat: 20 req/min (1.0s min gap); API: 120 req/min (0.05s gap); Auth: 20 req/min (0.25s gap) | `config.py:55-61` |
| Per-Instance Rate Limits (`host_research`) | Reads: 120 req/min; Mutations: 30 req/min | `host_research/app.py:42-44` |
| Upstream LLM Pacing & Timeouts | `XKIRO` -> `NVIDIA` fallback; 45s timeout; 0.8s per-worker spacing (`COMPLETE_SPACING_SECONDS`) | `host_inference/engine/llm.py:93-96` |
| Live Koha OPAC Client | 3s timeout, max 3 detail pages/query, 2MB cap, fallback to Supabase snapshot | `koha_bridge.py:26-29, 493-530` |

---

## 2. Target Pilot Workload Model (UEM Kolkata Cohort)

Assume a bounded initial pilot of **100 enrolled students + 10 staff** (peak classroom concurrency: **20 concurrent active users**, ~15% of cohort simultaneously querying):

| Traffic Mix | Weight | Endpoint | Auth Role | Expected Upstream Cost |
|---|---|---|---|---|
| Health / Readiness | 10% | `GET /api/readiness` | Anonymous | Zero (in-memory graph check) |
| Library Catalogue Browse | 25% | `GET /api/library/data` | Anonymous / Student | Low (300s cached snapshot) |
| Graph Neighborhood Explore | 30% | `GET /api/graph/subgraph`, `GET /api/graph/page` | Student (test account) | Low (in-memory graph) |
| Grounded Chat Query | 25% | `POST /api/chat` | Student (test account) | **High** (LLM stream + Supabase quota RPC) |
| Quota / Auth Status | 10% | `GET /api/chat/quota`, `GET /api/auth/me` | Student (test account) | Low (Supabase RPC / 45s principal cache) |

**Explicitly Excluded from Automated Load Tests:**
- Live `uemk-opac.l2c2.co.in` queries (must be mocked/stubbed in staging or capped at `<= 1 req/s` to avoid impacting UEM's production Koha OPAC).
- Live `/papers/` or `/pdfs/` streaming from HuggingFace (avoid bandwidth/quota exhaustion).
- `POST /api/research/jobs`, `POST /api/ingest`, and Vercel Cron endpoints.

---

## 3. Staged Bounded Execution Tiers

Tooling: `tests/performance/locustfile.py` (extended for staging test tokens and quota-aware pacing).

| Stage | Virtual Users | Ramp Rate | Duration | Max Total Chat Requests | Purpose |
|---|---|---|---|---|---|
| **Stage 1: Smoke Baseline** | 5 VUs | 1 VU/s | 3 min | <= 30 | Verify cold-start latency, auth, headers, zero 5xx |
| **Stage 2: Classroom Peak** | 20 VUs | 2 VU/s | 10 min | <= 150 | Simulate live lecture cohort; validate TTFT & quota enforcement |
| **Stage 3: Burst / Rate-Limit** | 40 VUs | 5 VU/s | 5 min | <= 200 | Verify graceful `429 Retry-After` and absence of cascading 503/504 |

---

## 4. Service Level Objectives (SLOs) & Error Budgets

| Metric | Target SLO (Pass) | Warning Threshold | Hard Abort Threshold |
|---|---|---|---|
| Non-LLM API latency (`p95`) | `<= 600 ms` | `> 800 ms` | `> 2000 ms` for 60s |
| Chat Time-To-First-Token (`p95`) | `<= 3.5 s` | `> 5.0 s` | `> 10.0 s` for 60s |
| Chat Full Stream Completion (`p95`) | `<= 15.0 s` | `> 25.0 s` | `> 45.0 s` (provider timeout) |
| Server Error Rate (`5xx`) | `< 0.5%` | `>= 1.0%` | `>= 2.0%` over any 60s window |
| Expected Quota/Rate `429` Handling | Valid JSON + `Retry-After` header | Missing `Retry-After` | Unhandled `500` on quota breach |
| Serverless Cold-Start 504s | `0` | `>= 1` | `>= 3` in 5 minutes |

---

## 5. Mandatory Safety Guardrails & Abort Conditions

1. **Staging Isolation Only:** Run against a dedicated Vercel preview + staging Supabase project with synthetic test student accounts (`pilot-load-01`..`pilot-load-40`); never run against production student data or live Koha OPAC.
2. **Pre-Test LLM Budget Cap:** Set a hard provider spend cap (<= $5 USD) on `XKIRO_API_KEY` / `NVIDIA_API_KEY` staging keys before starting Stage 1.
3. **Immediate Kill Switch:** Abort the Locust runner immediately if:
   - `5xx` rate exceeds **2%** for 60 seconds,
   - Supabase connection pool saturation or RPC timeouts (`503 quota_unavailable`) occur,
   - LLM provider returns sustained `429`/`503` fallback failures, or
   - Any unintended traffic reaches `uemk-opac.l2c2.co.in`.
4. **Post-Test Verification:** Purge synthetic test accounts' quota/run rows via `s5_research_rpc('delete_user_data')` and record a latency/error report (`p50`, `p95`, `p99`, `5xx%`, cold-start count) as evidence for Campus GO review.
