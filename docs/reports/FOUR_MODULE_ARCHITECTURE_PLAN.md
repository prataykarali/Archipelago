# Four-Module Architecture Plan + Live Eval Report

**Date:** 2026-07-27  
**Scope:** Target layout (`ingestion-frontend`, `backend`, `inference-backend`, `frontend`), dependency cleanup, async contracts, and live results for `docs/archipelago_eval_questions.md`.

---

## Executive verdict (eval + inference)

| Check | Result |
|-------|--------|
| Inference server boots (`:5051`) | **YES** — 460 concepts loaded, Gemini configured |
| End-to-end 5-stage pipeline (graph → Gemini) | **YES** — domain concept queries + Gemini (or grounded fallback) |
| Strict domain subset (Q21/26–30/51/52/61/64 + LoRA) | **11/11 PASS** (2026-07-27, after ranking/OOS fixes) |
| Full 75-question eval suite | **Partial** — meta/credential/system Qs still lack corpus; see residual gaps |
| Embeddings online | **NO** — lexical+alias mode works; load arctic for long-tail |
| LoRA in graph | **YES via alias** — `lora` → `low_rank_adaptation` (label present) |
| Chat UI static assets | **Minimal stub** — `frontend/chat_ui/index.html` + `graph_ui` symlink |
| `serve.sh` entrypoints | **FIXED** — `inference_server.py`, `frontend/*_server.py`, PYTHONPATH |

### Live proof that inference *can* work

Short concept-name queries through `run_archipelago_inference` (2026-07-27):

| Query | Route | Generation | Anchor | Prereqs / Unlocks / Cites |
|-------|-------|------------|--------|---------------------------|
| Self-Attention | graph_strong | **gemini** (`gemini-3.5-flash-lite`) | Self-Attention | 5 / 6 / 6 |
| Vector RAG | graph_strong | **gemini** | Vector RAG | 2 / 0 / 3 |
| Dimensionality Reduction | graph_strong | **gemini** | Dimensionality Reduction | 0 / 4 / 2 |
| BERT | graph_strong | **gemini** | BERT | 0 / 6 / 8 |
| Graph RAG | graph_strong | **gemini** | Graph RAG | 3 / 6 / 8 |
| Latent Variable | graph_strong | **gemini** | Latent Variable | 0 / 0 / 1 |

### Broader slice (post-FAQ + ranking fixes)

Raw log: `docs/reports/EVAL_BROADER_SLICE.json` — **23/23** after Q13 FAQ disambiguation.

| Band | Covered IDs | Result |
|------|-------------|--------|
| Meta/OKF FAQ | Q6–Q18, Q20 | `system_faq` deterministic answers |
| Domain RAG | Q21, Q26–Q28, Q30, Q61, LoRA | `graph_strong` + Gemini |
| Adversarial OOS | Q51, Q52 | `out_of_scope` |
| Earlier strict domain | 11/11 | `EVAL_DOMAIN_STRICT.json` |

### Original 75-case baseline (pre-fix)

Raw log: `docs/reports/EVAL_QUESTIONS_LIVE_RESULTS.json` — **25/75 loose** (stale; do not use as current quality).

**Residual gaps for full 75:**

1. Library credential Qs (Q1–Q5, Q19, Q25) need secure e-resource store / PDF corpus.
2. Fine-tune / dataset meta (Q22–Q24, Q31–Q35, …) need more FAQ entries or docs ingest.
3. Multi-anchor curriculum paths (full Latent→BERT chain) still single-anchor.
4. Gemini free-tier 429 on primary models — failover to `gemini-3.5-flash-lite` works.
5. Embeddings still off — lexical+alias mode is the live path.
5. **Broken packaging** — `pipeline` imports `ingestion_worker` from `ingestion_backend/`; requires `PYTHONPATH=.:ingestion_backend`.

---

## 1. Target directory tree

Map current messy layout onto four **isolated** deployable packages. Shared contracts live in a thin `packages/contracts` layer (OpenAPI + TS/Python types), not business logic.

