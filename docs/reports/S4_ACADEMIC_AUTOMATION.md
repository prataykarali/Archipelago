# S4 academic automation acceptance, 2026-11-11

**Current review candidate:** The initial 12-row/21-edge staging counts below are historical. See [S4 D2L scientific correction](S4_D2L_SCIENTIFIC_CORRECTION.md) for the corrected 10-row/8-edge candidate, exact disposition ledger, digests, and current BLOCKED status. The canonical and hosted graphs remain unchanged.

Branch: `codex/s4-academic-automation`. Starting remote commit: `ac56b212877ea3b82aef005ac93b8d269a30802a`. The final pushed commit is reported in the task handoff because a commit cannot contain its own SHA.

## Live source evidence

The ledger contains 178 catalog records after the five live OPAC detail checks. Every source match is retained in `source_evidence` with the OPAC URL, provider URL, match method, license, content status, eligibility, reason, and retrieval time. The dashboard API and UI expose these rows. No restricted or contents-only text is queued for concept extraction.

| Catalog item | Observed evidence | Extraction |
| --- | --- | --- |
| `opac_live:4150`, Dive into Deep Learning | Open Library `OL48193224M` metadata; official D2L chapter, CC-BY-SA-4.0 | Eligible; job `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` |
| `opac_live:4021`, Probabilistic Machine Learning | Open Library `OL34192800M`; author preprint CC-BY-NC-ND-4.0 | Blocked |
| `opac_live:4151`, How to Think about Algorithms | Open Library `OL48686803M` metadata | Blocked |
| `opac_live:588`, Operating System Concepts | No verified external full text | Blocked |
| `opac_live:576`, OPERATING SYSTEMS | No ISBN or verified external match | Blocked |
| OAPEN index proof, Scalable Data Management for Future Hardware, ISBN `9783031740961` | OAI ID `oai:library.oapen.org:20.500.12657/98554`, CC-BY-4.0, 11,189,926-byte PDF with MD5 | Eligible in index only; not claimed as a UEMK match |
| OAPEN restricted index proof, Liberalism against Liberalism, ISBN `9780203016886` | CC-BY-NC-ND rights | Blocked; not claimed as a UEMK match |

A fresh five-page DOAB harvest indexed 403 books; 135 have a parsed permissive license and 646 ISBN links were populated. The `name="*"` XOAI parser fix is retained. OAPEN and DOAB index evidence is resolved by exact ISBN plus verified title overlap. Open Library contributes metadata and contents, Crossref contributes DOI metadata, and Europe PMC may contribute licensed JATS body text when its OA and license checks pass. Only the D2L chapter and verified Europe PMC body text can be queued from these text providers. OAPEN PDF download additionally checks per-file license, size, and MD5.

| License | Decision |
| --- | --- |
| CC-BY-4.0, CC-BY-SA-4.0, CC-BY-3.0, CC0-1.0 | Eligible only with verified body text and provider checks |
| CC-BY-NC-ND-4.0, commercial copyright, unknown per-file rights | No extraction |

## Daily cycle and consent

The daily command reconciles Koha, Pearson, OPAC arrivals, and institutional repository metadata; advances the nine-query live OPAC cursor; and harvests five pages each from DOAB and OAPEN. It then runs at most one pending consent-gated job. An empty queue records `daily_cycle_noop` and returns without probing GPU, starting Ollama, or opening a dialog. The timer is configured for `09:00:00 Asia/Kolkata`, and both systemd units passed `systemd-analyze verify`. The timers remain disabled.

Two controlled `daily-cycle --skip-live-opac` runs used an isolated temporary ledger. The first found 109 Koha and 40 Pearson records, with zero eligible jobs. The second reported 109 and 40 unchanged, zero queued jobs, and `status=noop`. Both exited 0 without a popup or GPU job.

A repeat live `discover --query "Dive into Deep Learning" --max-records 1` returned `unchanged: 1` and `unchanged_evidence_retained`; it did not hunt or queue the record again.

The live GPU snapshot before extraction reported available=true, 4096 MiB total, 14 MiB used, zero loaded Ollama models, and zero compute PIDs. The local operator selected `approve_class` in the five-choice desktop dialog, creating a revocable 24-hour `trusted_academic_open_content` grant. Controlled tests cover defer, cancel, model conflict, shared lease, and CPU `num_gpu=0`; these branches were not exercised against the production job. The worker did not load a second model.

## D2L staging trace

OPAC 4150 matched the official D2L repository by ISBN and title. The source license file declared CC-BY-SA-4.0. The fetched `chapter_linear-regression/linear-regression.md` was bounded, stripped of code tabs, hashed into `data/academic_candidates/`, and recorded with its official chapter URL in a `.source.json` sidecar. After desktop consent, `lib-qwen:latest` extracted 12 source-linked concept rows into the isolated job directory. The cleaned rows include Linear Regression, Loss Function, Minibatch Stochastic Gradient Descent, and Normal Distribution, each with a summary and section title. Markdown has no printed page numbers, so rows correctly carry page number 0 and must be cited by chapter URL and section, not a fabricated page.

