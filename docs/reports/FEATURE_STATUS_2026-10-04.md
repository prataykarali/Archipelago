# Archipelago feature inventory: local code and deployed site

**Audit date:** 2026-10-04  
**Live URL:** <https://archipelago.antideploy.com>  
**Purpose:** Inventory the features named in the Advanced Personalized Traversal & Diagnostic Layer and Production Engineering / Restoration / Production Readiness specifications, plus the related app surfaces and API routes. This report distinguishes repository evidence from production evidence.

## How to read the status

- **Local tested** — relevant automated tests or a UI smoke check passed in this checkout. It does not imply that this exact checkout is deployed.
- **Local present / partial** — code or UI exists, but the full behavior or acceptance criteria are not established.
- **Live reachable** — the deployed URL returned a response for the route/page. This proves reachability only.
- **Live behavior verified** — a safe, read-only live request returned the expected kind of data. It does not prove all cases.
- **Not live-verified** — no end-to-end production interaction was performed. For chat, uploads, and other model or mutating requests, this audit did not send a POST.
- **Missing / incomplete** — the full specification capability is not present or current evidence does not show it meeting the stated requirement.

An endpoint appearing in source is not proof it is deployed. A green test is not proof that production uses the tested revision.

## Deployed snapshot

The current hosted release was observed through `https://archipelago.antideploy.com` with a browser-like User-Agent on 2026-10-04:

| Check | Observed result | What it establishes |
|---|---|---|
| `GET /`, `/chat`, `/library`, `/graph`, `/login` | HTTP 200 | Landing/chat/library/graph/login pages are reachable. No full browser workflow was performed. |
| `GET /health`, `/ready`, `/api/readiness` | HTTP 200 | Health/readiness pages and API are reachable. |
| `GET /api/readiness` | `ok=true`, mode `inference-only`, 520 concepts, full corpus, 40 Pearson books, cache `supabase`, ingestion `false` | A graph/corpus-backed inference runtime reports ready. This is not an ingestion readiness claim. |
| `GET /api/library/data` | HTTP 200; includes `ebook_shelf`, `ebook_stats`, `hf_paths`, `holdings`; `ebook_shelf` has 91 entries | Hosted library data endpoint responds and exposes a 91-entry shelf payload. |
| `GET /api/catalog/all` | HTTP 200; `total=91` | Hosted catalog endpoint responds with 91 records. This does not verify OPAC holdings or shelf-location accuracy. |
| `GET /api/graph/subgraph?q=attention&max_nodes=5` | HTTP 200; 5 nodes, 9 edges | Hosted graph subgraph query returns graph data. |
| `GET /api/roadmap?topic=attention` | HTTP 200; roadmap response has topic, stages, hops, target id | A hosted roadmap read request returns a roadmap-shaped response. |
| `GET /api/quiz?topic=attention` | HTTP 200; response contains `quiz` | The hosted quiz GET returns a quiz-shaped response. This does not test submitting an answer. |
| `GET /api/chat/diagnostic-mcqs?concept=attention` | HTTP 400 | This request did not yield a diagnostic payload. The endpoint/parameter behavior needs investigation before calling hosted diagnostics working. |
| `GET /api/metrics/cache` | HTTP 200; fields returned; observed requests/hits/misses all 0 and hit percentage `0.0%` | Metrics endpoint responds. The zero values are only this snapshot, not a performance result. |
| `GET /api/auth/config` | HTTP 200; `configured=true`, `required=false` | General hosted auth is configured but not required for public access. Do not assume every route is protected. |
| Anonymous `GET /api/ingest/capabilities` | HTTP 403 | This ingest capability request is denied anonymously. Other write routes were not probed. |
| `/chat` response headers | `x-archipelago-mode: inference-only`; release `554c8df13de83ba6757a66b1955f2a2573f2cdbc` | Identifies the observed production mode/release. That release SHA is not the current local `HEAD`. |

The checkout is on branch `archipelago3` at `5280237e69c31c8d15c59806579ea5cc4905ff27`; the configured GitHub default branch observed in repo configuration is `session3-stable`. The live release SHA differs from local `HEAD`. **This audit therefore does not establish that the current local changes are deployed.** The worktree has extensive tracked and untracked changes; no release was made as part of this inventory.

## User-facing features

| Feature | Local code / test status | Deployed evidence |
|---|---|---|
| Landing page and brand experience | Landing route and assets exist; UI smoke coverage was included in the 11-check smoke run. Detailed visual comparison was not performed. | `/` returned 200. Not visually audited. |
| Chat page, prompt entry, send flow, welcome state | Implemented in the host UI and mirrored UI trees. Chat UI smoke checks passed. | `/chat` returned 200. No production chat POST was sent, so answer generation, streaming, and citations are not verified live. |
| Normal concept graph | Graph UI/API code and smoke checks exist. | `/graph` returned 200; live subgraph GET returned 5 nodes/9 edges. Interactive graph behavior not tested in browser. |
| Chat mini graph / topology | UI smoke checked graph controls/render and topology structure. | Not separately verified in production beyond graph endpoint response. |
| Personalized learning graph | UI modules and adaptive-step/diagnostic code exist; local tests cover parts of the adaptive progression. | No hosted adaptive-step POST or full personalized session was run. Not live-verified. |
| Adaptive question card and answer submit UI | UI smoke checked adaptive flow and auto-prompt structure; diagnostic/adaptive unit tests passed. | No live answer submission. Hosted diagnostic GET returned 400 for the tested concept value. |
| Review gaps, mastered prerequisites, target states | Adaptive-step code builds status-tagged nodes; local diagnostic tests cover progression/completion behavior. | Not live-verified. |
| Remediation / corrective response | UI smoke found remediation structure. Misconception-aware Socratic handling backed by graph relations is not demonstrated as a complete feature. | Not live-verified. |
| Pearson/library book links | Link resolver/source-link tests and UI smoke Pearson-link check passed locally. | 40 Pearson books reported by readiness. No production citation/book-link click-through was tested. |
| Library/catalog page | Catalog UI and data routes exist. Local runtime/catalog tests passed. | `/library` returned 200; library data and catalog GETs returned 91-entry payloads. No individual title, copy, call number, or OPAC link was validated. |
| Reader, PDF/paper open, page view | Reader routes and source-link code exist; local deep-link tests passed. | Reader endpoints and real document page links were not verified in production. |
| Login page / auth status | Login/session routes exist; local auth-boundary tests passed for tested cases. | `/login` returned 200. Auth config reports `required=false`; no login/session was performed. |
| Accessible/simple student-first UI | The layout keeps the main chat surface and optional graph/diagnostic controls. Full keyboard and screen-reader acceptance has not been recorded. | Not audited live. |
| 3D book stack / animation / visual assets | Assets and book-stack code remain in the repo; no destructive asset changes were made in this audit. Full visual restoration review is incomplete. | No hosted visual/animation inspection was performed. |

