# ARCHIPELAGO-2 ANTIDEPLOY — CLEAN ARCHITECTURE & DEPLOYMENT PLAN

> Workspace: `/home/pratay-karali/Desktop/archipelago/Archipelago/` (work here directly — no copy)
> Deployment target: AntDeploy app **archipelago-2** (`archipelago-2.antideploy`)
> Source of truth: `docs/01_production_engineering_cicd.md`, `docs/02_institutional_deployment.md`, `docs/03_ai_call_minimization_caching.md`, `AGENTS.md`
> Constraint: **xkiro stays the primary inference provider. No regression to ingestion/graph/chat.**

---

## 0. Current State (audited 2026-10-01)

- Monorepo at `~/Desktop/archipelago/Archipelago/` (3.0 GB; 2.3 GB models, 102 MB Kùzu graph, 67 MB PDFs).
- Chat server already split into `chat_server/merged01–08`; chat UI split into `ui/chat/js/00–21`.
- **Not yet split / oversized:** `routes_chat.py` (1015+ lines), `routes_misc/*`, `librarian_worker/*`, several `archipelago/inference/*` modules — all violate the AGENTS.md ≤500-line rule.
- Resolvers exist: `archipelago/resolver/{resolver,pearson,huggingface,google_books,openlibrary,doi}.py` + `resource_registry.py` (46 resources, HF repo `Prataykarali/Library_books`).
- In-chat graph: `graphify.js` + `js/13,16,17,19` SVG cards — exists, needs verification end-to-end.
- Roadmap: `/api/roadmap/{quiz,plan,between}` + `diagnostic_mcq/` + `curriculum/` — exists; "custom QnA → personalized graph" flow exists but is not wired cleanly.
- Ingestion: file-based (PDF/MD/TXT) + ODS catalog (`ods_ingestion.py`, `catalog_ingest.py`). **No image/OCR "mention a book" auto-populate flow exists.**
- Sign-in: landing has none; chat header has Sign In link (`ui/chat/index.html:175–178`); library page has Sign In button (`ui/chat/library.html:420–423`); server-side gates redirect to `/login`.
- Landing page: `ui/chat/landing.html` — close to target but not matching the reference screenshot (hero video + link grid instead of the centered KNOWLEDGE hero).

---

## Phase 0 — Workspace & Clean Architecture Split

**Goal:** `archipelago-2.antideploy` is the single working copy; architecture violations fixed; all three services boot.

0.1 Work directly in `/home/pratay-karali/Desktop/archipelago/Archipelago/`. No copy. Deployment artifacts target AntDeploy app `archipelago-2`.
0.2 Split oversized modules per AGENTS.md (≤500 lines, one concern per package, downward imports only):
   - `routes_chat.py` → `archipelago/inference/routes/chat/` package (stream, routes, synthesis, mcq, telemetry)
   - `routes_misc/` oversized files → per-feature modules
   - `librarian_worker/` → already part-based; finish the split
   - Any other file >500 lines (audit with `scripts/quality_gate.py`)
0.3 Root shims: old import paths keep working via shims (backwards compat).
0.4 Verify: inference :5151, graph :5150, chat :5152 all boot; `/api/readiness` → `{"ready": true}`; xkiro config untouched (`llm_gateway.py`, `state.py`).
0.5 Graph integrity baseline: node/edge counts recorded as regression target (docs/01 §8).

**Exit criteria:** services boot, `ruff` + `quality_gate.py` pass, graph counts match baseline.

---

## Phase 1 — Source Links (fix #1: Pearson, fix #2: HF dataset page, fix #3: page links)

**Goal:** every book/paper/dataset mention links to the **exact verified page**, never a generic homepage.

1.1 **Pearson** — audit `resolver/pearson.py` + `citations.py` + `aliases.py`:
   - Exact reader URL with page: `https://ebooks.elibrary.in.pearson.com/wr/pdfviewer.html?version=…&subscriptionId=…#book/{uuid}/page/{page}` — verify for all 40 Pearson catalog books.
   - Kill the generic `https://elibrary.in.pearson.com/` fallback in chat/library surfaces (keep only as last-resort with `working:false` flag, never rendered as a plain link).
   - Library cards + chat evidence rail + page-view all use the exact URL.
1.2 **Hugging Face dataset page** — audit `resolver/huggingface.py` + `library_catalog_api.py`:
   - Every HF resource links to `https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/{path}` (exact file page), not the repo root.
   - `library_catalog_api.py` hardcoded `pdfUrl`/`resolveUrl` (lines ~259–298) → replaced by registry-driven exact URLs.
