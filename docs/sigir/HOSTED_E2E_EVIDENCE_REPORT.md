# Archipelago — Hosted E2E & Browser Integration Evidence Report (Issue #12)

**Date (UTC):** 2026-11-23T13:14:50Z  
**Branch:** `sigir/swarm-b-hosted-e2e` (baseline `00f38b81351ebaeb5aff2fd36c5e64ea37319524`)  
**Executable Harness:** [`scripts/e2e/hosted_e2e_harness.py`](../../scripts/e2e/hosted_e2e_harness.py)  
**Machine-Readable Evidence (Redacted):** [`docs/sigir/hosted_e2e_results.json`](hosted_e2e_results.json)  
**Rehearsal & Fallback Plan:** [`docs/sigir/SIGIR_REVIEWER_REHEARSAL_AND_FALLBACK.md`](SIGIR_REVIEWER_REHEARSAL_AND_FALLBACK.md)

---

## 1. Executive Verdict — Hosted SIGIR Demo Verification

> [!IMPORTANT]
> **Anonymous HTTP 401/403 is NEVER counted as `PASS`.**  
> Across the 6 required hosted journeys, **1 is `PASS` (public OPAC/Library)**, **0 are `FAIL`**, and **5 are `BLOCKED`** pending an authorized Supabase student session in the execution environment.  
> **Hosted SIGIR Demonstration Readiness:** **HOLD / BLOCKED** until a human operator runs the harness with an authorized student session to complete J1, J2, J3, J5, and J6 on live production.

---

## 2. Deployed Code Revision vs. Graph Fingerprint (Verified Separately)

| Origin | Endpoint | HTTP | Deployed Code Revision | Graph Fingerprint | Corpus / Service Status |
|--------|----------|------|------------------------|-------------------|-------------------------|
| `https://archipelago-blond.vercel.app` | `GET /api/readiness` | 200 | `X-Archipelago-Release: unversioned` (**not versioned**) | `graph_version: 9818ac0e8fd3` | `ok: true`, `610` concepts (`full`), `40` Pearson books |
| `https://archipelago-librarian.vercel.app` | `GET /api/readiness` | 200 | **missing** (no release header or SHA field) | N/A | `ready: true`, `service: research_transport` |
| `https://archipelago-blond.vercel.app` | `GET /api/auth/config` | 200 | N/A | N/A | `configured: true`, `required: true`, Supabase auth active |

**Observability Gap Identified:** `graph_version` (`9818ac0e8fd3`) is the SHA-256 fingerprint of the exported concept graph JSON (`host_inference/engine/graph.py`), NOT the deployed git commit SHA. Production currently emits `X-Archipelago-Release: unversioned` on the inference app and omits a release SHA on the research transport app. Operators should set `ARCHIPELAGO_RELEASE_SHA` (or fall back to `VERCEL_GIT_COMMIT_SHA`) during deployment so reviewers can verify deployed code revision independently of corpus fingerprint.

---

## 3. Real Hosted User Journey Matrix (`hosted_live`)

Executed against `https://archipelago-blond.vercel.app`, `https://archipelago-librarian.vercel.app`, `https://uemk-opac.l2c2.co.in`, OpenAlex, Crossref, arXiv, and `doi.org` using headless Google Chrome (`/usr/bin/google-chrome`) + Python `requests`.

| ID | Hosted Journey | Auth Required | Hosted Verdict | Redacted Evidence | Blocker / Next Action |
|----|----------------|---------------|----------------|-------------------|-----------------------|
| **J1** | Student login -> chat -> Transformer canonical chunk -> `/api/page-view` -> original PDF page bytes | Yes (Student) | **BLOCKED** | Anonymous `POST /api/chat` -> `401`; `GET /api/page-view` -> `401`. Browser `/chat` redirects cleanly to `/login?next=/chat` (0 page errors). | Supply authorized Supabase student session (`ARCHIPELAGO_E2E_STUDENT_TOKEN` or email/password) to verify canonical `transformer` chunk + `%PDF-` bytes. |
| **J2** | Research topic -> live papers (providers) -> dossier -> primary DOI/arXiv URL | Yes (Student) | **BLOCKED** | **Public provider leg verified:** OpenAlex `200` (3 papers), Crossref `200` (3 papers), DOI `10.18653/v1/2020.emnlp-main.550` -> `302` to `https://aclanthology.org/2020.emnlp-main.550`; arXiv returned `429` (rate-limited). Hosted `POST /api/research/intelligence/search` -> `401`. | Supply authorized student session to run hosted `/search` + `/dossier`. |
| **J3** | Save research run -> reopen -> Excel (`.xlsx`) export (verify valid XLSX bytes) | Yes (Student) | **BLOCKED** | Anonymous `GET /api/research/intelligence/runs` -> `401`. | Supply authorized student session to reopen saved run and validate `PK\x03\x04` + OOXML workbook bytes via `/xlsx`. |
| **J4** | Public OPAC / Library lookup -> Koha biblionumber -> availability & snapshot freshness | No (Public) | **PASS** | `/api/library/data`: `200`, `91` ebooks, `109` holdings (`holdings_status: koha_export`, `koha_stale: true`, `koha_source_updated_at: 2026-11-11T15:24:20.794016+00:00`). `archipelago-librarian.vercel.app/api/library/koha`: `200` (`stale: true` disclosed). Live Koha OPAC `biblionumber=1868`: `200` (`96,317` bytes, record content verified). Headless Chrome `/library`: `200`, title `"Library Details — Archipelago Central Repository"`, `4,005` text chars, `0` page errors, `0` console errors. | None (verified live). Note: Koha snapshot is explicitly disclosed as stale since `2026-11-11`. |
| **J5** | Unsupported topic (Q39: *"Explain Spanner TrueTime and its prerequisites."*) -> clean abstention (0 citations, 0 graph) | Yes (Student) | **BLOCKED** | Anonymous `POST /api/chat` -> `401` (auth gate only; does not prove hosted abstention). | Supply authorized student session to verify live hosted Q39 zero-citation/zero-graph abstention. |
| **J6** | Role negative test: student cannot perform librarian operations (`403`) | Yes (Student) | **BLOCKED** | Anonymous probes returned `401` on `/api/library/import`, `/api/auth/handoff-ticket`, `archipelago-librarian.vercel.app/api/library/opac/live`, and `/api/librarian/books`. Anonymous `401` does **not** prove authenticated student `403`. | Supply authorized student session to verify HTTP `403 Forbidden` across all four librarian routes. |