```
libraryAI/
├── docker-compose.yml                 # orchestration only
├── packages/
│   └── contracts/                     # versioned API schemas (OpenAPI 3.1)
│       ├── openapi/
│       │   ├── inference.v1.yaml
│       │   ├── backend.v1.yaml
│       │   └── ingestion.v1.yaml
│       └── python/archipelago_contracts/
│
├── frontend/                          # #4 main user UI (chat + graph viewer)
│   ├── package.json                   # UI-only deps (no Python)
│   ├── public/
│   ├── src/
│   │   ├── api/                       # typed clients + mock adapters
│   │   │   ├── client.ts              # fetch wrapper, timeouts, AbortController
│   │   │   ├── mock/                  # offline / degraded UI fixtures
│   │   │   └── types.ts               # generated from contracts
│   │   ├── components/                # pure presentational
│   │   ├── hooks/                     # data hooks isolate loading/error state
│   │   ├── styles/                    # CSS only — never imported by backends
│   │   └── App.tsx
│   ├── chat_server.py                 # optional static+proxy (port 5052)
│   └── Dockerfile
│
├── ingestion-frontend/                # #1 operator UI for corpus / jobs
│   ├── package.json
│   ├── src/
│   │   ├── api/ingestionClient.ts
│   │   ├── pages/{Upload,Jobs,Catalog}.tsx
│   │   └── mock/
│   └── Dockerfile
│
├── backend/                           # #2 operational API (catalog, jobs, graph CRUD)
│   ├── pyproject.toml
│   ├── requirements.txt               # flask, kuzu, pandas, odfpy, thefuzz
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/{catalog,jobs,graph,health}.py
│   │   ├── services/{ingestion_worker,catalog,graph_lock}.py
│   │   └── okf/                       # move from root okf/ (single copy)
│   ├── tests/
│   └── Dockerfile                     # port 5050
│
├── inference-backend/                 # #3 AI/ML chat pipeline (no UI)
│   ├── pyproject.toml
│   ├── requirements.txt               # flask, google-genai, torch/st (optional), kuzu
│   ├── app/
│   │   ├── main.py                    # :5051
│   │   ├── pipeline/                  # from archipelago/inference/*
│   │   ├── routing.py
│   │   ├── embeddings.py
│   │   └── synthesis.py
│   ├── tests/
│   └── Dockerfile
│
├── data/                              # runtime artifacts (not package code)
│   ├── okf_graph.db
│   ├── okf_graph.json
│   └── pdfs/ → ../pdfs (bind mount)
│
├── docs/
├── scripts/ops/
└── tests/                             # monorepo e2e only
```

### Current → target mapping

| Today | Target |
|-------|--------|
| `frontend/chat_server.py`, `frontend/ui/*` | `frontend/` |
| *(missing)* operator upload UI | `ingestion-frontend/` |
| `ingestion_backend/*`, root `okf/*`, catalog_* | `backend/` |
| `archipelago/inference/*`, `inference_server.py` | `inference-backend/` |
| Duplicated `ingestion_backend/okf` + root `okf` | **One** `backend/app/okf` |
| Root shims (`inference_server.py`) | Thin re-export or delete after cutover |

---

## 2. Migration & UI isolation strategy

**Invariant:** CSS, layout, and client interaction state must not depend on API latency or payload shape.

### Step A — Freeze the UI surface

1. Restore / rebuild `frontend/chat_ui` (currently missing — chat server points at it).
2. Snapshot visual baseline (screenshots + a11y tree) for chat + graph.
3. Introduce a **ViewModel** layer only:

```ts
// frontend/src/api/types.ts  (stable UI contract)
export type ChatViewModel = {
  status: "idle" | "streaming" | "error" | "degraded";
  route: string | null;
  anchor: { id: string; name: string } | null;
  prerequisites: { id: string; name: string }[];
  unlocks: { id: string; name: string }[];
  citations: CitationVM[];
  answerMarkdown: string;
  errorMessage?: string;
};
```

### Step B — Adapter + mock fallback (never block paint)