1.3 **Page links** — `citations.py` + `routes_page_view.py` + `js/02--kw-highlights.js`:
   - `[S1]` markers → clickable `p.N ↗` → `/api/page-view?doc_id=…&page=N#page=N` → Pearson reader or local `/read` deep link.
   - Verify printed-page mapping (`page_label_map`) so `p.N` matches the book's printed page.
1.4 IEMCRP + UEMK OPAC links present on landing + library (exact institutional URLs, https).

**Exit criteria:** automated source-link test (docs/01 §20) passes for Pearson, HF, page-view, IEMCRP, OPAC; no generic-homepage links rendered.

---

## Phase 2 — In-Chat Graph & Roadmap Custom QnA (fix #4, fix #5)

**Goal:** graph and roadmap are first-class, real graph data — never fabricated.

2.1 **In-chat graph** — verify `subgraph` payload (nodes/edges from Kùzu traversal) renders via `graphify.js` + SVG cards for `graph_strong`/`graph_soft` queries; fix empty-graph and loading states; node click → concept details.
2.2 **Roadmap custom QnA graph** — wire the full loop:
   - "Learn X" → 5 diagnostic MCQs (`/api/roadmap/quiz`) → user answers (`/api/chat/verify-mcq`) → mastered/gap scoring → personalized graph DAG (`build_personalized_graph_dag`) → roadmap steps with exact page links.
   - Render personalized graph card (`js/16/17`) + roadmap modal from real evaluation result.
2.3 Response validation: graph/roadmap payloads only from real traversal; honest "not available" otherwise (docs/01 §13).

**Exit criteria:** E2E chat test — "What should I learn before Transformers?" returns subgraph + MCQ card + personalized roadmap, all graph-backed.

---

## Phase 3 — Librarian Ingestion Cleanup (mention-a-book auto-populate)

**Goal:** a librarian can mention a book (or click an image of its index/content page) and the system auto-populates the record; same for spreadsheets.

3.1 **Mention-a-book auto-populate** (new `archipelago/ingestion/mention.py`):
   - Librarian types title/ISBN → matcher queries: Kùzu catalog (Resource/Document) → `resource_registry` (46 resources) → Pearson catalog (40 books) → HF repo file list → Google Books/OpenLibrary fallback.
   - Returns exact source URL + metadata; librarian confirms → record created/updated idempotently.
3.2 **Index/content page image** (new `archipelago/ingestion/page_image.py`):
   - Librarian uploads/clicks image of a book's index or content page → OCR (local, no external AI call) → extract title/author/ISBN/publisher/year → pre-fill the ingestion form → confirm → `metadata_only` or `full` job.
3.3 **Spreadsheet library details** — extend `ods_ingestion.py`/`catalog_ingest.py`:
   - ODS/CSV upload → schema validation → normalize → dedupe → `CREATE/UPDATE/UNCHANGED/RETIRE` per record (docs/01 §10) → graph + library + stats update.
   - Fix ODS path resolution (files live in parent dir; `default_docs_ods_paths()` looks in `docs/`).
3.4 Ingestion frontend: wire `ingestion-frontend/index.html` scaffold to real `/api/ingest/jobs` polling + the new auto-populate endpoints.

**Exit criteria:** librarian can (a) mention "Deisenroth Math for ML" → form pre-filled with exact HF/Pearson link; (b) upload index-page image → fields extracted; (c) upload ODS → records merged idempotently. Idempotency test passes (run twice, no duplicates).

---

## Phase 4 — UI: Landing Page & Sign-In Removal

**Goal:** landing matches the reference screenshot; no sign-in button anywhere.

4.1 **Landing page** (`ui/chat/landing.html`) — match screenshot:
   - Dark background, wordmark `△ Archipelago` top-left, tagline top-right.
   - Centered hero: `KNOWLEDGE OPERATIONS` eyebrow → huge `KNOWLEDGE` → "Islands of insight, connected — ask the corpus, follow citations, explore the graph."
   - Serif `Built for the curious` + subtext.
   - Bottom-center CTAs: **Enter the chat** (dark pill) + **Library details** (gold pill).
   - Remove hero video + institutional link grid (or move links into footer).
4.2 **Remove sign-in button:**
   - Chat header Sign In link (`index.html:175–178`) → remove.
   - Library page Sign In button (`library.html:420–423`) → remove.
   - Server-side gates: chat/library become publicly readable (keep staff-only graph + ingest endpoints gated).
4.3 Verify all pages render without auth; role-gated surfaces (graph explorer, librarian panel) unchanged.

**Exit criteria:** landing matches screenshot; no sign-in buttons in UI; staff gates still enforced.