Staging contains 617 concepts, 80 documents, 826 chunks, and 2,009 typed edges. Validation reports 7 added concepts, 21 added edges, zero missing prior concepts, zero missing prior edges, and `valid=true`. A cleanup removed two unrelated scratch rows from `results.json` and rebuilt the staged graph from the 12 source-linked rows; `Document.title` is now Dive into Deep Learning. The canonical graph is still untouched.

| Canonical graph | Before staging | Current |
| --- | ---: | ---: |
| SHA-256 | `3ee305138a4a3661b505c30a1f782baeddd7e0779eef634720392821c0eb46ed` | same |
| Concepts / documents / chunks / typed edges | 610 / 79 / 808 / 1,988 | same |

The plan quoted `df3943eeebd6a541ba83dde0cb7f0ed606a46deb40aecc9ff3db4d7888923cc8`, but the actual canonical file was already `3ee305...` when checked before the GPU job. Its node and edge counts still matched the plan. A controlled rollback test on a byte-for-byte copy restored the exact `3ee305...` SHA after simulated corruption. The existing publication failure tests also passed.

## Verification and outstanding gates

- **PASS:** Five live OPAC examples, source evidence, DOAB/OAPEN index proofs, strict metadata/body separation, consent-gated GPU staging, preservation validation, rollback copy, and 09:00 timer syntax.
- **PASS:** Focused S4 suite: 35 tests passed. Changed-module Ruff lint passed. The dashboard API returned HTTP 200 with seven evidence rows, one review-ready job, and one grant; Chromium screenshot: `artifacts/validation/s4-academic/dashboard-full-review-ready.png`.
- **PARTIAL:** Repository-wide quality gate remains red from unrelated existing Ruff and strict typing failures. New S4 modules are below the gate's 400-line file limit. Full strict mypy is red on hundreds of existing errors.
- **BLOCKED pending independent human review:** The job is `review_ready`; production publication, after-graph snapshot, idempotent post-publication ingestion, and D2L chat freshness have not happened. `AGENTS.md` requires a different-role human approval as pass 5. The librarian must review the staged results and approve publication. No reviewer identity has been fabricated.
- **PARTIAL:** Chat end-to-end answers and chat screenshots have not yet been captured against the unpublished D2L graph. The running staff graph API requires a Supabase token; a separate localhost test server was used only for the dashboard screenshot.

## Final review and hosted parity check

The authenticated graph console now exposes `/academic-automation.html` and `/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe`. The packet displays all 12 extracted rows, all 21 proposed typed edges, exact stored source excerpts, chapter and verified section anchors, the CC-BY-SA-4.0 source license, and the explicit absence of printed page numbers. The review endpoint and decision endpoint require a verified Supabase librarian or administrator session; the development token cannot decide. A decision is recorded with verified user ID, role, timestamp, note, and SHA-256 digest of the exact staged graph and results. Publication now rejects a missing or stale approval. No review decision has been recorded.

The candidate needs scientific correction before approval: the proposed `minibatch_stochastic_gradient_descent → stochastic_gradient_descent` `UNLOCKS` edge reverses the expected prerequisite direction; the generic `Mathematics` row comes from the Biology analogy; and several `RELATED` edges reflect co-mention rather than a supported conceptual relation. This is a human review finding, not an automated rejection. `lib-qwen` F1 remains below the required gate.

The operator's temporary GPU grant `d5cd86ef-9d0e-4394-94c5-d773e17cd6a8` was revoked after staging; `has_grant` is now false. The daily systemd timer remains `not-found` (configured files verified but not installed or enabled). No additional extraction ran.

The live Vercel inference endpoint `https://archipelago-blond.vercel.app/api/readiness` returned HTTP 200 with `cache=supabase`, `corpus.source=full`, and **537 concepts** on 2026-11-11. The local canonical graph still has **610 concepts** and SHA-256 `3ee305138a4a3661b505c30a1f782baeddd7e0779eef634720392821c0eb46ed`. Thus hosted graph parity is not established even before publication. The hosted readiness response now includes `graph_version` in code, and Vercel startup accepts an `ARCHIPELAGO_EXPECTED_GRAPH_VERSION` gate to fail closed when the Supabase artifact differs from the approved export. Those changes are not live until a hosted deployment. Do not set the expected version or publish a new artifact before human approval.

**Publication status: BLOCKED.** Approved concepts/edges: 0/0. Rejected concepts/edges: 0/0. All 12/21 remain pending. Canonical before/after SHA and identities are unchanged. No post-publication six-query chat evidence or main/hosted version match can be claimed. After a verified decision, the release operator must publish atomically, upload the approved export to the hosted Supabase cache, deploy the version-gated Vercel app, and run the actual six browser queries on both paths. S4 remains OPEN.

