#!/usr/bin/env bash
# SoFerence smoke bench — sequential queries against live inference :5151
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API="${ARCHIPELAGO_INFERENCE_URL:-http://127.0.0.1:5151}"
OUT="${ROOT}/logs/soference_bench_$(date +%Y%m%d-%H%M%S).jsonl"
mkdir -p "${ROOT}/logs"

queries=(
  "what is RAG?"
  "What is LoRA?"
  "what is SQL?"
  "what is an AI agent"
  "what is paging in operating systems"
  "what is PagedAttention in vLLM"
  "what is QLoRA"
  "what is third normal form 3NF"
  "What are the working hours of the central library?"
  "Does the library provide access to IEEE Xplore? What are the credentials?"
  "What is the passkey for the National Digital Library of India (NDLI) Club?"
  "hi what is RAG?"
)

echo "SoFerence bench → ${API}/api/chat"
echo "log: ${OUT}"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.used,utilization.gpu --format=csv,noheader || true
fi

pass=0
fail=0
for q in "${queries[@]}"; do
  t0=$(date +%s%3N)
  body=$(python3 -c 'import json,sys; print(json.dumps({"query":sys.argv[1],"session_id":"bench"}))' "$q")
  raw=$(curl -sS -N -X POST "${API}/api/chat" \
    -H 'Content-Type: application/json' \
    -d "$body" \
    --max-time 180 || echo "CURL_FAIL")
  t1=$(date +%s%3N)
  ms=$((t1 - t0))
  # Parse first JSON line as meta when present
  meta=$(printf '%s' "$raw" | head -n1)
  text=$(printf '%s' "$raw" | sed '1,/\[STREAM_START\]/d' | head -c 400)
  ok=1
  echo "$raw" | grep -q '\[STREAM_START\]' || ok=0
  [[ "$raw" == *CURL_FAIL* ]] && ok=0
  if [[ $ok -eq 1 ]]; then
    ((pass++)) || true
    status=PASS
  else
    ((fail++)) || true
    status=FAIL
  fi
  printf '{"status":"%s","ms":%s,"query":%s,"meta_head":%s,"text_head":%s}\n' \
    "$status" "$ms" \
    "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$q")" \
    "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1][:300]))' "$meta")" \
    "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$text")" \
    | tee -a "$OUT"
  echo "  [$status ${ms}ms] $q"
done

echo ""
echo "RESULT pass=$pass fail=$fail log=$OUT"
[[ $fail -eq 0 ]]
