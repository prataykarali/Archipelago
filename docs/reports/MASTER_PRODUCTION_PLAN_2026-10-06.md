# Archipelago institutional production master plan

Date: 2026-10-06. Scope: this Archipelago repository, the existing local library workstation, Cloudflare, Vercel, Supabase, Hugging Face, and the current AntDeploy deployment during migration. This is a living execution checklist. A checked item means the stated evidence exists; it does not imply the whole feature is production-ready.

## Decision rules and current truth

- Preserve the landing visuals, 3D assets, animations, video, existing feature paths, and six response contracts. Add IEM/UEM identity without altering the visual design.
- Keep raw licensed Pearson content and private student records on authorized local systems. Publish only rights-reviewed metadata, graph artifacts, and approved models. Never commit credentials or put service keys in browser code.
- Treat exact source links as verified behavior: a book-level link does not become an exact-page link by adding an untested fragment. If Pearson cannot deep-link to a page through a supported URL, show the book and an honest page instruction.
- Use the attached architecture image as a conceptual hybrid cloud/local model. The user's chosen public target is Cloudflare in front of Vercel, with Supabase for managed Auth/data/cache. AntDeploy remains a rollback origin only until the Vercel release passes the same gates. Railway is not a target.
- The documentation calls **5,151** the baseline graph *node count*. Local **:5151** is the inference service port; graph is **:5150**, chat **:5152**. Verify node count and integrity independently of port readiness.
- Maintain statuses as `not built`, `implemented but unverified`, `local verified`, `staging verified`, or `production verified`. Tests using mocks prove only the code path, not a live dependency.
- A shared initial student password is a bootstrap secret, supplied through a server secret store only. Enrollment numbers identify students; an immutable first-login flag requires each student to choose a unique password. Do not publish or repeat the bootstrap value.
- Every release must pass the repository's lint, format, strict typing, quality, architecture, unit, integration, security, graph, ingestion, live staging, and independent human-review gates. Production promotion requires backup and rollback readiness.

### Target data flow

`student/librarian → Cloudflare DNS/CDN/WAF/TLS → Vercel hosted UI and inference API → Supabase Auth and approved metadata/vector/cache tables → external LLM on cache miss`. The library workstation retains raw PDFs, local SLM extraction, and the Kùzu single-writer graph. It exports only rights-reviewed chunks, graph/index metadata, and versioned manifests after librarian approval. Every public document opening must respect its source rights and verified URL behavior. A Vercel preview must pass bundle, read-only filesystem, streaming, cold-start, and live-query checks before any Cloudflare traffic moves.

## Verified baseline and known blockers

- [x] Isolated release branch `codex/production-hardening` and draft PR #5 exist; the original dirty working tree was left intact.
- [x] Previous full unit run passed 1,520 tests with 7 skips. A fresh broad run after auth changes reached 988 passed, 10 failed, 6 errors, and 6 skipped because the isolated checkout lacked ignored institutional graph/catalog/model fixtures and included stale Pearson expectations. Copied graph/catalog fixtures enabled a focused 50-test pass; the full release suite remains open.
- [x] Local :5150/:5151/:5152 readiness endpoints returned HTTP 200 on 2026-10-06; this proves process readiness, not every end-to-end feature.
- [x] The public AntDeploy `/api/readiness` returned HTTP 200 with release `554c8df` on 2026-10-06; it is **older** than the draft PR.
- [x] Pearson browser test showed an invented `#book/<id>/page/35` URL opened the correct book but page 22; manual page navigation did not change its URL. Exact-page Pearson linking remains unproven.
- [x] Supabase project exists, Auth migrations are listed, and three public tables have RLS. Security advisor reports leaked-password protection disabled; the credential-import grant and audit tables currently have zero rows.
- [x] Read-only calls to live Supabase `profiles`, Auth Admin users, and private Storage returned HTTP 200 on 2026-10-06 using corrected server-only key headers; writes still need staging verification.
- [x] Vercel connection responded, but no Archipelago project was found. There is no verified Vercel inference URL.
- [x] A second read-only account check found seven Vercel projects, none named Archipelago; the connected Cloudflare account returned zero DNS zones. These are account inventory results, not proof that the institution has no zone under another account.
- [x] A fresh 2026-10-06 baseline and graph-count reconciliation is recorded in [`BASELINE_AND_PLATFORM_DECISION_2026-10-06.md`](BASELINE_AND_PLATFORM_DECISION_2026-10-06.md). The checked-in plan's 5,151-node number is not the current local count; see the report before treating it as a release gate.
- [x] The connected Hugging Face identity can read both `Library_books` and `graphier`; both repos are private and the connector has read-only repo scope, so publication and anonymous source opening are unverified.
- [x] Hosted roster import and first-login password-change code is on the release branch; focused auth, roster, source-link, and library checks pass locally. Live Supabase account creation/password change has **not** been exercised.
- [x] The local Pearson resolver, citation builder, demo cards, and library shelf now omit unverified `/page/N` fragments; the requested page remains explicit in handoff metadata. Fabricated sample table-of-contents pages and sample years were removed from Pearson/paper shelf entries.
- [ ] Locate provenance for the historical 5,151-node count and reconcile it with the current local 6,081 total Kùzu nodes, 537 exported concepts, 84-concept fixture, and hosted 520 concepts. Do not change the acceptance threshold until the authoritative snapshot is identified.
- [ ] Resolve the repo-wide quality gate and independent review before deployment. The 2026-10-06 run found 422 magic-number findings, a banned pattern, one oversized module, 15 dependency-direction violations, legacy formatting/lint debt, and missing mypy; remeasure after changes.

