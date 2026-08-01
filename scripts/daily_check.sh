#!/bin/bash
# Daily morning check for Archipelago pilot
# Usage: bash scripts/daily_check.sh
# Returns 0 if all checks pass, 1 otherwise.

set -e
PASS=0
FAIL=0

echo "=== Archipelago Daily Check — $(date) ==="

# 1. Servers
echo -n "[1/5] Servers: "
curl -sf http://localhost:5051/api/readiness > /dev/null && echo -n "inference:ON " || { echo "FAIL"; FAIL=$((FAIL+1)); }
curl -sf -o /dev/null http://localhost:5052/ && echo -n "chat:ON " || { echo "FAIL"; FAIL=$((FAIL+1)); }
curl -sf -o /dev/null http://localhost:5050/ && echo "graph:ON" || { echo "FAIL"; FAIL=$((FAIL+1)); }

# 2. Ollama
echo -n "[2/5] Ollama: "
curl -sf http://localhost:11434/api/tags > /dev/null && echo "ON" || { echo "OFF"; echo "  WARNING: Start Ollama with 'ollama serve'"; FAIL=$((FAIL+1)); }

# 3. Tests
echo -n "[3/5] Unit tests: "
cd /home/pratay-karali/Desktop/libraryAI/libraryAI
python3 -m pytest tests/unit/ -q > /tmp/test_output.txt 2>&1 && echo "PASS" || { echo "FAIL"; tail -5 /tmp/test_output.txt; FAIL=$((FAIL+1)); }
PASS=$((PASS+1))

# 4. Smoke test
echo -n "[4/5] Smoke test: "
python3 -c "
import requests, json
BASE='http://localhost:5051/api/chat'
tests = [
    ('What is attention mechanism?', 'graph_strong'),
    ('best books on DBMS', 'library_books'),
    ('When is the library open?', 'library_info'),
    ('Build a SQL table for users', 'implementation_request'),
    ('e-resource login credentials', 'library_info'),
]
all_ok = True
for q, route in tests:
    try:
        r = requests.post(BASE, json={'query':q, 'mode':'rag_synthesis', 'synthesis': False, 'session_id':'smoke'}, stream=True, timeout=10)
        body = ''.join(chunk.decode() for chunk in r.iter_content(8192))
        if route in body:
            continue
        else:
            print(f'FAIL: {q[:30]:30s} expected {route}', end='')
            all_ok = False
    except Exception as e:
        print(f'FAIL: {q[:30]:30s} error: {e}', end='')
        all_ok = False
if all_ok:
    print('ALL PASS')
else:
    print()
" 2>&1

# 5. Link verification
echo -n "[5/5] Citation links: "
python3 -c "
import requests
r = requests.get('http://localhost:5051/api/page-view?doc_id=papers%2FBahdanau2014_Attention.pdf&page=4&highlight=Attention', timeout=5)
assert r.status_code == 200, f'page-view {r.status_code}'
data = r.json()
assert data.get('passage'), 'no passage text'
assert data.get('cited_spans'), 'no highlight spans'
print('PASS')
" 2>&1 && PASS=$((PASS+1)) || { echo "FAIL"; FAIL=$((FAIL+1)); }

echo ""
echo "=== SUMMARY ==="
echo "Passed: $PASS checks"
echo "Failed: $FAIL checks"
echo ""
if [ "$FAIL" -gt 0 ]; then
    echo "❌ Some checks failed — review above."
    exit 1
else
    echo "✅ All checks passed — ready for demo."
    exit 0
fi
