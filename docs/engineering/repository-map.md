# Archipelago Repository Map & W0 Reconnaissance Report

**Date**: 2026-10-06  
**Repository Root**: `/home/pratay-karali/Desktop/archipelago/Archipelago`  
**Current Branch**: `codex/production-hardening`  
**Status**: W0 Reconnaissance Completed  

---

## 1. Git State and Workspace Inventory
- **Current Branch**: `codex/production-hardening`
- **Git Status**: 100+ modified files (primarily in `tests/` and `ui/`), untracked files (`.codex-release/`, `.release-artifacts/`, `host_inference/hostapp/routes/ingest.py`, etc.).
- **Safety Guarantee**: Zero destructive commands (`git reset`, `git clean`) executed. All visual assets and data files preserved.

---

## 2. Application & Runtime Entry Points
1. **Primary Production Entry Point (`start.sh`)**:
   - Launches `python graph_server.py` on background port `5050` (internal KùzuDB/SQLite service).
   - Launches Gunicorn WSGI process on `$PORT` (default 8080) serving `archipelago.apps.inference_app:app`.
2. **Hosted Container Entry Point (`host_inference/hostapp/wsgi.py`)**:
   - Flask application generated via `host_inference.hostapp.factory.create_app()`.
3. **Legacy / Development Entry Points**:
   - `chat_server.py`: Legacy standalone chat server.
   - `inference_server.py`: Legacy inference server wrapper.
   - `app.py`: Minimal Flask test entrypoint.

---

## 3. Frontend / UI Trees & Asset Mapping
- **Active Web Application (`ui/chat/`)**:
  - `index.html`: Main interactive chat and graph visualizer (711 lines).
  - `library.html`: Physical/digital OPAC catalog search (1075 lines).
  - `landing.html`, `login.html`: Landing and auth interfaces.
  - `ui/chat/js/`: Client scripts for topology, book rendering, keyword highlighting, and API streaming.
- **Hosted UI Mirror (`host_inference/ui/`)**: Duplicate copy of `ui/chat/` for standalone hosted image builds.
- **React 3D Book Showcase (`frontend/book-stack/books_showcase_src.tsx`)**: 1844-line Three.js / React interactive book stack component.
- **Ingestion Frontend (`ingestion-frontend/`)**: HTML/JS staging and review dashboard for librarians.
- **Unconsolidated Stubs (`frontend/`)**: Contains partial layout copies (`frontend/ui/`, `frontend/library/`).

---

## 4. Inference & Request Routing Path
- **API Entrypoint**: HTTP POST `/chat/stream` or `/chat` -> `archipelago/apps/inference_app.py`.
- **Intent Gate (`archipelago/inference/intent_gate/`)**: Classifies user queries into 10 intent types (greeting, concept explanation, relationship, prerequisite, library lookup, shelf location, MCQ diagnostic, ingestion, auth, out-of-domain).
- **Master Router (`archipelago/inference/routing.py`)**: 1307-line central router directing queries to catalog, graph synthesis, MCQ diagnostic, auth boundary, or guardrail fallback.
- **LLM Synthesis (`archipelago/inference/synthesis/`)**: 1204-line module managing grounded context assembly, provider timeout/retry policies, schema validation, and citation binding.

---

## 5. Graph Implementation & Storage
- **Primary Database**: `okf_graph.db` (KùzuDB graph engine, 102.6 MB) & `okf_graph_staging.db`.
- **JSON/SQLite Graph Exports**: `okf_graph.json`, `_graph_nodes.json`, `_graph_edges.json`.
- **Internal Graph RPC**: `graph_server.py` running on `http://127.0.0.1:5050`.
- **Python Graph API (`okf/graph/`, `archipelago/graph/`)**: Provides k-hop subgraph traversal, seed node expansion, co-mention link discovery, and evidence extraction (`okf/graph/evidence.py`).

---

## 6. Retrieval & Ranking Engine
- **Concept & Document Ranking (`archipelago/inference/ranking/`)**: `seed_expansion.py`, `graph_traversal.py`.
- **Catalog Ranking**: `catalog_ranking.py`, `archipelago/inference/catalog_ops/`.
- **GraphRAG / Vector Index**: `okf/exports.py` (`build_graph_rag_index`), `backend/retrieval/`.

---

## 7. Personalization & Diagnostic MCQ Engine
- **Diagnostic MCQ (`archipelago/inference/diagnostic_mcq/`)**: `mcq_generator.py`, `mcq_evaluator.py`, `misconception_map.py` (maps incorrect distractor choices to misconception tags).
- **Adaptive Curriculum (`archipelago/inference/curriculum/`)**: `prerequisite_traversal.py`, `mastery_decay.py`, `learner_state.py`.
- **Duplicate Stubs**: `backend/personalization/`, `backend/quiz/`.

---

## 8. Citations & Deep Linking Engine
- **Citation Cleanser & Verifier (`archipelago/inference/citations/`)**: Grounding verification, passage/page coordinate matching, hash verification.
- **Evidence Collector (`okf/graph/evidence.py`)**: Extracts verbatim quote spans and document IDs.
- **Deep Link Resolver (`host_inference/engine/links.py`)**: Resolves Pearson textbook links and HuggingFace dataset deep links.

