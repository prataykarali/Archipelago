# 00_MASTER_RULES

This document is the **SUPREME constraint document** for the Archipelago project. Every other document in the 01-17 series defers to these rules. All developers and agents must strictly adhere to these principles at all times.

## 1. Preservation Rules (STRICT)
- **NEVER** remove 3D assets, videos, animations, mascots, or visual effects.
- **NEVER** delete functionality just because it is currently unused.
- **NEVER** simplify working components without explicit approval.
- **PRESERVE** all existing UI visual identity.

## 2. Honesty Rules
- **NEVER** claim a feature works unless it has been E2E tested.
- **NEVER** hardcode or fake responses to make demos look good.
- **NEVER** fabricate book titles, page numbers, graph edges, or citations.
- **DISTINGUISH CLEARLY** in all documentation and logs: `works` vs `exists but broken` vs `not built`.
- **ZERO TOLERANCE** for hallucinated catalog records, shelf locations, or page URLs.

## 3. Security Rules
- **NEVER** commit API keys, tokens, or secrets to git.
- **NEVER** send private student data to external LLMs.
- **NEVER** expose raw credentials in the UI or in logs.
- **NEVER** disable auth enforcement in production.
- **ALWAYS** filter private data BEFORE external inference calls.

## 4. Architecture Rules
- The **Six Response Contracts** are the immutable foundation: 
  1. `GRAPH_SYNTHESIS`
  2. `CATALOG_SHELF_ROUTING`
  3. `AUTH_GATEWAY`
  4. `MCQ_DIAGNOSTIC`
  5. `INGESTION_ANALYSIS`
  6. `GUARDRAIL_INTERCEPT`
- Every route maps to exactly one contract type.
- Graph rendering is a pure function of the contract type.
- **Don't optimize by deleting complexity** — make it explicit, modular, and testable.
- Use existing technology choices (Flask, KùzuDB, Supabase, Vanilla HTML5/JS/D3/Three.js) unless replacement is fundamentally justified.

## 5. Testing Rules
- No feature is complete without regression tests.
- Integration tests must use real (or staging) services, not mocked-to-pass implementations.
- E2E tests must hit actual deployed endpoints.
- The test matrix must cover edge cases and ambiguous Natural Language (NL) queries.

## 6. Ingestion Rules
- Test the ingestion model BEFORE using it in production.
- Graph updates must be append-safe and idempotent.
- Running the same ingestion twice must NOT create duplicate nodes/edges.
- The OCR pipeline must be validated end-to-end.
- **NEVER** upload copyrighted Pearson full-text to public repositories.

## 7. Inference Rules
- Only send the minimum relevant context to NVIDIA/XKIRO/Gemini (do not send the entire DB).
- Implement retry, timeout, rate limiting, and provider fallbacks.
- Cache deterministic responses to minimize API costs.
- Greetings and static queries should NOT trigger expensive LLM calls.

## 8. Cross-Reference
This document is referenced by ALL other documentation files (01-17). When resolving conflicts in specifications or behavior, **00_MASTER_RULES** supersedes all other directives.
