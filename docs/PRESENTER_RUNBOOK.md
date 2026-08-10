# Archipelago Pilot — 5-Minute Presenter Runbook

## Reboot during the session

`./scripts/ops/serve.sh restart` reloads only code; config is cached.
After editing any config, do a full stop/start:

```bash
./scripts/ops/serve.sh stop; ./scripts/ops/serve.sh start
```

## Before the demo (morning check)

```bash
# 1. Verify servers are up
curl -s http://localhost:5151/api/readiness | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['ready'], 'Inference down'"
curl -s -o /dev/null -w "%{http_code}" http://localhost:5152/ | grep -q 200 || echo "Chat UI down!"
curl -s -o /dev/null -w "%{http_code}" http://localhost:5150/ | grep -q 200 || echo "Graph UI down!"

# 2. Verify Ollama model is available
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); models=[m['name'] for m in d.get('models',[])]; assert 'qwen3.5:0.8b' in models, 'Model missing'"

# 3. Export the librarian token (required by start_pilot.sh)
export ARCHIPELAGO_LIBRARIAN_TOKEN="$(openssl rand -hex 24)"
./scripts/ops/start_pilot.sh

# 4. Run test suite
cd /home/pratay-karali/Desktop/archipealgo
python3 -m pytest tests/unit/ -q --timeout=15 2>&1 | tail -3

# 5. Quick smoke test (5 queries covering all pilot routes)
python3 -c "
import requests, json
BASE='http://localhost:5151/api/chat'
tests = [
    ('Attention mechanism?', 'graph_strong'),
    ('best books on DBMS', 'library_books'),
    ('When is the library open?', 'library_info'),
    ('Build a SQL table', 'out_of_scope'),
    ('e-resource login', 'library_info'),
]
for q, route in tests:
    r = requests.post(BASE, json={'query':q, 'mode':'rag_synthesis', 'synthesis': False, 'session_id':'smoke'}, stream=True)
    body = ''.join(chunk.decode() for chunk in r.iter_content(8192))
    if route in body:
        print(f'OK: {q[:30]:30s} → {route}')
    else:
        print(f'FAIL: {q[:30]:30s} expected {route}')
"
```

## Demo flow (5 minutes total)

### Minute 0-1: Theory question
1. Open the student UI http://127.0.0.1:5152/ in browser
2. Verify "Online" status dot is green
3. Type: **"What is attention mechanism?"**
4. Point at the grounded answer with inline citation links (blue, underlined)
5. Click a citation link → page viewer modal opens with highlighted passage
6. Close the modal

**What to say:** "This is a local RAG engine. Every answer is grounded in real indexed documents — click any citation to verify the source page. No invented facts."

### Minute 2: Ranking / books
1. Click **New Chat** (clears context)
2. Type: **"best books on operating systems"**
3. Show the curator-ranked seed list with author authority scores
4. Point out the 3 pilot subjects covered: DBMS, Data Structures, Operating Systems

**What to say:** "Seed rankings come from librarian-curated lists — clear reasons, not AI-suggested titles. Only metadata is shown, never full book text."

### Minute 3: Library info
1. Type: **"When is the library open?"**
2. Show the structured answer: 24×7×365, weekend rules, OPAC link
3. Type: **"e-resource login credentials"**
4. Show: "This chat does not display shared passwords or passkeys"

**What to say:** "Library rules and timings are structured responses — no credential exposure. E-resource links point to institutional portals, not shared passwords."

### Minute 4: Safety / refusal
1. Type: **"Build a SQL table for users"**
2. Show the implementation refusal + closest concepts bridge
3. Type: **"best books on DBMS"** again
4. Show the seed ranking renders correctly

**What to say:** "The system refuses code generation and deployment guides. It only provides theory, metadata, and sourced citations from the pilot corpus."

### Minute 5: Graph + wrap-up
1. Click **"View concepts in graph"** button (appears after first theory query)
2. Graph UI opens with relevant concepts highlighted
3. Mention: the pilot corpus is frozen — Vaswani/BERT/LoRA/RAG/GraphRAG papers + the AIML syllabus, with sha256 in `pilot_corpus/MANIFEST.tsv`. Adding new content needs the librarian bearer token.