## P0 — inventory, architecture, and release control

- [ ] Freeze a reproducible baseline: commit, branch, graph/catalog hashes, model revision, corpus manifest, Supabase migration versions, runtime config names, asset checksums, and deployed release header.
- [x] Record the locally reproducible hashes, node-type counts, migration files/live versions, key asset checksums, and deployed release header in the linked baseline report. Model revision and corpus provenance remain open in the full freeze item above.
- [ ] Map every endpoint to exactly one of the six response contracts and one owning runtime. Record where `host_inference/`, `archipelago/`, and `chat_server/` intentionally differ.
- [ ] Identify all secrets and exposed credentials in tracked files, Git history, browser bundles, screenshots, logs, CI, and deployment config; rotate compromised institutional/provider credentials through their owners.
- [x] Investigated the GitGuardian PR alert on a roster test's credential-shaped fixture. The fixture is synthetic test data and has been replaced in the branch head with assembled, explicitly fake values; the historical alert and broader secret inventory remain open in the parent item.
- [ ] Confirm source rights, Pearson subscription terms, robots policy, HF dataset licenses, and private/public artifact boundaries before any automated extraction or publication.
- [ ] Make the draft PR the reviewable release unit; require CI and a reviewer from another role. Do not silently promote a red build.
- [ ] Maintain an explicit risk/decision log for features whose source service does not support the demanded behavior, especially Pearson page links and Vercel Python runtime fit.
- [ ] Confirm Cloudflare zone/domain control and current DNS/WAF configuration; inventory the AntDeploy rollback origin before changing DNS.
- [x] The public Cloudflare hostname is not chosen yet (user confirmation on 2026-10-06). Keep DNS and production cutover gated until an institution-controlled hostname is selected and verified.

## P1 — authentication, Supabase, and security

