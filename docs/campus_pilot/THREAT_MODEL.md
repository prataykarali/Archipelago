# Campus Pilot Threat Model — UEM Kolkata

**Scope:** Hosted Archipelago services (`host_inference`, `host_research`), Supabase Postgres/Auth/Storage, external LLM providers (`XKIRO`, `NVIDIA NIM`), private HuggingFace dataset (`Prataykarali/Library_books`), UEM Kolkata Koha OPAC (`uemk-opac.l2c2.co.in`), and local library workstation.

---

## 1. Protected Assets

| Asset | Sensitivity | Storage / Transit Location |
|---|---|---|
| Student & faculty Supabase JWTs / cookies | High | Browser `HttpOnly` cookie (`archipelago_token`), `Authorization: Bearer`, Vercel serverless RAM |
| Student queries, diagnostic quiz state, research runs | Medium–High (PII / Academic Privacy) | In-memory `user_traffic` (`deque(maxlen=2000)`), Supabase `research_intelligence.s5_runs`, external LLM API requests |
| Private HF dataset PDFs (`HF_TOKEN`) | High (Copyright / License) | `Prataykarali/Library_books` streamed via `host_inference/hostapp/routes/reader.py` |
| Pearson eLibrary subscription IDs & shelf metadata | High (Vendor Contract) | `pearson_bookshelf.json` in Supabase `archipelago-cache` bucket; deep links via `/open/<book_id>` |
| Librarian operational records (`catalog`, `circulation`, `orders`, `fines`) | Medium | Supabase `public.archipelago_librarian_records` |
| Supabase service-role key, `CRON_SECRET`, `HF_TOKEN`, LLM API keys | Critical | Vercel environment variables, local workstation `.env` |
| Institutional concept graph (`okf_graph.json`, Kùzu DB) | Medium | Local workstation + Supabase `archipelago-cache` bucket |

---

## 2. Trust Boundaries

1. **Public Internet -> Vercel Edge -> Flask WSGI (`host_inference`, `host_research`)**: Untrusted HTTP traffic, spoofable headers (mitigated via `X-Vercel-Forwarded-For` / `X-Real-IP` when `VERCEL` is set, `security.py:50, 663-674`), CSRF/Origin boundaries (`middleware.py:147-200`).
2. **Browser -> Supabase Auth (`publishable_key`) vs Server -> Supabase (`service_role`)**: Browser holds only `SUPABASE_PUBLISHABLE_KEY` (`routes/auth.py:96-111`); server holds `SUPABASE_SECRET_KEY`/`SUPABASE_SERVICE_ROLE_KEY` and enforces RLS/RPC boundaries (`supabase/migrations/20261118000000_prelaunch_rls_and_privilege_hardening.sql`).
3. **Hosted Flask -> External Services**: Outbound calls to `api.xkiro.com` / `integrate.api.nvidia.com` (LLM synthesis), `huggingface.co` (private PDF streaming), `uemk-opac.l2c2.co.in` (live OPAC HTML), OpenAlex/CrossRef/arXiv/Semantic Scholar (research discovery).
4. **Hosted Vercel <-> Local Library Workstation**: Staging review packets are uploaded to Supabase Storage (`s4_academic_automation_snapshot.json`), while immutable Kùzu graph publication is restricted to the local workstation (`analytics.py:366-372`).

---

## 3. Threat Actors