## Query routing, retrieval, and answer features

The repository contains two backend surfaces: the Antideploy-oriented `host_inference/` runtime and the separate `archipelago/api` service. The source route inventory below belongs to these local applications; it is not proof that both are hosted at the same domain.

| Spec feature / contract | Local code and evidence | Current status |
|---|---|---|
| `GRAPH_SYNTHESIS`: concept explanations, graph retrieval, synthesis | Inference engine, intent/routing, graph traversal, retrieval, synthesis, and chat route exist. Query-pipeline and graph integration tests are included in the passing suite. | Implemented and locally tested in covered cases; no hosted chat request was executed. |
| `CATALOG_SHELF_ROUTING`: title/inventory/library lookup | Catalog query/ranking/resolver modules and host catalog routes exist; catalog/source-link tests passed. | Partial. Hosted catalog endpoints respond, but no specific physical copy, shelf/rack, barcode, or call-number lookup was validated. |
| `AUTH_GATEWAY`: hours, e-resource, institutional access | Auth/access response code and host inference response card exist; the shared credentials were removed from the access card. | Partial. Live general auth is optional (`required=false`); deterministic answers were not tested against production. |
| `MCQ_DIAGNOSTIC`: diagnostic questions and personalized learning | Diagnostic payload, adaptive step, roadmap/quiz routes, and browser flow are present. Unit tests cover selected adaptive progression. The code currently sets a four-question checkpoint and max four questions. | Partial. Not the requested 1–3 question sequence or confidence-adaptive 3–10 budget. Hosted diagnostic GET returned 400 in this probe. |
| `INGESTION_ANALYSIS`: analyze uploaded academic material | Ingestion/OCR/parsing/projection modules and tests exist, and host ingest routes are mounted in source. Readiness reports ingestion disabled. | Inference-only runtime reports ingestion `false`; no production upload was attempted. Do not call production ingestion available. |
| `GUARDRAIL_INTERCEPT`: out-of-domain handling without rejecting normal greetings | Guardrail/routing code and contract tests exist. | Local tested in selected cases; no production chat/guardrail interaction was run. |
| Intent before expensive inference | Intent gate and routing modules exist; contract routing tests passed. | Local implementation exists. Production dispatch and cost behavior not measured. |
| Domain/topic identification | Routing and graph anchoring modules exist; query pipeline tests passed. | Local tested in selected cases; production chat not tested. |
| Bounded graph traversal | Graph traversal and subgraph endpoints exist; graph integrity tests passed. | Local tested and live subgraph GET returned data. Personalization/coverage-aware selection is incomplete (see below). |
| Page-level citations and grounded sources | Citation/link modules, citation fallback, and citation correctness/source-link tests exist. | Local tested for fixtures. No production generated answer or page citation was inspected. |
| Private-data filtering before model context | Code contains filtering/credential protections and relevant local test areas. Full live context inspection is unavailable and was not performed. | Partial; cannot verify model payload privacy from public route checks. |
| NVIDIA/XKIRO external inference integration | Provider/inference configuration code exists in repository. | Runtime readiness says inference-only but does not identify provider success. No production chat request/provider response was exercised. |
| Cache and request deduplication | Answer cache, deduplication, and metrics code/tests exist; local cache unit tests passed. | Live metrics route responds with zero observed counters. No production chat request was made to test cache hits, deduplication, invalidation, or token savings. |
| Streaming, timeout/failover, request IDs, safe wrappers | Some host chat streaming/wrapper code exists. Full acceptance across providers has not been established. | Not live-verified. |
| Six response contracts end-to-end | Contract routing tests exercise contract selection/behavior. | No full end-to-end production contract matrix. |

## Advanced personalized traversal specification: item-by-item

| Requested capability | Finding |
|---|---|
| Optional glass-box Query Inspector showing intent, anchor/scores, graph path, pages, OPAC, context/tokens | **Missing/incomplete.** No complete collapsible inspector covering the specified pipeline was found. Do not expose sensitive provider payloads. |
| Student sees simple answer → mini graph → relevant books/pages by default | **Partial.** The chat, graph, and book/source surfaces exist; complete layout/accessibility behavior is not fully audited. |
| Optional mathematical / code / conceptual learning preference | **Missing/incomplete.** No complete session preference control and differentiated trajectory was found. |
| Preference affects question selection and edge weights while sharing one knowledge graph | **Missing/incomplete.** The requested preference-based edge weighting/path behavior is not demonstrated. |
| Graph-grounded misconception tags and Socratic correction | **Missing/incomplete.** Remediation UI/code exists, but evidence does not show misconception relation matching, confidence gating, and grounded follow-up as specified. |
| Mastery state with confidence, last verified, verification count | **Partial.** Adaptive code uses correct/incorrect history and mastered/review-gap/target node states. Durable per-node confidence, timestamps, and verification counts are not established. |
| Time-based mastery fading / Fading state | **Missing/incomplete.** No time-decay policy or persisted fading mastery behavior was found. |
| Confidence-aware choice of prerequisite questions | **Partial.** Diagnostics choose prerequisite concepts, but calibrated confidence separate from correctness is not demonstrated. |
| Start at three questions, early stop when calibrated, expand only as needed, cap at ten | **Not implemented to spec.** Current source constants implement a four-question checkpoint/max-four path and three consecutive correct ticks; no 3-to-10 adaptive budget is demonstrated. |
| Coverage-aware 1–6 hop traversal based on evidence, confidence, and goal | **Partial.** Bounded graph/path traversal exists, but the complete evidence-coverage/confidence/goal selection policy is not demonstrated. |
| Clean student graph without internal scores/debug data | **Partial.** Public node shaping and student graph UI exist; a full privacy/schema audit of every response was not completed. |
| Map learning gaps to physical holdings and distinguish unavailable from unknown | **Partial.** Catalog/holdings query code and graph gaps exist. End-to-end gap-to-specific-copy availability and unknown-inventory semantics are not established. |
| OPAC lookup from the learning gap | **Partial.** Catalog routes and holdings data exist; no production OPAC link/copy lookup was tested. |
| Faculty/librarian aggregate cohort diagnostics with minimum group-size privacy | **Missing/incomplete.** Librarian demand/acquisition endpoints exist, but a privacy-controlled faculty cohort diagnostic dashboard is not established. |
| Authorized, opt-in, redacted developer debug mode | **Missing/incomplete.** No complete role-gated inspector/debug UI meeting this contract was found. |
| Recalculate path when answers/preferences change | **Partial.** Adaptive-step builds a path/graph from the current answer history. Preference-triggered recalculation and full persisted session behavior are not established. |
| “Why am I seeing this?” explanation based on selection evidence | **Partial.** Graph/path/source evidence exists, but a dedicated learner-facing reason sourced from the actual selection decision is not established. |
| Lightweight consented session memory, reset/expiry, user isolation | **Partial / not fully verified.** Session-scope tests exist, but the complete consent, preference/mastery persistence, reset, expiry, and isolation acceptance set is not established. |
| Librarian intelligence: coverage/gaps, proposals, provenance, approval before publication | **Partial.** Acquisition/demand APIs and ingestion/source lifecycle modules exist locally. Full approval-to-publication production workflow is not verified. |
| UI not overloaded; optional diagnostics and accessible controls | **Partial.** Smoke checks cover key controls; full accessibility and usability acceptance is outstanding. |
| Full personalized traversal algorithm with diagnostics, evidence, gap-to-library, explainability | **Partial.** Several primitives exist; the integrated end-to-end feature is not demonstrated locally or live to the full spec. |

