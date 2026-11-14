# Archipelago — P0 Chat Intelligence, XKIRO Synthesis, Live OPAC & Latency Repair Report

**Date:** 2026-11-14  
**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Verified Production Commit:** `179abd8` (building on `d63c83b`)  
**Production Target:** `https://archipelago-blond.vercel.app/` (Vercel deployment `J6a4dkmj3W5w21hoURFiZwfNrxxJ`)

---

## 1. Root Causes Identified & Repaired

1. **Retired XKIRO Model Causing Silent LLM Failure:**
   - `host_inference/engine/llm.py` and `host_inference/.env` previously defaulted `XKIRO_MODEL` to `qwen/qwen3.8-max:free`, which returned `404 not_found_error` from `https://api.xkiro.com/v1/chat/completions`.
   - **Fix:** Updated `XKIRO_DEFAULT_MODEL` in `host_inference/engine/llm.py` (and `host_inference/.env`) to `cohere/command-a` (verified live `200 OK` on XKIRO), with automatic override if `XKIRO_MODEL` is unset or still set to `qwen/qwen3.8-max:free`. Added `MULTI_CONCEPT` and `DISCONNECTED` to `POLISH_ROUTES` / `POLISHABLE_ROUTES`.
2. **Capabilities Inquiry (`"What domains do you cover?"`) Rejected by Guardrail:**
   - **Fix:** Added `IntentCategory.CAPABILITY_INQUIRY` in `host_inference/engine/intent.py` and handled it before guardrail fallback in `host_inference/engine/route_logic.py`, returning a transparent breakdown of Academic domains, Indexed books & PDFs, Knowledge graph (`610` concepts), Research Intelligence, Institutional library catalogue, and Interactive learning (`render_graph: false`).
3. **`research_overlay` Hijacking Conceptual Explanations & Attaching Irrelevant Papers:**
   - `host_inference/hostapp/research_chat.py` previously set `research_overlay = True` after loose token overlap (`MIN_RELEVANCE_SCORE = 3`), causing `host_inference/hostapp/routes/chat.py` to skip XKIRO streaming.
   - **Fix:** Restricted `research_overlay = True` to `RESEARCH_EVIDENCE` (`out_of_corpus`), `_inventory_answer()`, and `EXPLICIT_SAVED_QUERY`. Added `GENERIC_ACADEMIC_TERMS` filtering, `_core_phrases()`, and `MIN_RELEVANCE_SCORE = 4`.
   - **Code-Owned Citations:** Added `host_inference/engine/citations.py` (`assign_canonical_citations`, `validate_response_citations`, `infer_synthesis_mode`) and integrated it into `host_inference/hostapp/routes/chat.py`, emitting `synthesis_mode` (`xkiro_synthesis`, `nvidia_fallback`, `verified_deterministic`, `provider_unavailable_fallback`).
4. **Graph Card Suppressed on Multi-Concept Queries:**
   - **Fix:** Updated `host_inference/engine/route_logic.py` and `host_inference/engine/answer.py` so `MULTI_CONCEPT` and `GRAPH_SYNTHESIS` preserve `anchor_concept` and `render_graph = True` whenever verified graph edges exist.
5. **UEM Kolkata Live OPAC Chat Integration:**
   - **Fix:** Implemented `lookup_chat_library_holding()` in `host_inference/hostapp/koha_bridge.py` using stdlib `html.parser` with HTTPS/host/path validation (`https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-*`), conversational stopword stripping (`_extract_library_search_terms`), and clean `KOHA_EXPORT_SNAPSHOT` fallback (returning `None` instead of mismatched snapshot rows when no match exists). Integrated into `_route_shelf_query()` in `host_inference/engine/answer.py`.
6. **Sign-In / Page-Switch Latency & Librarian Real-Time People Traffic Graph:**
   - **Fix:** Added a thread-safe 45s TTL `_principal_cache` in `host_inference/hostapp/security.py`, `Cache-Control: public, max-age=300` on static assets in `host_inference/hostapp/routes/static.py`, and `<link rel="prefetch" href="/chat">` in `login.html`.
   - **Fix:** Added `#people-traffic-panel` and `#traffic-chart` (`hourly_activity` / `daily_entries`, `total_entries`, `total_exits`, `total_qr_checkins`, `current_occupancy`, 15s auto-refresh toggle) in `host_inference/ui/librarian.{html,js}` and `host_research/ui/librarian.{html,js}`, plus mobile CSS grid overflow fix in `librarian.css`.

---

## 2. Verification Results

- **Lint & Unit Tests:**
  - `ruff check` across all modified Python modules: `All checks passed!`
  - `pytest` across 13 unit test files (`test_research_worker_bridge.py`, `test_s4_academic_automation.py`, `test_s1_multi_hop_reasoning.py`, `test_diagnostic_mcq.py`, `test_ui_link_integrity.py`, `test_research_reply.py`, `test_production_citation_hygiene.py`, `test_host_quota_routes.py`, `test_hosted_library_koha_bridge.py`, `test_academic_opac_live.py`, `test_auth.py`, `test_auth_boundary.py`, `test_librarian_workspace.py`): **118 passed, 0 failed**.
- **Live Production Verification (`https://archipelago-blond.vercel.app/`):**
  - `api_login_s`: `2.473s` | `/api/auth/me` (warm): `0.262s`, `0.267s` | Playwright UI login (`/login?next=/chat` -> `/chat`): `3.437s`
  - Page-switch timings: `/library` `5.584s`, `/graph` `2.988s`, `/research` `0.747s`, `/librarian` `0.694s`
  - **Test A (`"What domains do you cover?"`):** `200 OK` (`0.283s`), `route: CAPABILITY_INQUIRY`, `render_graph: false`
  - **Test B (`"Explain gradient descent and error backpropagation."`):** `200 OK` (`12.189s`), `route: MULTI_CONCEPT`, `synthesis_mode: xkiro_synthesis`, `provider: xkiro`, `model: cohere/command-a`, `render_graph: true`, `anchor_concept: gradient_descent`
  - **Test C (`"Explain deadlock"`):** `200 OK` (`7.284s`), `route: GRAPH_SYNTHESIS`, `synthesis_mode: xkiro_synthesis`, `model: cohere/command-a`, `render_graph: true`, `anchor_concept: deadlock`
  - **Test D (`"Give me a simple example"` follow-up):** `200 OK` (`6.931s`), `synthesis_mode: xkiro_synthesis`, preserved `deadlock` context
  - **Test E (`"Is Operating System Concepts available in the UEM library?"`):** `200 OK` (`6.026s`), `route: CATALOG_SHELF_ROUTING`; live OPAC from Vercel US-East timed out at 5s and snapshot fallback returned no false-positive match, emitting honest campus OPAC link (`https://uemk-opac.l2c2.co.in/`). (Local live OPAC verified `biblionumber=588` `"Operating System Concepts"` and `biblionumber=576` `"OPERATING SYSTEMS"`.)
  - **Test F (`"What papers do we have on QLoRA quantization?"`):** `200 OK` (`4.270s`), `synthesis_mode: xkiro_synthesis`, `anchor_concept: qlora`
  - **Test G (`"What is the recipe for butter chicken?"`):** `200 OK` (`0.274s`), `route: GUARDRAIL_INTERCEPT`
  - **Playwright Visual Check:** Verified `#people-traffic-panel`, `#traffic-chart`, and live XKIRO streaming + concept graph sidebar on `/chat`.
