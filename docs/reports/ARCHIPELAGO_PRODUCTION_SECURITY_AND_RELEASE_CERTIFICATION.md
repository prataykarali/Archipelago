# ARCHIPELAGO — PRODUCTION SECURITY CERTIFICATION, ROLE-BASED ACCESS AUDIT & RELEASE REPORT

**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Release Candidate Commit:** `7674238` (built on `a926fe874ea3ce13f4c897f018b272439c22fb32`)  
**Protected Preview Verified:** `https://archipelago-lqs7nreqc-archipelago-6383.vercel.app`  
**Main Production Target:** `https://archipelago-blond.vercel.app/`  
**Librarian Production Target:** `https://archipelago-librarian.vercel.app/` (separate Vercel team `shinaura`)  

---

## 1. Executive Release Verdict

**Verdict: `ARCHIPELAGO CONDITIONALLY RELEASED`**

All security, role-based access control (RBAC), Supabase RPC hardening, rate-limit/quota, and Academic Chat concept-mapping fixes have been implemented, verified by automated tests (`75 passed`, `ruff check` clean), live RBAC/JWT/RPC probes (`55/55` passed), and deployed to the **protected Vercel preview** (`https://archipelago-lqs7nreqc-archipelago-6383.vercel.app`).

**Why conditional (not immediate production switch):**
1. Production deployment via `vercel --prod` is gated by the active workspace security hook and requires explicit operator promotion in Vercel (`archipelago-6383` -> `archipelago-blond.vercel.app`).
2. `host_research/app.py` (`https://archipelago-librarian.vercel.app/`) belongs to a separate Vercel project/team (`shinaura`); its defense-in-depth route role checks were committed to the repository (`cd83273`) and await promotion on `shinaura`.

---

## 2. Phase 1 — Release Candidate & Infrastructure Verification

- **Production Readiness (`https://archipelago-blond.vercel.app/api/readiness`)**: `200 OK`, `mode: "inference-only"`, `concepts: 610`, `corpus: {"concepts": 610, "full": true, "source": "full"}`, `graph_version: "9818ac0e8fd3"`, `pearson_books: 40`, `research_intelligence: {"durable_storage_configured": true, "runtime_packaged": true}`.
- **Protected Preview Readiness (`https://archipelago-lqs7nreqc-archipelago-6383.vercel.app/api/readiness`)**: `200 OK`, identical live corpus (`610` concepts, `graph_version: "9818ac0e8fd3"`, durable Supabase Research Intelligence storage configured).
- **Librarian Production (`https://archipelago-librarian.vercel.app/`)**: `200 OK`.
- **Supabase Migrations**: Verified `20261114020000_s6_rpc_service_role_guc_fix.sql` and `20261114010000_s6_library_analytics_and_rpc_hardening.sql`:
  - `public.s5_research_rpc` uses `SECURITY DEFINER` with `SET search_path = pg_catalog, research_intelligence, public`.
  - `REVOKE ALL ON FUNCTION public.s5_research_rpc(text, jsonb) FROM PUBLIC, anon, authenticated; GRANT EXECUTE ... TO service_role;`.
  - `research_intelligence.s6_library_events` and `s6_analytics_audit_log` have `REVOKE ALL ... FROM PUBLIC, anon, authenticated`.
- **Vercel Configurations**: Both `host_inference/vercel.json` and `host_research/vercel.json` exclude `.env*` files from serverless bundles (`excludeFiles`).

---

## 3. Phase 2 — Role-Based Access Control (RBAC) Matrix & Live Verification

Live positive and negative tests were executed against `https://archipelago-blond.vercel.app` using real Supabase JWTs minted via `/auth/v1/admin/generate_link` + `/auth/v1/verify` across all 5 roles (**55 / 55 checks passed**):

| Surface / Endpoint | Unauth | Student | Faculty | Librarian | Admin |
|---|---|---|---|---|---|
| `GET /api/readiness`, `/api/auth/config`, `/api/library/data`, `/api/library/koha` | `200` | `200` | `200` | `200` | `200` |
| `GET /chat` (HTML shell) | `302` (`/login`) | `200` | `200` | `200` | `200` |
| `GET /api/auth/me`, `/api/graph/hubs`, `/api/research/intelligence/runs` | `401` | `200` | `200` | `200` | `200` |
| `POST /api/chat` | `401` | `200` | `200` | `200` | `200` |
| `GET /api/research/intelligence/monitors` | `401` | `403` | `200` | `200` | `200` |
| `POST /api/research/intelligence/monitors` | `401` | `403` | `200` | `200` | `200` |
| `GET /api/analytics/sources`, `/api/analytics/summary` | `401` | `403` | `200` | `200` | `200` |
| `GET /api/librarian/catalog` | `401` | `403` | `200` | `200` | `200` |
| `POST /api/librarian/catalog`, `POST /api/analytics/events` | `401` | `403` | `403` | `200/201` | `200/201` |
| `POST /api/ingest/upload` | `401` | `403` | `403` | `400/200` | `400/200` |
| `GET /api/academic-automation/status` | `401` | `403` | `200` | `200` | `200` |
| `GET /api/academic-automation/review/<job_id>` | `401` | `403` | `403` | `200` | `200` |
| `POST /api/academic-automation/review/<job_id>/decision` | `401` | `403` | `403` | `409` (`BLOCKED`) | `409` (`BLOCKED`) |
| `GET /api/internal/s5-monitor-tick`, `/api/research/intake/scheduled` | `401` | `401` | `401` | `401` | `401` |

### Defense-in-Depth Hardening Applied (`host_research/app.py`, commit `cd83273`)
- Added explicit role checks in `host_research/app.py` so `GET /api/librarian/<record_type>`, `GET /api/research/topics`, and `GET /api/library/opac/live` explicitly enforce `{"faculty", "librarian", "administrator"}` (`403` for students) in addition to `verify_user` (`401` for students on the live `archipelago-librarian.vercel.app` deployment).

