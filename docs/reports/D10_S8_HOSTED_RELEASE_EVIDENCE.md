# D10-S8 hosted engineering release evidence — 2026-11-27

**Verdict: READY FOR AUTHOR TESTING.** This is an engineering access verdict, not a human answer or source-quality grade. The release is **not frozen**; the author still needs to complete the 36-question diagnostic and source/edge audit before any final tag.

## Deployment and isolation

| Item | Verified state |
|---|---|
| Git source | `prataykarali/Archipelago`, branch `sigir/demo-2027`, deployed source SHA `0195b074ea2ef452b6936a41f84c7e87c06af3ac` |
| Original site | `https://archipelago-blond.vercel.app`, release header `f76c1c4ddb91bbf1947dbb820c971c51e04753cf`; still returns readiness 200; no original deployment or database mutation was performed |
| Research site | `https://archipelago-sigir.vercel.app`, Vercel workspace `sigir1`, project `archipelago-sigir`, deployment `dpl_AU9dWU4KffXbeU8fb6b2kj16bb4t`, release header matches the deployed SHA |
| Vercel Git policy | Production branch `sigir/demo-2027`; preview deployments disabled; Git-triggered builds ignored by `exit 0`; production alias assigned only after clean protected-deployment checks |
| Supabase | Research Staging `edokbtmhztkhndmxetpy`, distinct from original production `spllaastejfwclllfndp`; production-scoped Vercel variables point only to Research Staging |
| Storage | Private staging buckets `archipelago-sigir-private` for immutable candidate passages and `archipelago-cache` for a dated Koha metadata snapshot; neither bucket is public |
| HF | Graph `Prataykarali/graphier@86e29828c38dbf0f8cea5d50ed6a341ccde3a8f3`; documents `Prataykarali/Library_books@b0561c76a4c5a7a8cb1fe3bd91b389280d504cbd`; installed HF token has read-only role |
| Services | `inference` serves the catch-all; `research` serves `/librarian*`, `/librarian-assets/*`, `/api/librarian/*`, `/api/library/koha`, and `/api/library/opac/live`. The research service has a private `INFERENCE_SERVICE_URL` binding to inference. These names and paths were confirmed by the user. |

The project has no `ARCHIPELAGO_RESEARCH_DATABASE_URL`: the existing database password was not reset or copied. Research persistence uses the service-role `s5_research_rpc` fallback against staging. Hosted `/api/research/intelligence/readiness` returned 200 with `ready: true`; save, retrieve and XLSX export also passed. The staging S5 and quota SQL was applied directly and verified; these statements are not yet recorded in Supabase migration history. Reconcile that history before future automated database migrations.

## Hosted acceptance

| Check | Result |
|---|---|
| Readiness and corpus | Two clean protected deployments and the public alias returned readiness 200. Graph 610 concepts, 1,988 edges; 40 Pearson books; 43 approved documents and 3,025 candidate passages loaded from private staging Storage with SHA-256 `93f6db39cb10d03beeb41c48469d138be27b62ed90aa59d20dd4c5107fbb2e52` verified. |
| Student and librarian auth | Fresh Supabase password sign-ins registered durable sessions and returned the expected roles. Anonymous chat quota 401. Student quota 200. Librarian catalog 200 for staff, 401 for student. Public browser student login reached `/chat` using the temporary account's full email. |
| Multi-instance sessions | The same student token worked on two clean deployment URLs. Logout on one produced `revoked_credentials` on the other. New login/registration restored access across deployments. |
| Idle expiry | Advanced only the temporary student's staging session activity timestamp beyond the configured five-minute idle limit. `/api/auth/me` returned `idle_expired` 401; a fresh sign-in and registration returned authenticated 200. |
| Live provider and cache provenance | Transformer, LoRA, paging and RAG returned completed streams with `provider: xkiro`, verified grounding and cited passages. The trace identifies `cache_status: miss_no_reuse`; no cross-account chat cache replay is used. An initial supported request stalled and a rapid repeat hit the app rate limit; subsequent controlled streaming retries completed. XKIRO availability and quota remain shared external dependencies. |
| Exact-page PDF | Authenticated `/api/page-view` resolved OSTEP `07_Address_Translation.pdf` page 7; the PDF endpoint returned `%PDF-` bytes. Chrome rendered page 7 of 15 with the base-and-bounds text visible. |
| Research-run account isolation | A student saved a live Dense Passage Retrieval run. The student retrieved and exported its XLSX (`PK` ZIP signature); the librarian account received 404 for that run and did not list it. Anonymous run listing returned 401. |
| Six preliminary questions | Spanner TrueTime abstained with `GUARDRAIL_INTERCEPT`, no citations and deterministic synthesis. Transformer, LoRA, paging, OSTEP base-and-bounds and RAG completed with expected routing and source links. These are technical checks; answer correctness and citation entailment remain for the author. |
| Targeted and differential regression | 19 targeted pytest cases passed. Offline comparison against candidate `b949d65b9b2d503dd997b25cebba8b365d5242a1` with the identical candidate passage file matched all six routes, grounding states, citation counts and answer text. A provider stub showed the former candidate would polish a `general` OSTEP answer; this branch keeps it deterministic. |
| Koha metadata | Public `/api/library/koha` returned 200 with 109 catalog holdings from the four repository ODS exports. The response explicitly marks the 2026-11-24 export as stale; physical availability is not presented as live. |

## Remaining shared dependencies and author work

- XKIRO API availability, rate limits and charges; Hugging Face dataset access; Supabase Research Staging availability; and Vercel infrastructure can still affect the research site. The research project has its own Vercel deployment and database credentials. No new paid plan was enabled; incremental metered charges depend on the existing workspace and provider plans and were not estimated.
- The live OPAC endpoint depends on the university OPAC and may return a dated snapshot. It is separate from the verified repository Koha export.
- The repository-wide `python3 scripts/quality_gate.py` remains red on inherited lint, type, banned-pattern and file-size baselines (including 1,348 existing strict mypy errors and 100 files over the interim 400-line limit). The 19 targeted regressions pass. This engineering evaluation deployment does not assert that the repository-wide release gate is green.
- The six-query pass confirms routing, transport, provenance and page resolution. It does not replace the author's 36-question technical, evidence, edge-direction and citation review.
- Temporary staging test users were created for student and librarian journeys. Their credentials are stored only in a local mode-600 file under the user's `.codex` directory, never in Git or this report. Use the **full email address** in the login form. Replace these with author-owned accounts after evaluation.
- The original production site and production Supabase database were not written. The graph and held-out evaluation dataset were not modified. No final release tag was created.