```ts
// frontend/src/api/client.ts
export async function chat(query: string, signal?: AbortSignal): Promise<ChatViewModel> {
  try {
    const res = await fetch(`${INFERENCE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, session_id: sessionId() }),
      signal,
    });
    return await parseStreamToViewModel(res); // maps wire format → ChatViewModel
  } catch {
    return mockChatViewModel(query); // layout still renders; badge = "degraded"
  }
}
```

Rules:
- Components only consume `ChatViewModel`.
- Loading skeletons are CSS/DOM only — no “wait for backend before first paint”.
- Stream tokens update **text node only**; sidebar graph state is independent.
- Backend field renames require adapter change, not component change.

### Step C — Split servers without moving pixels

| Phase | Action | UI impact |
|-------|--------|-----------|
| 0 | Document contracts; add mock adapters | None |
| 1 | Move inference code → `inference-backend/` behind same `/api/chat` | None if URL env stays |
| 2 | Move graph/catalog → `backend/` | Proxy URLs via env |
| 3 | Build `ingestion-frontend` as separate SPA | New surface only |
| 4 | Delete duplicate `okf` trees; fix PYTHONPATH | None |
| 5 | docker-compose multi-service | Config only |

### Step D — Decouple inference from ingestion worker

Today: `archipelago/inference/pipeline.py` does `from ingestion_worker import graph_lock`.

**Fix:** extract `backend/app/services/graph_lock.py` (or a tiny shared `packages/graph_lock`) so inference never imports the ingestion job runner / ollama extraction stack.

---

## 3. Dependency audit plan

### Current problems

| Issue | Evidence |
|-------|----------|
| Duplicate OKF trees | `okf/` and `ingestion_backend/okf/` (~748K each) |
| Cross-package import | inference → `ingestion_worker` → `okf.extraction` → `ollama` |
| Monolithic `requirements.txt` | UI/proxy, Kùzu, PDF, catalog ODS, Gemini all one file |
| Missing declared dep | `ollama` needed to import worker even for read-only chat |
| serve.sh path drift | servers live under `frontend/`; apps package missing |

### Standardization rules

1. **One package owns one concern** — no shared “god” requirements.
2. **No transitive UI libs in Python services.**
3. **HTTP client:** browser `fetch` only in frontends; Python `httpx` or `requests` only in services that call peers (prefer one).
4. **Graph engine:** `kuzu` only in `backend` + `inference-backend` (read path).
5. **LLM:** `google-genai` only in `inference-backend`. Local SLM/`ollama` only in `backend` ingestion.
6. **PDF:** `pymupdf` only in `backend` (and inference PDF serve if kept).
7. **Catalog:** `pandas` + `odfpy` only in `backend`.
8. **Ban** second copy of OKF, duplicate training trees under `ingestion_backend/training*`.

### Per-package dependency matrix

| Package | Allowed | Forbidden |
|---------|---------|-----------|
| `frontend` | React/Vite (or static HTML/JS), no Python runtime deps for UI build | torch, kuzu, gemini SDK |
| `ingestion-frontend` | Same UI stack as frontend (one design system) | Direct DB access |
| `backend` | flask, kuzu, pymupdf, pandas, odfpy, thefuzz, ollama (ingest) | google-genai (keep synthesis out) |
| `inference-backend` | flask, google-genai, kuzu (RO), optional sentence-transformers | pandas/odfpy, fine-tune stacks |

### Audit checklist (CI)

```bash
# fail if inference imports ingestion job runner
rg -n "from ingestion_worker|import ingestion_worker" inference-backend/ && exit 1
# fail if frontend vendors python
test ! -f frontend/requirements.txt
# fail duplicate okf
test ! -d ingestion_backend/okf   # after migration
```

---

## 4. Integration guide (async contracts)

### Ports (keep existing pilot numbers)

| Service | Port | Role |
|---------|------|------|
| `backend` | 5050 | Graph API, catalog, ingestion jobs, graph UI static optional |
| `inference-backend` | 5051 | `/api/chat`, readiness, page-view, PDF |
| `frontend` | 5052 | Chat UI + reverse-proxy to 5051 |
| `ingestion-frontend` | 5053 | Operator UI → backend jobs API |

### Wire protocol: chat (NDJSON + stream marker)

**Request**

```http
POST /api/chat HTTP/1.1
Host: inference-backend:5051
Content-Type: application/json

