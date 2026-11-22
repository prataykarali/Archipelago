# 07_API_CONTRACT.md: Archipelago API Specification

Complete API specification for all endpoints across the Archipelago services.

## 1. Service Architecture
- **Inference API** (port 5151): Primary backend, Flask/Gunicorn.
- **Graph API** (port 5150): Graph visualization server.
- **Chat Gateway** (port 5152): Reverse proxy + UI serving.
- **AntDeploy Hosted** (port 5151): [`host_inference/hostapp/`](file:///home/pratay-karali/Desktop/archipelago/host_inference/hostapp/)

## 2. Health & Readiness
- `GET /health` — liveness probe.
- `GET /ready` or `/api/readiness` — readiness check (corpus loaded, graph available).
- **Response**: `{ "status": "ok", "corpus": "fixture" | "full", "node_count": int, "edge_count": int }`

## 3. Chat & Inference Endpoints
- `POST /api/chat` — Main chat endpoint (SSE streaming).
  - **Request**: `{ "query": string, "session_id"?: string, "context"?: string[] }`
  - **Response**: SSE stream with event types: `token`, `graph`, `citations`, `metadata`, `done`.
  - **Source**: [`archipelago/api/routes_chat.py`](file:///home/pratay-karali/Desktop/archipelago/archipelago/api/routes_chat.py), [`host_inference/hostapp/routes/chat.py`](file:///home/pratay-karali/Desktop/archipelago/host_inference/hostapp/routes/chat.py)
- `POST /ask` — Legacy inference endpoint.
- `GET /api/chat/history` — Chat history.

## 4. Graph Endpoints
- `GET /api/graph/neighborhood?concept=<id>&k=<hops>` — K-hop subgraph.
- `GET /api/graph/prereqs?concept=<id>` — Prerequisites.
- `GET /api/graph/unlocks?concept=<id>` — What concept unlocks.
- `GET /api/graph/path?from=<id>&to=<id>` — Shortest dependency path.
- `GET /api/concepts` — List all concepts.
- **Source**: [`host_inference/hostapp/routes/graph.py`](file:///home/pratay-karali/Desktop/archipelago/host_inference/hostapp/routes/graph.py), [`archipelago/api/routes_discovery.py`](file:///home/pratay-karali/Desktop/archipelago/archipelago/api/routes_discovery.py)

## 5. Library & Catalog Endpoints
- `GET /api/catalog/search?q=<query>` — Catalog search (uses parameterized Cypher, patched for injection).
- `GET /api/library/inventory` — Physical library holdings.
- `GET /api/library/books` — Book list with metadata.
- `GET /resolve/<book_id>` — Pearson/HF deep link redirect.
- **Source**: [`host_inference/hostapp/routes/library.py`](file:///home/pratay-karali/Desktop/archipelago/host_inference/hostapp/routes/library.py), [`archipelago/api/routes_library.py`](file:///home/pratay-karali/Desktop/archipelago/archipelago/api/routes_library.py)

## 6. Diagnostic/Quiz Endpoints
- `POST /api/diagnostic/start` — Start diagnostic for concept.
  - **Request**: `{ "concept_id": string }`
  - **Response**: `{ "target_concept": string, "chain": [], "prereq_chain": [], "initial_question": {}, "mcqs": [] }`
- `POST /api/diagnostic/answer` — Submit answer.
  - **Request**: `{ "concept_id": string, "answer": string, "slot": string }`
- `POST /api/diagnostic/personalized-graph` — Get personalized graph result.
- **Source**: [`host_inference/engine/diagnostics.py`](file:///home/pratay-karali/Desktop/archipelago/host_inference/engine/diagnostics.py)

## 7. Ingestion Endpoints (LIBRARIAN AUTH REQUIRED)
- `POST /api/ingest/pdf` — Upload PDF for ingestion.
- `POST /api/ingest/spreadsheet` — Upload ODS/CSV.
- `POST /api/ingest/mention` — Mention-a-Book auto-populate.
- `POST /api/ingest/page-image` — Scanned page OCR intake.
- `GET /api/ingest/status/<job_id>` — Ingestion job status.
- **Source**: [`host_inference/hostapp/routes/ingest.py`](file:///home/pratay-karali/Desktop/archipelago/host_inference/hostapp/routes/ingest.py), [`archipelago/api/routes_acquisition.py`](file:///home/pratay-karali/Desktop/archipelago/archipelago/api/routes_acquisition.py)

## 8. Auth Endpoints
- `POST /api/auth/login` — Supabase JWT login.
- `POST /api/auth/refresh` — Token refresh.
- `GET /api/auth/profile` — User profile.
- **Source**: [`host_inference/hostapp/routes/auth.py`](file:///home/pratay-karali/Desktop/archipelago/host_inference/hostapp/routes/auth.py), [`archipelago/api/routes_auth.py`](file:///home/pratay-karali/Desktop/archipelago/archipelago/api/routes_auth.py)

## 9. Admin Endpoints
- `POST /api/internal/reload-graph` — Hot-reload graph (internal only).
- `GET /api/admin/cache/metrics` — Cache hit/miss metrics.
- `GET /api/admin/telemetry` — P50/P90/P99 latency.

## 10. Rate Limiting
- **Per-minute**: `ARCHIPELAGO_RATE_LIMIT_PER_MIN` (default 20).
- **Burst**: `ARCHIPELAGO_RATE_LIMIT_BURST` (default 50).
- **Global**: `ARCHIPELAGO_RATE_LIMIT_GLOBAL` (default 500).
- **Source**: [`archipelago/inference/rate_limit.py`](file:///home/pratay-karali/Desktop/archipelago/archipelago/inference/rate_limit.py)

## 11. Authentication & Authorization
- **Bearer Token**: Supabase JWT.
- **Librarian Token**: `ARCHIPELAGO_LIBRARIAN_TOKEN`
- **Roles**: student (default), librarian, admin.
- **Open Routes**: `/`, `/chat`, `/library`, `/read/*`
- **Protected Routes**: `/api/ingest/*`, `/api/users`, `/api/admin/*`
