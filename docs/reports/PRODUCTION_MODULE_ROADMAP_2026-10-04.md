# Archipelago Production Modules and Delivery Checklist

**Updated:** 2026-10-04  
**Scope:** Advanced Personalized Traversal spec and Production Engineering,
Restoration & Production Readiness spec supplied for this work.  
**Status rule:** checked means supported by current test or live evidence; code
presence alone is not completion.

## Current verified baseline

- Live `https://archipelago.antideploy.com/chat` responds with HTTP 200.
- Live `/api/readiness` reports ready, inference-only, 520 concepts, 40 Pearson
  books, and a full corpus. This does not verify chat, personalized learning,
  citations, or librarian workflows.
- The current checkout is `archipelago3`; Antideploy's configured GitHub default
  branch is `session3-stable`. Production does not automatically build this
  checkout's branch.
- The worktree already contains extensive uncommitted feature and refactor work.
  Preserve and review it before staging or releasing.
- Existing code includes graph routing, curriculum, quiz endpoints, citations,
  catalog lookup, and personalization-related UI/API code. Mark each item below
  complete only after its acceptance test passes.
- Full local regression: **1,449 passed, 7 skipped** across unit, integration,
  frontend, inference, ingestion, and retrieval tests.
- Ruff lint and format checks pass on the touched Python files; repo-wide
  lint/type/security gates were not run for this release check.
- `node scripts/refactor/smoke_chat_ui.mjs`: **passed**; 11 structural/browser
  contract checks (chat, graph choice/render, adaptive flow, topology,
  remediation, auto-prompt, and Pearson link) returned no errors.
- Credential values were removed from `.antideploy.json`; the credential PDF is
  kept locally under ignored `data/private/` rather than `docs/`.
- The hosted access card now contains portal links and campus sign-in guidance,
  not shared usernames or passwords. Provider-side rotation is still required
  for any credential that was previously committed or shared.

## Canonical module map

Use these existing boundaries as the implementation destinations. The similarly
named `backend/` packages are currently empty namespace placeholders; do not add
a second implementation there. Keep old imports and the `host_inference/` runtime
as compatibility/service boundaries until parity tests prove consolidation safe.

| Concern | Canonical implementation | Acceptance evidence |
|---|---|---|
| HTTP contracts and intent routing | `archipelago/inference/routes/`, `routing/`, `intent_gate/` | Contract tests for all six response types |
| Retrieval and graph traversal | `archipelago/inference/ranking/`, `curriculum/`, `archipelago/graph/` | Stable top-k, bounded traversal, graph integrity |
| Personalization state and assessment | `archipelago/inference/curriculum/`, `diagnostic_mcq/`, `backend/personalization/` only after consolidation | Deterministic mastery/path tests; no cross-user state bleed |
| Grounding and page citations | `archipelago/inference/citations/`, `okf/graph/evidence.py`, `host_inference/engine/links.py` | Source/page/hash contract tests |
| Catalog and OPAC | `archipelago/inference/library_queries/`, `catalog_ops.py`, `archipelago/resolver/` | Fixture catalog + live-link contract tests |
| Ingestion and OCR | `archipelago/ingestion/`, `okf/`, `backend/OCR/` | Fixture PDF/image/ODS tests and idempotency |
| Hosted API and browser | `host_inference/hostapp/`, `host_inference/ui/`; keep `ui/` parity | API + browser contract tests across both trees |
| Configuration and operations | `infrastructure/`, `deploy/`, `scripts/ops/` | Clean-checkout deployment and secret scan |

## Workstreams and acceptance checklist

### W0 — Preserve, inventory, and normalize the repository

- [ ] Record all tracked and untracked work before staging; retain all visual
  assets, video, book-stack animation, and local data.
- [ ] Map API routes to their browser callers; identify dead code only with
  import/reference evidence.
- [ ] Keep one canonical implementation per feature. Replace duplicated files
  with tested imports/build outputs in a later parity-gated change.
- [ ] Move root-level launch shims into `scripts/` or documented entry points;
  keep only intentional backwards-compatible shims at repo root.
- [ ] Establish a hard source-file limit of 400 lines and a 300-line target.
  Split large modules by cohesive responsibility; do not split generated data,
  fixture assets, or minified/vendor files mechanically.
- [ ] Run secret scanning and remove institutional credentials from tracked
  config/docs. Rotate any credential that was previously committed or shared.

### W1 — Deterministic query and response contracts

- [ ] Normalize and validate input, identify intent/domain, retrieve graph and
  catalog evidence, filter private fields, synthesize only minimal context,
  validate model output, and attach citations in a deterministic pipeline.
- [ ] Preserve six contracts: `GRAPH_SYNTHESIS`, `CATALOG_SHELF_ROUTING`,
  `AUTH_GATEWAY`, `MCQ_DIAGNOSTIC`, `INGESTION_ANALYSIS`, and
  `GUARDRAIL_INTERCEPT`.
