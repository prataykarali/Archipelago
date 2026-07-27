#!/bin/sh
# start.sh — Boot Archipelago inside the container
#
# Graph server runs in the background on port 5050 (internal, not exposed).
# Inference server (Gunicorn) is the main process and listens on $PORT (default 8080).
# Northflank / Render / Railway all inject PORT=8080 automatically.

set -e

# Respect PORT env var; default to 8080 for Northflank
PORT=${PORT:-8080}

echo "────────────────────────────────────────────────"
echo "  Archipelago Container Starting"
echo "  Internal graph server → http://0.0.0.0:5050"
echo "  Inference server      → http://0.0.0.0:${PORT}"
echo "  Ollama host           → ${OLLAMA_HOST:-http://localhost:11434}"
echo "────────────────────────────────────────────────"

# Start graph server in background (internal only)
python graph_server.py &
GRAPH_PID=$!
echo "Graph server started (PID $GRAPH_PID)"

# Give graph server a moment to initialise before inference starts
sleep 2

# Start inference server with Gunicorn (production WSGI)
# --workers 1: single worker to avoid KuzuDB lock contention
# --threads 4: handle concurrent requests within the worker
# --timeout 300: allow long-running LLM synthesis requests
exec gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers 1 \
  --threads 4 \
  --timeout 300 \
  --worker-class sync \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  "archipelago.apps.inference_app:app"
