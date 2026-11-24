# UEM Kolkata Campus Pilot Readiness Assessment (Issue #14)

**Assessment Scope:** Archipelago hosted services (`host_inference` on `archipelago-blond.vercel.app`, `host_research` on `archipelago-librarian.vercel.app`), Supabase database/RLS migrations, and local library workstation workflows (`deploy/library-computer/`).  
**Assessment Mode:** Read-only architecture, security, RBAC, privacy, licensing, and operational readiness audit (no production runtime mutations, no live load generation, no live ILS/Koha writes, no licensed textbook scraping).  
**Baseline Commit:** `00f38b81351ebaeb5aff2fd36c5e64ea37319524`

---

## Explicit Readiness Verdict

| Track | Verdict | Scope Note |
|---|---|---|
| **UEM Kolkata Campus Pilot** | **HOLD** | Blocked by 2 verified P0 security defects, 5 P1 architectural/privacy/governance gaps, and missing formal UEM Kolkata institutional sign-offs. |
| **SIGIR 2027 Research Demonstration** | **NOT BLOCKED BY THIS ASSESSMENT** | This Campus Pilot `HOLD` is strictly scoped to institutional campus rollout and does not block controlled SIGIR demo readiness (tracked separately under Issues #11, #12, #13). |

> **Why `HOLD` (not `GO`)?**  
> Code changes alone cannot authorize a campus pilot. Even after engineering fixes land for the P0/P1 findings below, Campus `GO` requires explicit written authorization from UEM Kolkata IT, Central Library, and academic governance covering student privacy disclosure, Koha OPAC integration consent, Pearson/dataset licensing, and named staff operational ownership.

---

## Verified Findings Summary

| ID | Severity | Area | Summary & Exact Code Evidence |
|---|---|---|---|
| **P0-1** | **P0** | Auth Bypass / License Boundary | `GET /pdfs/<doc_path>` streams private HuggingFace dataset PDFs (using server `HF_TOKEN`) **without authentication or rate limiting** because `middleware.py:256-258` guards `/open/`, `/papers/`, and exact `/read`, omitting `/pdfs/` and `/read/<subpath>` registered in `reader.py:116-118, 176-178`. |
| **P0-2** | **P0** | Authorization (IDOR / BOLA) | `GET /api/research/intelligence/runs/<run_id>/dossier` (`research_intelligence.py:336-351`) falls back to `hosted_store().get_run(str(run_id), manager=True)` when owner lookup fails, allowing any authenticated student or faculty user to read another user's private research run dossier. |
| **P1-1** | **P1** | Serverless Session State | Session revocation (`end_session`), 5-min idle timeout, handoff tickets, IP rate buckets, and fallback CSRF key (`_PROCESS_CSRF_KEY`) are process-local in-memory (`security.py:70-73, 161-165, 205, 240-340, 472-477`) and do not synchronize across Vercel serverless instances. |
| **P1-2** | **P1** | Privacy & Retention Mismatch | `docs/guides/PRIVACY_POLICY.md` v1.0 claims local-only operation with no cloud DB or external LLM APIs, contradicting hosted Supabase storage and external LLM calls (`XKIRO`/`NVIDIA`, `engine/llm.py:79-86`). `DELETE /api/chat/history` (`chat.py:546-569`) clears only single-instance memory + local SQLite, not Supabase tables (`s5_research_rpc` `delete_user_data` has no HTTP route). `GET /api/analytics/summary` exposes 80-char student query snippets (`user_traffic.py:160-168`) to staff. |
| **P1-3** | **P1** | Institutional Identity | No SSO/LDAP/Google Workspace `@uem.edu.in` domain enforcement or automated graduation/offboarding lifecycle (`supabase/migrations/20260916_000001_auth_roles.sql:59-77`). |
| **P1-4** | **P1** | Browser Security / CSP | CSP in `middleware.py:50-59` and `host_research/app.py:311-319` permits `'unsafe-inline'` scripts and Tailwind Play CDN (`https://cdn.tailwindcss.com`), weakening XSS defense-in-depth. |
| **P1-5** | **P1** | Institutional & License Governance | Missing formal UEM IT/Library sign-off, Koha OPAC live-lookup consent (`uemk-opac.l2c2.co.in`), Pearson eLibrary deep-link/ToS confirmation, and copyright provenance audit of `Prataykarali/Library_books` HF dataset. |
| **P2-1** | **P2** | Elevated UI Shells | `/librarian`, `/analytics`, `/academic/graph`, `/academic-automation`, `/research`, and `/index.html` return HTML shells unauthenticated (`pages.py`, `analytics.py`, `static.py`), though backing APIs enforce auth. |
| **P2-2** | **P2** | RBAC Fragmentation | Role sets (`STAFF_ROLES`, `MANAGER_ROLES`, `_RESEARCH_STAFF_ROLES`) are duplicated across 7+ route modules, increasing drift risk. |
| **P2-3** | **P2** | Operational Coupling | Hosted librarian review sign-off (`POST /api/academic-automation/review/<job_id>/decision`, `analytics.py:366-372`) always returns `409 workstation_required`; no documented multi-staff workstation backup/failover runbook exists. |

---

## Assessment Document Index

1. [**Campus Pilot Threat Model**](THREAT_MODEL.md) — Assets, trust boundaries, actors, STRIDE analysis, and required mitigations.
2. [**Verified RBAC Matrix**](RBAC_MATRIX.md) — Route-by-route authorization matrix mapped to `host_inference`, `host_research`, and Supabase RLS/RPC guards.
3. [**Privacy, Data Retention, License & Koha Checklist**](PRIVACY_AND_DATA_RETENTION.md) — Student conversation retention, external LLM disclosure, deletion gaps, Pearson/HF/OA license boundaries, and Koha OPAC live-vs-snapshot freshness & librarian approval workflows.
4. [**Institutional Permissions & Operational Approvals**](INSTITUTIONAL_APPROVALS.md) — Required UEM Kolkata authorizations, vendor/copyright clearances, and staff operational ownership matrix.
5. [**Bounded Load Test Plan**](BOUNDED_LOAD_TEST_PLAN.md) — Safe, non-executed load test design, serverless concurrency/error budgets, and stop conditions.
6. **Non-Production Verification Tests:** `tests/unit/test_campus_pilot_rbac_assessment.py` — Offline `pytest` suite verifying RBAC guards, privacy/PII scrubbing, Koha/Pearson boundaries, and documenting P0-1/P0-2 as `xfail(strict=True)` probes until isolated fixes land.
