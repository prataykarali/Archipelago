#!/usr/bin/env bash
# Recover / verify local GPU SLM after boot or driver glitch.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
LOG="${ROOT}/logs/gpu_recover.log"
mkdir -p "${ROOT}/logs"
exec >>"$LOG" 2>&1
echo "===== $(date -Is) gpu_recover ====="

echo "[1] nvidia-smi"
if ! nvidia-smi; then
  echo "GPU still dead after boot — need another reboot or driver reinstall."
  exit 1
fi

echo "[2] ollama"
systemctl --user start ollama.service 2>/dev/null || true
for i in $(seq 1 30); do
  curl -sf --max-time 1 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  sleep 0.5
done

MODEL="${ARCHIPELAGO_OLLAMA_MODEL:-qwen3.5:0.8b}"
echo "[3] unload any CPU-stuck runner, warm on GPU"
curl -sf --max-time 30 http://127.0.0.1:11434/api/generate \
  -d "{\"model\":\"${MODEL}\",\"keep_alive\":0}" >/dev/null 2>&1 || true
sleep 1
curl -sf --max-time 120 http://127.0.0.1:11434/api/chat \
  -d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"stream\":false,\"keep_alive\":-1,\"options\":{\"num_predict\":2,\"num_ctx\":2048}}" \
  >/dev/null
ollama ps || true

# Fail if still on CPU
if ollama ps 2>/dev/null | grep -qi '100% CPU'; then
  echo "WARN: model still on CPU — GPU may not be usable for Ollama yet"
  exit 2
fi

echo "[4] start Archipelago services"
bash "${ROOT}/scripts/ops/serve.sh" restart || bash "${ROOT}/scripts/ops/serve.sh" start
bash "${ROOT}/scripts/ops/serve.sh" status
echo "OK — GPU SLM recovery done"