---

## 4. Headless Browser Smoke Summary (`hosted_live`)

Browser executable: `/usr/bin/google-chrome` (Playwright sync API, headless).

| Page | Requested URL | Final URL | HTTP | Title | Uncaught Page Errors |
|------|---------------|-----------|------|-------|----------------------|
| Library (Public) | `/library` | `/library` | 200 | `Library Details — Archipelago Central Repository` | 0 |
| Chat (Auth Gate) | `/chat` | `/login?next=/chat` | 200 | `Sign in — Archipelago` | 0 |
| Research Shell | `/research` | `/research` | 200 | `Research — Archipelago Research` | 0 |
| Login | `/login` | `/login` | 200 | `Sign in — Archipelago` | 0 |
| Research Landing | `archipelago-librarian.vercel.app/` | `archipelago-librarian.vercel.app/` | 200 | `Archipelago — Choose your space` | 0 |

---

## 5. Local Fixture Integration Tests (Explicitly Separate from Hosted Proof)

> [!NOTE]
> The tests below run in-process against the local Flask `host_inference` app and tracked fixtures (`tests/integration/test_hosted_journeys_local.py` and `tests/e2e/test_hosted_e2e_harness.py`). They verify route contracts, RBAC `403` enforcement, Q39 abstention, and byte validators **locally** and do **not** replace authenticated live hosted verification.

| Test Suite | Scope | Result |
|------------|-------|--------|
| `tests/e2e/test_hosted_e2e_harness.py` | Unit tests for PDF `%PDF-` / page-range validator, OOXML `.xlsx` validator, revision-vs-graph separation, `[STREAM_START]` parser, Q39 abstention check, secret redaction, verdict policy | **6 passed** (1 live-gated test skipped without `RUN_LIVE_E2E=1`) |
| `tests/integration/test_hosted_journeys_local.py` | Local fixture Flask tests: J1 chat + `/api/page-view`, J4 `/api/library/data` + `/api/readiness`, J5 Q39 zero-citation/zero-graph abstention, J6 student `403` on `/api/library/import`, `/api/auth/handoff-ticket`, `/api/ingest/upload`, and anonymous `401` | **5 passed** |
| `tests/unit/test_d7_1_audit_integrity.py` | D7.1 verdict semantics and scientific-claim regression guard | **15 passed** |

---

## 6. Concrete P1 Bug Reproduced & Fixed

- **Bug:** Calling `GET /api/library/data` when the remote Koha snapshot is unavailable and the handler falls back to bundled manifest holdings raised `KeyError: 'total_copies'` (HTTP `500`) in `host_inference/library_inventory.py:inventory_stats` because fallback manifest rows use `no_of_copies` or omit `total_copies`.
- **Fix:** Updated `inventory_stats()` in [`host_inference/library_inventory.py`](../../host_inference/library_inventory.py) to safely read `row.get("total_copies", row.get("no_of_copies", 0))` and `row.get("available_copies", 0)`. Verified by `test_local_j4_library_data_and_readiness_separation`.

---

## 7. How a Human Operator Unblocks J1, J2, J3, J5, and J6 on Live Production

No authorized student credentials or tokens exist in this automated environment. To execute all 6 journeys against live production without exposing secrets in git or logs:

```bash
export ARCHIPELAGO_E2E_STUDENT_EMAIL="<authorized-student-email>"
export ARCHIPELAGO_E2E_STUDENT_PASSWORD="<authorized-student-password>"
# Or supply a short-lived Supabase access token directly:
# export ARCHIPELAGO_E2E_STUDENT_TOKEN="<short-lived-jwt>"

python3 scripts/e2e/hosted_e2e_harness.py
```

The harness automatically redacts emails, Bearer tokens, JWTs, cookies, and Supabase keys before writing `docs/sigir/hosted_e2e_results.json`.