## Production engineering and restoration specification: item-by-item

| Area | Finding |
|---|---|
| Repository audit and existing-function preservation | **Partial.** Module map and file-size audit exist. Duplicate UI trees and compatibility modules remain; dead-code and caller mapping are not complete. Visual assets are present, but complete visual regression/restoration is not verified. |
| Professional module architecture | **Partial.** `archipelago/`, `host_inference/`, `frontend/`, `infrastructure/`, tests, docs and scripts contain organized modules. `backend/` currently has namespace placeholders, and there are duplicated UI implementations. |
| Source files at or below 300–400 lines | **Not complete.** The existing audit counted 56 code-source paths above 400 lines. `docs/reports/PRODUCTION_MODULE_ROADMAP_2026-10-04.md` lists all measured paths and line counts. |
| Deterministic query → intent → graph → retrieval → page → filter → synthesis → response flow | **Partial.** The main components and local pipeline tests exist; full contract-by-contract production verification is absent. |
| Six named response contracts | **Partial.** Contract types and tests exist. All six have not been exercised as production end-to-end workflows. |
| Relevant minimal model context; no raw private institutional data | **Partial.** Filtering/context assembly code exists; production model payload was not inspected. |
| Page-level citations with actual document/page/passage provenance | **Partial.** Citation builders/fallback and tests exist. Production-generated citations and page opens were not verified. |
| Pearson deep links and entitlement-safe behavior | **Partial.** Pearson linking and UI check exist locally; 40 Pearson books appear in readiness. Live click-through and entitlement behavior were not tested. |
| Hugging Face dataset/document links | **Partial.** HF resolver/storage/sync code exists, and local tests cover selected resolver behavior. Live dataset sync/link validity was not checked. |
| Backend ingested graph and bounded graph API | **Present; partial acceptance.** Graph data/API exist, local integrity tests pass, and live graph subgraph responds. Full graph coverage/freshness is not measured here. |
| Three distinct graph experiences (backend, chat mini graph, personalized graph) | **Partial.** Corresponding code/UI surfaces exist. Shared-ID/visual consistency and all three live behaviors are not fully verified. |
| Book stack restoration | **Present locally, visual acceptance outstanding.** Source and assets remain. No production visual review performed. |
| Normal-answer versus personalized-learning choice | **Partial.** UI choice/adaptive modules exist; smoke checks passed. End-to-end live choice and resulting workflows were not run. |
| Caching, deduplication, cache versioning/invalidation | **Partial.** Cache/dedup modules and tests exist. Live cache counters were zero; production invalidation/version changes were not verified. |
| Domain detection / routing away from graph for catalog and access questions | **Partial.** Routing and catalog/auth responses exist locally with tests. Production intent dispatch was not tested. |
| Librarian ingestion: academic document upload, parse/OCR, chunk, extraction, graph projection, searchable publication | **Not production available in observed snapshot.** Source code/routes exist, but readiness says `ingestion=false`; upload and publication were not tested. |
| OCR, PDF/text/ODS validation and provenance | **Partial.** Parsers/OCR/ODS modules and fixture tests exist; the full file-type/size/schema/provenance matrix is not confirmed. |
| Extraction model evaluated before automated ingestion | **Known blocker.** The existing readiness evaluation reports alias-aware F1 `0.125` against a required `≥0.35`; only 1 of 8 real passage probes predicted the central concept. Keep unattended SLM ingestion disabled until it passes. |
| Pearson content extraction | **Incomplete / not live-verified.** Related ingestion code may exist, but no fully authorized extraction-to-index acceptance run was evidenced. |
| Automated graph population, idempotency, staging, review, atomic publish, rollback | **Partial.** Ingestion/source lifecycle components and tests exist; full staging→approval→publish→rollback flow has not been verified, and hosted readiness disables ingestion. |
| Source lifecycle: new/changed/withdrawn source reconciliation | **Partial.** Local source lifecycle module/tests exist. Full connector synchronization and production tombstoning behavior are not established. |
| Apify / web fetchers with robots, terms, spend caps, approvals | **Partial.** An Apify connector and fetch-policy code exist. Production credentials, policies, spend limits, and a compliant live fetch run are not verified. |
| Hugging Face dataset sync and production corpus freshness | **Partial.** Repository/sync code exists. Live sync and freshness were not tested. Hosted readiness reports a full corpus, which does not prove current synchronization. |
| Production inference provider integration (NVIDIA/XKIRO) | **Not live-verified.** Provider code/config exists; no production chat invocation was made. |
| Auth boundaries for every mutating route | **Partial / security finding.** Local auth-boundary tests cover selected routes. Hosted general auth reports `required=false`; anonymous ingest capabilities returned 403. Do not infer that all writes are protected from that one 403. |
| Rate limits and 429 / Retry-After behavior | **Partial.** Rate-limit code and tests exist. No live limit behavior was exercised. |
| Structured, redacted logs; request IDs; provider/routing/latency/ingestion metrics | **Partial.** Telemetry/metrics code exists. Only cache metrics endpoint reachability was checked; privacy and completeness of live logs/metrics were not audited. |
| Secret hygiene | **Local cleanup done for identified files; provider rotation remains.** Credential values were removed from `.antideploy.json`; private credential PDF moved under ignored `data/private/`. Existing shared/committed credentials should be rotated by the provider. This audit does not prove the whole Git history is clean. |
| Portable Docker, mounted data, backup/restore, offline library-computer mode | **Incomplete / not verified.** Infrastructure/deployment files and portability tests exist. No clean-host, backup restore, or offline acceptance run was performed. |
| CI: lint, typing, architecture/file-size checks, secret/dependency scans, test suites | **Partial.** Tests and touched-file Ruff checks passed in the preceding implementation work. Repo-wide type/security/dependency scans and size-limit gate are not complete; 56 files exceed 400 lines. |
| Production E2E test matrix (greeting, concept, prerequisite, adaptive early stop/expansion, citations, OPAC, auth, ingestion, rollback) | **Not complete.** No production chat POST, answer flow, upload, approval, rollback, or citation click-through was performed. |

