Granular, actionable microtasks for production readiness. Each task should be small enough for a single focused session.

### Format: Grouped by priority tier, each task with estimated effort and dependencies.

**TIER 0 — CRITICAL (Security & Blocking Bugs)**
1. Set ARCHIPELAGO_AUTH_REQUIRED=1 in production .env and .antideploy.json — 15min
2. Rotate all API keys (XKIRO, NVIDIA, Gemini, HF) and update in AntDeploy secrets — 30min
3. Remove hardcoded 'librarian_secret_token_2026' from .env and code — 15min
4. Add auth middleware to graph_server.py port 5150 — 1h
5. Apply faculty role migration to Supabase (003_add_faculty_role.sql) — 30min
6. Audit all markdown docs for exposed API keys and redact — 1h
7. Resolve Git LFS: ui_assets/*.mp4 and *.png files are 131-byte stubs (LFS pointers not pulled) — 30min

**TIER 1 — CORE FUNCTIONALITY GAPS**
8. Change MCQ_MAX_QUESTIONS from 4 to 10 in host_inference/engine/diagnostics.py — 15min, also update CHECKPOINT_QUESTIONS
9. Wire book stack frontend: replace 28-byte stub books_showcase_src.tsx with actual component from root books_showcase_src.tsx (68KB) — 2h
10. Populate Prataykarali/graphier HuggingFace dataset using scripts/sync_to_graphier.py — 1h
11. Complete remaining 22 Pearson book UUIDs in data/catalogs/pearson_bookshelf.json — 2h
12. Fix Pearson cold redirect issue (session cookie requirement) in resolver — 2h
13. Run ingestion model benchmark on >=100 chunks and update accuracy.json — 4h
14. Fix 13 integration test failures (update fixtures, reconcile baseline) — 4h

**TIER 2 — ADVANCED PERSONALIZED LEARNING (from spec)**
15. Add Fading mastery state (🟠) with time decay to node mastery model — 4h
   - Add fields: last_verified, verification_count, confidence to mastery state
   - Implement lightweight time decay (24-day threshold)
   - Single micro-verification question to restore confidence
16. Add confidence calibration to MCQ UI — 3h
   - Add 🔴 Guessing / 🟡 Somewhat sure / 🟢 Very sure selector
   - Map correctness×confidence to mastery interpretation table
17. Implement adaptive question budget — 3h
   - Initial: 3 questions, Max: 10
   - Stop when coverage sufficient (graph traversal satisfied)
   - Coverage-aware K-hop distribution across prerequisite hops
18. Add learning preference selector — 3h
   - Mathematical / Code / Conceptual trajectories
   - Influence edge weighting and question selection
19. Implement Socratic misconception detection — 4h
   - Check graph for contrasts_with/variant_of edges before flagging
   - Only trigger when graph evidence exists
20. Build Query Inspector / Glass-Box console — 6h
   - Collapsible panel showing: intent, vector anchor, cosine score, K-hop depth, graph path, sources, OPAC result, context tokens, provider info
   - Student view: collapsed by default
   - Developer view: expanded with full trace

**TIER 3 — LIBRARY INTELLIGENCE**
21. Build OPAC live API integration (http://uemk-opac.l2c2.co.in) — 8h
22. Implement Gap → Physical Library Mapping — 4h
   - When learning gap identified (🔴 Missing), map concept to physical resources
   - Show call number, location, availability
23. Build librarian aggregate dashboard — 6h
   - Most requested concepts, demand vs availability, high-demand resources
24. Build faculty diagnostic mode — 4h
   - View: target concept, questions asked, answers, confidence, mastery transitions, recommended resources
25. Add "Why Am I Seeing This?" transparency popovers — 3h

**TIER 4 — ARCHITECTURAL CLEANUP**
26. Resolve host_inference/ vs archipelago/ duplication — 16h (MAJOR)
   - Decide: which is canonical runtime?
   - Consolidate or clearly separate concerns
   - Update all imports and test paths
27. Retire 7 root shim files — 2h
28. Fix ~385 magic numbers in legacy modules — 8h
29. Implement okf_watcher.py daemon for auto-catalog watching — 4h
30. Add automated graph population cron job — 2h
31. Add PDF chunker section filtering (skip TOC, bibliography, index) — 2h

**TIER 5 — DEPLOYMENT & MONITORING**
32. Run full E2E test suite against archipelago.antideploy — 2h
33. Set up structured JSON logging in production — 2h
34. Add Supabase cache tables (ai_response_cache, retrieval_cache, graph_cache) — 2h
35. Configure production rate limiting — 1h
36. Set up monitoring/alerting for LLM provider failures — 2h
37. Document deployment runbook for AntDeploy — 2h