---

## 4. Phase 3 & 4 — Rate Limits, Quotas, JWT/Auth, CORS & RPC Security

- **Burst Rate Limiting (`POST /api/chat`)**: 5 parallel simultaneous requests from one authenticated client yielded **3 × `429 rate_limited`** and **2 × `200 OK`**, confirming per-IP sliding-window and 1s mutation gap enforcement.
- **Student Daily Quota & Idempotency**: Enforced via `archipelago_runtime_consume` / `archipelago_runtime_query` (`40` daily AI queries, 10-query burst cooldown, UUID `request_id` deduplication).
- **Cross-User Isolation**: Faculty and Student attempts to read a Librarian's Research Intelligence run (`GET /api/research/intelligence/runs/9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3`) both returned `404 not_found`.
- **JWT & Token Tampering**:
  - Tampered JWT signature -> `401`
  - Malformed/garbage token -> `401`
  - `Bearer local-dev-token` on `/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` -> `401`
- **Direct Supabase RPC Protection**:
  - `POST /rest/v1/rpc/s5_research_rpc` as `anon` -> `401`
  - `POST /rest/v1/rpc/s5_research_rpc` as authenticated `student` -> `403`
  - `POST /rest/v1/rpc/archipelago_runtime_query` as authenticated `student` -> `403`
- **Security Headers & CORS**:
  - Verified `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`, and strict `Content-Security-Policy`.
  - `OPTIONS` preflight from untrusted origin `https://evil.example.com` returned `Access-Control-Allow-Origin: null` (no wildcard `*`).
- **S4 Academic Automation Boundary**: Hosted `POST /api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe/decision` remains strictly blocked (`409 workstation_required` / `publication_status: BLOCKED`), preserving human-in-the-loop workstation sign-off.

---

## 5. Phase 5 — Academic Chat Concept-Mapping Fixes

### Root Causes Fixed (`host_inference/engine/multi_hop_concepts.py`, commit `cd83273`)
1. **Test A (`"Explain gradient descent and backpropagation."`)**: Previously mapped `"backpropagation"` to `Decidability` via cosine fallback because `extract_concept_mentions` left `"Explain "` attached and `resolve_concept` had no whole-word lexical pass before `graph.rank()`. Fixed by stripping leading instructional verbs (`explain`, `define`, `describe`, `summarize`, `what is/are`) and adding a whole-word lexical match pass across node labels/IDs before embedding fallback.
   - **Verified on Protected Preview**: Maps to **`Gradient Descent`** (`gradient_descent`) and **`Error Backpropagation Algorithm`** (`error_backpropagation_algorithm`).
2. **Test B (`"Explain Transformers and self-attention."`)**: Previously mapped both to `Attention Mechanism` because hyphens were not normalized to underscores (`self-attention` -> `self_attention`) and `phrase_hits` picked the alphabetically first tie (`attention_mechanism`). Fixed by normalizing `[\s-]+` to `_` and ranking `phrase_hits` by exact label match and specificity.
   - **Verified on Protected Preview**: Maps to **`Transformer`** (`transformer`) and **`Self-Attention`** (`self_attention`).
3. **Unindexed Academic General Topics (`host_inference/engine/route_logic.py`, commit `7674238`)**: Queries like `"Explain Dijkstra's algorithm."` that match `ACADEMIC_DOMAIN_RE` without research-gap intent now route to `GENERAL_EXPLANATION` with a clean student-facing fallback (no raw prompt-instruction text).

---

## 6. Phase 6, 7 & 8 — Browser Acceptance, Mobile Responsiveness & Latency

- **Automated Regression Suite (`pytest` + `ruff`)**:
  - `ruff check host_inference/engine/multi_hop_concepts.py host_inference/engine/route_logic.py host_research/app.py`: **All checks passed**.
  - Focused 11-file test run (`test_auth.py`, `test_auth_boundary.py`, `test_supabase_auth.py`, `test_rate_limit.py`, `test_rate_limit_tiers.py`, `test_host_account_quota.py`, `test_host_quota_routes.py`, `test_research_transport.py`, `test_s1_multi_hop_reasoning.py`, `test_s6_platform_integration.py`, `test_ui_link_integrity.py`): **75 passed in 21.67s**.
- **Playwright Browser Verification (`1440×960` desktop & `390×844` mobile)**:
  - Unauthenticated `/chat` redirects cleanly to `/login?next=/chat`.
  - Mobile `390×844` horizontal overflow check: `false` on both `/chat` and `/analytics`.
  - Updated screenshot archive: `artifacts/validation/final-ui-audit/Archipelago_Final_UI_Audit.zip` (`24` screenshots).
- **Live Latency Benchmarks (`https://archipelago-blond.vercel.app`)**:
  - `GET /api/readiness` (`n=6`): **p50 = `420.4 ms`**, **p95 = `425.9 ms`**, max = `1128.4 ms` (`6/6` `200 OK`).
  - `GET /api/graph/hubs` (`n=6`): **p50 = `1540.7 ms`**, **p95 = `1801.5 ms`**, max = `1972.3 ms` (`6/6` `200 OK`).

---

## 7. Next Action for Operator

1. Promote the verified protected preview **`https://archipelago-lqs7nreqc-archipelago-6383.vercel.app`** (commit `7674238`) to production (`https://archipelago-blond.vercel.app/`) via the Vercel dashboard or authorized `vercel promote` CLI.
2. Deploy `host_research/` from commit `7674238` to the `shinaura` Vercel project (`https://archipelago-librarian.vercel.app/`).
