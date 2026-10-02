# Production Readiness & Platform Plan — 2026-10-02

**Branch:** `archipelago3` · **Live:** `archipelago-2.antideploy.com` (deploys the
repo default branch `session3-stable`)

This document is the honest state-of-play for the "make inference and ingestion
production-ready, regression-test everything, and add the librarian/ingestion
platform features" request. It records what is **verified done**, what exists but
is **unverified/partial**, and what is **not built**. Nothing here is claimed to
pass unless it was run.

---

## 1. Completed in this turn

| Item | Evidence |
|------|----------|
| Artifact-leak regression **fixed + guarded** | `finalize_and_build` now threads its resolved `BASE_DIR` into `write_all_artifacts`; `tests/conftest.py` gained an autouse guard that fails any test writing `okf_graph.json`/`okf_graph.db`/… into the repo root. |
| `pdf_ingestion` regression **fixed** | Stale patch target → `archipelago.ingestion.pdf_io.ingest_document`; `tests/integration/test_staged_pipeline_regression.py` **2 passed**. |
| Repo corpus restored | `okf_graph.json` = **514 concepts** (from `okf_graph.bak-soference-20260912-183509/`); tc75 structural suite **75 passed**. |
| New contract tests | `tests/unit/test_pipeline_base_dir_contract.py` (2 tests) pin the late-bound `BASE_DIR` contract. |
| ~~SLM verified ready~~ **SUPERSEDED — see below** | ~~`lib-qwen:latest` (v44, qwen2, 494M params, Q8_0) loaded in Ollama; live smoke extraction returned `Stochastic Gradient Descent`. No re-training required.~~ **This claim was wrong.** A single smoke extraction cannot detect a centrality or consistency failure. The 11-probe harness (`python -m archipelago.eval.extract_eval`) measures alias F1 **0.125** (gate 0.35): 1 of 8 real passages yields the right concept, and two paraphrases of the same passage produce *different wrong* answers. **Do not enable unattended SLM ingest.** Full numbers and remediation: [`docs/guides/SLM_EXTRACTION_EVAL.md`](../guides/SLM_EXTRACTION_EVAL.md). The model is structurally sound (100% valid JSON, 100% schema, 0 celebrity nodes, 100% correct on negatives) but picks a plausible *neighbouring* concept instead of the passage's central one. |

Commit: `93d40cb`. Three follow-up commits total this turn (`e35f392`, `93d40cb`, plus `e7ecc47`).

---

## 2. Verified current state

### Inference (hosted)
- `host_inference/hostapp` factory, `GET /api/readiness` returns
  `{mode: inference-only, concepts, pearson_books, cache: supabase}`.
- LLM: XKIRO preferred (`qwen/qwen3.8-max:free`), Ollama fallback (`qwen3.5:0.8b`).
- Response cache: **Supabase `ai_response_cache`** with in-memory fallback
  (`host_inference/cache_service.py`); metrics at `GET /api/metrics/cache`
  (`ai_cache_hits`/`ai_cache_misses`/`cache_hit_ratio`).
- Request dedup/coalescing: `archipelago/inference/request_dedup.py`.
- Rate limiting: `archipelago/middleware/rate_limiter.py` — in-memory sliding
  window, tiers anonymous/student/librarian/administrator (5/30/100/200 per 60 s).
- Auth: Supabase session (`host_inference/hostapp/security.py`,
  `archipelago/supabase_auth/`), gated by `ARCHIPELAGO_AUTH_REQUIRED`.

### Ingestion (local)
- PDF/PDF-formats/OCR path: `archipelago/ingestion/pdf_io.py`, `pdf_chunk.py`,
  `page_image/`, `spreadsheet/`, `mention/`.
- Librarian worker + staging → atomic swap: `archipelago/ingestion/librarian_worker/`,
  `archipelago/graph/engine.py` (`KuzuGraphEngine.atomic_swap`).
- Institutional connectors: `archipelago/ingestion/pearson_connector.py`,
  `archipelago/resolver/{pearson,google_books,openlibrary,resolver}.py`.
- SLM extraction: `archipelago/ingestion/lib_qwen_extractor/` (`lib-qwen:latest`).
- Docker stack: `deploy/library-computer/docker-compose.yml` (ingestion worker +
  graph + library index; corpus stays on-prem, minimal context to the inference API).

### Not present / partial
- **Security scanners not installed**: `bandit`, `detect-secrets`, `pip-audit`,
  `mypy` are all absent from `.venv`. CI references them but they cannot run locally.
- **No auto-ingest prompt** when a new book/paper is detected.
- **No expiry / "no longer in records"** handling when a source is withdrawn by
  Pearson/HF.
- **No scraping integration** (Scrapling / Apify / proxy service).
- **`ui/graph/okf_graph.json`** is a stale 2-node copy that can shadow the root
  corpus for the graph UI.

---

## 3. Requested features → gap analysis