## Local verification evidence

The current local source had the following verification recorded in the preceding implementation work on 2026-10-04:

- Full automated suite: **1,449 passed, 7 skipped**, with 8 warnings.
- Chat UI smoke check: **11 checks passed**, covering chat input/send structure, welcome state, graph controls/render, adaptive flow, topology, remediation, auto-prompt, and Pearson link.
- Ruff lint and format checks passed for the modified Python files in that work. Repo-wide lint/type/security gates were not run.
- Covered test areas include runtime API, host inference/deployment, diagnostic MCQ/adaptive progression, answer cache/dedup/metrics, rate limiting, auth boundaries, source links, UI deep links, graph integrity, query pipeline, citation correctness, source lifecycle, ingestion, retrieval, and frontend contracts.

These results describe the local checkout. The hosted release SHA differs from local `HEAD`; they should not be presented as tests of production.

## API route inventory in the repository

This is a source-code inventory, not a claim that each route is live at the public URL. Live checks are listed in the deployed snapshot above. No POST endpoint below was exercised against production in this audit.

### `host_inference/hostapp` runtime

| Methods | Route(s) | Purpose / status |
|---|---|---|
| GET | `/`, `/landing`, `/chat`, `/graph`, `/library`, `/login` | Page routes; selected pages returned HTTP 200 live. |
| GET | `/health`, `/ready`, `/api/health`, `/api/readiness`, `/api/metrics/cache` | Health/readiness/metrics; readiness and cache metrics were live checked. |
| GET | `/api/auth/config`, `/api/auth/me` | Auth configuration/current-user read. Auth config live checked; no session performed. |
| POST, DELETE | `/api/auth/session` | Session mutation; source route only, not live-tested. |
| POST | `/api/chat` | Chat/inference stream; source route only, deliberately not live-tested. |
| GET | `/api/chat/diagnostic-mcqs` | Diagnostic payload; source route exists; tested query returned HTTP 400 live. |
| POST | `/api/chat/adaptive-step`, `/api/chat/telemetry` | Adaptive progression / telemetry; source only, not live-tested. |
| GET, POST, OPTIONS | `/api/roadmap`, `/api/quiz` | Roadmap and quiz; GET topic requests returned HTTP 200 live. POST not tested. |
| GET | `/api/library/data`, `/api/catalog/all` | Library and catalog reads; both returned data live. |
| POST | `/api/library/import` | Library import mutation; not live-tested. |
| GET | `/api/graph/subgraph` | Graph subgraph; one query returned 5 nodes and 9 edges live. |
| GET, POST | `/api/page-view` | Page view/recording; not live-tested. |
| GET | `/read`, `/read/<path>`, `/api/reader/info/<resource_id>`, `/papers/<path>`, `/pdfs/<path>`, `/open/<book_id>`, `/open/book/<book_id>` | Reader/document routes; source only, not live-tested. |
| GET | `/api/ingest/capabilities`, `/api/ingest`, `/api/ingest/<job_id>` | Ingest capability/status/list; anonymous capabilities request returned 403 live. |
| POST | `/api/ingest`, `/api/ingest/index` | Ingest/index mutations; not live-tested; deployed readiness says ingestion false. |
| GET | `/assets/<path>`, `/ui/assets/<path>`, `/<path>` | Static assets/fallback; only pages noted above were checked. |

### Separate `archipelago/api` service in the repository

| Methods | Route(s) | Purpose / status |
|---|---|---|
| GET | `/api/auth/config`, `/api/auth/me` | Auth configuration and current user. |
| GET, POST, OPTIONS | `/api/users`, `/api/users/<user_id>` (PUT, DELETE, OPTIONS for item route) | User management. |
| POST | `/api/chat` | Chat API. |
| GET | `/api/catalog/search`, `/api/eresources`, `/api/documents` | Catalog, e-resource, document reads. |
| GET | `/api/topics/suggest` | Topic suggestions. |
| POST | `/api/roadmap/quiz` | Roadmap quiz. |
| GET, POST | `/api/chat/diagnostic-mcqs` | Diagnostic MCQs. |
| POST | `/api/chat/verify-mcq`, `/api/chat/adaptive-step`, `/api/chat/telemetry` | MCQ verification, adaptive step, telemetry. |
| GET | `/api/librarian/demand-digest`, `/api/librarian/acquisition-plan` | Librarian acquisition/demand data. |
| GET | `/api/readiness` | Service readiness. |
| POST | `/api/upload` | Upload endpoint. |

This second service is present in the repository; this audit did not establish that Antideploy runs it.

## Overall state

### Confirmed in production

- Public landing, chat, library, graph, and login pages respond.
- Readiness responds with an inference-only runtime, a full corpus, 520 concepts, 40 Pearson books, and ingestion disabled.
- Library/catalog reads return a 91-entry payload; a graph subgraph and roadmap/quiz GETs return structured responses.
- Cache metrics and auth configuration endpoints respond; general authentication is configured but not required.
- Anonymous ingest capability is denied with HTTP 403.

### Locally implemented and tested, but not proven deployed

- Core graph/retrieval and synthesis pipeline components, response routing/contracts, source/citation resolution, catalog/library APIs, adaptive diagnostic primitives, cache/deduplication, rate limiting, auth-boundary cases, ingestion/OCR/source lifecycle components, and UI behavior covered by the reported test suites.

### Incomplete or not established as working

- The requested glass-box inspector; preference-driven learning trajectories; misconception-linked Socratic handling; fading mastery; calibrated confidence and an adaptive 3-to-10 question budget; coverage-aware personalized traversal; cohort-safe faculty diagnostics; fully explained path selection; and complete consented mastery/session persistence.
- Full live answer generation/citation click-through, physical holdings/OPAC accuracy, user login, upload-to-approval-to-publication/rollback, provider failover, live cache behavior, and security/rate-limit behavior.
- The extraction model readiness gate, unattended ingestion, source synchronization, and the 300–400 line file limit. The readiness model evaluation is below its stated quality threshold and 56 source files exceed 400 lines.
- Whether current uncommitted local work is part of the hosted release. The release identifier differs.

## Source references

- `docs/reports/PRODUCTION_MODULE_ROADMAP_2026-10-04.md` — workstreams, target module map, file-size audit, release blockers.
- `host_inference/hostapp/routes/` and `host_inference/engine/` — Antideploy-oriented runtime routes and inference/diagnostic implementation.
- `archipelago/api/` — separate API service and its routes.
- `tests/` — local automated evidence; test success applies only to the tested local checkout.

## Deep module-by-module inventory

This section maps the major code areas and concrete responsibilities. “Local code” means present in this checkout. The same file may contain more detail than the user-facing feature that currently exposes it; a module existing does not prove its path is active in production.

### 1. Web applications and UI trees

