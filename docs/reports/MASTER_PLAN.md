# Archipelago — Master Plan: Modularization → Fixes → Deployment → Ingestion

**Date:** 2026-10-01
**Branch:** `archipelago3`
**Sources of truth:** [`AGENTS.md`](../../AGENTS.md), [`docs/CI_CD.md`](../CI_CD.md),
[`docs/guides/ARCHITECTURE.md`](../guides/ARCHITECTURE.md),
`docs/01_production_engineering_cicd.md`, `docs/02_institutional_deployment.md`,
`docs/03_ai_call_minimization_caching.md` (the briefs the user asked us to follow).

This plan sequences the work so that **clean architecture comes first**, then the
functional fixes land on top of split modules (so a fix touches one small file,
not a 1,200-line monolith). Deployment readiness and ingestion UX are later
phases because they depend on the earlier ones.

---

## Ground rules (non-negotiable)

| Rule | Source |
|------|--------|
| Files ≤ 500 lines (prefer ≤ 300) | `AGENTS.md` |
| One feature per package; features import **downward only** (`apps → inference / okf`) | `AGENTS.md` |
| No magic numbers; every literal is a named constant | `AGENTS.md` |
| `from __future__ import annotations`, type hints, docstrings | `AGENTS.md` |
| Banned: `except: pass`, `eval(`, `exec(`, `shell=True`, `verify=False`, `pickle.load`, `os.system`, unsafe `yaml.load`, unchecked LLM output, inline prompt-injection sinks | `AGENTS.md` Skill 4 |
| Preserve existing functionality; do not rewrite working systems | `docs/01…` §1 |
| XKIRO stays the inference provider (`XKIRO_API_KEY` / `XKIRO_BASE_URL` / `XKIRO_MODEL`) | repo reality |
| Never fabricate URLs; link to the **exact** source page | `docs/01…` §5 |
| Graph/library statistics computed from data, never hard-coded | `docs/01…` §6 |
| Ingestion stays **local** and is **idempotent** | `docs/01…` §9-10 |

---

## Snapshot (measured 2026-10-01)

Already done this effort:

- `ui/chat/index.html` 10,309 → **740 lines**; CSS in `ui/chat/styles/` (10
  files), JS in `ui/chat/js/` (26 ES modules).
- `host_inference/ui/index.html` 10,311 → **737 lines**; its own `styles/` + `js/`.
- `tests/unit/_ui_source.py` shared loader; contract tests rewired and green
  (123 passed / 6 skipped).
- `scripts/refactor/smoke_chat_ui.mjs` headless-Chrome smoke test — SMOKE OK for
  both trees.
- Pre-existing UI syntax bug fixed (duplicate `const citations` in
  `appendEvidenceRail`) — it had frozen the chat page.

Still oversized (Python, > 400 lines) — **40+ files**. Highest-value first:

```
1376  archipelago/inference/routing.py
1340  archipelago/inference/synthesis.py
1327  chat_server.py
1211  host_inference/engine.py          <-- hosted path, do first
1183  src/archipelago/inference/diagnostic_mcq.py
1124  archipelago/inference/routes_misc.py
1026  archipelago/inference/routes_chat.py
 862  archipelago/ingestion/librarian_worker.py (+ src/ duplicate)
 847  host_inference/server.py          <-- hosted path, do first
```

Still oversized (HTML):

```
2231  frontend/ui/graph/index.html
2171  ui/graph/index.html               <-- canonical graph UI
1081  ui/chat/library.html
 993  host_inference/ui/library.html
 832  ui/graph/neon.html
```

---

## Phase P1 — Clean architecture (splitting)

Goal: no application file over ~400 lines; one concern per module; import
direction respected. Work **package by package**, verifying after each.

### P1.1 — Hosted chat path (`host_inference/`) — *highest priority*

