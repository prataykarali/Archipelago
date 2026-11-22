# Changelog

All notable changes to Archipelago are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]
### Planned
- Increase MCQ_MAX_QUESTIONS to 10
- Query Inspector / Glass-Box diagnostics
- Fading mastery with time decay
- Confidence-aware MCQ diagnostics
- Adaptive question budget (3-10)
- Learning preference selector
- OPAC live API integration
- Librarian aggregate dashboard
- Faculty diagnostic mode
- Prataykarali/graphier HuggingFace dataset population

## [Phase 5] - 2026-10-02 — Deployment Readiness
### Added
- /health and /ready endpoints
- Dockerfile healthchecks
- Repaired CI YAML

## [Phase 4] - 2026-10 — UI Redesign & Open Reading
### Changed
- Landing page aligned to reference design (dark aesthetic, KNOWLEDGE OPERATIONS eyebrow)
- Removed login barriers for public campus reading
### Added
- Secured staff routes (/api/ingest/*, /api/users) behind 401 gates

## [Phase 3] - 2026-10 — Librarian Ingestion
### Added
- Mention-a-Book auto-populate (mention.py)
- Scanned page OCR intake via Tesseract (page_image/)
- Spreadsheet merge (spreadsheet.py) — ODS/CSV/XLSX with idempotency

## [Phase 2] - 2026-10 — In-Chat Graph & Roadmap
### Fixed
- In-chat graph was returning 1 node / 0 edges → connected live Kùzu graph
- Citation ranking tuned for title-weighted relevance
### Verified
- 5-MCQ diagnostic roadmap loop working

## [Phase 1] - 2026-09 — Source Links
### Added
- 17-test source-link gate
- 40/40 Pearson books → exact reader URLs (#book/{uuid}/page/{page})
- 21/21 HuggingFace files → exact blob/main/ URLs

## [Phase 0] - 2026-09 — Clean Architecture Split
### Changed
- Split 7 oversized modules (>500 lines) into sub-packages
  - routes_chat.py (1,026 lines) → inference/routes/chat/ (8 modules)
  - citations.py → inference/citations/ (3 modules)
  - library_catalog_api.py → inference/library_catalog/ (5 modules)
  - llm_gateway.py → inference/llm_gateway/ (5 modules)
  - intent_gate.py → inference/intent_gate/ (3 modules)
  - supabase_auth.py → supabase_auth/ (4 modules)
  - api/app.py → api/ (5 route modules + middleware)
### Fixed
- Critical syntax error in ingestion_worker_job_mixin.py
- REPO_ROOT path resolution regression in chat_server/
- Cypher injection vulnerability in /api/catalog/search (parameter binding)
- Fabricated catalog records

## [Initial] - 2026 — Foundation
### Built
- KùzuDB OKF graph engine with atomic swap
- 6-contract deterministic routing system
- SSE streaming chat with inline graph cards
- Hybrid retrieval (Snowflake Arctic + Lexical)
- LLM gateway (xkiro → NVIDIA → Gemini → Ollama)
- Supabase authentication
- PDF ingestion pipeline
- OKF extraction with lib-qwen
- D3.js graph explorer
- Library catalog browser
- 3D book showcase (Three.js)
- Pearson eLibrary integration
- HuggingFace corpus integration
