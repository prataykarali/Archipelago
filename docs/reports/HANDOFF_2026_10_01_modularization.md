# Handoff — 2026-10-01: engine split, roadmap fix, Pearson URL fix

**Branch:** `archipelago3`
**Plan:** [`docs/reports/MASTER_PLAN.md`](MASTER_PLAN.md) (phases P1–P4).
**Briefs followed:** `docs/01_production_engineering_cicd.md`,
`docs/02_institutional_deployment.md`, `docs/03_ai_call_minimization_caching.md`.

## What was built

### 1. `host_inference/engine.py` (1,211 lines) → `host_inference/engine/` package

One concern per module, all ≤ 310 lines:

| Module | Lines | Concern |
|--------|------:|---------|
| `constants.py` | 173 | static tables + reply strings |
| `docmap.py` | 52 | document id → dataset path |
| `patterns.py` | 51 | intent-detection regexes |
| `text.py` | 46 | hashed embedder |
| `nodes.py` | 25 | public node projection |
| `graph.py` | 229 | in-memory concept graph |
| `render.py` | 41 | markdown graph helpers |
| `links.py` | 39 | exact-source link lines |
| `llm.py` | 153 | XKIRO (preferred) / OpenRouter |
| `compose.py` | 197 | synthesis / relation / matrix / shelf / auth |
| `diagnostics.py` | 212 | diagnostic MCQ + adaptive personalized graph |
| `answer.py` | 310 | routing, streaming, payload assembly |
| `__init__.py` | 74 | backwards-compatible shim |

**Invariants preserved** (verified): `from engine import Engine, maybe_polish,
_hf_doc_path`, `import engine as hosted_engine`, and the
`hosted_engine.requests` monkeypatch used by the deployment test.

### 2. Roadmap feature fixed — `POST /api/roadmap` was missing

`chat_server.py` proxies `/api/roadmap` to the inference engine, and
`ui/chat/js/21-generate-roadmap.js` POSTs to it, but `host_inference/server.py`
**never implemented the route**, so the roadmap modal always showed
"Failed to connect to API".

Added:
- `host_inference/host_roadmap.py` — `build_roadmap()` (walks *backwards*
  through REQUIRES/UNLOCKS to stage foundation → prerequisites → target) and
  `build_quiz()` (reuses the diagnostic MCQ builder).
- `POST|GET /api/roadmap` and `POST|GET /api/quiz` in `host_inference/server.py`.
- `/api/graph/subgraph`, `/api/roadmap`, `/api/quiz` added to `_PUBLIC_API` so
  they are not 401-blocked behind Supabase auth in production.
- `tests/unit/test_host_roadmap.py` (6 tests) pinning the UI-facing shape.

### 3. Pearson exact-page link fixed

The **hosted** tree had a malformed Pearson URL — `?version=1.0.317.1?subscriptionId=`
(a second `?` instead of `&`), which makes Pearson's reader ignore the
subscription id and open the wrong page. Fixed in three places in
`host_inference/ui/`:

- `index.html` (inline badge interceptor)
- `js/02--kw-highlights.js`
- `js/21-generate-roadmap.js`