| UI area / modules | What the code provides | Status / evidence |
|---|---|---|
| `host_inference/ui/landing.html` and assets | Landing/brand page, campus sign-in prompt, navigation to chat/library, video/poster imagery. | Local page exists; live `/` returned 200. Visual/accessibility behavior not inspected in a browser. |
| `host_inference/ui/index.html` | Main chat layout, conversation history, chat composer, source/book area, mini-graph/pipeline areas, graph-experience choice dialog, settings and responsive panels. Uses Tailwind CDN, Marked, Prism, Cytoscape, `graphify.js`, `chromatic_waves.js`, `auth_bridge.js`. | Local page exists and UI smoke structure passed. Live `/chat` returned 200; no production browser session or chat request was made. |
| Chat JS `00-state.js`, `00-current-origin.js`, `index.js`, `expose.js` | Shared state, API origin, module bootstrap and browser-facing bindings. | Present in all three mirrored UI trees; local UI smoke passed. |
| Chat JS `01`–`07` | Welcome transition; keyword highlighting; library inventory section; new-chat reset; book/source cards; unavailable/open-book behavior; page viewer modal. | Present; selected link and UI contract tests pass. Reader/book links not clicked on production. |
| Chat JS `08-send-message.js`, `stream-support.js` | Submit chat query, read stream chunks/metadata, render answer and attached evidence. | Present; smoke/test coverage exists. Production POST/streaming not exercised. |
| Chat JS `09-patterns.js`, `10-populate-pipeline.js`, `11-populate-topology.js` | Render response patterns, pipeline step display and graph topology from response metadata. | Present; smoke covered topology/pipeline structure. No complete production response metadata was obtained. |
| Chat JS `12-choose-graph-experience.js`, `13-render-horizontal-graph-card.js` | Let user select a graph experience and render the normal concept graph card. | Present; UI smoke checked graph choice/render. No live browser interaction. |
| Chat JS `14-render-adaptive-mcqcard.js`, `15-submit-adaptive-answer.js` | Render diagnostic multiple-choice card and submit answer to adaptive endpoint. | Present; local adaptive tests/smoke cover pieces. Hosted diagnostic GET returned 400 for tested query, and answer POST was not sent. |
| Chat JS `16-render-personalized-graph-ca.js`, `17-draw-personalized-svg.js`, `18--init-graph-ripple.js`, `19-draw-horizontal-svg.js` | Render personalized path card/SVG and graph animation. | Present; structure smoke check passed. Durable mastery and full personalization requirements remain incomplete. |
| Chat JS `20--compact-history.js`, `21-generate-roadmap.js` | Compact chat history and request/display roadmap UI. | Present; roadmap GET returned a roadmap-shaped response live. Browser integration not tested against production. |
| `host_inference/ui/graph.html`, `graphify.js` | Standalone interactive graph page and Cytoscape-based rendering/helpers. | Page returned 200; graph API returned sample nodes/edges. No live graph interaction was performed. |
| `host_inference/ui/library.html`, `library_showcase_3d.js` | Library discovery/showcase, 3D book shelf, book metadata/TOC and open-reader action. Loads Three.js and OrbitControls. | Source/assets exist and API returns 91 entries; 3D rendering, book navigation and open action not browser-verified. |
| `host_inference/ui/reader.html` | Embedded reader/page-view experience for supported documents. | Source exists; no hosted reader/page endpoint or actual book opened during audit. |
| `host_inference/ui/login.html`, `auth_bridge.js` | Login/session client, session identity/config calls, role handling. | Source exists; login page 200 and auth config reachable. No sign-in/session test; public auth is optional. |
| `performance.html`, `safety.html`, styles, assets, videos | Performance/safety-related pages and UI CSS/branding assets (hero, librarian videos, controls, animations). | Kept in source. No live asset-by-asset or visual-regression test in this audit. |
| `chat_ui/`, `ui/chat/`, `host_inference/ui/` | Three copies of the same chat UI family. SHA-256 prefixes matched for sampled `index`, `landing`, `library`, `graph`, `login`, `reader`, key chat JS and book-showcase files. | Sampled files are identical across these trees today, but they are duplicated source trees that can drift. Antideploy app factory serves `host_inference/ui/`. |
| `frontend/ui/graph/` | Separate D3 graph/books experience, graph modules, neon visualization; `frontend/book-stack/` and TSX sources include another book-stack implementation. | Separate frontend/prototype tree. No route from hosted Flask app was found serving it; not verified deployed. |
| `frontend/src/api/`, `frontend/chat_server.py`, `frontend/graph_server.py` | Frontend API mock/type definitions and standalone dev servers. | Present as local development/support code; not proof of deployed React/Vite frontend. |

### 2. Hosted application, runtime wiring, and security

| Modules | Responsibilities | Status / observed behavior |
|---|---|---|
| `host_inference/hostapp/factory.py`, `context.py`, `routes/__init__.py` | Build Flask application, initialize runtime context (engine/auth/rate limiter/inventory/cache/dedup), provision graph corpus, register route groups. | Antideploy-oriented local runtime. Production page/readiness responses indicate a hosted inference runtime, but release SHA differs from local `HEAD`. |
| `host_inference/hostapp/config.py` | Read env, set UI paths, 5 MiB request cap, public API allowlist, rate limit settings, CORS origins, roles, cookie settings. | Source policy is readable; do not assume deployment env matches local config. Live auth config is optional (`required=false`). |
| `host_inference/hostapp/middleware.py`, `security.py` | Request auth guard, API/chat rate limits, CORS, CSP/security headers, JSON errors. Rate limit code emits 429 and `Retry-After`. | Locally implemented; rate-limit/auth tests passed for covered cases. No production 429 or header/security audit beyond mode/release headers. |
| `host_inference/hostapp/log_redaction.py` | Redact sensitive values from application logs. | Local redaction code and tests exist; production log redaction was not inspected. |
| `host_inference/hostapp/corpus_bootstrap.py` | Provision corpus/graph data from hosted storage or fixture fallback during startup. | Readiness reports 520 concepts/full corpus. Does not establish source freshness or which fallback path populated it. |
| `host_inference/hostapp/inventory_store.py` | Local inventory store used by hosted app. | Present; production copy-level accuracy not audited. |
| `host_inference/wsgi.py` and root `start.sh` / Docker files | Server entrypoint and container build/run setup. | Source/config exists. Clean build, container start, rollback, and restore were not run during this report. |

### 3. Hosted API and separate API service

#### Antideploy-oriented `host_inference/hostapp/routes/`

