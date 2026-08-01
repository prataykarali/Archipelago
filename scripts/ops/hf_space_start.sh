#!/usr/bin/env bash
# Start Archipelago inference for Hugging Face Spaces (single-port demo).
set -euo pipefail
cd "$(dirname "$0")/../../.."

PORT="${PORT:-7860}"
export ARCHIPELAGO_BIND="${ARCHIPELAGO_BIND:-0.0.0.0}"
export ARCHIPELAGO_DB_READ_ONLY="${ARCHIPELAGO_DB_READ_ONLY:-1}"

# Prefer read-only graph if present; Spaces should mount or bake a small DB.
if [[ ! -e okf_graph.db && ! -d okf_graph.db ]]; then
  echo "WARN: okf_graph.db missing — chat will run with empty/partial graph."
fi

if [[ -z "${OLLAMA_HOST:-}" ]]; then
  echo "WARN: OLLAMA_HOST not set — synthesis falls back to grounded cards only."
  echo "      Point it to a GPU Ollama endpoint (e.g. http://gpu-host:11434)."
fi

# Start inference_server in the background on local interface
mkdir -p logs
export ARCHIPELAGO_BIND="127.0.0.1"
python inference_server.py > logs/inference_start.log 2>&1 &

# Start chat_server in the foreground (serves the UI and proxies to local inference)
export ARCHIPELAGO_BIND="0.0.0.0"
exec python chat_server.py