Focused review, source, and publication tests: **22 passed**; changed-file Ruff lint and format passed. A broader 33-test command had two failures in `test_host_inference_pages.py` involving pre-existing research-page asset version and login redirect expectations, unrelated to S4. The Vercel connector returned 403 for the linked project/team and its team-authorization call returned 404. The locally authenticated Vercel CLI could access that team, so commit `8034a8abe1fb1a34cc2ab829906cac65e122d55f` was deployed as a protected **preview** at `https://archipelago-gekz67pgk-archipelago-6383.vercel.app`. Preview readiness returned HTTP 200, 537 concepts, `cache=supabase`, and `graph_version=bafb91ebe902`, proving the new version-reporting code runs on Vercel. Preview `/chat` redirected to `/login?next=/chat`; an unauthenticated graph request returned 401. No production deployment or graph artifact upload occurred, and hosted D2L chat acceptance remains blocked on review and corpus synchronization.

## Final gate recheck — 2026-11-12

| Gate | Status | Actual evidence |
| --- | --- | --- |
| Scientific candidate | PASS for technical preparation | Current packet is `review_ready`: 10 rows, 8 `RELATED` edges; all 8 match the explicit semantic labels in the correction ledger and have stored supporting excerpts. The bad minibatch SGD `UNLOCKS` edge and generic Mathematics/Model rows are absent. All 33 original decision items have excerpts that match the official chapter Markdown byte for byte; all 11 distinct section anchors occur in the live chapter HTML. License is CC-BY-SA-4.0 and page number is 0 for Markdown. |
| Identity and integrity | PASS for staging | Baseline and current canonical SHA-256 both equal `3ee305138a4a3661b505c30a1f782baeddd7e0779eef634720392821c0eb46ed`. Staged SHA-256 is `ac4d0bfa45edec7c933be7038e1db9a7d683bf7915adc0acd13636e03eb67ec0`; review digest is `0fba3b14cc9e50fac0fd32fb960ac2a94fe9430f71b6fdbb10e640dd58fc9c77`. Validation reports 610 → 615 concepts, 1,988 → 1,996 edges, 1 new document, 16 new chunks, no removed identities, no broken edges or self references. |
| Independent review | BLOCKED | `review_packet` returns `decision: null` and `publication_status: BLOCKED`. Local librarian route and review API both return 401 without a verified session. No attributable decision or approved digest exists. |
| Canonical publication and rollback | BLOCKED | No publication operation was run. The canonical graph remains at 610 concepts and 1,988 edges. A production backup, atomic swap, postpublication counts, export, and rollback exercise must follow an exact-digest approval. |
| Hosted parity | BLOCKED | The authoritative hosted artifact is private Supabase Storage `archipelago-cache/okf_graph.json`. Read-only GET returned HTTP 200, 537 concepts, 1,903 edges, SHA-256 `bafb91ebe902dc2f4cafd2bc3d079582cf55baf0202ee51c832897459124660c`. Production `/api/readiness` returned 537 concepts and `cache=supabase`. No approved artifact upload or cache invalidation occurred. The protected preview was inaccessible with ordinary curl and the Vercel CLI is unavailable here; no current preview parity claim is made. |
| Six live chat queries and production promotion | BLOCKED | No approved graph is published or hosted. Consequently there are no D2L responses or screenshots to accept. Production remains on its last known-good deployment; no promotion occurred. |
| Scheduler and GPU | PARTIAL | `systemd-analyze verify` passed for the discovery/worker units. The four S4 units were linked to user systemd and reloaded; both timers are `linked` and `inactive`, not enabled or started. The configured discovery time is 10:00 Asia/Kolkata with `Persistent=true`. The temporary trusted-class GPU grant has a recorded `revoked_at` of `2026-11-11T17:02:29.710693+00:00`. Live scheduler behavior awaits explicit enablement. |
| Focused tests and security boundary | PASS | `pytest -q tests/unit/test_s4_academic_automation.py tests/integration/test_s4_academic_dashboard.py tests/unit/test_academic_opac_live.py tests/unit/test_academic_repository_feed.py`: 23 passed, 1 dependency deprecation warning. Changed Python files pass `ruff check` and `ruff format --check`. Unauthenticated review GET and UI returned 401. Repository-wide quality debt remains separately documented. |

The precise edge labels (`uses_affine_map`, `uses_squared_loss`, etc.) are scientific review metadata. The current graph schema stores all eight retained edges as `RELATED`; neither the stored graph nor the review UI promotes them to `REQUIRES` or `UNLOCKS`. The [itemized scientific packet](S4_D2L_SCIENTIFIC_CORRECTION.md) is the decision evidence. S4 remains **OPEN** pending an independent authorized reviewer, followed by publication, exact hosted parity, six actual browser queries, and separate release approval.