**What to say:** "This is a pilot with limited data — 5-6 books, 10-15 papers, 3 subjects. It demonstrates input → retrieval → grounded output. The database construction follows copyright policy: only indexes, content pages, and author metadata."

## Known Limitations (slide / talking points)

| Limitation | Explanation |
|---|---|
| Limited corpus | Only AI/ML + 3 pilot subjects (DBMS, DS, OS). Niche topics may miss. |
| No full books | Only indexes, content pages, and author metadata per copyright policy |
| No code generation | Implementation refusals; theory-only responses |
| Ollama required | Natural synthesis needs `qwen3.5:0.8b` running; falls back to "Library closed" |
| Local server | Runs on internal hardware; not a cloud deployment |
| Single concurrent chat | `/api/chat` locks; one query at a time |
| Limited journal coverage | 20-25 web publications with common keywords for pilot |

## Troubleshooting

First reflex for any routing or scope fail: `tail -50 logs/inference.log` — it shows why the router/scope picked what it did.

| Symptom | Fix |
|---|---|
| "Offline" status | Reboot: `./scripts/ops/serve.sh stop; ./scripts/ops/serve.sh start` |
| "Library closed" message | Start Ollama: `ollama serve` → `ollama pull qwen3.5:0.8b` |
| Blank chat page | Reboot: `./scripts/ops/serve.sh stop; ./scripts/ops/serve.sh start` |
| Citation link 404s | Page not in KuzuDB — report the doc_id, never invent |
| Embeddings not ready | Restart inference server; wait 5s for Snowflake model to load |

---

*Last reviewed: Jul 23, 2026. Verify with library before each demo; stamp review date.*

## Server Restart Order (after code changes)

Skip `serve.sh restart` while iterating on config — it reloads code only.

1. **Full reboot**: `./scripts/ops/serve.sh stop; ./scripts/ops/serve.sh start`
2. **Readiness check**: `curl -s http://localhost:5151/api/readiness | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['ready'], 'Inference down'"`
3. **If a routing/scope fail persists**: `tail -50 logs/inference.log`

**Ports**: 5151 (inference), 5152 (chat UI), 5150 (graph UI), 11434 (Ollama)
**Librarian UI**: http://127.0.0.1:5150/  ·  **Student UI**: http://127.0.0.1:5152/

## Queries to demo vs NOT to demo

**Safe demo queries (all verified against the pilot corpus):**
- "What is attention mechanism?" / "What is Low-Rank Adaptation?" — grounded theory + citations
- "best books on operating systems" / "best books on DBMS" — librarian-curated ranked list
- "When is the library open?" / "e-resource login credentials" — deterministic facts, no secrets
- "Build a SQL table" — implementation refusal + concept bridge (deliberate safety demo)
- "hi i wanna start learning AIML" / "who are you" — onboarding + identity

**Do NOT demo (off-corpus → weak or out-of-scope answers):**
- Astronomy / history / medicine / any non-(AIML|DBMS|OS|DSA) topic (e.g. "books about stars")
- Agent frameworks beyond the seeded anchors (no LangChain/AutoGPT papers in corpus)
- Requests for live OPAC availability, real-time barcode checks, or full Pearson textbook text
- Niche sub-topics with <2 sources in the graph (sparse regions)

## Librarian upload (token) demo

The upload endpoint is guarded by the librarian bearer token. Export it before
`start_pilot.sh`, then:

```bash
# 401 without token
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:5151/api/ingest -F 'file=@paper.pdf'

# 202 with token (returns job_id, poll GET /api/ingest/<job_id> until COMPLETE)
curl -s -X POST http://127.0.0.1:5151/api/ingest \
  -H "Authorization: Bearer $ARCHIPELAGO_LIBRARIAN_TOKEN" \
  -F 'file=@paper.pdf' -F 'kind=paper'
```

Verification: `GET http://127.0.0.1:5151/api/documents` lists the new doc, and
`http://127.0.0.1:5150/api/stats` (header `X-Archipelago-Token: $ARCHIPELAGO_LIBRARIAN_TOKEN`)
shows node count grew; merge is a full rebuild from merged OKF results — prior pilot
docs are retained (a safety guard aborts the swap if prior docs would be wiped).

**Restart after any code edit:** `./scripts/ops/serve.sh restart`
**Full bounce after config/env change:** `./scripts/ops/serve.sh stop; ./scripts/ops/serve.sh start`