| Route module | Capabilities | Evidence/status |
|---|---|---|
| `pages.py` | Landing/chat/graph/library/login pages; health/readiness/cache metrics. | Selected page, readiness, and metrics GETs responded live. |
| `chat.py` | POST chat streaming with query validation; cache lookup; in-flight deduplication; metadata framing; GET diagnostics; POST adaptive-step and telemetry; roadmap/quiz GET/POST. | Source implements these routes. Read-only roadmap/quiz worked live; diagnostic GET returned 400 for the supplied query; chat/adaptive POST not tested. |
| `graph.py` | GET bounded subgraph. | One production query returned 5 nodes and 9 edges. Other graph parameters and browser rendering not tested. |
| `library.py` | GET library data/catalog records; POST library import. | Both GETs responded with 91 records/shelf entries. Import POST not tested. |
| `reader.py` | Page view, reader info, `/read`, papers/PDFs, book-open routes. | Source only in this audit; no actual hosted reader was checked. |
| `auth.py` | Auth config, current user, create/delete session. | Config GET live checked; no identity/session operation. |
| `ingest.py` | Capability discovery, document upload/index, job status/list. | Capability request returned anonymous 403. Readiness says ingestion disabled. No write route tested. |
| `static.py` | UI asset serving and path fallback. | Selected HTML pages returned 200; no complete asset integrity check. |

#### Separate `archipelago/api/`

| Module | Capabilities | Evidence/status |
|---|---|---|
| `app.py`, `engine_state.py`, `middleware.py` | Build/service bind address, load Kùzu and concepts, initialize API engine, CORS/session middleware. | Separate service implementation; not established as mounted on the Antideploy domain. |
| `routes_chat.py`, `contract_handlers.py` | POST `/api/chat`; classify/dispatch contracts and direct intents; MCQ contract handler and response payload helpers. | Local API/test evidence only; separate from hosted route namespace and no production POST. |
| `routes_discovery.py` | Topic suggest, roadmap quiz, diagnostic MCQ GET/POST, verify MCQ, adaptive step, telemetry. | Local code; not live-identified as this deployment. |
| `routes_library.py` | Catalog search, e-resources, documents. | Local code; not live-identified as this deployment. |
| `routes_auth.py` | Auth config/current user and user CRUD management. | Local code; selected auth-boundary tests passed; not production-verified. |
| `routes_acquisition.py` | Librarian demand digest and acquisition plan. | Local API routes; cohort privacy/production workflow not verified. |
| `routes_docs.py` | Readiness and document upload. | Local route; separate runtime; not production-verified. |

### 4. Chat request and inference stack

| Modules | What they do | Status |
|---|---|---|
| `host_inference/engine/answer.py` (`Engine`) | Hosted engine facade: graph-backed responses, chat stream, diagnostic/adaptive calls. | Core hosted code exists; host deployment tests/local suite cover contracts. No live answer generation requested in this audit. |
| `host_inference/engine/contract.py`, `patterns.py` | Select response contract and graph decision/pattern based on query/intent. | Local implementation; no six-contract live matrix. |
| `host_inference/engine/graph.py` | `LibraryGraph` abstraction for concepts, labels, prerequisites, ranking, citations and graph access. | Local tests pass for covered behavior; hosted graph endpoint demonstrates one graph read. |
| `host_inference/engine/compose.py`, `render.py`, `text.py` | Compose answer types (concept, relation, matrix, disconnected, shelf, auth/admin), graph lineage/neighborhood, normalize/embed text. | Present; local host query tests cover portions. No production chat response inspection. |
| `host_inference/engine/llm.py` | Provider settings, completion/stream calls and optional polishing. | Provider code present; production provider success/failover not established. |
| `archipelago/inference/pipeline.py`, `synthesis_pipeline.py` | Main inference pipeline: guardrails, vector/anchor retrieval, graph traversal, prompt payload, model synthesis. | Local tests include full/query pipelines. Do not conflate this service with the host engine; Antideploy runtime has its own `host_inference/engine`. |
| `archipelago/core/router.py`, `contract.py`, `context.py`, `manifest.py` | Typed query router/intents, contract decision, request context and run manifest. | Local source/test coverage; production trace not observed. |
| `archipelago/inference/intent_gate.py`, `intent_gate/`, `query_classifier.py`, `routing.py`, `routing/` | Intent scoring/classification and staged route decisions for small talk, library, graph, quiz and scope/out-of-domain cases. | Broad routing implementation and test cases exist; live intent dispatch untested. |
| `archipelago/inference/ranking.py`, `ranking/`, `ranking_seeds.py`, `aliases.py`, `embeddings.py` | Query normalization, concept candidates/anchors, alias expansion, seed ranking and embedding support. | Local implementation; quality is corpus/model dependent. No hosted anchor score or ranking trace available. |
| `archipelago/core/retrieval.py`, `inference/neighborhood.py`, `subgraph.py`, `graph/traversal.py` | Hybrid retrieval, prerequisite/neighborhood lookup, bounded subgraphs and graph traversal. | Local bounded-subgraph and graph tests; hosted subgraph route returned one result. Full vector+graph path not measured live. |
| `inference/evidence_filter.py`, `grounded_answers.py`, `grounded_fallback.py`, `cleanser.py`, `sanitizer.py` | Select source evidence, format grounded responses/fallbacks, remove model artifacts/unsafe output. | Local tests cover grounded output and cleansing; production output unobserved. |
| `inference/synthesis/`, `synthesis.py`, `synthesis_library.py`, `synthesis_cleaner.py` | Compose grounded prose, graph notes/path explanations, library answers/resources, stream finalization and style cleanup. | Local implementation and suite coverage. Not all pathways have isolated acceptance tests or production samples. |
| `inference/llm_gateway/` | Provider config and NVIDIA/XKIRO/Gemini/OpenAI-compatible chat, stream, tools, sanitization/fallback. | Local provider-chain tests exist; deployed provider health/latency/failover was not tested. |
| `inference/stream_budget.py`, `core/prompt_assembly.py`, `core/chunk.py` | Estimate/trim context, assemble external model payload and serialize retrieved chunks. | Local code/tests; no production prompt/token trace. |
| `inference/cache_service.py`, `cache_metrics.py`, `query_cache.py`, `request_dedup.py` | Cache answers/query results, deduplicate concurrent work, record hit/miss/dedup/token metrics. | Local tests passed. Live metrics endpoint responded but counters were zero; no production cache-hit request was generated. |
| `inference/rate_limit.py`, middleware modules | Per-client sliding-window limiters and endpoint-level rate policies. | Local tests passed; live throttling not exercised. |
| `inference/context_tracker.py`, `state.py`, `bootstrap.py`, `scope_gate.py` | Request/session context, lazy DB state, verified-session bootstrap and query scope checks. | Local tests include isolation/reset/scope cases. Full learner mastery persistence and production session behavior remain unverified. |
| `inference/orchestration/subagents.py`, `orchestration/okf_facets.py` | Internal agents/facets for similarity, pedagogical traversal, critic synthesis, recovery, catalog, auth, diagnostic and context. | Code is present in the separate inference package. This is not the same as spawning coding agents; runtime activation path is not proven for every class. |

