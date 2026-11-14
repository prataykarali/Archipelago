#!/usr/bin/env bash
# One-shot SoFerence booth boot: Ollama warm + three services on 5150/5151/5152
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export ARCHIPELAGO_OLLAMA_MODEL="${ARCHIPELAGO_OLLAMA_MODEL:-qwen3.5:0.8b}"
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-0}"
export ARCHIPELAGO_OLLAMA_NUM_PREDICT="${ARCHIPELAGO_OLLAMA_NUM_PREDICT:-320}"
export ARCHIPELAGO_PDF_BASE_URL="${ARCHIPELAGO_PDF_BASE_URL:-http://localhost:5151}"

echo "=== SoFerence boot ==="
echo "  model=${ARCHIPELAGO_OLLAMA_MODEL} keep_alive=${OLLAMA_KEEP_ALIVE}"

# Ensure Ollama is reachable without pinning any model in GPU memory
if command -v ollama >/dev/null 2>&1; then
  curl -sf --max-time 10 "${OLLAMA_HOST}/api/generate" \
    -d "{\"model\":\"${ARCHIPELAGO_OLLAMA_MODEL}\",\"prompt\":\"\",\"stream\":false,\"keep_alive\":0}" \
    >/dev/null 2>&1 || true
  ollama ps || true
fi

bash "${ROOT}/scripts/ops/serve.sh" restart || bash "${ROOT}/scripts/ops/serve.sh" start
bash "${ROOT}/scripts/ops/serve.sh" status

echo ""
echo "Chat UI:  http://127.0.0.1:5152"
echo "API:      http://127.0.0.1:5151/api/readiness"
echo "Graph:    http://127.0.0.1:5150"
echo "Bench:    bash scripts/ops/soference_bench.sh"