- **Unauthenticated Internet User**: Probes public URLs, attempts to download private dataset PDFs or exhaust LLM/serverless budgets.
- **Authenticated Student (Campus User)**: Attempts horizontal privilege escalation (reading peers' research runs or history), vertical privilege escalation (calling faculty/librarian/admin endpoints), quota bypass, or prompt injection.
- **Compromised Staff Browser / Shared Library Kiosk**: Leaves an active session open, triggers CSRF from another tab, or replays a logged-out bearer token.
- **External Provider / Malicious Metadata Source**: Returns malicious redirects from OPAC/campus URLs, formula-injection payloads in scholarly metadata, or prompt-injection strings in abstracts/pages.

---

## 4. STRIDE Threat Analysis & Verified Code Controls

| Category | Threat Scenario | Current Control (Code Evidence) | Verified Gap / Risk | Severity |
|---|---|---|---|---|
| **Spoofing** | Forged `alg=none` or malformed JWT | `_is_rejected_jwt_or_token()` (`security.py:125-143`) rejects `alg=none`, missing signatures, and oversized tokens; Supabase `/auth/v1/user` verifies signature. | None in token parser. | Mitigated |
| **Spoofing** | Replaying a logged-out JWT or cross-instance handoff ticket | `end_session()` stores SHA-256 token hash in process-local `_SHARED_REVOKED_BY_SCOPE` (`security.py:240-254`). | **P1-1**: Not shared across Vercel serverless instances; logged-out tokens remain valid on other warm instances until JWT expiry. | **P1** |
| **Tampering** | Cross-site state-changing request (CSRF) | `_check_csrf()` validates `Origin`, `Referer`, `Sec-Fetch-Site`, and HMAC `X-CSRF-Token` (`middleware.py:147-200`). | **P1-1**: If `ARCHIPELAGO_CSRF_SECRET` is unset, `_PROCESS_CSRF_KEY` (`security.py:73, 205`) is random per instance, breaking multi-instance CSRF validation. | **P1** |
| **Tampering** | Spreadsheet formula injection via scholarly metadata in Excel export | `_safe_workbook_cell()` prefixes `=`, `+`, `-`, `@`, `\t`, `\r` with `'` (`research_intelligence.py:54-62`). | Mitigated in `host_inference`. | Mitigated |
| **Repudiation** | Unaudited librarian/staff mutations | `audit_action()` logs JSON to `archipelago.research.audit` (`research_access.py:57-80`); `s6_analytics_audit_log` records library events in DB (`20261118000000:543-552`). | Stdout/logger audit trails on Vercel are ephemeral unless forwarded to an institutional log sink. | **P1** |
| **Information Disclosure** | **Unauthenticated download of private HF dataset PDFs** | `middleware.py:256-258` gates `/open/`, `/papers/`, `/read`. | **P0-1**: `reader.py:177` also exposes `/pdfs/<path:doc_path>` and `reader.py:117` exposes `/read/<path:subpath>`, neither of which is matched by `middleware.py:257` or rate-limited by `middleware.py:273`. Anonymous callers can stream private HF PDFs. | **P0** |
| **Information Disclosure** | **Cross-user access to another user's research run dossier (IDOR)** | `research_intelligence.py:132-138` scopes `_run(run_id)` to owner or manager. | **P0-2**: `intelligence_dossier()` (`research_intelligence.py:344-345`) falls back to `hosted_store().get_run(str(run_id), manager=True)` when `_run(run_id)` returns `None`, allowing any authenticated user to read any run's dossier by UUID. | **P0** |
| **Information Disclosure** | Student chat query leakage to staff or external LLMs | `_scrub_detail()` strips emails and tokens (`user_traffic.py:72-76`); `log_redaction.py` scrubs logs. | **P1-2**: 80-char query text is exposed in `GET /api/analytics/summary` (`recent_actions`) to all `ELEVATED_ROLES`; full queries are sent to external LLM APIs (`XKIRO`/`NVIDIA`) contrary to `PRIVACY_POLICY.md`. | **P1** |
| **Information Disclosure** | XSS / script injection in browser UI | Security headers (`nosniff`, `SAMEORIGIN`, `HSTS`, `Permissions-Policy`) set in `middleware.py:324-332`. | **P1-4**: CSP allows `'unsafe-inline'` scripts and external Play CDN (`middleware.py:53`, `host_research/app.py:313`). | **P1** |
| **Denial of Service** | Serverless concurrency or LLM/OPAC budget exhaustion | Student rolling 10-query/hour quota in Supabase (`security.py:538-620`, `20261114030000`); per-IP rate limits (`config.py:55-61`); OPAC 3s timeout + 2MB cap (`koha_bridge.py:26-27`). | **P1-1**: IP rate limits are process-local per serverless instance; `/pdfs/` bypasses rate limiting (`middleware.py:273`); faculty/librarian/admin have unrestricted chat quotas (`chat.py:255-256`). | **P1** |
| **Elevation of Privilege** | Student invoking staff/librarian/admin APIs | Middleware + route-level role checks (`ELEVATED_ROLES`, `LIBRARIAN_ROLES`, `ResearchCapability`) + Supabase RLS/RPC `service_role` lockdown (`20261118000000`). | Well-enforced on tested routes except **P0-2** (horizontal/vertical dossier read) and **P2-2** (duplicated role sets). | Mitigated (except P0-2) |

---

## 5. Mandatory Pre-Pilot Engineering Remediations (Coordinated via `@integrator`)

1. **Fix P0-1**: Add `"/pdfs/"` and `"/read/"` to both the auth guard (`host_inference/hostapp/middleware.py:257`) and API rate limiter (`middleware.py:273`), or remove the unguarded `/pdfs/` alias.
2. **Fix P0-2**: Remove the `manager=True` fallback in `intelligence_dossier()` (`host_inference/hostapp/routes/research_intelligence.py:344-345`) so only the run owner or verified `MANAGER_ROLES` can read a dossier.
3. **Fix P1-1**: Back session revocation, handoff tickets, and distributed rate limits with shared storage (Supabase/Redis), and require `ARCHIPELAGO_CSRF_SECRET` in production startup.
4. **Fix P1-2**: Update `PRIVACY_POLICY.md` for hosted cloud architecture; wire `DELETE /api/chat/history` to Supabase `s5_research_rpc('delete_user_data')` and quota/quiz cleanup; remove raw query `detail` from staff `recent_actions` or require explicit student consent.
5. **Fix P1-4**: Remove `'unsafe-inline'` and Tailwind Play CDN from production CSP by bundling static CSS/JS with nonces or hashes.