| Target | Split into |
|--------|-----------|
| `engine.py` (1211) | `engine/__init__.py` (shim re-exporting `Engine`, `maybe_polish`, `_hf_doc_path`), `engine/constants.py` (messages, aliases, formulas, shelf, portals, schedule, passing mentions), `engine/patterns.py` (regexes, `_tokens`, `embed`, `_node_public`), `engine/graph.py` (`LibraryGraph`), `engine/answer.py` (`Engine` core), `engine/links.py` (Pearson/HF line builders), `engine/polish.py` (`maybe_polish`, `_complete`) |
| `server.py` (847) | `host_routes/__init__.py` (`create_app` wiring), `host_routes/pages.py` (landing/chat/graph/library/login), `host_routes/graph.py` (`/api/graph/subgraph`), `host_routes/chat.py` (`/api/chat` + diagnostic/adaptive/telemetry + **new** roadmap/quiz), `host_routes/reader.py` (`/read`, `/api/reader/info`, `/papers`, `/pdfs`, `/open`, `/api/page-view`), `host_routes/library.py` (`/api/library/*`, `/api/catalog/all`) |

**Invariant:** `from engine import Engine, maybe_polish, _hf_doc_path` and
`import engine as hosted_engine` must keep working (shim). Same for `server`.

### P1.2 — Canonical graph UI (`ui/graph/index.html` 2171)

Same tooling as chat: `scripts/refactor/split_inline_css.py` then
`scripts/refactor/split_chat_js.mjs`, plus a `graph_ui_source()` branch in
`tests/unit/_ui_source.py` and a graph smoke test.

### P1.3 — Python inference package (`archipelago/inference/`)

`routing.py`, `synthesis.py`, `routes_misc.py`, `routes_chat.py`,
`curriculum.py`, `ranking.py`, `intent_gate.py`, `library_catalog_api.py`,
`citations.py`, `llm_gateway.py` — each split along its existing section
comments into a sub-package. Do not change behaviour; move only.

While here, fix the **dependency-direction violations**: `routes_misc.py`
imports `okf.graph.*` (must go through a downward-facing adapter), and
`okf/pipeline*.py` import `archipelago.ingestion.pdf_io`.

### P1.4 — Remaining monoliths

`chat_server.py`, `src/archipelago/inference/diagnostic_mcq.py`,
`ingestion_worker.py`, `librarian_worker.py` (both copies),
`archipelago/inference/library_queries.py`, `okf/relations.py`,
`training/*`, `scripts/*`, `tests/unit/test_inference_75_cases.py`.

### P1.5 — De-duplicate trees

`src/archipelago/*` is a live duplicate of `archipelago/*`. Decide one
canonical tree and make the other a re-export shim (or delete), updating
`app.py` / `chat_server.py` / `ingestion_worker.py` / tests. Same for
`host_inference/ui` vs `ui/chat` (repoint `host_inference/server.py` at shared
files once content differences are reconciled).

---

## Phase P2 — The requested fixes (one by one)

Each fix: reproduce → fix in one module → verify with
`node scripts/refactor/smoke_chat_ui.mjs` + the relevant pytest subset.

| # | Fix | Where | Acceptance |
|---|-----|-------|-----------|
| 1 | **Pearson book links open the correct reader page** | `engine/links.py` + `remote_cache.pearson_page_url` + `ui/js` interceptor | Clicking a Pearson citation opens `pdfviewer.html`/`index.html` on the cited page with `subscriptionId` + `#book/<id>/page/<n>` |
| 2 | **HF dataset / paper page links work** | `engine/links.py` (`pearson_line` emits `**Hugging Face page.**`), `CITATION_LINE_PREFIXES`, `demo_cards.redact_for_model` | HF link survives citation filtering and opens the exact dataset blob page |
| 3 | **In-chat graph returns after every grounded reply** | `ui/js/11-populate-topology.js`, graph toggle | Every grounded answer renders the interactive neighborhood from `/api/graph/subgraph` |
| 4 | **Replies include clickable page/paper/Pearson links** | `engine.py` link builders + `ui/js/02--kw-highlights.js` | Answer markdown contains at least one exact-source link when a source exists |
| 5 | **Roadmap feature works** | **add `POST /api/roadmap`** (missing — verified absent) + `POST /api/quiz` fallback | Modal renders stages from the real graph; no "Failed to connect to API" |
| 6 | **Personalized QnA graph restored** | choice modal (Personalized vs Normal) + `POST /api/chat/adaptive-step` + `/api/chat/diagnostic-mcqs` | Choosing Personalized shows adaptive MCQs and a personalized topology |
| 7 | **Reply variation + architect-level intent routing** | `routing.py` / synthesis | Not every reply is a graph; intent decides |
| 8 | **Proper inventory from page links/keywords** | `library_index.py`, inventory route | Inventory reflects real indexed records |
| 9 | **Concise replies** | `engine.py` system prompt / `max_tokens` | 1–3 sentences unless asked to expand |

