Production readiness checklist — every item must be verified before declaring production-ready.

### Format: Checkbox list grouped by category, with current status noted.

**Architecture & Code**
- [ ] Codebase is modularized into clean packages — PARTIAL (host_inference/engine is production, archipelago/ is refactored but not primary runtime; duplication exists)
- [ ] All files ≤500 lines (AGENTS.md rule) — MOSTLY (Phase 0 split done, some legacy files may exceed)
- [ ] Root shim files retired — NOT DONE (7 shim files remain)
- [ ] Resolve host_inference/ vs archipelago/ duplication — NOT DONE (critical architectural debt)

**Functionality**
- [ ] Intent routing works for all 6 contracts — WORKING
- [ ] Domain detection works — WORKING (3-tier confidence gating)
- [ ] Graph retrieval works — WORKING (KùzuDB + JSON in-memory)
- [ ] K-hop traversal works — WORKING (BFS in graph.py)
- [ ] Page citations work — WORKING (40 Pearson, 21 HF deep links)
- [ ] Pearson deep-linking handled correctly — PARTIAL (cold redirect fails without session cookie)
- [ ] HuggingFace deep-linking works — WORKING
- [ ] Prataykarali/graphier populated correctly — NOT DONE (scripts exist but dataset empty/untested)
- [ ] Book stack works — PARTIAL (books_showcase_src.tsx is 28-byte stub, library_showcase_3d.js is 36-byte stub in frontend/)
- [ ] Mini graph works — WORKING (SVG inline in chat)
- [ ] Personalized graph works — WORKING (but limited to 4 questions, spec says 10)
- [ ] Diagnostic quiz works — WORKING (MCQ_MAX_QUESTIONS=4, MUST be 10)
- [ ] Normal graph works — WORKING
- [ ] Library inventory works — WORKING
- [ ] OCR works — WORKING (Tesseract)
- [ ] ODS/spreadsheet ingestion works — WORKING
- [ ] Graph append works — WORKING (idempotent via Kahn DAG validation)
- [ ] Inventory append works — WORKING
- [ ] Ingestion model benchmarked — NOT DONE (accuracy.json has only 2 chunks)
- [ ] NVIDIA integration works — CONFIGURED (API key required)
- [ ] XKIRO integration works — WORKING
- [ ] Private data filtered before inference — WORKING (system prompt instructs, log redaction exists)
- [ ] Caching works — PARTIAL (cache_service.py exists, needs Supabase tables)
- [ ] Rate limiting works — WORKING

**Visual Assets**
- [ ] 3D assets intact — YES (22 assets in ui_assets/)
- [ ] Videos intact — YES (6 .mp4 files, BUT most are 131-132 byte stubs — likely LFS pointers not resolved)
- [ ] Animations intact — YES
- [ ] Landing page has IEM/UEM/Archipelago content — WORKING

**Security**
- [ ] ARCHIPELAGO_AUTH_REQUIRED=1 in production — NOT DONE
- [ ] All API keys rotated — NOT DONE
- [ ] Hardcoded tokens removed — NOT DONE
- [ ] Port 5150 auth gated — NOT DONE
- [ ] Faculty role migration applied — NOT DONE
- [ ] Log redaction verified — PARTIAL

**Testing**
- [ ] Unit tests pass — 905/905 PASSING
- [ ] Integration tests pass — 26 pass, 13 FAIL, 6 errors
- [ ] E2E tests pass — NOT VERIFIED on production
- [ ] Ingestion E2E tested — PARTIAL
- [ ] Regression suite complete — PARTIAL

**Deployment**
- [ ] Deployed to archipelago.antideploy — EXISTS but health unknown
- [ ] /health endpoint responds — EXISTS
- [ ] /api/readiness responds with corpus info — EXISTS
- [ ] Real E2E request succeeds on production — NOT VERIFIED

**Advanced Features (from spec — NOT YET BUILT)**
- [ ] Query Inspector / Glass-Box Diagnostics
- [ ] Fading mastery with time decay
- [ ] Confidence-aware diagnostics
- [ ] Socratic misconception detection
- [ ] Learning preference selector
- [ ] Adaptive question budget (3-10 dynamic)
- [ ] Gap → Physical Library Mapping
- [ ] OPAC live integration
- [ ] Faculty diagnostic mode
- [ ] Librarian aggregate dashboard
- [ ] "Why Am I Seeing This?" transparency
