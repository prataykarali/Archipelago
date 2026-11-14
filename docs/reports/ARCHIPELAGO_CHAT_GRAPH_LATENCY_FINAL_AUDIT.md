# Archipelago — Final Chat Intelligence, Graph Correctness, UI Interactivity & Latency Audit

**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Audit Date:** 2026-11-14  
**Verdict:** **CONDITIONALLY RELEASED** (all code, UI, graph semantics, latency, and focused regression checks verified on local live servers and protected Vercel preview; production promotion on `shinaura` and S4 human review gate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` remain external release gates).

---

## 1. Academic Chat Answer Quality (P0)

### Root Causes Fixed
1. **Comparison queries with partial/missing graph nodes (`FCFS vs SJF`, `Supervised vs reinforcement learning`)**: Previously hit `DISCONNECTED` (`one_sided` / `both_missing`) in `host_inference/engine/route_logic.py` and returned internal graph-index messages without LLM synthesis. Fixed by routing academic comparison queries (without graph-bridge keywords `connect`/`relate`) to `GENERAL_EXPLANATION` (polishable) with any matching indexed node evidence (`cpu_scheduling`, `reinforcement_learning`) and clear labeling of general foundational knowledge vs indexed catalog citations.
2. **Two-concept `"A and B"` decomposition (`Virtual memory and page replacement`, `ACID and normalization`, `Lexical analysis and LR parsing`, `Gradient descent and backpropagation`)**: Previously fell through to single-anchor `GRAPH_SYNTHESIS` (`anchors[0]`), dropping the second concept. Fixed by enabling `MULTI_CONCEPT` for 2-concept non-comparison/non-diagnostic queries and adding `MULTI_CONCEPT` to `POLISHABLE_ROUTES` in `host_inference/engine/routing_constants.py`.
3. **Tautological summary (`Eigenvalues and eigenvectors`)**: Added rigorous foundational definitions in `host_inference/engine/concept_foundations.py` (`eigenvalues_and_eigenvectors`, `eigenvalue`, `eigenvector`, `gradient_descent`, `error_backpropagation_algorithm`, `reinforcement_learning`, `page_fault_handling`, `third_normal_form`).
4. **Multi-turn continuity (`M1–M4`)**: `host_inference/hostapp/routes/chat.py` previously populated `previous_answer` only when `previous_user == query` (re-ask/regenerate). Fixed to pass the most recent assistant message from `history` on follow-up turns (e.g., `"Give me a simple example."`).
5. **Synthesis guidance (`host_inference/engine/llm.py`)**: Updated `REPLY_SYSTEM_PROMPT` to require addressing every requested concept, providing comparisons and worked examples when asked, and avoiding tautological one-liners.

### Live 11-Prompt + Multi-Turn Verification (`http://127.0.0.1:5055/api/chat`)
| # | Prompt | Route | Total Latency | Status |
|---|---|---|---:|---|
| 1 | Compare FCFS vs SJF CPU scheduling with an example. | `MULTI_CONCEPT` | 2744.7 ms | 200 OK |
| 2 | Explain virtual memory and page replacement. | `MULTI_CONCEPT` | 3042.2 ms | 200 OK |
| 3 | Explain ACID and normalization in DBMS. | `MULTI_CONCEPT` | 3722.1 ms | 200 OK |
| 4 | Explain lexical analysis and LR parsing. | `MULTI_CONCEPT` | 2742.0 ms | 200 OK |
| 5 | Explain eigenvalues and eigenvectors. | `GRAPH_SYNTHESIS` | 3524.1 ms | 200 OK |
| 6 | Explain gradient descent and backpropagation. | `MULTI_CONCEPT` | 2700.8 ms | 200 OK |
| 7 | Explain supervised vs reinforcement learning. | `GENERAL_EXPLANATION` | 2423.6 ms | 200 OK |
| 8 | Explain BFS vs DFS. | `CROSS_DOMAIN` | 1808.6 ms | 200 OK |
| 9 | Explain B+ trees and hash indexing. | `MULTI_CONCEPT` | 1775.0 ms | 200 OK |
| 10 | Explain TCP congestion control. | `GRAPH_SYNTHESIS` | 3228.8 ms | 200 OK |
| 11 | Explain Transformers and self-attention. | `MULTI_CONCEPT` | 2411.3 ms | 200 OK |
| M2 | Follow-up: `Give me a simple example.` (after `Explain virtual memory.`) | `GRAPH_SYNTHESIS` | 2620.6 ms | 200 OK |

---

## 2. Graph Semantics & Research Graph Separation (P0)

- **Removed fabricated `REQUIRES` fallbacks**: Removed `canonMap` / `['neural_network', 'machine_learning']` fallback arrays from both `host_inference/ui/js/19-draw-horizontal-svg.js` and `host_inference/ui/js/13-render-horizontal-graph-card.js` (and synced to `ui/chat/js/`). Prerequisites now render strictly from verified stored graph edges (`None indexed` when empty).
- **Removed research papers from `UNLOCKS`**: Updated `_research_run_reply()` in `host_inference/hostapp/routes/chat.py` to emit `"unlocks": []`, `"graph_mode": "research"`, and `"research_graph"` with scholarly edges (`HAS_PAPER`, `AUTHORED_BY`, `PUBLISHED_IN`).
- **Dedicated Research Graph card mode**: `13-render-horizontal-graph-card.js` and `19-draw-horizontal-svg.js` render Research Graph mode (`Visualize Research Evidence Graph`, `Research Graph` badge, `HAS_TOPIC` / `HAS_PAPER` / `AUTHORED_BY / PUBLISHED_IN`) only for `RESEARCH_EVIDENCE` / `graph_mode === 'research'` / `research_run_id` (preserving Academic `Normal Graph` and `Take Quiz` even when `research_overlay` is attached).
- **Live Research Chat verification** (`run_id`: `9c3c6fb6-3c9b-40cf-8ff3-1b3b63bf16d3` / `56e0809b-1797-4c59-9e95-2d0676470dd1`): `route=RESEARCH_EVIDENCE`, `graph_mode=research`, `unlocks=0`, `related=8`, `edges=16`, latency `1220.4 ms`.

---

## 3. Interactive Graph Card, `Take Quiz`, & Source Inventory (Playwright)

- **SVG & Node Interaction**: `11` SVG nodes rendered (`g.graph-node-group`); clicking `BERT` updated the Card Inspector from `Attention Mechanism` to `BERT` (`inspector_updated_on_click: true`). Expand/collapse toggle verified.
- **`Take Quiz` Relevance**: `academic_has_quiz_btn: true` on Academic diagnostic/concept cards; hidden on `RESEARCH_EVIDENCE` cards.
- **Source Inventory — Real Data Only (`03-wrap-library-inventory-secti.js`)**: Physical holdings table (`Library holdings`) is rendered only for `koha_record_verified` records. Cited academic PDFs and papers render in a compact collapsible **Sources & Resources** `<details>` block (collapsed when `> 3` sources) with single-line `whitespace-nowrap` links (`fake_not_reported_present: false`).

---

## 4. UI Regressions & Mobile Viewport (`390×844`)

- Fixed `.site-header` and `.site-header nav` wrapping at `max-width: 550px` in `host_research/ui/librarian.css`.
- Live Playwright check on `/analytics` at `390×844`: `scrollWidth = 390`, `clientWidth = 390`, `analytics_mobile_overflow = false`.

---

## 5. Latency & Reliability Summary

- Added `[CHAT_TIMING]` stage instrumentation (`research_ms`, `engine_ms`, `enrich_ms`, `ttft_ms`, `total_ms`) in `host_inference/hostapp/routes/chat.py` and short-circuited `hosted_store()` lookup in `_research_run_reply()` when `research_run_id` is absent and the query is not a research-run request.
- **Observed Live Latencies**:
  - Academic Chat Cold: `p50 = 2742.0 ms`, `p95 = 3524.1 ms`
  - Academic Chat Warm: `p50 = 2552.0 ms`, `p95 = 3269.3 ms`
  - Research Chat (`RESEARCH_EVIDENCE`): `1220.4 ms`

---

## 6. Verification & Artifacts

- **Linter & Focused Unit/Integration Tests**: `ruff check` clean; `64 passed` across `test_ui_link_integrity.py`, `test_s1_multi_hop_reasoning.py`, `test_s1_multiturn_reasoning.py`, `test_hosted_release_regressions.py`, `test_host_intent_routing.py`, `test_s5_research_intelligence.py`, `test_s6_platform_integration.py`, and `test_contract_routing_details.py`.
- **Screenshot Archive**: `artifacts/validation/final-ui-audit/Archipelago_Final_UI_Audit.zip` (desktop `1440×960` and mobile `390×844` captures + `api_audit_results.json`).