> **Status (2026-10-01):** fixes 1–7 and 9 are implemented and verified
> (behavioral checks + targeted suites — see
> `HANDOFF_2026_10_01_modularization.md` batches 1–3).

---

## Phase P3 — Deployment readiness

Per `docs/01` §15-27 and `docs/02`:

1. `/health` + `/ready` honest — report db mode, concept count, XKIRO
   availability, embeddings, graph version. (`host_inference/server.py` already
   has `/health`, `/ready`, `/api/readiness` — extend, don't duplicate.)
2. Rate limiting at the API boundary (per-IP / per-user / per-endpoint) with
   real `429` + `Retry-After` (`archipelago/middleware/rate_limiter.py` exists).
3. Secrets never reach the frontend (audit `/api/auth/config`).
4. Request IDs + structured logs + cache/inference metrics
   (`/api/metrics/cache` exists; add `ai_requests_total`, `ai_cache_hits`,
   `ai_cache_misses`, `ai_requests_saved`).
5. Cache correctness: versioned cache keys
   (`normalized_query + graph_version + library_version + model_version +
   prompt_version`) per `docs/03`. `supabase/migrations/20260930_000001_response_cache.sql`
   exists — reconcile column names with the brief.
6. Request deduplication/coalescing (`archipelago/inference/request_dedup.py`
   exists — wire it into `/api/chat`).
7. Docker appliance under `deploy/library-computer/` boots with
   `docker compose up -d`; `.antideploy.json` drives the public push.
8. CI: add live inference / graph-retrieval / source-link / roadmap smoke gates
   behind `RUN_LIVE_E2E=1`; add the 5151-node graph integrity check.

> **Status (2026-10-01):** the public entrypoint is settled — the live site
> (`archipelago-2.antideploy.com`) is the hostapp serving `host_inference/ui/`,
> and `.antideploy.json` `start_command` now boots
> `hostapp.factory:create_app()` (verified boot + landing served locally).
> The hosted landing was rebuilt to the Archipelago brand page (△ wordmark,
> KNOWLEDGE hero, video overlay, no sign-in UI — sign-in stays server-side at
> `/login`). Redeploy required to publish.

---

## Phase P4 — Ingestion UX (librarian auto-populate)

Goal per `docs/02` §4-6 and the user's ask: **a librarian uploads/clicks a book
and it auto-populates** — from index/content-page images and from library
detail spreadsheets (CSV/ODS) — idempotently.

1. **Image → record.** Accept index-page / content-page images; OCR/extract
   title, author, publisher, year, ISBN, page ranges; map to a library record +
   concepts. Route through the existing local extraction model (do **not**
   replace it).
2. **Spreadsheet → records.** CSV/ODS library-detail ingestion:
   schema-validate → normalize → dedupe → CREATE/UPDATE/UNCHANGED/DELETE →
   graph + index + statistics update.
3. **Idempotency test.** Re-running ingestion adds zero duplicate books,
   concepts, nodes or edges.
4. **Live ingestion E2E.** Inject a known test book; assert it appears in
   library, graph nodes/edges generated, source URL retained, chat can retrieve
   it and answer about it.
5. **Library statistics** computed from data (no hard-coded counts).

---

## Verification commands

```bash
# UI contract tests (loader-based)
python3 -m pytest tests/unit/test_chat_ui_contract.py tests/unit/test_stream_contract.py \
  tests/unit/test_three_bugs_fix.py tests/unit/test_ui_deeplinking.py \
  tests/unit/test_tc75_honest_pass.py tests/unit/test_host_inference_deployment.py -q

# Browser smoke (both trees)
node scripts/refactor/smoke_chat_ui.mjs

# Split tools
python3 scripts/refactor/split_inline_css.py <html> --out-dir <dir> --url-prefix /styles --dry-run
node scripts/refactor/split_chat_js.mjs <html> --dry-run
```

> **Honesty note:** the repo-wide quality gate is currently red for pre-existing
> reasons (ruff errors, 481 magic numbers, 14 dependency-direction violations,
> missing `mypy`, 2 banned patterns). Splitting work is verified with the UI
> contract tests + the browser smoke test; we do not claim `quality_gate.py`
> passes until Phase P1/P3 cleanup actually lands.