- [x] Production-hosted AuthGuard requires a verified Supabase session on protected APIs; bootstrap accounts now use server-owned `app_metadata` in the working branch.
- [ ] Complete and test 14-digit enrollment CSV import: preview, validation, idempotent create, audit hash/counts, administrator grant for librarians, no uploaded roster retention, and partial-failure recovery.
- [x] Local roster boundary: 14-digit validation, duplicate detection, 100-row and 1 MB limits, CSV MIME gate, formula-name rejection, preview/apply auth checks, first-login flag, and audit-call behavior have unit coverage; this is not a live Supabase write test.
- [ ] Enforce first-login password change on the UI and protected APIs, reject the bootstrap value as a new password, and test login, token refresh, logout, and password-change failure paths against staging Supabase.
- [ ] Resolve anonymous reading versus personalized student access; prevent one student's learning memory, diagnostics, or caches from crossing into another user's session.
- [ ] Apply and verify the faculty-role migration, policy grants, RLS ownership tests, and live unauthorized User A → User B probes.
- [ ] Fix modern Supabase secret-key header usage across Admin, Storage, response cache, inventory, and sync paths; test with the live project using a narrowly scoped read before any write.
- [x] Auth Admin and local sync now use opaque `sb_secret_` keys as `apikey` without a Bearer header; legacy JWT keys retain Bearer. Focused tests pass. Live write and the full endpoint inventory remain open in the parent item.
- [ ] Enable leaked-password protection if compatible with the approved enrollment rollout; verify Auth's configured password policy.
- [ ] Remove hardcoded/inert user-management UI and DOM HTML interpolation risks; validate all uploaded types, size limits, Unicode, CSV formula injection, filenames, and path traversal.
- [ ] Audit prompt-injection boundaries, private-data stripping before XKIRO/NVIDIA/Gemini, CORS, cookie flags, CSRF, token handling, CSP, egress allowlist, and staff mutating endpoints.
- [ ] Replace unbounded in-process per-IP limiter state with bounded/expiring state and a shared limiter for horizontally scaled production; prove 429 and `Retry-After` by role and endpoint.
- [ ] Run dependency, secret, Bandit, and Supabase security advisors; resolve findings or record a reviewed exception.
- [ ] Introduce `/api/v1/` aliases for stable contracts only after compatibility tests for existing `/api/` clients and SSE streams.

## P2 — source identity, citations, and direct opening

- [ ] Build one authoritative source registry keyed by stable book/paper IDs with title, publisher, ISBN/DOI, rights, provider, verified canonical URL, page scheme, and last validation time.
- [ ] Reconcile all Pearson book UUIDs against the authenticated institutional bookshelf; do not guess missing IDs, titles, holdings, copies, or page counts.
- [ ] Probe Pearson's supported navigation flow with a permitted account and documented URL behavior. Test cold session, warm session, exact book, page 1, middle page, invalid page, and expired session. Mark exact-page support unavailable unless a real page-specific URL is proven.
- [x] Stop emitting invented Pearson `/page/N` fragments in both hosted and local reader URL builders. A previous browser probe demonstrated that the fragment does not move to the requested page; the broader navigation matrix above remains open.
- [ ] Validate each HF dataset repo, revision, path, viewer/PDF page fragment, license, and 404 behavior. Keep book and paper links distinct; pin revisions where necessary.
- [ ] Use one link builder in chat citation cards, book stack, library details, graph node details, MCQs, and roadmaps. All clickable links must come from the registry.
- [ ] Link IEM CRP and UEMK OPAC only to verified official destinations; never use a generic homepage when an exact authorized record URL exists.
- [ ] Run a link checker that follows safe redirects without exposing institutional cookies or crawling disallowed content; report broken/missing links as data defects.
- [ ] E2E click real links in a browser from chat, cards, and library detail, including session-dependent Pearson navigation.

## P3 — graph integrity, traversal, and presentation

- [ ] Identify the authoritative full corpus and check node IDs, edge IDs, supported types, duplicate IDs/edges, orphan references, isolated concepts, empty summaries, provenance, and counts by source. The historical 5,151 count needs provenance before it can be enforced.
- [ ] Keep Kùzu local as the single-writer graph and export a signed/versioned lightweight snapshot for hosted inference; verify atomic publication, reload, rollback, and no silent fixture fallback in production.
- [ ] Implement/test context-aware two-pass retrieval: pass 1 selects evidence-backed anchors from query/history; pass 2 traverses a bounded relevant neighborhood with prerequisites, relations, and source constraints.
- [ ] Compare two-pass output with lexical/vector baseline for ambiguity, unsupported topics, multi-hop questions, collisions, and sparse islands; report precision/recall and latency distributions.
- [ ] Verify main graph UI zoom, pan, filters, search, node details, source links, keyboard access, loading/empty states, and performance without dumping the entire institutional graph to the browser.
- [ ] Verify the in-chat concept graph and personalized diagnostic graph are distinct and appear only under appropriate contracts; test click-through into source and neighborhood.
- [ ] Make librarian node edits staged, role-gated, provenance-preserving, schema-validated, auditable, reversible, and idempotent; ensure readers never see half-written graph state.
- [ ] Gate production on graph count/version and integrity, but allow legitimate additive changes through an approved manifest update.

## P4 — answer quality, personalization, and provider reliability