---

## Phase 5 — Deployment Readiness

**Goal:** deployable on AntDeploy per docs/01 + docs/02.

5.1 Docker: `Dockerfile` + `docker-compose.yml` (inference, graph, chat, ingestion); HF model pulled pinned at runtime (docs/01 §9, docs/02 §1C).
5.2 CI/CD: ruff, mypy, quality_gate, unit/integration tests, graph integrity gate, source-link test, live ingestion + inference smoke tests (docs/01 §8, §11, §20).
5.3 Supabase: auth/roles/RLS + response/retrieval/graph cache tables (docs/03); secrets never reach frontend.
5.4 Health/readiness, rate limiting (429 + Retry-After), request dedup, versioned cache keys (docs/03).
5.5 Observability: structured logs, request IDs, AI-call metrics (cache hit ratio, tokens saved).
5.6 Docs: API docs, runbooks, changelog; Definition of Done checklist (docs/01 §28) verified.

**Exit criteria:** full pipeline green in staging — ingestion → graph → library → retrieval → inference → chat → links → roadmap → graph UI.

---

## Execution Order (per user instruction: fixes 1-by-1)

```
Phase 0 (split + workspace)
  → Phase 1.1 Pearson
  → Phase 1.2 HF dataset page
  → Phase 1.3 Page links
  → Phase 2.1 In-chat graph
  → Phase 2.2 Roadmap custom QnA graph
  → Phase 3   Ingestion cleanup (mention-a-book, page image, spreadsheets)
  → Phase 4   Landing UI + sign-in removal
  → Phase 5   Deployment readiness
```

Each phase: implement → test → verify no regression → next.

---

# COMPLETION REPORT (2026-10-02)

## Verification summary

| Suite | Result |
|---|---|
| `tests/unit` (gating) | **905 passed, 6 skipped, 0 failed** |
| `tests/unit/test_source_links.py` | 17 passed (new gate) |
| `tests/unit/test_ingestion_intake.py` | 25 passed (new gate) |
| `tests/integration` | 26 passed, 13 failed, 6 errors — see known-issues below |
| Files > 500 lines | 0 in production code |
| Services boot | inference 5151, chat 5152, graph 5150 all import and serve |
| Probes | `/health` 200, `/ready` 200, `/api/readiness` ready=true |
| Open reading + gated staff | `/ /chat /library` 200 anonymous; `/api/users`, `/api/librarian/*`, `/api/ingest/*` 401 |

## Phase 0 — clean architecture

Split 7 oversized modules into packages (all now ≤500 lines):

| Was | Now |
|---|---|
| `routes_chat.py` (1026) | `inference/routes/chat/` (8 modules) |
| `citations.py` (516) | `inference/citations/` (3 parts) |
| `library_catalog_api.py` (524) | `inference/library_catalog/` (5 parts) |
| `llm_gateway.py` (505) | `inference/llm_gateway/` (5 parts) |
| `intent_gate.py` (537) | `inference/intent_gate/` (3 parts) |
| `supabase_auth.py` (529) | `supabase_auth/` (4 parts) |
| `api/app.py` (671) | `api/` (engine_state, middleware, 5 route modules) |

Bugs fixed while splitting:

1. `ingestion_worker_job_mixin.py` had a **syntax error** (bad indentation) — the app could not boot.
2. `chat_server` **REPO_ROOT regression**: after the earlier split, `BASE_DIR` resolved to `chat_server/`, so the landing page, library, reader and every page link returned 404.
3. **Cypher injection** in `/api/catalog/search` — user input was interpolated into Cypher. Now `$q` parameter binding.
4. **Fabricated library record** — catalog search invented "Principles of {query}" on no match. Now returns real rows or an empty set.
5. **Broken catalog query** — referenced a nonexistent `Resource.location` column, so search *always* fell through to the fabricated record. Fixed to the real schema; now returns real records (2498 catalogue entries).
6. `quality_gate.py` reported **0/7 always** — gates set `passed=False` on failure but never `True` on success. Also fixed the magic-number check flagging constant *definitions*.
7. `synthesis`/`routing`/`llm_gateway` test patch targets repointed at the modules that now own the moved code.

## Phase 1 — source links

- 17-test source-link gate added (`tests/unit/test_source_links.py`).
- Pearson: **40/40** catalog books resolve to an exact `#book/{uuid}/page/{N}` reader page.
- Hugging Face: **21/21** entries use exact per-file `blob/main/<file>` pages; **0** repo-root links.
- Page links: `/api/page-view?doc_id=…&page=N#page=N` with percent-encoded doc ids; printed-page label mapping verified.
- Corrected 3 mismatched links: "Deep Learning" pointed at the GAN paper (now correctly labelled *Generative Adversarial Nets*), OSTEP claimed the full book while linking one chapter, Nilsson pointed at a dead local route.
- OpenLibrary/Google Books resolvers now **reject irrelevant search results and placeholder ISBNs**, so garbage input can never surface an unrelated book.

