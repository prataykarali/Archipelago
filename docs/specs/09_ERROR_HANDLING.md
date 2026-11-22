# Comprehensive Error Handling Specification

This document details the error handling, resilience, and fallback specifications for the Archipelago project.

## 1. Error Philosophy
- **No Stack Traces:** Never show raw stack traces to users.
- **Data Integrity:** Never fabricate data to hide errors.
- **Graceful Degradation:** Show an honest "not available" state rather than crashing.
- **Logging:** Log all errors server-side with structured logging.

## 2. LLM Provider Errors
- **Fallback Chain:** `xkiro` → `NVIDIA NIM` → `Gemini` → `Ollama (local)`
- **Pinning:** The `ARCHIPELAGO_LLM_PROVIDER` environment variable pins a single provider if needed.
- **Timeouts:** 
  - `STREAM_TIMEOUT_SECONDS=30`
  - `COMPLETE_TIMEOUT_SECONDS=40`
- **Spacing:** `COMPLETE_SPACING_SECONDS=1.2` between calls to prevent rate limits.
- **Provider Failure:** Return a grounded draft without LLM polish (handled in `llm.py` via `maybe_polish`).
- **Zero-Token Stream:** Fall back to raw grounded text.
- **Rate Limiting:** Gentle spacing is used to avoid triggering provider rate limits.
- **Source:** `host_inference/engine/llm.py`

## 3. Graph Errors
- **Missing Concept:** Fall back to nearest alias/phrase match.
- **Island Node (0 edges):** Return an honest "limited graph data" message rather than a BFS failure.
- **KùzuDB Connection Failure:** Execute read-only reconnect with exponential backoff.
- **Corrupted Graph DB:** Perform atomic swap from staging backup.
- **JSON Graph Missing:** Fall back to fixture slice.
- **Source:** `archipelago/graph/engine.py` (close/reopen logic), `host_inference/hostapp/corpus_bootstrap.py`, `host_inference/fixtures/`

## 4. Ingestion Errors
- **PDF Parse Failure:** Log error, skip document, continue batch.
- **OCR Failure:** Log and flag for manual review.
- **Duplicate Detection:** Idempotent merge prevents duplicate nodes/edges.
- **Invalid ODS/CSV Schema:** Return specific validation error (missing columns, bad types).
- **OKF Extraction Failure:** Log chunk, continue pipeline.
- **Source:** `ingestion_worker.py`, `ingestion_worker_job_mixin.py`

## 5. Authentication Errors
- **Expired JWT:** Return 401 with refresh hint.
- **Invalid Token:** Return 401, never reveal reason details.
- **Missing Librarian Token:** Return 403 on protected routes.
- **Supabase Unavailable:** Use local JWT verification fallback.
- **Source:** `archipelago/auth.py`, `host_inference/hostapp/security.py`

## 6. Network/External Service Errors
- **HuggingFace Unreachable:** Use local fixture corpus.
- **Supabase Cache Unreachable:** Fall back to in-memory LRU cache.
- **Pearson Portal Session Expired:** Show honest "authentication required" message.
- **Apify Actor Failure:** Log error, do not retry without explicit approval.

## 7. Frontend Error Handling
- **SSE Stream Interruption:** Reconnect with exponential backoff.
- **Graph Render Failure:** Show text-only response.
- **Asset Load Failure:** Degrade gracefully; never show a blank screen.

## 8. Rate Limiting Responses
- **Per-minute Exceeded:** HTTP 429 with Retry-After header.
- **Burst Exceeded:** HTTP 429.
- **Global Limit:** HTTP 503 Service Unavailable.
- **Source:** `archipelago/inference/rate_limit.py`

## 9. Error Logging & Monitoring
- **Structured Logging:** Uses structured JSON logging via Python logging module.
- **Telemetry:** P50/P90/P99 latency tracked.
- **Log Redaction:** Strips API keys, tokens, and passwords. NEVER log raw API keys, student data, or auth tokens.
- **Source:** `host_inference/engine/telemetry.py`, `host_inference/hostapp/log_redaction.py`