- [ ] Test normal explanations, shelf lookup, auth, diagnostic assessment,
  ingestion analysis, greetings, and guardrail refusals independently.
- [ ] Enforce output schema, context-size limits, provider timeout/failover,
  request IDs, safe streaming, and no raw private catalog/account data to LLMs.

### W2 — Personalized traversal and diagnostics

- [ ] **Glass-box inspector:** student responses expose a short reason; staff
  inspector exposes intent, anchors, evidence, traversal, confidence, and timing
  with private fields redacted.
- [ ] **Learning preference:** explicit math/code/conceptual preference changes
  explanation presentation without changing graph evidence or mastery scoring.
- [ ] **Misconception detection:** wrong options map to misconception tags and
  a corrective Socratic follow-up; no unsupported diagnosis from free text.
- [ ] **Fading mastery:** repeated evidence adjusts hint detail gradually and
  resets or decays by the documented policy.
- [ ] **Confidence-aware questions:** question selection targets uncertain
  prerequisite nodes and records confidence separately from correctness.
- [ ] **Adaptive budget:** start with three questions; stop early when confidence
  is calibrated, expand only when ambiguity remains, and cap at ten.
- [ ] **Coverage-aware traversal:** select one to six hops using evidence
  coverage, confidence, and user goal; bound nodes/edges and prevent cycles.
- [ ] **Clean student graph:** student view contains only the learning path and
  sources; internal scores, debug nodes, and private metadata stay hidden.
- [ ] **Gap-to-library / OPAC:** map a missing prerequisite to available holdings
  and authorized OPAC links; distinguish unavailable from unknown inventory.
- [ ] **Faculty/librarian mode:** aggregate cohort diagnostics with minimum
  group-size/privacy controls; never expose named learner records by default.
- [ ] **Developer debug mode:** authorized and opt-in, redacted, and absent from
  ordinary student responses.
- [ ] **Path recalculation and transparency:** answer “why this path” from the
  actual selection evidence; recalculate after learner answers/preferences.
- [ ] **Session memory:** retain only consented, minimal mastery/preference data;
  provide reset/expiry and isolate sessions/users.
- [ ] **Librarian intelligence:** show catalog coverage/gaps and ingestion
  proposals with provenance; librarian approval precedes publication.
- [ ] Keep the UI progressive: normal answer first, optional diagnostics and
  graph controls on demand, keyboard/screen-reader accessible.
- [ ] Test 3-question early stop, 10-question maximum, calibration, mastery
  fading, misconception handling, session reset, and personalized path evidence.

### W3 — Graph, citations, and library experience

- [ ] Support bounded k-hop retrieval and explain selected nodes/edges.
- [ ] Keep the normal graph, chat mini graph, and personalized learning graph
  separate, with shared stable node IDs and clear visual semantics.
- [ ] Every source badge resolves to a real document, page, and available passage
  coordinates/hash; never fabricate a page or institutional shelf location.
- [ ] Pearson/Hugging Face links follow documented URL contracts and do not
  expose credentials or claim entitlement the user lacks.
- [ ] Restore and verify book stack, graph interactions, landing experience, and
  existing image/video/animation assets.
- [ ] Make catalog counts derive from records, not hard-coded presentation data.

### W4 — Ingestion and source lifecycle

- [ ] PDF/text/OCR/ODS inputs validate size, type, schema, and provenance.
- [ ] Evaluate extraction model on a held-out gold set before enabling automatic
  ingestion; unattended model ingestion stays disabled until its score gate
  passes.
- [ ] Ingest to staging, deduplicate idempotently, validate graph invariants,
  require librarian review, then atomically publish with rollback.
- [ ] Exercise TOC/index/content-page extraction end to end with licensed or
  authorized fixtures.
- [ ] Detect new, changed, and withdrawn sources. Preserve provenance and
  tombstone withdrawn records so answers say “no longer in records.”
- [ ] Web fetching must enforce robots/terms policy, per-domain limits, audit
  provenance, and human approval; never bypass paywalls or authentication.
- [ ] Treat Apify or other paid fetchers as opt-in with an explicit spend cap.

### W5 — Production security, observability, and operations

- [ ] Keep deploy credentials in Antideploy's encrypted secret store, not in
  `.antideploy.json`, checked-in `.env`, logs, fixtures, or browser config.
- [ ] Confirm auth boundaries on every mutating endpoint; rate limits return 429
  with `Retry-After` and are tested per role/IP.
- [ ] Readiness reports meaningful dependency/data state; liveness remains fast.
- [ ] Log request IDs and redacted structured events; record cache, latency,
  provider, routing, and ingestion metrics without personal content.
- [ ] Version cache keys by graph/library/model/prompt versions and test invalidation.
- [ ] Verify Docker portability, mounted data paths, backup/restore, and offline
  behavior for the library-computer deployment.
- [ ] CI includes lint, typing, architecture/file-size checks, secret/dependency
  scans, unit/integration suites, and opt-in live E2E.