- [ ] Preserve all six response contracts and route every supported query correctly: concept, catalog, library admin, MCQ, ingestion, and guardrail.
- [ ] Make answers concise by default, vary presentation by intent, and include only relevant citations/graph/roadmap. Do not append the same graph or roadmap to every reply.
- [ ] Ground every answer in retrieved facts; distinguish direct source evidence, graph inference, and unavailable information. Reject fabricated pages, books, edges, shelf counts, and citations.
- [ ] Use minimal, sanitized context for XKIRO, NVIDIA, Gemini, or local fallback; test timeout, retry/backoff, quota, malformed output, provider failover, and no-source behavior.
- [ ] Revalidate SSE chunk order, completion, cancellation, client reconnection, error display, and provider usage metrics under load.
- [ ] Expand graph-grounded MCQs toward the documented adaptive 3–10 budget; test distractors, answer replay protection, progress, feedback, and source grounding.
- [ ] Add confidence calibration, fading mastery, learning preference, and gap-to-resource mapping only with explicit consent and evidence. Keep aggregate faculty/librarian reporting privacy-preserving.
- [ ] Add Query Inspector/transparency with safe trace fields (route, anchor, hops, evidence IDs, latency) and no prompts, secrets, or private student data.
- [ ] Establish a held-out answer-quality set with adversarial, ambiguous, short, long, repeat, and prompt-injection queries; measure citation validity and hallucination rate.

## P5 — local ingestion, OCR, spreadsheets, model, and sync

- [x] Graph and chat upload proxies reject missing/nonlocal ingestion origins and do not follow redirects; tests confirm raw multipart never falls back to the cloud inference URL. Compose now wires the existing local HTTP ingestion API and one worker into the appliance; static YAML/startup tests pass. A live container and upload-to-citation test remain open.
- [ ] Boot the Docker library appliance with bind-mounted institutional state and pinned image/model revisions; prove it works after restart and without internet once models are present.
- [ ] Exercise PDF parsing and OCR on born-digital, scanned, rotated, damaged, mixed-language, and empty pages; preserve page provenance and rights flags.
- [ ] Exercise ODS, CSV, TSV, and XLSX import with schema validation, encoding errors, duplicate rows, formula payloads, large files, and malicious archives; produce dry-run CREATE/UPDATE/UNCHANGED/RETIRE diffs.
- [ ] Validate mention-a-book and index-page prefill; require librarian confirmation before publishing uncertain metadata or destructive retire operations.
- [ ] Make file/HF/authorized Pearson metadata watchers detect changes, stage jobs, deduplicate, extract with the local SLM, validate graph DAG/integrity, update index/stats, and notify reviewers before model or source upgrades.
- [ ] Guarantee ingestion retry safety and cleanup: job queue, idempotency keys, partial failures, locks, temp files, DB connections, logs, and rollback.
- [ ] Benchmark the current SLM on at least 100 held-out, representative chunks including aliases, relations, pages, OCR noise, and adversarial text; compare with simpler rules/prompts before any retraining.
- [ ] Retrain only if a documented benchmark shows a material gain; retain old revision, publish a model card, rights review, hashes, version pin, and rollback. Do not publish copyrighted Pearson full text.
- [ ] Sync only approved graph/index/metadata deltas to Supabase/HF, verify manifest and checksums, then trigger hosted cache invalidation/reload. Never auto-publish unreviewed model upgrades.
- [ ] Prove one real fixture flows `upload → OCR/parse → SLM → graph → library → sync → chat citation`, then rerun it to prove no duplicates.

## P6 — caching, scale, and resource safety

- [ ] Test response/retrieval/graph cache with Supabase tables, TTL expiry, graph/catalog/model/prompt version invalidation, cross-worker behavior, and provider-call savings.
- [ ] Exclude personalized, enrollment, private, and unsafe questions from shared cache; prevent stale graph or citation results after ingestion.
- [ ] Bound all local caches, rate-limit key maps, robots/host maps, async cache-write work, SSE client state, and generated session data; measure memory under repeated requests.
- [x] Audit resource lifecycle read-only first: files, temporary uploads, PDF handles, SQLite connections, HTTP responses, threads, timers, DOM listeners, WebSockets, exception paths, and shutdown. Findings and limits are in `docs/reports/RESOURCE_LEAK_AUDIT_2026-10-06.md`; remediation and measured retest remain open.
- [x] Local spreadsheet upload staging now has a 32 MB streamed cap and request-owned temporary directory. Preview, apply, parser-error, and oversize cleanup paths pass unit tests. Production disk behavior and the remaining cache/limiter leaks still need load testing.
- [ ] Load test realistic API request bursts and LLM token throughput separately. Verify p50 first chunk <500 ms and p95 complete answer <20 s under an agreed institutional concurrency profile.
- [ ] Instrument cache hit ratio, tokens/API calls, queue depth, graph version, source-link failures, ingestion lag, provider failures, and user-visible errors without collecting private question text by default.