### 5. Graph, concept model, evidence, and citations

| Modules | What they do | Status |
|---|---|---|
| `archipelago/graph/engine.py` | Kùzu-backed graph access and lifecycle. | Local graph DB/integrity tests; production reports 520 concepts. Database freshness/edge-quality metrics not in the live snapshot. |
| `archipelago/graph/traversal.py`, `subgraph/`, `integrity.py` | Traverse relationships, generate bounded subgraphs, check structural integrity. | Local tests pass in covered cases; a small live subgraph request works. |
| `archipelago/graph/graph_fusion.py` | Merge graph data and validate cycles/DAG constraints. | Used by ingestion components; local graph/ingestion tests. Full production merge not run. |
| `okf/` extraction and canonicalization | Extract OKF concepts/relations, normalize names/aliases, deduplicate, filter weak/out-of-domain concepts, orient prerequisites and build validated edges. | Large tested subsystem. Extraction evaluation is below its production gate (`0.125` alias-aware F1 vs `0.35` threshold), so quality is not production-ready for unattended ingest. |
| `okf/graph/evidence.py`, `okf/graph/ingest.py`, `graph_db.py` | Store document/chunk/concept/edge provenance and ingest graph records to Kùzu. | Local tests cover evidence/integrity; full deployed provenance audit absent. |
| `okf/exports.py`, `exports_extra.py`, `eval/` | Export graph JSON/visual/index artifacts, compare against gold graphs and run structural/quality metrics. | Present and tested as library functions; no current CI/export artifact audit completed. |
| `inference/citations/`, `citation_lineage.py`, `citation_output.py`, `citation_renderer.py`, `aliases.py` | Resolve evidence to citation/page URL payloads, rendered links, lineage metadata and clean citation output. | Citation/source tests pass locally; production-generated citations and page access not checked. |
| `host_inference/engine/links.py`, `docmap.py`, `withdrawal.py` | Hosted source link creation, HF path mapping, and exclusion/notices for withdrawn sources. | Local tests/source lifecycle coverage exists; current hosted corpus withdrawal state not inspected. |
| `resolver/pearson.py`, `huggingface.py`, `doi.py`, `openlibrary.py`, `google_books.py`, `resolver.py` | Resolve known resources and external/document links across providers. | Selected local resolver/link tests pass. External availability and user entitlement are not live-verified. |
| `resolver/source_lifecycle.py`, `ingest_proposals.py`, `sync.py`, `validator.py`, caches/filters | Track source health/withdrawals, propose discovered sources, validate links and sync catalogs. | Local modules/tests exist; complete scheduled sync/reconciliation workflow is not shown as active in production. |

### 6. Library catalog, inventory, and resource access

| Modules | What they do | Status |
|---|---|---|
| `host_inference/engine/catalogue.py`, `inventory.py`, `inventory_card.py` | Load/match title catalog records, score likely matches, format shelf/copy cards and attach inventory. | Local matching tests exist; production catalog exposes 91 records, but exact physical inventory accuracy remains unchecked. |
| `host_inference/engine/telemetry.py` | Log query demand/unmet titles and render a librarian demand digest. | Present in host code. Whether production persists/aggregates this data was not tested. |
| `archipelago/inference/library_catalog/` | Parse ODS/Koha holdings, subject/journal reports, build prominent e-book/Pearson/paper/HF/Koha payload. | Local implementation and tests exist; production payload is exposed but exact source records/count consistency were not compared. |
| `inference/library_queries/`, `catalog_ods.py`, `catalog_ops/`, `library_catalog_api.py` | Match topic/title/chapter queries, answer library schedule/material/holdings questions, parse ODS operational reports and format catalog replies. | Local tests cover selected catalog questions; live chat routing was not called. |
| `inference/corpus_inventory.py`, `inventory_ssot.py`, `reply_inventory.py`, `library_resource_access.py` | Normalize holdings/inventory sources, select catalog-backed resources, attach access guidance. | Present and locally exercised in selected test cases; record-of-truth and live inventory reconciliation not audited. |
| `inference/library_credentials/`, `eresource_credentials.py`, `library_schedules.py` | Detect access/hour questions and provide credential-safe portal/access/schedule responses. | Source exists; hosted general auth is optional. Shared credentials were removed from visible access-card content; provider-side rotation remains necessary for any exposed historical value. |
| `host_inference/engine/ingestion_view.py` | Read recent ingest-job metadata and project status into a librarian view/reply. | Source exists; host readiness currently says ingestion disabled. |

### 7. Ingestion, OCR, and source publication

| Stage / modules | What the code provides | Status |
|---|---|---|
| File reading/chunking: `archipelago/ingestion/pdf_io.py`, `pdf_chunk.py`, `pdf_formats.py`, `pdf_utils.py` | PDF, text, Markdown and DOCX extraction/chunking; page labels, hashes, metadata and section/chunk annotation. | Local fixture/ingestion tests exist; file support is not uniform (legacy `.doc` explicitly rejected, unsupported extensions are best-effort text in one function). Hosted ingestion is disabled. |
| Image/OCR: `ingestion/page_image/` | OCR image text, parse bibliographic fields/TOC/pages, search/match candidates and prefill librarian form. | Local code and ingestion/UI support exist; no production OCR request was run. |
| Spreadsheet/ODS: `ingestion/spreadsheet/`, `inference/ods_parser/`, `ods_ingestion.py`, `ods_parser.py` | Validate/normalize spreadsheet schemas, create merge plans, import holdings, subject/journal/keyword reports. | Local ODS/ingestion tests exist; production import/sync not tested. |
| Source discovery: `acquisition_discovery.py`, `apify_source.py`, `fetch_policy.py`, `mention/` | Find candidate resources, enforce allowlists/robots/credentials/fetch policy, gate paid Apify runs, identify books by ISBN/title. | Local policy/connector tests exist. Live Apify configuration, spend cap and authorized fetch were not checked. |
| OKF extraction: `okf/extraction/`, `relations/`, `cleanup_parts/`, `pipeline.py` | Local-model extraction, canonicalization, relation validation, domain/grounding filters, DAG cleanup and evidence graph assembly. | Tests exist, but measured alias-aware F1 is 0.125 vs 0.35 gate; automatic unattended model ingestion should remain off. |
| Staged ingestion: `okf/pipeline_staged.py` | Parse → extract → canonicalize → build temporary Kùzu graph → structural validation; checks cancellation/progress. | Local integration/unit tests cover parts. Not equivalent to production approval/publish/rollback. |
| Background librarian job: `ingestion/librarian_worker/` | Persist jobs, process uploads, transfer files to HF, chunk/extract, merge into staging, check DAG and publish staging. | Source and tests exist; 15-section/page caps and SLM extraction path are code constraints. Hosted readiness says ingestion false; no end-to-end production job. |
| Librarian intake: `mention/`, page image, spreadsheet, `host_inference/hostapp/routes/ingest.py`, separate misc routes | Upload capabilities/status and intake endpoints for documents/images/text/spreadsheets. | Local route groups exist. Anonymous host ingest capability got 403; general upload/apply/publish routes not probed live. |
| HF storage: `archipelago/storage/hf_remote.py`, `resolver/huggingface.py`, sync scripts | Transfer/list/resolve corpus and document paths using Hugging Face dataset/repository. | Local storage tests pass; hosted readiness says full corpus but live repository identity/content freshness were not checked. |
| Publication and recovery: `librarian_worker/part03_copy_db.py`, `part04_publish_staging.py`, source deletion/lifecycle utilities | Clone/stage database, review counts, swap/publish staging, notify inference reload and remove/tombstone records. | Local tests cover lifecycle/worker paths; production approval, atomicity under failure and rollback are unverified. |

