# Release baseline and platform decision — 2026-10-06

This report is a read-only snapshot for the [production master plan](MASTER_PRODUCTION_PLAN_2026-10-06.md). It separates observed state from the Cloudflare/Vercel/Supabase target. No production deployment or database write was performed.

## Reproducible local baseline

| Item | Observed value |
| --- | --- |
| Release worktree | `codex/production-hardening` at `7adbbfb9e685df3cb68e88b64d3840573d4dbc26`; clean before this report |
| Kùzu database | `okf_graph.db`, SHA-256 `c09d0cabcf6dc2ef2f639b0fd969960eb5c1bfc9b3b561a0df0ff33988e6a5d5` |
| Graph export | `okf_graph.json`, SHA-256 `bafb91ebe902dc2f4cafd2bc3d079582cf55baf0202ee51c832897459124660c` |
| Tracked fallback fixture | `host_inference/fixtures/okf_graph.json`, SHA-256 `64050efdfa698dc2501d895adf32fd3981991bfeb1788ceb7b9d533c9ccb41dd` |
| Local Pearson catalog | `data/catalogs/pearson_bookshelf.json`, SHA-256 `414d334fedcab1bd9e2fe1d98b29834fcd024a6d64265e9770f08458623f319f`; local ignored fixture, not a tracked release artifact |
| Extraction model | `okf.config.MODEL_NAME` defaults to `lib-qwen:latest`; appliance example says HF revision `v5`, but no model directory or resolved artifact hash exists in this worktree. Revision is **unverified**. |
| UI assets | `archi_main.mp4` SHA-256 `5d55f70aa4a2a995e017b46c242a2561b0976dc7b02bb2056bc69393220f4f79`; `landing_hero_curious.jpg` `f875953319af1c88cac66ffcfbf4c33724d6379173aa7cde92522115917a2e35`; `intro_archi.jpeg` `d9984771578ab4e72b79439bcd6c16de8e1f98ff83c630792cc62f3fb75d94a2`. `file` identifies full MP4/JPEG content in this checkout, not LFS pointer text. |

Reproduce local counts with read-only Kùzu queries such as `MATCH (n:Concept) RETURN count(n)` and graph export counts with the `stats` field in `okf_graph.json`. Reproduce hashes with `sha256sum` on the exact paths above. Configuration **names**, never values, come from `.env.example` and `deploy/library-computer/.env.example`; relevant families are `ARCHIPELAGO_*`, `SUPABASE_*`, `XKIRO_*`, `NVIDIA_*`, `GEMINI_*`, `HF_*`, `OKF_*`, and `PEARSON_*`. The deployment-specific value inventory remains private.

## Graph identity: why the reported counts differ

| Layer | Count | Meaning |
| --- | ---: | --- |
| Local Kùzu `Concept` | 537 | Teachable concept nodes in this database |
| Local Kùzu `Document` | 69 | Document nodes |
| Local Kùzu `Chunk` | 786 | Evidence chunks |
| Local Kùzu `Resource` | 2,498 | Catalog resources, not all concepts |
| Local Kùzu `Subject` | 1,010 | Subject nodes |
| Local Kùzu `JournalIssue` | 1,181 | Periodical issue nodes |
| **Local Kùzu total across these six node tables** | **6,081** | Current local multi-type graph node count |
| Local `okf_graph.json` | 537 concepts, 1,903 edges | Export for concept traversal; its `stats.total_concepts` is 537 |
| Tracked fixture | 84 concepts, 327 edges | Fallback slice, explicitly marked `fixture: true` |
| Hosted AntDeploy readiness | 520 concepts | Different deployed release/corpus; API does not expose its export hash |
| Historical plan claim | 5,151 nodes | No matching current snapshot or source manifest was found in this checkout |

The historical 5,151 figure cannot be used as a current release threshold. The Kùzu total counts six node types while the JSON and hosted readiness count concepts. The 537 versus 520 concept difference still needs export revision and source-manifest reconciliation.