| # | Request | State | Work needed |
|---|---------|-------|-------------|
| 1 | All 3 follow-ups | ✅ done | — |
| 2 | Verify live redeploy | ⛔ blocked | antideploy trigger (external); branches already fast-forwarded |
| 3 | Inference production-ready | 🟡 partial | health/readiness depth, structured logs, request IDs, cache-key versioning, 429 `Retry-After` tests |
| 4 | Ingestion production-ready + portable Docker | 🟡 partial | verify image builds, worker healthcheck, offline SLM load, portable volumes |
| 5 | Regression test every feature (graph→login→cache→rate-limit) | 🔴 missing | new suites: graph, auth boundary, cache, rate limit, citations, roadmap |
| 6 | "Fix security, no hack" | 🔴 unverified | install scanners, run them, remediate; auth-boundary tests on **every** mutating endpoint |
| 7 | Librarian can populate graph/library comfortably | 🟡 partial | upload→review→swap UX + tests; index/content-page ingest |
| 8 | Fetch/populate books from index/content pages | 🟡 partial | `page_image/` exists; wire TOC/chapter extraction end-to-end |
| 9 | Site-scrape via proxy, **legally** | 🔴 not built | robots.txt+ToS gate, provenance, human approval, no auth/paywall bypass |
| 10 | Pearson credentials used properly | 🟡 partial | load from env/secret store, never log, redaction tests |
| 11 | HF Spaces as a feature | 🔴 not built | model/dataset sync (`scripts/sync_to_hf_library.py` exists) as a first-class toggle |
| 12 | Auto-ask librarian to ingest new books | 🔴 not built | detect new/changed sources → librarian prompt/queue |
| 13 | Forget withdrawn sources ("not in records") | 🔴 not built | source-version reconciliation + tombstone/soft-delete + reply copy |
| 14 | SLM fine-tuned & ready | 🔴 **not ready** | eval harness built (`archipelago/eval/extract_eval.py`, 51 tests); measured alias F1 **0.125** vs 0.35 gate. Structural checks pass, concept centrality does not. Needs dataset rebuild — see [`docs/guides/SLM_EXTRACTION_EVAL.md`](../guides/SLM_EXTRACTION_EVAL.md) |
| 15 | Scrapling | 🔴 not built | evaluate OSS lib (no license/ToS conflict) |
| 16 | Apify setup | 🔴 not built | token + `apify-client`; paid-run cost caps; MCP optional |

---

## 4. Proposed workstreams (priority order)

**W1 — Security baseline — ✅ DONE (`257d45d`).**
* `requirements-dev.txt` declares ruff/mypy/bandit/detect-secrets/pip-audit.
* **bandit** medium/high findings: **10 → 0** (was 5 high, 10 medium). Real fixes:
  XXE-safe ODS parsing via `defusedxml`; absolute-http(s) validation before every
  `urlopen`; fail-closed Supabase key; pinned Hugging Face download revision;
  `usedforsecurity=False` on non-security MD5; loopback-default binds.
* **Log redaction** added (`archipelago/middleware/log_redaction.py`) and wired
  into hostapp, chat_server, graph_server, the inference API and
  `setup_logging` — a live access log had captured a `?token=` JWT.
* **Secret scan:** `.env`, `host_inference/.env`, `logs/` are gitignored and
  untracked; remaining `detect-secrets` hits are doc/test fixtures.
* **pip-audit:** *No known vulnerabilities found.*
* **Auth boundary:** parametrised suite (`tests/unit/test_auth_boundary.py`)
  proves every protected mutating endpoint returns 401/403 anonymously while the
  deliberate-public ones do not; log-redaction unit tests in
  `tests/unit/test_log_redaction.py`.
* Still red by design: `mypy --strict` and repo-wide `ruff` (pre-existing,
  thousands of legacy findings). Not claimed green.

**W2 — Regression suites.** One suite per feature: graph retrieval + subgraph,
Supabase login/session, answer cache (hit/miss/dedup + metrics), rate limit
(429 + `Retry-After` per tier), citations/page-links, roadmap/quiz. Acceptance:
each suite present, deterministic, and green.

**W3 — Ingestion portability.** Build `deploy/library-computer` image; add a
worker healthcheck; confirm `lib-qwen:latest` loads from a mounted volume offline;
document restore/backup of `okf_graph.db`. Acceptance: `docker compose up -d`
reaches healthy with no host-only paths.

**W4 — Librarian UX.** Upload → parse → review → approve → atomic swap, with
status and rollback; TOC/content-page chapter ingest through `page_image/`.
Acceptance: an end-to-end test ingests a fixture PDF into a temp graph.

**W5 — Source lifecycle.** New-source detection → librarian prompt; withdrawal
detection → soft-delete + "not in records anymore" reply path; provenance kept.
Acceptance: tests for add/withdraw/expire.

**W6 — Compliance-aware web fetch.** `robots.txt` + ToS check, per-domain rate
limits, provenance/audit log, human approval before ingest. **Never** bypass auth,
paywalls, or use stolen credentials. Acceptance: fetcher refuses disallowed paths;
audit record per fetch.

**W7 — Integrations.** Scrapling (OSS) evaluation; Apify via `apify-client` with
`maxTotalChargeUsd` caps and a required user go-ahead before any paid run; optional
Decodo/Hyperbrowser proxy behind the W6 gate.

**W8 — SLM evals.** Extraction eval harness (precision/recall vs a gold set) over
`lib-qwen:latest`, reporting distributions per Skill 2.

---

## 5. Decisions / credentials needed

0. **Apify token** — user will paste `APIFY_TOKEN` (+ per-run USD cap) for W7.
1. **Deploy trigger** — the fast-forward to `session3-stable` has not rebuilt the
   live site; confirm how antideploy is triggered (dashboard vs integration).
2. **Scraping scope** — which domains/collections? Any that require login or
   payment must be excluded (no bypass). Written sign-off on the allowed list.
3. **Apify** — an `APIFY_TOKEN` and confirmation of a per-run USD cap.
4. **Proxy provider** — Decodo (named in the request) vs the catalog-recommended
   Hyperbrowser; either way it sits behind the W6 compliance gate.
5. **Workstream order** — which of W1–W8 to execute first.