---

## 9. Catalog & OPAC Integration
- **Catalog Resolver (`archipelago/inference/library_queries/`)**: Physical shelf routing, Koha OPAC search bridge, availability checking.
- **Catalog Ops (`catalog_ops.py`, `catalog_bridge.py`, `catalog_populate.py`)**: Ingestion and indexing of MARC/CSV library records.

---

## 10. Ingestion Pipeline & Workers
- **Ingestion Orchestrator (`okf/pipeline.py`, `archipelago/ingestion/`)**: Staged pipeline (`SOURCE` -> validation -> extraction -> normalization -> staging -> deduplication -> librarian review -> publish).
- **Asynchronous Worker (`ingestion_worker.py`, `ingestion_worker_job_mixin.py`, `ingestion_jobs.py`)**: Background job processor.
- **Extractors**: `archipelago/ingestion/lib_qwen_extractor/`, `archipelago/ingestion/ods_parser/`, `backend/OCR/`.

---

## 11. Persistence & Storage Layer
- **Graph Database**: KùzuDB (`okf_graph.db`).
- **Catalog Storage**: SQLite (`data/catalogs/catalog.db`).
- **Fixtures & Corpora**: `pdfs/`, `pilot_corpus/`, `data/uploads/`.

---

## 12. Test Suite Status
- **Test Locations**: `tests/unit/` (111 files), `tests/integration/` (14 files), `tests/e2e/` (7 files), `tests/performance/` (2 files).
- **Test Collection Baseline**: Fixed `okf/evaluate.py` shim and `okf/pipeline_staged.py` circular import. All **1,472 tests collect cleanly with 0 collection errors**.

---

## 13. Infrastructure & Deployment Configurations
- **Docker**: `Dockerfile` (Gunicorn + Python 3.12), `Dockerfile.hf` (HuggingFace Spaces deployment), `docker-compose.yml`.
- **Target Environments**: Northflank / Render / HuggingFace Spaces (`deploy/library-computer/`, `.antideploy.json`).

---

## 14. Duplicated Modules Audit
1. `backend/` stub tree (`backend/quiz`, `backend/telemetry`, `backend/OCR`, `backend/authentication`, `backend/caching`, `backend/personalization`, `backend/routing`, `backend/synthesis`, `backend/retrieval`, `backend/ingestion`, `backend/intent`, `backend/graph`, `backend/catalog`, `backend/citations`) vs canonical `archipelago/` tree.
2. `ui/chat/` vs `host_inference/ui/` vs `frontend/` vs `chat_ui/`.
3. `okf_pipeline.py` (root) vs `okf/pipeline.py`.
4. `books_showcase_src.tsx` (root) vs `frontend/book-stack/books_showcase_src.tsx`.

---

## 15. Large Critical Files Audit (>300 lines)
- `training/prepare_okf_training_data.py` (2096 lines)
- `frontend/book-stack/books_showcase_src.tsx` (1844 lines)
- `archipelago/inference/routing.py` (1307 lines)
- `archipelago/inference/synthesis.py` (1204 lines)
- `ui/chat/library.html` (1075 lines)
- `tests/unit/test_inference_75_cases.py` (941 lines)
- `scripts/run_master_library_ingest.py` (880 lines)
- `archipelago/inference/routes_misc.py` (871 lines)
- `archipelago/inference/demo_query_books.py` (725 lines)
- `ui/chat/index.html` (711 lines)

---

## 16. Security & Secret Audit
- Hardcoded `DEV_ACCESS_TOKEN = "local-dev-token"` in `archipelago/supabase_auth/part01_verify.py`.
- Development `.env` present in root. Needs verification that no production credentials are leaked in tracked files.

---

## 17. Features Already Implemented
- Grounded LLM answer synthesis with citations.
- Multi-hop graph traversal & seed node expansion.
- Diagnostic MCQ generation & distractor misconception mapping.
- Catalog search & physical shelf location routing.
- Rich UI with book showcase, topology viewer, chat, and OPAC search.

---

## 18. Features Partially Implemented
- Test suite evaluation export in `okf/evaluate.py`.
- Rate limiting and auth integration.
- Staged ingestion worker job queue.
- Adaptive 3-to-10 diagnostic question budget.

---

## 19. Features Missing or Disconnected
- Glass-box student vs developer query inspector toggles in UI.
- Tombstone/state mechanism for withdrawn sources in catalog.
- Unified telemetry/logging across `host_inference` and `archipelago`.

---

## 20. Highest-Risk Architectural Inconsistencies
1. [RESOLVED IN W0] Missing re-exports in `okf/evaluate.py` and circular import in `okf/pipeline_staged.py` (fixed: 1,472 tests now collect cleanly).
2. Parallel existence of `backend/` stub tree and canonical `archipelago/` modules.
3. Multiple UI trees (`ui/chat/` vs `host_inference/ui/` vs `frontend/`).
4. Dual deployment entry points (`start.sh` / `archipelago.apps.inference_app` vs `host_inference/hostapp`).