### 8. Storage, providers, deployment, and operations

| Modules / files | Purpose | Status |
|---|---|---|
| `archipelago/storage/hf_remote.py`, `supabase_sync_client.py`, host cache setup | Remote corpus and cache persistence. | Live readiness identifies cache as Supabase and corpus as full; consistency/recovery not tested. |
| `archipelago/supabase_auth/`, `archipelago/auth.py`, host `security.py` | Supabase session validation, user management and host role checks. | Local auth tests passed for cases; live policy says `required=false`, no login tested. |
| `middleware/health.py`, rate limiter, shutdown, logging/redaction | Health probes, request throttles, graceful shutdown and safe logging. | Code/tests exist; live health routes respond, but operational behavior/log privacy not tested. |
| `Dockerfile`, `Dockerfile.hf`, `docker-compose.yml`, `deploy/library-computer/docker-compose.yml`, `host_inference/Dockerfile` | Container and local/library-computer deployment definitions. | Config files exist; reproducibility, backup/restore, offline operation and production rollback not verified. |
| `infrastructure/`, `.antideploy.json`, host Antideploy config | Runtime/deploy configuration. | Antideploy public route is live; this checkout's GitHub default branch and observed release differ from local branch/HEAD. No deploy occurred in this inventory turn. |
| `scripts/ops/`, `scripts/run_*`, `scripts/sync_*`, `scripts/validate_graph.py` | Local corpus build/ingest, graph rebuild/validation, tunnel/worker/sync/seed/backup-like operations. | Many operational scripts exist but are not a unified release pipeline. No full clean-host execution was recorded. |
| `scripts/quality_gate*.py`, `scripts/refactor/*`, `pyproject.toml`, test suites | Quality gates, refactoring helpers, Ruff and tests. | Prior run: 1,449 passed/7 skipped, UI smoke 11 checks, touched-file Ruff passed. Repo-wide type/security/dependency/file-size gates remain incomplete. |
| `tests/e2e/`, `tests/performance/` | E2E, upload/live-model/deep-link/latency/Locust test definitions. | Test definitions exist; presence is not a pass. This report does not claim every E2E/live/performance test was run. |

### 9. Other repository roots and migration seams

| Root / package | Contents and status |
|---|---|
| `archipelago/apps/`, `dataset/`, `eval/`, `cli.py`, `config.py`, `auth.py` | App entry points, dataset generation, evaluation, CLI/config/auth helpers. These support the inference/graph/ingestion packages; not each is independently exposed by Antideploy. |
| `backend/` | README describes an operational API and says implementation is migrating to `ingestion_backend/` plus `okf/`. The README-named `ingestion_backend/` directory is absent in this checkout; `backend/` itself mostly contains `__init__.py` namespace placeholders. |
| `chat_server/` | Merged compatibility/proxy modules for repo root, index, reader, HF token, link resolution, chat/roadmap proxy and librarian upload. Distinct from `host_inference/server.py`; whether this legacy server is used is not established. |
| `inference-backend/`, `ingestion-frontend/`, `libraryAI/` | Additional README/prototype or compatibility surfaces. `libraryAI/` has a citation wrapper; no deployed route wiring was identified for these roots. |
| `frontend/` | Intended separated chat, graph, library, landing, quiz, citations, book-stack and shared UI, plus prototypes/dev servers. The Antideploy Flask factory serves `host_inference/ui/`, not this tree. |
| `infrastructure/` and `deploy/library-computer/` | Hugging Face, Supabase, inference, deployment, Apify and monitoring layout plus offline/local compose files. Configuration presence does not prove these environments were deployed or exercised. |
| `packages/contracts/openapi/` | Separate backend/inference OpenAPI YAML contracts. Local contract tests exist; compatibility between these schemas and both Flask services was not exhaustively checked. |
| `supabase/migrations/` | Role/auth and response/retrieval/graph cache migrations. No live migration state was queried. |
| `training/`, `training_data/`, `models/`, `data/`, `pdfs/`, `pilot_corpus/` | Training/extraction/model and document/corpus artifacts. Availability, licensing, git tracking and production freshness vary; this audit did not enumerate or validate corpus contents. |
| `jobs/`, `logs/`, `okf_graph.bak-*`, `*.bak*` | Job snapshots, logs and graph backups exist in the working tree. They are operational data/artifacts, not application modules; retention, privacy, backup restore and whether deployed storage uses them are unverified. |
| Root launchers and tools (`chat_server.py`, `okf_pipeline.py`, `pdf_ingestion.py`, `start.sh`, scripts) | Compatibility/operational launch and ingestion entry points. Multiple ways to start or ingest make the canonical production path ambiguous; only host `server.py` → `hostapp.create_app()` was identified as the Antideploy-oriented entry point. |

### 10. Module inventory summary by state

| State | Included modules/features |
|---|---|
| **Observed responding in production** | Landing/chat/library/graph/login page GETs; health/readiness/cache metrics; auth config; library/catalog GET; bounded graph GET; roadmap/quiz GET; anonymous ingest capability denied. |
| **Substantial local implementation and reported tests** | Chat UI stream/render; intent and response contracts; graph access/traversal/integrity; citation/source resolution; library/catalog parsing and matching; diagnostic/adaptive primitives; answer cache/dedup; auth/rate-limit cases; PDF/OCR/ODS/OKF ingestion primitives; source lifecycle/HF resolver. |
| **Present as separate/unconfirmed service or prototype** | `archipelago/api/`, `frontend/ui/graph/`, frontend dev servers, `libraryAI/`, helper/legacy scripts and extra inference orchestration. Their inclusion in the deployed Antideploy runtime is not established. |
| **Explicitly incomplete or blocked** | Inspector/debug console; modality-driven traversal; misconception relation remediation; mastery fading; calibrated adaptive 3–10-question budget; cohort-safe faculty diagnostics; full student-specific coverage-aware path/explanation; unattended ingestion; current extraction quality gate; full publish/rollback/live E2E; repo 400-line target. |