## Managed services and migration state

- Public `https://archipelago.antideploy.com/api/readiness` returned HTTP 200 at 2026-10-06 01:23 UTC, with `x-archipelago-release: 554c8df13de83ba6757a66b1955f2a2573f2cdbc`, `concepts: 520`, `ingestion: false`, and `cache: supabase`. The response included Cloudflare headers (`cf-ray`, `server: cloudflare`) and `via: fly.io`. This proves Cloudflare is in the observed request path; zone ownership, DNS settings, WAF rules, and origin controls were not inspected.
- The connected Vercel account returned **zero** projects matching `archipelago`. No preview, project configuration, or Vercel inference endpoint exists in this snapshot.
- Supabase project `Archipelago` (`spllaastejfwclllfndp`) is `ACTIVE_HEALTHY`. The live migration list contains only `20260916152842 auth_roles` and `20260916152945 auth_performance`. The repository has six SQL files (`003_add_faculty_role.sql`, two Auth migrations, and three response/retrieval/graph cache migrations). Do not assume the faculty/cache schema is deployed. Public `profiles`, `credential_import_permissions`, and `credential_import_audits` have RLS enabled; the two import tables currently have zero rows. The security advisor still flags [leaked-password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection) as disabled.

## Platform decision and open gates

| Decision or risk | Required evidence before cutover |
| --- | --- |
| Target is Cloudflare → Vercel → Supabase with local ingestion/Kùzu | Record Cloudflare zone/domain configuration, Vercel project ID and preview URL, Supabase schema and RLS grants, and the approved local-to-cloud artifact contract. |
| Vercel currently has no project | Create a reviewable, slim inference build and preview only after separating local ML/OCR dependencies and raw corpus. [Vercel documents Flask WSGI support](https://vercel.com/kb/guide/ship-a-flask-app-on-vercel), but that does not prove this repository fits. |
| Vercel function fit | The current `requirements.txt` includes `torch`, `transformers`, `kuzu`, and OCR/ingestion dependencies. Vercel documents a [500 MB uncompressed Python function bundle limit and 4.5 MB request/response payload limit](https://vercel.com/docs/functions/limitations), and a [read-only filesystem with writable `/tmp` scratch space](https://vercel.com/docs/functions/runtimes). Test cold start, bundle size, corpus bootstrap, static assets, SSE, and actual chat output in preview. |
| Supabase schema gap | Reconcile repository migrations with the two live versions, then test staging migrations, RLS, Auth, cache invalidation, and vector/retrieval queries before promoting. [Supabase RAG permissions guidance](https://supabase.com/docs/guides/ai/rag-with-permissions) applies to any approved chunk table. |
| Raw document privacy | Graph and chat ingestion proxies now fail closed unless `ARCHIPELAGO_LOCAL_INGEST_URL` points to an allowlisted local HTTP origin; their requests cannot follow redirects. Focused tests prove no cloud fallback. Compose now starts the existing inference API locally as the sole ingestion worker and routes the graph service to it. Static YAML/startup tests pass, but container boot and real upload-to-citation remain unverified. |
| Extraction quality | Existing gold eval reported alias-aware F1 of 0.125 against a 0.35 gate. Keep unattended extraction/publication disabled until the larger held-out benchmark and review gate pass. |
| AntDeploy during migration | Keep it as the known rollback origin. No Cloudflare DNS or production traffic switch until Vercel preview, CI, staging Supabase, independent review, backup, and rollback pass. |

## Next release work

1. Finish the P0 endpoint ownership and secret/rights inventory without publishing credentials.
2. Close P1 Auth/RLS and cache migration gaps in a staging Supabase environment.
3. Build the slim Vercel preview and run a real six-contract/citation/streaming matrix.
4. Boot the Docker appliance and verify the complete local upload path, single-writer graph behavior, and rights-reviewed export before any cloud sync.
