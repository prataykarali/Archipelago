#!/bin/sh
# start.sh — Boot both Archipelago Flask servers inside the container
# Graph server runs in the background; inference server takes PID 1 (exec)

set -e

echo "──────────────────────────────────────────────"
echo "  Archipelago Container Starting"
echo "  Graph server    → http://0.0.0.0:5050"
echo "  Inference server→ http://0.0.0.0:5051"
echo "──────────────────────────────────────────────"

# Start graph server in background
python graph_server.py &
GRAPH_PID=$!
echo "Graph server started (PID $GRAPH_PID)"

# Start inference server as main process (PID 1)
# exec replaces the shell so Docker stop/SIGTERM is handled correctly
exec python -m archipelago.apps.inference_app
