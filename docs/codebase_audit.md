# Archipelago Codebase Audit

**Date:** September 2026  
**Auditor:** Archipelago Lead Systems & Research Engineering Team  
**Repository Paths:**
- Primary: `/home/pratay-karali/Desktop/archipelago/Archipelago`
- Workspace Root: `/home/pratay-karali/Desktop/archipelago`

---

## 1. Executive Summary

This codebase audit establishes the empirical baseline of the Archipelago repository prior to the production engineering upgrade. It catalogues existing modules, identifies architectural debt, analyzes test suite collection failures, audits the knowledge graph state on disk, and details the legacy compatibility shims.

### Headline Findings
1. **Broken Test Collection:** Running `pytest` fails with **13 collection errors** across unit and integration suites due to missing shim modules (`catalog_ranking`, `catalog_schema`), missing function exports (`clean_catalog_topic`, `resolve_pdf_file`), and unimported pipeline modules (`synthesis_pipeline`).
2. **Monolithic Feature Files:** Several core inference files severely exceed the 500 LOC architectural budget documented in `docs/guides/ARCHITECTURE.md`:
   - `archipelago/inference/routing.py`: 51,066 bytes (~1,250 lines)
   - `archipelago/inference/synthesis.py`: 51,188 bytes (~1,300 lines)
   - `archipelago/inference/routes_chat.py`: 41,446 bytes (~1,050 lines)
   - `archipelago/inference/routes_misc.py`: 33,425 bytes (~850 lines)
3. **Graph State on Disk:**
   - Database: `okf_graph.db` (78.5 MB KùzuDB file)
   - JSON Snapshot: `okf_graph.json` contains **460 concept nodes** and **1,832 edges** (196 `REQUIRES`, 358 `UNLOCKS`, 1,278 `RELATED`).
   - Kahn's algorithm verifies **0 cycles** in the `REQUIRES` directed graph ($V=199, \text{visited}=199$).
   - **50 concepts are complete topological orphans** (0 incoming or outgoing edges).
4. **Corpus Scale Reality:**
   - Literature claims "412 Research Papers / 48 Textbooks".
   - Actual files on disk: **43 PDFs total**, comprising **25 research papers** and **6 textbooks** (in `pdfs/archipelago-books-cs/` and `pdfs/papers/`). 31 distinct documents are cited in `okf_graph.json`.
   - The 412/48 claim is an ungrounded engineering target.

---

## 2. Directory & Package Structure Analysis

```text
Archipelago/
├── archipelago/                 # Primary application package
│   ├── apps/                    # Entrypoints (inference_app.py)
│   ├── auth.py                  # Basic bearer token checks (lacks granular RBAC)
│   ├── inference/               # Chat RAG, routing, synthesis, neighborhood
│   │   ├── state.py             # Global Flask/in-memory state
│   │   ├── routing.py           # Monolithic intent classifier & heuristic router
│   │   ├── synthesis.py         # Response generation & Ollama/Gemini streaming
│   │   ├── neighborhood.py      # Upstream/downstream Cypher traversal
│   │   ├── curriculum.py        # Multi-hop shortest path algorithms
│   │   ├── citations.py         # Citation extraction & deep-linking
│   │   ├── context_tracker.py   # Multi-turn deictic working memory
│   │   └── library_queries.py   # Physical catalog lookups (missing clean_catalog_topic)
│   └── ingestion/               # Document chunking & PDF parsing
├── okf/                         # OKF extraction & graph construction
│   ├── canonicalize.py          # Fuzzy matching & alias deduplication
│   ├── cleanup_parts/           # Cycle breaking, junk entity filters, backfills
│   ├── extraction.py            # SLM concept extraction prompt harness
│   └── graph/                   # KùzuDB schema & ingestion engine
├── pdfs/                        # Local PDF corpus (43 files)
├── training_data/               # Versioned train/test pairs (v1.6 to v5)
├── ui/                          # Static web interfaces (ui/chat, ui/graph)
├── tests/                       # Unit, integration, and e2e tests
├── scripts/                     # Operational, evaluation, and rebuild scripts
├── okf_graph.db                 # Production KùzuDB database (78 MB)
└── okf_graph.json               # Full graph JSON export (8 MB)
```

---

## 3. Test Suite Collection Failures (13 Errors)

Executing `pytest` produces 13 collection failures:

| # | Test Module | Error Class | Root Cause |
|---|---|---|---|
| 1 | `tests/unit/test_catalog_ranking_topic.py` | `ModuleNotFoundError` | Missing root-level shim `catalog_ranking.py`. |
| 2 | `tests/unit/test_five_stage_pipeline.py` | `ModuleNotFoundError` | `archipelago.inference.pipeline` attempts to import non-existent `synthesis_pipeline`. |
| 3 | `tests/unit/test_session7_catalog_queries.py` | `ImportError` | Missing export `clean_catalog_topic` in `archipelago/inference/library_queries.py`. |
| 4 | `tests/unit/test_subject_ingestion.py` | `ModuleNotFoundError` | Missing root-level shim `catalog_schema.py`. |
| 5 | `tests/unit/test_system_enhancements.py` | `ImportError` | Missing export `resolve_pdf_file` in `archipelago/inference/routes_misc.py`. |
| 6 | `tests/unit/test_title_ingestion.py` | `ModuleNotFoundError` | Missing root-level shim `catalog_schema.py`. |
| 7 | `tests/test_system_enhancements.py` | `ImportError` | Duplicate test file with same missing `resolve_pdf_file` import. |
| 8 | `tests/unit/test_50_cases_library.py` | `ImportError` | Dependency cascade from `clean_catalog_topic`. |
| 9 | `tests/unit/test_50_new_cases_verification.py` | `ImportError` | Dependency cascade from `clean_catalog_topic`. |
| 10 | `tests/unit/test_catalog_bridge.py` | `ModuleNotFoundError` | Missing `catalog_ranking` shim. |
| 11 | `tests/integration/test_full_pipeline.py` | `ModuleNotFoundError` | Legacy import of old monolithic server module. |
| 12 | `tests/integration/test_graph_db.py` | `ModuleNotFoundError` | Missing legacy `graph_db` shim functions. |
| 13 | `tests/e2e/test_ui_deeplinking.spec.py` | `SyntaxError/Collection` | Playwright spec file named `.spec.py` matching pytest collection pattern. |

**Plan 1 Action:** Implement the missing shims and exported utility functions, and configure pytest ignore rules for JS/Playwright spec files so `pytest --collect-only` executes with 0 errors.

---

## 4. Graph Topology & Integrity Audit

Direct evaluation of `okf_graph.json` and `okf_graph.db`:
- **Total Canonical Concepts:** 460
- **Total Topological Edges:** 1,832
  - `REQUIRES` (Prerequisites): 196
  - `UNLOCKS` (Downstream Enablement): 358
  - `RELATED` (Semantic Association): 1,278
- **Self-Loops ($A \to A$):** 0 (Passed)
- **Reciprocal Cycles ($A \leftrightarrow B$ on REQUIRES):** 0 (Passed)
- **Kahn DAG Sort:** 199 nodes in `REQUIRES` graph visited in topological order; 0 directed cycles detected.
- **Topological Orphans:** 50 concepts have 0 edges of any kind.
- **Curriculum Islands:** Concepts like `principal_component_analysis` have 5 `RELATED` edges but 0 `REQUIRES`/`UNLOCKS` edges, causing multi-hop curriculum pathfinding to fail with 0 hops.

---

## 5. Security & Isolation Deficiencies

1. **Lack of RequestContext:** Ingestion and chat routes use global variables in `state.py` (`SESSION_CONTEXTS = {}`, `CONCEPTS_DATA = {}`). While session dictionaries are keyed by `session_id`, global state mutations risk cross-request pollution during concurrent asynchronous execution.
2. **Missing Granular Authorization:** `auth.py` checks a single static token `LIBRARIAN_API_KEY`. It does not support RBAC or user identity claims (`student`, `faculty`, `admin`).
3. **Context Leakage Risk:** Chunks stored in KùzuDB and JSON carry database fields (`chunk_id`, `doc_id`, internal table columns). If passed directly into prompt templates, these leak into model output.
4. **Cloud Fallback Data Egress:** If local Ollama fails, fallback to Gemini sends retrieved textbook chunks to a cloud API without checking copyright or data classification.

---

## 6. Conclusion & Plan 1 Remediation Priorities

1. Restore test suite collection health (fix 13 import/shim issues).
2. Establish formal research verification documentation (`source_registry.md`, `citation_audit.md`, `claim_audit.md`).
3. Formally register models: `lib-qwen` for ingestion, `qwen3.5:0.8b` for inference, rejecting `Qwen2.5-0.8B-Instruct`.
4. Implement clean, typed core contracts under `src/archipelago/core/` (`RequestContext`, `RetrievedChunk`, `ContextSerializer`, `RunManifest`).
5. Implement standalone KùzuDB engine with Kahn DAG validation under `src/archipelago/graph/`.