### W6 — Verification and release

- [x] Run unit, integration, frontend, retrieval, ingestion, and inference suites.
- [ ] Run live test matrix: greeting, concept explanation, prerequisite,
  personalized diagnostic, early stop, adaptive expansion, citation/page open,
  catalog/OPAC, auth boundary, upload-to-staging, approval, and rollback.
- [ ] Confirm GitHub default branch, reviewed diff, green CI, and deploy trigger
  before production release. Do not release directly from a dirty worktree.
- [ ] After release, check readiness plus real chat, citation, catalog, and graph
  workflows on the deployed URL; record release ID and observed results.

## Release blockers at this update

- No Antideploy deploy/status connector is available in this session.
- The configured default branch is `session3-stable`, not this checkout's
  `archipelago3`; the production change set has not been released from this
  branch.
- Full local regression is green, but the file-size audit still finds 56 source
  files over 400 lines. The requested size cleanup is not complete.
- Several worktree changes are pre-existing and uncommitted. Review ownership
  and secrets before creating a release commit.

## File-size audit (source files over 400 lines)

Audit covered Python, JavaScript/TypeScript, HTML, CSS, shell, and YAML under
application, frontend, test, and script directories; generated data and vendor
assets were excluded. There are **56 paths** over 400 lines. Several are copies
of the same page or script across `chat_ui/`, `host_inference/ui/`, and `ui/chat/`
and should be consolidated only after parity tests pass.

| Lines | File |
|---:|---|
| 1844 | `frontend/book-stack/books_showcase_src.tsx` |
| 1145 | `archipelago/inference/synthesis.py` |
| 1075 | `ui/chat/library.html` |
| 1075 | `host_inference/ui/library.html` |
| 1075 | `frontend/library/library.html` |
| 1075 | `chat_ui/library.html` |
| 1073 | `archipelago/inference/routing.py` |
| 846 | `archipelago/inference/routes_misc.py` |
| 834 | `scripts/download_pilot_corpus.py` |
| 817 | `scripts/run_master_library_ingest.py` |
| 814 | `tests/unit/test_inference_75_cases.py` |
| 714 | `archipelago/inference/demo_query_books.py` |
| 711 | `ui/chat/index.html` |
| 711 | `host_inference/ui/index.html` |
| 711 | `chat_ui/index.html` |
| 635 | `tests/unit/test_source_lifecycle.py` |
| 621 | `host_inference/engine/answer.py` |
| 542 | `archipelago/inference/ranking.py` |
| 539 | `ui/chat/auth_bridge.js` |
| 539 | `host_inference/ui/auth_bridge.js` |
| 539 | `chat_ui/auth_bridge.js` |
| 530 | `archipelago/inference/intent_gate.py` |
| 526 | `ui/chat/library_showcase_3d.js` |
| 526 | `host_inference/ui/library_showcase_3d.js` |
| 526 | `frontend/book-stack/library_showcase_3d.js` |
| 526 | `chat_ui/library_showcase_3d.js` |
| 517 | `ui/chat/chromatic_waves.js` |
| 517 | `host_inference/ui/chromatic_waves.js` |
| 517 | `chat_ui/chromatic_waves.js` |
| 498 | `ui/chat/js/08-send-message.js` |
| 498 | `host_inference/ui/js/08-send-message.js` |
| 498 | `chat_ui/js/08-send-message.js` |
| 495 | `scripts/ops/seed_soference_nodes.py` |
| 494 | `okf/relations.py` |
| 487 | `scripts/ops/gpu_ingest_local_pdfs.py` |
| 480 | `tests/integration/test_citation_correctness.py` |
| 478 | `tests/unit/test_contract_routing.py` |
| 476 | `archipelago/inference/tc75_cases.py` |
| 466 | `okf/graph/evidence.py` |
| 465 | `archipelago/inference/ods_parser.py` |
| 462 | `archipelago/cli.py` |
| 458 | `archipelago/inference/library_credentials.py` |
| 451 | `archipelago/eval/extract_eval.py` |
| 444 | `archipelago/core/router.py` |
| 441 | `scripts/eval_lib_qwen_ingestion.py` |
| 438 | `tests/conftest.py` |
| 427 | `archipelago/resolver/huggingface.py` |
| 424 | `okf/pipeline.py` |
| 417 | `tests/unit/test_ui_deeplinking.py` |
| 414 | `tests/unit/test_portability.py` |
| 409 | `ui/chat/reader.html` |
| 409 | `host_inference/ui/reader.html` |
| 409 | `chat_ui/reader.html` |
| 407 | `okf/extraction.py` |
| 403 | `okf/eval/gold.py` |
| 402 | `archipelago/ingestion/fetch_policy.py` |

Split order: active request/response path and shared browser sources first;
then ingestion/evaluation utilities; then oversized tests and operational
scripts. After each split, run the affected tests and retain old import/route
behavior.