## P7 — UI, accessibility, and institutional identity

- [ ] Preserve and checksum all original landing assets; resolve Git LFS pointer files before release. Keep animation, palette, layout, and book stack visual quality.
- [ ] Add/verify supplied IEM and UEM logos with accessible alternative text, rights, responsive sizing, and no credential exposure.
- [ ] Test keyboard and screen-reader flow for login, chat, graphs, MCQs, source cards, librarian import/edit screens, loading, errors, and reduced-motion mode.
- [ ] Verify mobile phones, tablets, library kiosks, low-bandwidth conditions, slow APIs, and cross-browser behavior.
- [ ] Treat AdMob spec as a future optional decision; do not add student tracking or ads to institutional learning flows without a separate approved requirement.

## P8 — CI, release, and operations

- [ ] Run Ruff lint/format, strict mypy, architecture and 500-line checks, banned-pattern gate, unit/integration suites, Bandit, secret scan, prompt-injection suite, frontend smoke, and dependency scan on the PR.
- [ ] Make graph integrity and local ingestion fixture E2E mandatory before staging; use a known source to verify book, concept, relation, library record, retrieval, citation, and no-duplicate rerun.
- [ ] Build a slim Vercel inference artifact from the reviewed branch, provision an isolated preview with production-like secret names, then run browser and API E2E against that preview. Keep the local workstation and raw PDFs outside the function bundle.
- [ ] Verify staging Supabase Auth/RLS, cache, provider fallbacks, rate limits, graph, library, chat SSE, two chat graphs, exact source links, metrics, and failure recovery.
- [ ] Obtain independent human approval per AGENTS.md pass 5 after all automated gates; back up data, promote the reviewed Vercel artifact, and record release SHA and migration versions.
- [ ] Point the approved Cloudflare hostname at Vercel only after preview verification; check TLS/WAF, readiness/corpus/fullness, a real chat query, graph, library, Supabase connectivity, provider response, and citation clicks from a clean browser.
- [ ] Evaluate Vercel's Python function limits, cold start, read-only runtime filesystem, model/dependency footprint, static assets, SSE, and budget. Resolve each blocker and prove a live query before promotion. Keep AntDeploy serving as the rollback origin during migration.
- [x] Record the current Vercel fit blockers in the baseline report: repository-tree corpus/cache writes, ephemeral SQLite quiz/learning state, fixture fallback, missing project, and unmeasured cold start/SSE/assets. This is an inventory, not a feasibility pass.
- [x] A Vercel Flask entrypoint and config now exist on the branch. It uses pinned hosted dependencies, keeps disposable downloaded artifacts under runtime scratch, and refuses a fixture, undersized graph/catalog, or missing approved Supabase artifacts. Local hosted-path tests and a Vercel build pass; successful live readiness, cold-start, and query results remain open.
- [x] The `shinaura/archipelago` Vercel project and `codex/production-hardening` preview now build from this branch. A live `/api/readiness` invocation returned 500 before corpus hydration because preview lacked the private Supabase key. The project production domain still serves an older branch and is not a release URL. The live Supabase private `archipelago-cache` bucket has the three required artifacts; preview credentials and corpus-read verification remain open.
- [ ] Replace Vercel's ephemeral SQLite diagnostic/learning state and file-backed demand telemetry with durable, role-isolated Supabase storage before claiming adaptive learning or purchase digests work across instances. Scratch storage is only a boot/cache mechanism.
- [ ] Retire the AntDeploy origins only after primary-site traffic, redirects, credentials, and rollback dependencies are inventoried and the Vercel replacement passes production smoke.
- [ ] Publish local operator URLs for :5150 graph, :5151 inference, :5152 chat, and the Docker appliance only after authenticated readiness and end-to-end ingestion succeed.
- [ ] Write rollback runbooks, alerts, error budgets, backup/restore tests, on-call handoff, and a final verification matrix with direct evidence for every claimed feature.

