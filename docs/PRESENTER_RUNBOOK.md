# Archipelago Pilot — 5-Minute Presenter Runbook

## Before the demo (morning check)

```bash
# 1. Verify servers are up
curl -s http://localhost:5051/api/readiness | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['ready'], 'Inference down'"
curl -s -o /dev/null -w "%{http_code}" http://localhost:5052/ | grep -q 200 || echo "Chat UI down!"
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/ | grep -q 200 || echo "Graph UI down!"

# 2. Verify Ollama model is available
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); models=[m['name'] for m in d.get('models',[])]; assert 'qwen3.5:0.8b' in models, 'Model missing'"

# 3. Run test suite
cd /home/pratay-karali/Desktop/libraryAI/libraryAI
python3 -m pytest tests/unit/ -q --timeout=15 2>&1 | tail -3

# 4. Quick smoke test (5 queries covering all pilot routes)
python3 -c "
import requests, json
BASE='http://localhost:5051/api/chat'
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
1. Open http://localhost:5052 in browser
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
3. Mention: "460 concepts from 6 books and ~15 papers in the pilot corpus"

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

| Symptom | Fix |
|---|---|
| "Offline" status | `python3 inference_server.py &` starts on :5051 |
| "Library closed" message | Start Ollama: `ollama serve` → `ollama pull qwen3.5:0.8b` |
| Blank chat page | `python3 chat_server.py &` starts on :5052 |
| Citation link 404s | Page not in KuzuDB — report the doc_id, never invent |
| Embeddings not ready | Restart inference server; wait 5s for Snowflake model to load |

---

*Last reviewed: Jul 23, 2026. Verify with library before each demo; stamp review date.*

## Server Restart Order (after code changes)

1. **Stop all servers**: `pkill -f inference_server.py; pkill -f chat_server.py; pkill -f graph_server.py`
2. **Start inference**: `python3 inference_server.py &` (port 5051 — wait for "Snowflake" + "qwen3.5:0.8b" ready)
3. **Start chat UI**: `python3 chat_server.py &` (port 5052)
4. **Start graph UI**: `python3 graph_server.py &` (port 5050)
5. **Readiness check**: `curl -s http://localhost:5051/api/readiness | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['ready'], 'Inference down'"`
6. **Restart Ollama if needed**: `ollama serve & sleep 3; ollama pull qwen3.5:0.8b`

**Ports**: 5051 (inference), 5052 (chat UI), 5050 (graph UI), 11434 (Ollama)