{
  "query": "Explain Self-Attention",
  "session_id": "demo-1",
  "history": [],
  "synthesis": true
}
```

**Response** (non-blocking stream; UI paints after first metadata line)

```text
{"anchor_concept":{"id":"self_attention","name":"Self-Attention"},"prerequisites":[...],"unlocks":[...],"citations":[...],"routing":{"route":"graph_strong"},"generation":{"provider":"gemini","source":"gemini","model":"..."}}
[STREAM_START]
Self-attention is a core mechanism...
```

### Frontend consumer (async, abortable)

```ts
async function* streamChat(query: string, signal: AbortSignal) {
  const res = await fetch(`${INFERENCE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
    signal,
  });
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let meta: ChatMeta | null = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    if (!meta && buf.includes("[STREAM_START]")) {
      const [head, rest] = buf.split("[STREAM_START]");
      meta = JSON.parse(head.trim().split("\n")[0]);
      yield { type: "meta" as const, meta };
      buf = rest;
    }
    if (meta && buf) {
      yield { type: "token" as const, text: buf };
      buf = "";
    }
  }
}
```

### Backend ↔ inference (read-only graph)

- Inference opens `okf_graph.db` **read-only** (`ARCHIPELAGO_DB_READ_ONLY=1`).
- Backend owns writes + **atomic swap** (`ingestion_worker` pattern).
- Shared lock primitive only — no job queue import into inference.

```python
# inference-backend/app/graph_access.py
from contextlib import contextmanager
import threading

_lock = threading.RLock()

@contextmanager
def read_lock():
    with _lock:
        yield
```

### Ingestion-frontend → backend jobs

```http
POST /api/ingest/jobs
{ "paths": ["pdfs/papers/Hu2021_LoRA.pdf"], "priority": "normal" }

GET  /api/ingest/jobs/{id}     # polling or SSE
GET  /api/ready                # { "ready": true, "graph_nodes": N }
```

Prefer **SSE or job polling** so the operator UI never blocks on multi-minute SLM extraction.

### docker-compose sketch

```yaml
services:
  backend:
    build: ./backend
    ports: ["5050:5050"]
    volumes: ["./data:/data", "./pdfs:/data/pdfs:ro"]
  inference-backend:
    build: ./inference-backend
    ports: ["5051:5051"]
    environment:
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      ARCHIPELAGO_DB_READ_ONLY: "1"
      OKF_GRAPH_DB: /data/okf_graph.db
    volumes: ["./data:/data:ro", "./pdfs:/data/pdfs:ro"]
  frontend:
    build: ./frontend
    ports: ["5052:5052"]
    environment:
      ARCHIPELAGO_INFERENCE_URL: http://inference-backend:5051
  ingestion-frontend:
    build: ./ingestion-frontend
    ports: ["5053:5053"]
    environment:
      ARCHIPELAGO_BACKEND_URL: http://backend:5050
```

---

## 5. What must be fixed before the 75-case suite can pass

These are **product/pipeline** issues, not folder-move issues:

| # | Fix | Unblocks |
|---|-----|----------|
| 1 | Load Snowflake arctic embeddings at inference startup; precompute concept vectors | Long-form Q21–Q30, kill-switch fairness |
| 2 | Align kill-switch: if embeddings off, use lexical≥0.5 **or** lower cos threshold | False OOS on known concepts |
| 3 | Ingest **LoRA / PEFT** papers into graph | Q26, Q45, demos |
| 4 | Dedicated routes for e-resource credentials / OKF meta FAQ (or ingest docs as corpus) | Q1–Q25 system facts |
| 5 | Soften false `onboarding` / `general_chat` pre-routes when domain terms present | Q26–Q29 |
| 6 | Unifyмент Gemini quota or paid tier; prefer flash-lite in `.env` for free tier | Stable synthesis |
| 7 | Restore `frontend/chat_ui` assets | End-to-end UI demo |
| 8 | Fix `serve.sh` paths + PYTHONPATH | Reproducible local start |

### Minimal local start (works today)

```bash
source .venv/bin/activate
set -a; source .env; set +a
export PYTHONPATH=".:ingestion_backend"
python inference_server.py   # :5051
# optional:
# python frontend/chat_server.py   # needs chat_ui/
# python frontend/graph_server.py
```

### Re-run this eval

```bash
# results written previously:
# docs/reports/EVAL_QUESTIONS_LIVE_RESULTS.json
# docs/reports/EVAL_DOMAIN_STRICT.json
```

---

## 6. Recommended execution order (PRs)

1. **PR-A (unblock inference packaging):** extract `graph_lock`, fix PYTHONPATH/serve.sh, declare `ollama` only for backend.
2. **PR-B (UI contract):** ChatViewModel + mock adapter; restore chat_ui; no backend change.
3. **PR-C (inference-backend folder):** move `archipelago/inference` + server; keep URL/port.
4. **PR-D (backend folder):** single `okf`, catalog, worker; delete duplicate tree.
5. **PR-E (ingestion-frontend):** job UI against backend API.
6. **PR-F (quality):** embeddings on, LoRA ingest, eval harness wired to `archipelago_eval_questions.md` with strict scorers (not loose substring).

---

## Appendix — Honest scoring note

The first 75-case run used **loose keyword** matching. Several “PASS” rows matched incidental words inside the generic refusal (`not`, `library`, `citation`). Treat **33% as an upper bound**, not quality. Strict domain re-test showed most multi-word pedagogical questions hit **kill_switch** because embeddings are off. Concept-name smoke tests prove the **pipeline + Gemini path is real** when retrieval clears the gate.