## P9 — campus library operations and identity federation

These workflows extend the architecture image from general retrieval to the operational library system. Each needs an authoritative campus source, a named owner, role tests, freshness rules, and a real end-to-end demonstration. Current status below is based on repository inspection; no live campus integration is implied.

### Periodical receipts and open-access alternatives

- [x] The local ODS ingestor now preserves identified issue rows in a `JournalReceipt` table with normalized source status, raw status, publication date, import time, and stable identity. A synthetic Kùzu integration test proves duplicate rows collapse and `Late → Received` updates; real campus ODS and student UI remain open.
- [ ] Preserve each serial issue from Koha/ODS with journal identity, volume/issue label, expected or published date, source status (`Expected`, `Late`/`Overdue`, `Received`, or `Unknown`), import time, and provenance. Reimports must update the same issue without duplicates; missing status must never be presented as received.
- [ ] Distinguish a journal subscription from a particular physical issue. Show current status, last source refresh, and a stale-data warning in librarian and student views. Test late-to-received transitions and a real ODS export.
- [ ] When an issue is late or overdue, offer a verified, rights-compliant open-access article/preprint match (for example, an exact arXiv record) alongside the physical issue status. Require DOI/title/author identity and license checks; do not redirect to a merely related paper or claim the substitute is the same edition.
- [ ] Keep automatic outbound navigation opt-in and log the source decision without saving private student queries. Test no match, withdrawn preprint, wrong paper, and provider outage.
- Current state: local ingestion now stores issue rows and statuses as well as aggregate counts, but no real ODS file was available in this checkout for validation. The journal-status formatter accepts status data; unknown journal lookups and blank statuses no longer claim verified holdings or receipt. No late-issue-to-open-access route exists.

### Physical membership tokens

- [x] Student replies no longer turn missing configuration into a claim of zero cards; configured totals are clearly labeled as totals, with live checkout availability referred to the desk. Hardcoded card counts were removed from the credential registry. This does not provide a live ledger.
- [x] A librarian-only Supabase card/loan/event migration is staged in `supabase/migrations/20261006061112_external_membership_ledger.sql`. Disposable PostgreSQL 17 tests proved single-active-loan enforcement, lost-card checkout denial, return audit events, browser-role denial, and service-role reads. It has not been applied to the live project or connected to the staff UI.
- [ ] Replace static British Council/American Library card counts with a librarian-owned token ledger: total, available, checked out, due, lost/unavailable, and last reconciliation. Enforce a single active holder per physical card and prevent negative availability or double checkout.
- [ ] Give students current availability and desk pickup guidance without exposing borrower identity. Provide staff checkout/return, audit trail, overdue view, and correction workflow; test concurrency and offline desk reconciliation.
- Current state: optional `ARCHIPELAGO_MEMBERSHIP_*` values still provide only configured totals in the running app. The new ledger schema is branch-only pending live migration and staff API integration.

### Class routines and pre-lecture briefs

- [ ] Ingest approved timetable tables or a reviewed OCR result from `lib-time.jpg` with term, class, room, teacher, session time, and source revision. Require human review for ambiguous image text and timetable changes.
- [ ] Map each upcoming class to teacher lesson-plan topics, OKF concepts, and verified shelf/resource IDs. Distinguish library opening hours from class routine data; do not infer room or lesson from a static hours poster.
- [ ] Generate weekly and pre-lecture reading briefs for enrolled students with citations, physical availability, and accessible alternatives. Use enrollment and consent controls; support cancellation/reschedule, avoid duplicate briefs, and prove timezone/holiday behavior before enabling notifications.
- Current state: `library_schedules.py` covers static library operating hours only. No class routine, lesson-plan ingestion, enrollment join, or scheduled brief delivery was found.

### Demand-driven procurement

