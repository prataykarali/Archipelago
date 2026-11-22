# 10. Security Specification

This document outlines the comprehensive security architecture and known vulnerabilities for the Archipelago project. 

## 1. Authentication Architecture
- **Supabase JWT Authentication**: Managed via `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`.
- **Roles**: Support for `student` (default), `librarian`, and `admin`. Note: The `faculty` role is currently MISSING and requires a migration.
- **Production Guardrails**:
  - `ARCHIPELAGO_AUTH_REQUIRED=1` MUST be set in production.
  - **CRITICAL**: Currently set to `0` in the local `.env` configuration.
  - `ARCHIPELAGO_ALLOW_DEV_AUTH=0` (must stay 0 in prod) prevents dev authentication header bypass.
- **Librarian Token**: Protected endpoints (upload/delete/admin) use `ARCHIPELAGO_LIBRARIAN_TOKEN`. A legacy `ARCHIPELAGO_TOKEN` exists for backward compatibility.
- **Source References**:
  - `archipelago/auth.py`
  - `archipelago/supabase_auth/`
  - `host_inference/hostapp/security.py`

## 2. Known Security Vulnerabilities (HONEST)
The following vulnerabilities exist and must be addressed prior to any production deployment:
- **[CRITICAL]** `ARCHIPELAGO_AUTH_REQUIRED=0` in `.env` disables ALL authentication. This must be fixed before production.
- **[CRITICAL]** A hardcoded fallback token `librarian_secret_token_2026` is referenced in the code and must be rotated immediately.
- **[HIGH]** API keys are visible in plaintext in some documentation files. Rotate keys.
- **[MEDIUM]** Port `5150` (`graph_server.py`) lacks page-level auth gating.
- **[LOW]** No `faculty` role in the Supabase enum; a migration is pending.
- **Source**: `ARCHIPELAGO_AUDIT_AND_INSTRUCTIONS.md` (Findings F1, F2, F3, F9, F12).

## 3. Input Validation & Firewall
- **Max Query Length**: 500 characters, enforced via `MAX_QUERY_LENGTH` in `core/router.py`.
- **Prompt Injection**: Intercepted using 8 regex patterns in `_INJECTION_PATTERNS` (`core/router.py`).
- **Code Execution Trap**: The `CODE_TRAP` route connects to the `GUARDRAIL_INTERCEPT` contract.
- **Persona Lock**: `PERSONA_LOCK` route stops identity manipulation attempts.
- **Cypher Injection**: PATCHED. Uses `$q` parameter binding in catalog search.
- **Source References**: `archipelago/core/router.py`, `host_inference/engine/patterns.py`, `firewall.py`.

## 4. Private Data Protection
- **No Raw Data to LLMs**: NEVER send raw institutional data to external LLMs.
- **Data Filtering**: Filter private fields BEFORE inference, including student records, API keys, and internal DB names.
- **Context Constraints**: The context sent to the LLM is restricted strictly to synthesized graph context, never raw database contents.
- **Credentials**:
  - `ARCHIPELAGO_EXPOSE_READER_CREDENTIALS=0` must be set in production (kiosk-only feature).
  - E-resource credentials are dynamically loaded from `ARCHIPELAGO_ERESOURCE_JSON` and never hardcoded.
- **Source References**: `host_inference/hostapp/log_redaction.py`, `host_inference/engine/llm.py` (system prompt instructions).

## 5. Secrets Management
- Environment variables manage ALL secrets. These should never be committed to git.
- **Required Secrets**: `XKIRO_API_KEY`, `NVIDIA_API_KEY`, `GEMINI_API_KEY`, `HF_TOKEN`, `SUPABASE_SECRET_KEY`, `ARCHIPELAGO_LIBRARIAN_TOKEN`, `PEARSON_ACCOUNT_PASSWORD`, `APIFY_TOKEN`.
- `.env` is properly in `.gitignore`, while `.env.example` (161 lines) is committed as a template.
- Production uses AntDeploy env injection.
- **NEVER COMMIT**: API keys, database passwords, JWT secrets, or student credentials.

## 6. Rate Limiting
- **Per-minute**: 20 req/min (`ARCHIPELAGO_RATE_LIMIT_PER_MIN`)
- **Burst**: 50 (`ARCHIPELAGO_RATE_LIMIT_BURST`)
- **Global**: 500 (`ARCHIPELAGO_RATE_LIMIT_GLOBAL`)
- **Disable Flag**: `ARCHIPELAGO_RATE_LIMIT_DISABLED` (for dev usage only).
- **Source Reference**: `archipelago/inference/rate_limit.py`.

## 7. CORS & Cookie Security
- `ARCHIPELAGO_COOKIE_DOMAIN`: Configured for sibling subdomain sharing.
- `ARCHIPELAGO_COOKIE_SECURE`: Ensures HTTPS-only cookies.
- `ARCHIPELAGO_ALLOW_OPEN_MUTATIONS=0`: Ensure this is never enabled in production environments.

## 8. Web Fetch Compliance
- **Default Policy**: DENY-ALL default managed via `ARCHIPELAGO_FETCH_ALLOWLIST`.
- **Audit Trail**: Maintained via `ARCHIPELAGO_FETCH_AUDIT_LOG` (JSONL).
- **User Agent**: Enforces `ArchipelagoLibraryBot/1.0`.
- **Compliance**: Adheres strictly to `robots.txt` rules.
- **Source Reference**: `archipelago/ingestion/fetch_policy.py`.

## 9. Security Remediation Checklist
- [ ] Set `ARCHIPELAGO_AUTH_REQUIRED=1` in production `.env`
- [ ] Rotate all API keys (XKIRO, NVIDIA, Gemini)
- [ ] Remove hardcoded librarian token
- [ ] Add auth gate to port 5150 graph server
- [ ] Add faculty role migration to Supabase
- [ ] Audit all docs for exposed credentials
- [ ] Enable `ARCHIPELAGO_COOKIE_SECURE` in production
- [ ] Verify log redaction covers all sensitive fields