Also removed the dead `<script src="roadmap_quiz.js">` from both trees
(`ui/chat/index.html` and `host_inference/ui/index.html` — the file never
existed, so it 404'd on every page load).

## Verified

```
pytest tests/unit/test_host_inference_deployment.py       9 passed
pytest tests/unit/test_host_roadmap.py                    6 passed
pytest test_chat_ui_contract / test_three_bugs_fix       15 passed, 3 skipped
pytest test_chat_ui_contract / test_stream_contract /
       test_three_bugs_fix / test_ui_deeplinking /
       test_tc75_honest_pass                             114 passed, 6 skipped
pytest (deployment + roadmap + link integrity + intent routing +
        chat contract + three_bugs + deeplinking + stream)  65 passed, 6 skipped
pytest (all of the above + tc75_honest_pass)             143 passed, 6 skipped
node scripts/refactor/smoke_chat_ui.mjs                   SMOKE OK
```

Behavioral checks against the real graph:

- `Engine.answer()` still routes correctly (DEMO / BOOK_PAGE / SCHEDULE / GRAPH_SYNTHESIS).
- `POST /api/roadmap {"topic":"bert"}` → 4 stages, foundation → target, items
  carry `study_hours` + `citations`.
- `GET /api/chat/diagnostic-mcqs?concept=bert` → 4 MCQs;
  `POST /api/chat/adaptive-step` → personalized graph
  (`mastered` + `target` nodes, REQUIRES edge, score `1/1`).

## Fix batch 2 — UI dedupe, link integrity, in-chat graph

The hosted tree (`host_inference/ui`) had drifted from canonical `ui/chat`;
that drift was the root cause of several hosted-only bugs. Resolved:

- **Synced** `host_inference/ui/js/*` to `ui/chat/js/*` — now byte-identical.
  `ui/chat/styles/*` were already identical. Both trees have no unique modules.
- **Removed the dead duplicate click handler** from both `index.html` files. It
  targeted `[data-doc-id][data-page]` badges that no code creates, and carried a
  second (now redundant) Pearson URL builder. This is where the double-`?` bug
  lived.
- **Restored the full exact-source link interceptor** on the hosted deployment
  (Pearson `/open/` gateway, Hugging Face dataset links, `#page=` / view-page
  links) by loading the canonical modules.
- **In-chat graph** verified end-to-end: `explain BERT` → `GRAPH_SYNTHESIS` with
  anchor **BERT**, 6 prerequisites, 6 unlocks, 1 citation. The cache-replay path
  preserves the whole metadata frame, so a repeated question still draws the
  graph.
- **Intent routing** verified: `library opening hours` → `SCHEDULE` with
  `anchor_concept: None` and no prerequisites, so no graph is drawn. Graph routes
  (`GRAPH_SYNTHESIS`/`RELATION`/`CROSS_DOMAIN`/`DISCONNECTED`/`MCQ_DIAGNOSTIC`)
  always expose an anchor.
- **Concise replies** still enforced: `max_tokens=220` and the “1–3 sentences /
  under 90 words” system prompt now live in `engine/llm.py` as named constants
  (`REPLY_MAX_TOKENS`, `REPLY_SYSTEM_PROMPT`).
- **XKIRO confirmed intact**: the live `/api/chat` metadata reports
  `model.provider == "xkiro"`.

The Personalized-vs-Normal choice is delivered **inline in the graph card**, not
by a modal: the card is the “Normal Graph” and carries a
`switchToPersonalizedGraph()` button that starts the diagnostic QnA. No modal
restore is required.

New tests: `tests/unit/test_ui_link_integrity.py` (6),
`tests/unit/test_host_intent_routing.py` (5).

## Fix batch 3 — `server.py` (847 → 20 lines) via a `create_app()` factory

`host_inference/server.py` is now a thin shim:

```python
from hostapp import create_app
from hostapp.config import DEFAULT_PORT
app = create_app()
```

The implementation lives in the `host_inference/hostapp/` package, all modules
≤ 236 lines:

| Module | Lines | Concern |
|--------|------:|---------|
| `config.py` | 105 | env loading, roots, public-API policy, rate policy, role sets |
| `security.py` | 134 | `AuthGuard` (Supabase principal) + `RateLimiter` |
| `inventory_store.py` | 22 | holdings validation / persistence boundary |
| `context.py` | 23 | the injected `AppContext` |
| `middleware.py` | 116 | request guard, CORS + security headers, error handlers |
| `factory.py` | 58 | `create_app(ctx=None)` and `build_context()` |
| `routes/pages.py` | 73 | UI shells + health/readiness |
| `routes/graph.py` | 79 | bounded `/api/graph/subgraph` |
| `routes/auth.py` | 63 | session config / issue / me |
| `routes/library.py` | 148 | shelf, holdings import, catalog |
| `routes/reader.py` | 236 | page-view, reader info, PDF stream, Pearson `/open` |
| `routes/chat.py` | 170 | streaming chat, diagnostics, roadmap, quiz |
| `routes/static.py` | 29 | UI + asset serving |
| `routes/__init__.py` | 19 | route registry |

**Routes no longer read module globals.** They receive an `AppContext`
(`engine`, `auth`, `limiter`, `inventory`, caches) stored at
`app.extensions["archipelago"]`. That is what made the split testable: a test
builds `create_app(ctx)` with fakes, or replaces
`ctx.auth.principal` / `ctx.inventory.save` after the app exists.
`Engine` is imported lazily inside `build_context()`, so patching
`engine.Engine` before the app is created still takes effect.

`tests/unit/test_host_inference_deployment.py` updated: 9 → 12 tests. The new
tests assert the shim still exposes `app`/`create_app`, that the factory accepts
an injected context, and that `/api/readiness` reports live counts.

Live route check after the split (real graph): readiness, all four pages,
auth config, subgraph, catalog, library data, page-view (302), reader info
(404 on unknown), roadmap, quiz, `/js/index.js`, `/js/stream-support.js` all as
expected; `/api/nope` and `/.env` correctly 404.

## Fix batch 4 — hosted landing redesign + deployment entrypoint resolved

User report: `archipelago-2.antideploy.com` showed a template header ("Asme"
wordmark + Sign Up / Login buttons — the "ACME default") and a newsletter
email-capture hero instead of the Archipelago brand page.

**Which app serves the live site — resolved with evidence:**

- `GET https://archipelago-2.antideploy.com/api/readiness` returns exactly the
  payload built in `hostapp/routes/pages.py::health` (`mode: inference-only`,
  `concepts`, `pearson_books`) — the live app is the **hostapp**, not
  `archipelago.apps.inference_app` (whose `/` is a GPU diagnostic page).
- The served landing is byte-close to `host_inference/ui/landing.html` (it
  predates the local institutional-links edit) → the live app serves
  `host_inference/ui/`.
- `.antideploy.json` `start_command` repointed to
  `gunicorn --chdir host_inference --bind 0.0.0.0:5151
  'hostapp.factory:create_app()'` (gunicorn ≥ 21 inserts `--chdir` into
  `sys.path`, so `hostapp` plus the top-level `engine` / `cache_service`
  modules import). Boot verified locally: `GET /` → 200 serving the new
  landing; readiness responds (rate limiter intact).

**Landing rebuilt** (`host_inference/ui/landing.html`, 219 lines, synced
byte-identical to `ui/chat/landing.html`):

- Header: `△ Archipelago` wordmark left; right nav "AI/ML study assistant ·
  grounded answers · library knowledge". **No sign-in / sign-up anywhere on
  the page** — the auth modal, `Sign Up` / `Login` buttons, newsletter email
  capture, and the auto-popup-on-load are all removed. `/chat` and `/library`
  stay server-gated (`AUTH_GATED_PAGES` → redirect to `/login`) when
  `ARCHIPELAGO_AUTH_REQUIRED` is set, so security is unchanged.
- Hero: `KNOWLEDGE OPERATIONS` eyebrow → spaced `KNOWLEDGE` headline →
  "Islands of insight, connected — ask the corpus, follow citations, explore
  the graph."
- Hero video (same CloudFront loop, 500 ms rAF fade engine kept) contained in
  a `max-w-6xl aspect-video` block with serif `Built for the curious` overlay,
  "Your campus AI/ML co-pilot…" subline, and two CTAs: **Enter the chat**
  (`/chat`, white pill) and **Library details** (`/library`, liquid-glass
  pill) — plain anchors, no client-side auth interception.
- Kept the institutional research links grid (IEMCRP, UEMK OPAC, IEEE Xplore,
  Pearson eLibrary, Indian Journals); dropped the dead `#` social footer.
- `auth_bridge.js` still loads and mounts the in-app nav for visitors with an
  existing verified session.

Verified: `test_ui_link_integrity` + `test_host_inference_deployment` +
`test_host_intent_routing` + `test_host_roadmap` → 29 passed; SMOKE OK in both
trees.

### 4. Modularization wave — every production module ≤ 400 lines

Target: no production `.py` under `archipelago/`, `host_inference/`, `okf/`
exceeds 400 lines (and none exceed the 500 hard cap in `AGENTS.md`). All splits
preserve the original public namespace (facade `__init__.py` / re-export) and
behaviour.

| Original | → Package / modules | Max file |
|----------|--------------------|---------:|
| `archipelago/api/app.py` (671) | slimmed to 110-line facade + `engine_state.py`, `middleware.py`, `routes_{auth,chat,discovery,docs,library}.py` | ≤ 320 |
| `archipelago/inference/intent_gate.py` (537) | `intent_gate/` (4) | ≤ 300 |
| `archipelago/inference/routing.py` (1,376) | `routing/` (14) | ≤ 300 |
| `archipelago/inference/synthesis.py` (1,340) | `synthesis/` (11) | ≤ 286 |
| `archipelago/inference/routes_misc.py` (1,124) | `routes_misc/` (11) | ≤ 284 |
| `chat_server.py` (1,327) | `chat_server/` (9) | ≤ 260 |
| `archipelago/inference/diagnostic_mcq.py` (1,183) | `diagnostic_mcq/` (7) | ≤ 293 |
| `archipelago/ingestion/librarian_worker.py` (862) | `librarian_worker/` (6) | ≤ 400 |
| `archipelago/inference/library_queries.py` (662) | `library_queries/` (5) | ≤ 334 |
| `archipelago/graph/subgraph.py` (621) | `subgraph/` (4) | ≤ 315 |
| `archipelago/inference/curriculum.py` (611) | `curriculum/` (5) | ≤ 317 |
| `archipelago/inference/ranking.py` (541) | `ranking/` (4) | ≤ 346 |
| `okf/relations.py` (494) | `relations/` (4) | ≤ 361 |
| `archipelago/inference/catalog_ops.py` (494) | `catalog_ops/` (4) | ≤ 385 |
| `archipelago/ingestion/spreadsheet.py` (491) | `spreadsheet/` (4) | ≤ 389 |
| `archipelago/ingestion/mention.py` (480) | `mention/` (4) | ≤ 352 |
| `archipelago/inference/tc75_cases.py` (472) | `tc75_cases/` (4) | ≤ 394 |
| `okf/graph/evidence.py` (466) | `evidence/` (5) | ≤ 352 |
| `archipelago/inference/ods_parser.py` (465) | `ods_parser/` (4) | ≤ 384 |
| `archipelago/inference/library_credentials.py` (458) | `library_credentials/` (4) | ≤ 359 |
| `okf/pipeline.py` (443) | `pipeline/` (4) | ≤ 315 |
| `archipelago/ingestion/lib_qwen_extractor.py` (434) | `lib_qwen_extractor/` (4) | ≤ 219 |
| `okf/extraction.py` (407) | `extraction/` (5) | ≤ 301 |
| `archipelago/inference/demo_query_books.py` (407) | `demo_query_books/` (4) | ≤ 347 |
| `okf/graph/ingest.py` (405) | `ingest.py` (309) + `ingest_manual.py` (110) | ≤ 309 |
| `okf/eval/gold.py` (403) | `gold/` (4) | ≤ 374 |
| `ingestion_worker.py` (612) | `ingestion_worker.py` (247) + `ingestion_worker_job_mixin.py` (387) | ≤ 387 |

`ui/graph/index.html` (2,171 → 366) and `ui/graph/neon.html` (832 → 113)
were split earlier in the wave (CSS under `ui/graph/styles/`, JS under
`ui/graph/js/`).

**Tooling:** `scripts/refactor/split_module.py` (generalized AST splitter)
was extended this wave:
* guarded top-level `try: import x` blocks now contribute their bound names to
the package owner map (late-bound through `_deps`), and their module is
imported for side effects;
* the facade emits part-module imports **before** the re-exported original
imports, so a trailing import (e.g. `from okf.pipeline_staged import …`)
no longer creates a cycle;
* the dotted import path is derived by probing for a real `__init__.py`, fixing
`okf.*` packages;
* `okf/graph/ingest.py` was split **manually** because an inner helper shares
its name with a module-level function (auto sibling-rewriting would corrupt the
nested `def`) — re-exported from `okf/graph/ingest_manual.py`;
* `okf/pipeline` uses late-bound `_rt.` lookup for `BASE_DIR`,
`cleanup_and_canonicalize`, and `ingest_to_kuzu` so the documented
`patch("okf.pipeline.…")` contracts in `tests/unit/test_quality_and_eval.py`
keep working.

**Verified:** `compileall` clean; `test_quality_and_eval` (5),
`test_relations` / `test_manual_graph_api` / `test_ingestion_intake` /
`test_demo_query_books` / `test_lib_qwen_extractor` / `test_librarian_pipeline` /
`test_library_recovery` / host/api suites (90) all pass; UI browser smoke
(`node scripts/refactor/smoke_chat_ui.mjs`) → `SMOKE OK` on both trees.
**Root-caused during verification:** the Category-1 `low_similarity_reject`
failures were **not** environmental. The pipeline split temporarily broke the
`patch("okf.pipeline.BASE_DIR")` contract, so
`test_pipeline_structural_audit_abort` wrote generated artifacts into the repo
root and overwrote the local (gitignored) `okf_graph.json` corpus with a
2-concept fixture; with an empty corpus `rank_concepts` returns generic scores
(~0.26) below the kill-switch threshold, so every in-scope curriculum query was
rejected. The `_rt.` late-binding fix stops the writes (verified:
`test_quality_and_eval` no longer mutates `okf_graph.json` or emits
`graph_audit.json`), and the corpus was restored from
`okf_graph.bak-soference-20260912-183509/` (514 concepts). Result:
`test_tc75_honest_structural_pass` is now **75 passed**.

The only remaining known red is `test_staged_pipeline_regression`, which
imports a `pdf_ingestion` module that does not exist anywhere in the repo
(unrelated, pre-existing).

## Deferred / known issues

1. ~~`host_inference/server.py` not split~~ — **resolved** (see fix batch 3).
   ~~`.antideploy.json` entrypoint question~~ — **resolved** (see fix batch 4):
   the live site is the hostapp serving `host_inference/ui/` (readiness payload
   + landing revision match), and `start_command` now boots
   `hostapp.factory:create_app()` with a locally verified boot. The live
   deployment still runs an **older build** — redeploy to pick up the new
   landing and the repointed start command.
2. ~~`ui/graph/index.html` (2,171) and `frontend/ui/graph/index.html` (2,231)
   not split.~~ — **resolved** (batch 5): `ui/graph/index.html` is 366 lines
   with CSS/JS under `ui/graph/styles/` + `ui/graph/js/`; `graph_ui_model.md`
   and the browser smoke exercise the split tree.
2b. **Test + script files still exceed 400 lines:**
   `tests/unit/test_inference_75_cases.py` (814),
   `tests/integration/test_citation_correctness.py` (480),
   `tests/unit/test_ui_deeplinking.py` (417),
   `scripts/download_pilot_corpus.py` (834),
   `scripts/run_master_library_ingest.py` (817),
   `scripts/ops/seed_soference_nodes.py` (495),
   `scripts/ops/gpu_ingest_local_pdfs.py` (487),
   `scripts/eval_lib_qwen_ingestion.py` (441). These are excluded from the
   quality-gate file-size check but can be split next.
3. **Dead modal left in the tree.** `showGraphChoiceModal()` in
   `js/11-populate-topology.js` is now a no-op and `graph-choice-modal` in
   `index.html` is never shown, because the choice is delivered inline in the
   graph card instead. Remove both as cleanup (and the `showGraphChoiceModal`
   export) once confirmed unused.
4. ~~`host_inference/ui` vs `ui/chat` diverged~~ — **resolved**: the JS trees are
   now byte-identical and `tests/unit/test_ui_link_integrity.py` fails if they
   drift again. Remaining P1.5 work is the *other* divergent pieces:
   `login.html`, `graph.html` (hosted-only) and the duplicate
   `src/archipelago/*` tree.
5. **Quality gate remains red for pre-existing reasons** (ruff errors, 481 magic
   numbers, 14 dependency-direction violations, missing `mypy`, 2 banned
   patterns). Do not claim it passes.

## Next pair should

1. ~~Split `host_inference/server.py`~~ — done (batch 3). ~~§P2 fix list~~ —
   done and verified (in-chat graph, clickable page links, intent routing,
   concise replies).
2. **Redeploy `archipelago-2`.** The host is an antideploy build and its
   default branch is **`session3-stable`** (`68f06cf`), *not* `archipelago3`.
   `archipelago3` (`51b4e99`) is 2 commits ahead and fast-forwards cleanly, but
   nothing deploys until `session3-stable` is fast-forwarded. Verified live on
   2026-10-02: `/` still serves the old "Built for the Curious" landing
   (`<title>Archipelago — Built for the Curious</title>`), `/chat` → 302
   `/login`, `/api/graph/subgraph` → 401; `/api/readiness` confirms the hostapp
   (`mode: inference-only`, `concepts: 520`, `pearson_books: 40`).
3. ~~Split `ui/graph/index.html` + `frontend/ui/graph/index.html`.~~ — done
   (batch 5). Next: split the >400-line test/script files listed in Deferred
   §2b.
4. Reconcile the remaining divergent pieces (`login.html`, hosted-only
   `graph.html`) into one canonical UI tree.
5. Remove the dead `graph-choice-modal` + `showGraphChoiceModal` no-op.
6. Work `MASTER_PLAN.md` §P4 (librarian ingestion auto-populate).