- [ ] Join privacy-safe concept query counts over a defined time window to current `Resource.available_copies`, holdings freshness, and catalog identity. Produce a librarian-only purchase order **draft** when demand exceeds a reviewed threshold and available copies are zero; never place an order automatically.
- [ ] Deduplicate concepts/titles, account for digital access and already-open purchase requests, show evidence and estimated demand, and record librarian approve/defer/reject decisions. Test zero versus unknown copy count, a spike followed by replenishment, and student data suppression.
- Current state: `/api/librarian/demand-digest` and `/api/librarian/acquisition-plan` record repeated requests for *unheld titles*. They do not join concept spikes with zero-copy physical resources, and the digest currently uses local file state that is unsuitable for Vercel durability.

### Institutional SSO and RLS

- [ ] Select the college identity provider and protocol with campus IT: Supabase Auth SAML enterprise SSO for a supported Google Workspace/Microsoft Entra IdP, or an approved OAuth/OIDC provider flow. Record plan/feature availability, domain verification, redirect URLs, account linking, and deprovisioning behavior before enabling it. [Supabase SSO guidance](https://supabase.com/docs/guides/auth/enterprise-sso/auth-sso-saml) and [OAuth provider guidance](https://supabase.com/docs/guides/auth/social-login) describe distinct paths.
- [x] The user confirmed that enrollment number and UEM Kolkata email must identify students; the exact email domain and provider are still pending. Keep the existing 14-digit enrollment validator, and never infer an email suffix from the shorthand supplied. Campus source uploads and updates are librarian-only.
- [ ] Map immutable campus identity and enrollment/employee status to server-controlled student, faculty, librarian, and administrator roles. Keep authorization in Supabase RLS and verified server claims; reject self-assigned roles, stale group membership, cross-student reads, and offboarded accounts.
- [ ] Replace `ARCHIPELAGO_LIBRARIAN_TOKEN` for interactive staff actions after SSO staging passes. Keep any service-to-service credential scoped, rotated, and separate from human login. Test SSO login/logout, MFA policy, session refresh, role change, deprovisioning, and break-glass recovery.
- Current state: verified Supabase session guards exist, but local ingestion still accepts a configured legacy shared librarian token and no college IdP/SAML/OAuth federation setup or live RLS role mapping is proven.

## Latest local validation (2026-10-06)

- `pytest tests/unit/test_source_links.py tests/unit/test_library_recovery.py tests/unit/test_student_roster_hosted.py -q`: **50 passed** after copying the ignored Pearson catalog and graph artifacts into this isolated worktree.
- `pytest tests/unit/test_auth_boundary.py tests/unit/test_student_roster_hosted.py -q`: **9 passed** after the latest auth guard update.
- `pytest tests/unit/test_librarian_upload_cleanup.py tests/unit/test_student_roster_hosted.py -q`: **12 passed**, including 4 upload-cleanup success/failure/size paths.
- `pytest -q tests/unit/test_local_ingest_privacy.py tests/unit/test_supabase_service_key_headers.py tests/unit/test_auth_boundary.py tests/unit/test_student_roster_hosted.py`: **21 passed**, including local-only upload forwarding, cloud fallback denial, Supabase key headers, auth boundaries, and roster behavior.
- `pytest -q tests/integration/test_ingestion_worker.py tests/integration/test_ingestion_safety.py`: **8 passed** for staged worker and rollback safety; this does not exercise the Docker HTTP receiver.
- `pytest -q tests/unit/test_library_api_startup.py tests/unit/test_local_ingest_privacy.py tests/unit/test_auth_boundary.py`: **11 passed** for local API startup order and privacy/auth boundaries. Compose YAML parsed, but Docker Compose/Gunicorn are unavailable on this host, so the container has not been booted.
- `pytest -q tests/integration/test_periodical_receipts.py tests/unit/test_membership_card_honesty.py tests/unit/test_student_roster_hosted.py tests/unit/test_session7_catalog_queries.py`: **47 passed** for issue receipt persistence, honest card totals, roster, and existing catalog behavior. The new receipt tests use synthetic rows; campus ODS validation remains open.
- `pytest -q tests/integration/test_periodical_receipts.py tests/unit/test_periodical_receipts.py tests/unit/test_membership_card_honesty.py tests/unit/test_student_roster_hosted.py tests/unit/test_session7_catalog_queries.py tests/unit/test_inference_75_cases.py`: **132 passed** including status normalization and the existing institutional query cases.
- `pytest -q tests/integration/test_periodical_receipts.py tests/unit/test_periodical_receipts.py tests/unit/test_membership_card_honesty.py tests/unit/test_student_roster_hosted.py tests/unit/test_session7_catalog_queries.py tests/unit/test_inference_75_cases.py tests/unit/test_tc75_honest_pass.py`: **207 passed** including the broader TC75 honesty checks.
- `pytest -q tests/unit/test_periodical_receipts.py tests/unit/test_session7_catalog_queries.py tests/unit/test_50_new_cases_verification.py tests/unit/test_membership_card_honesty.py`: **96 passed** after removing fabricated unknown-journal holdings and blank-status optimism.
- `pytest -q tests/unit/test_vercel_runtime_paths.py tests/unit/test_antideploy_release.py tests/unit/test_host_inference_deployment.py tests/unit/test_library_restoration.py tests/unit/test_reader_safety.py`: **65 passed** after the Vercel scratch-path and fail-closed entrypoint changes. This is a local regression set, not a live Vercel preview.
- `pytest -q tests/unit/test_vercel_runtime_paths.py tests/unit/test_antideploy_release.py`: **14 passed** after making the preview report a missing private Supabase configuration explicitly. The Vercel preview build succeeded, while its readiness request failed because that configuration was absent.
- Ruff lint and format checks passed for the changed Pearson resolver, citation/demo/shelf files, roster modules, and affected tests. `git diff --check` passed.
- The broad suite and repository-wide quality gate are **not green**. The current quality gate reports 417 magic-number findings, one unchecked Ollama call, an oversized answer module, 15 dependency-direction violations, legacy lint/format debt, and missing mypy. Independent review and live staging E2E remain pending. Neither AntDeploy nor Vercel has been updated from this branch.

## Document coverage map

| Source document | Applied plan areas |
| --- | --- |
| `00_MASTER_RULES.md` | Preservation, honesty, six contracts, privacy, testing, ingestion rights |
| `01_PRD.md` | Personas, chat/graph/library, accessibility, metrics, advanced learning |
| `01_production_engineering_cicd.md` | End-to-end product, direct links, graph 5,151, local ingestion, CI, deployment |
| `02_institutional_deployment.md` | AntDeploy + Docker workstation + HF model, 5,151 integrity, real staging |
| `02_TRD.md` | Three local ports, query pipeline, graph, OCR, personalized MCQs, cache |
| `03_ai_call_minimization_caching.md` | Supabase answer/retrieval/graph caches, TTL, invalidation, dedup, cost |
| `03_ARCHITECTURE.md` | Service and data-flow boundaries, dual-runtime debt |
| `04_clean_architecture_deployment_plan.md` | Source links, chat graphs, intake, preserved UI, release order |
| `04_DATA_MODEL.md` | Kùzu, OKF, Supabase roles, catalog, provenance |
| `05_DATA_SOURCES.md` | Pearson, HF, local PDFs, Koha, rights, data quality |
| `06_SCRAPING_SPEC.md` | Deny-all fetch policy, Pearson metadata, Apify, HF, robots |
| `07_API_CONTRACT.md` | Versioned endpoint and auth/rate semantics |
| `08_UI_SPEC.md` | Visual preservation, graph/book stack, responsive accessibility |
| `09_ERROR_HANDLING.md` | Explicit provider/ingestion/network errors and redacted logging |
| `10_SECURITY.md` | Supabase auth, RLS, PII, secrets, CORS, rate limits, egress |
| `11_ADMOB_SPEC.md` | Deferred optional monetization; no student tracking |
| `12_GITHUB_ACTIONS.md` | CI/CD gates, secret handling, post-deploy checks |
| `13_TESTING.md` | Unit, integration, E2E, ingestion, browser, load and adversarial tests |
| `14_PRODUCTION_CHECKLIST.md` | Release definition of done and honest status |
| `15_MICROTASKS.md` | Priority order and known debt |
| `16_CHANGELOG.md` | Historical claims to revalidate against current code/live release |
| `17_DECISIONS.md` | Kùzu, six contracts, xkiro, vanilla UI, dual runtime, Supabase, deny-all |
| `CODEBASE_MINDMAP.md` | Module ownership and impact map; verify stale paths before edits |