## Phase 2 — graph

- **In-chat graph was broken**: it returned 1 node / 0 edges because `generate_bounded_subgraph` received no Kùzu connection and the in-memory index holds no edges (0 of 537 nodes). Now defaults to the live graph: mode_a 3n/4e, mode_b 10n/16e, mode_c 10n/14e.
- Citation ranking now prefers the document that discusses a concept most and one titled after it, so **Transformer → Vaswani2017**, **Attention → Vaswani2017**, **BERT → Devlin2018** (previously Transformer cited the Bahdanau paper).
- Roadmap custom QnA loop verified end-to-end: 3 MCQs → verify → score → mastered/gaps → baseline → personalized DAG (4 nodes/3 edges) → roadmap with page links.

## Phase 3 — librarian ingestion

- **Mention-a-book** (`archipelago/ingestion/mention.py`): searches ISBN → catalogue (2498 rows) → registry (46) → Pearson (40) → HF → local PDFs; returns exact source URLs; honest no-match instead of a guess. Weak matches never auto-apply metadata.
- **Scanned page intake** (`archipelago/ingestion/page_image/`): local Tesseract OCR (no external AI call, air-gap safe) reads title, author, ISBN, publisher, year, edition and the full table of contents, then resolves the exact source page. Verified at 94.5% OCR confidence on a generated index page.
- **Spreadsheet merge** (`archipelago/ingestion/spreadsheet.py`): CREATE/UPDATE/UNCHANGED/RETIRE over ODS/CSV/XLSX. Verified **idempotent** — pass 1 wrote 37 changes, passes 2 and 3 wrote 0 with the node count stable at 2529. Destructive retire requires explicit confirmation and is off by default.
- 5 librarian routes added under `/api/ingest/*` and gated to librarian/admin.

## Phase 4 — UI

- Landing page rebuilt to the reference layout: dark hero, `KNOWLEDGE OPERATIONS` eyebrow, large `KNOWLEDGE` wordmark, serif *Built for the curious*, and **Enter the chat** + **Library details** CTAs at the bottom. Hero video removed.
- Sign-in removed: no `href="/login"` anywhere in the user-facing pages; the only remaining "Sign In" text is *Sign In to Pearson* (instructions for the external institutional portal, which is correct).
- Reading is now open to every campus user: `/`, `/chat`, `/library`, `/read/*` and `/api/chat` all work anonymously, while `/api/users`, `/api/librarian/*`, `/api/ingest/*`, `/api/documents`, `/api/manual/*` return 401. Set `ARCHIPELAGO_OPEN_READING=0` to restore mandatory sessions.

## Phase 5 — deployment readiness

- **Probes added** (`/health` liveness, `/ready` readiness, `/api/health` alias) and added to the bootstrap allow-list. Dockerfile now liveness-checks `/health`; compose gates on `/ready`.
- **CI repaired**: it referenced `src/` and `chat_server.py`, both of which no longer exist, so every run would have failed. Now points at `archipelago/ okf/ chat_server/ graph_server.py tests/`.
- **4 CI jobs added**: Source Link Verification, Librarian Intake, Secret Scan, Deployment Readiness (runs the real probe/open-reading checks). 12 jobs total; YAML validated.
- Tesseract added to the image and `pytesseract`/`Pillow` to requirements so the OCR intake works in the container.
- Supabase migrations for response/retrieval/graph cache, auth roles and auth performance are in place.

## Known issues (pre-existing, not introduced here)

- `tests/integration`: 13 failures + 6 errors from a legacy `inference_server` shim expectation, a missing `okf_relationships.json` data artifact, `/api/page-view`'s documented 302-to-reader behaviour, and baseline node-count drift (`okf_graph.json` holds 514 nodes while the docs cite a 5151 baseline; Kùzu holds 537 concepts). CI marks this suite `continue-on-error: true`.
- `quality_gate.py` still reports pre-existing debt: ~385 magic numbers and 14 dependency-direction violations in untouched modules (`okf/pipeline*.py`, `routes_misc/m05_graph_admin.py`), plus 2 banned patterns in `okf/extraction.py` and `test_inference.py`. The gate is now honest about these.
- `ruff`/`mypy` across the whole repo remain non-clean (pre-existing; two directories alone report 199 findings).
