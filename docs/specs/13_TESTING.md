# 13. Comprehensive Testing Strategy

This document outlines the testing infrastructure, coverage areas, and current status for the Archipelago project.

## 1. Test Infrastructure
- **Framework:** `pytest >=8.0` with `pytest-timeout>=2.2`
- **Config:** `pyproject.toml` (`[tool.pytest.ini_options]`)
- **Test Directory:** `Archipelago/tests/`
- **Subdirectories:** `unit/`, `integration/`, `e2e/`, `graph/`, `inference/`, `ingestion/`, `retrieval/`, `frontend/`, `performance/`, `fixtures/`
- **Conftest:** `tests/conftest.py` (16KB — extensive shared fixtures)
- **Coverage:** Targets `source=["archipelago", "okf"]` with `branch=true`

## 2. Current Test Status (HONEST)
- **Unit tests:** 905 passed, 0 failed, 6 skipped **[GOOD]**
- **Integration tests:** 26 passed, 13 failed, 6 errors **[BROKEN — needs fixing]**
- **E2E tests:** Opt-in via `RUN_LIVE_E2E=1` **[UNTESTED on production]**
- **Source link gate:** 17 tests (all passing)
- **Ingestion intake gate:** 25 tests (all passing)

## 3. Unit Test Coverage
- **Intent routing:** Tests all 6 contract types with representative user queries.
- **Graph traversal:** BFS, K-hop, prerequisites, unlocks, shortest path algorithms.
- **Citation generation:** Page links, Pearson URLs, and HF URLs validation.
- **OKF extraction:** Node/edge validity and schema compliance.
- **Cache:** Cache hit/miss scenarios, TTL expiry, and deduplication.
- **Rate limiting:** Per-minute, burst, and global limits.
- **Firewall:** Prompt injection patterns, code traps, and persona locks.

## 4. Integration Test Coverage
- Query → Intent → Graph → Retrieval → Synthesis flow.
- KùzuDB read and write operations.
- OKF Pipeline: PDF → chunks → concepts → graph.
- Supabase auth flow (mocked/when available).
- LLM provider fallback chain (xkiro → NVIDIA NIM → Gemini/Ollama).
- Cache service with Supabase backend.

## 5. E2E Test Queries (Section 24 Spec)

| Category | Query | Expected Intent | Graph? | Quiz? | Citation? | Library? |
|----------|-------|----------------|--------|-------|-----------|----------|
| Concept | "How does Softmax connect to Self-Attention?" | GRAPH_SYNTHESIS | Yes | No | Yes | Optional |
| Prereq | "What should I know before learning Transformers?" | GRAPH_SYNTHESIS | Yes | No | Yes | Optional |
| Learning | "I want to learn RAG" | MCQ_DIAGNOSTIC | Yes | Yes | Yes | Optional |
| Catalog | "Where can I find Database System Concepts?" | CATALOG_SHELF_ROUTING | No | No | No | Yes |
| Admin | "What are library opening hours?" | AUTH_GATEWAY | No | No | No | Yes |
| Upload | "Analyze this paper and show concept graph" | INGESTION_ANALYSIS | Yes | No | Yes | No |
| Greeting | "Hi" | GUARDRAIL_INTERCEPT | No | No | No | No |
| Off-domain | Random unrelated request | GUARDRAIL_INTERCEPT | No | No | No | No |

## 6. Ingestion Tests
- PDF parsing using PyMuPDF.
- OCR fallback using Tesseract on scanned images.
- ODS/CSV/Spreadsheet schema validation.
- Book metadata extraction.
- Graph append idempotency (ensuring running twice yields no duplicate nodes/edges).
- Library inventory CSV validation.
- Duplicate content detection.

## 7. Frontend Tests
- Landing page loads with correct institutional content.
- Chat UI correctly renders SSE (Server-Sent Events) streams.
- Graph visualization successfully renders nodes and edges (D3.js).
- Library page displays available books.
- Login authentication flow works properly.
- Reader gateway correctly redirects users based on roles.
- 3D assets (Three.js book showcase) load without errors.

## 8. Performance Tests
- **Directory:** `tests/performance/` exists.
- **Latency SLOs:** p50 < 500ms, p95 < 20s.
- Concurrent request handling and throughput.
- Cache efficiency under load.
- Graph traversal performance at scale.

## 9. Test Fixtures
- **Directory:** `tests/fixtures/` contains required test data.
- **Graph fixture:** `okf_graph.db.fixture-backup` (17MB)
- **Test PDFs:** `test_dpo_5pages.pdf`, `test_flashattention_5pages.pdf`, `test_moe_5pages.pdf`
- **Accuracy data:** `accuracy.json` — OKF extraction accuracy (currently only 2 chunks — needs more).

## 10. Remaining Test Debt
- **Critical:** Fix the 13 integration test failures.
- Add automated E2E tests that run against the staging AntDeploy environment.
- Add an ingestion model benchmark test (>100 sample chunks).
- Add Pearson deep-link resolution tests.
- Add personalized learning E2E test (full diagnostic → graph → citations flow).
- Add confidence calibration tests (when feature is built).
- Add fading mastery tests (when feature is built).
