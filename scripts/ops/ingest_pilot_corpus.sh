#!/usr/bin/env bash
# Ingest the curated CS/ML pilot corpus into the local Archipelago graph.
# Uses the project venv + local model path (never system python for GPU work).
#
# Source of truth: pilot_corpus/MANIFEST.tsv (sha256 + path + role).
#   core     — always ingested (5 papers + syllabus seed)
#   optional — only when INCLUDE_MATH_ML=1 (Deisenroth textbook, ~17 MB)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "ERROR: expected venv at .venv/bin/python — create/activate the project venv first." >&2
  exit 1
fi

LOGDIR="${ROOT}/ingest_logs"
mkdir -p "$LOGDIR"

MANIFEST="${ROOT}/pilot_corpus/MANIFEST.tsv"
if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: pilot manifest not found at ${MANIFEST}" >&2
  echo "Generate it first (see pilot_corpus/README.md)." >&2
  exit 1
fi

INCLUDE_OPTIONAL="${INCLUDE_MATH_ML:-0}"

DOCS=()
while IFS=$'\t' read -r path _sha _size role; do
  [[ "$path" == "path" ]] && continue  # header
  if [[ "$role" == "core" ]]; then
    DOCS+=("$path")
  elif [[ "$role" == "optional" && "$INCLUDE_OPTIONAL" == "1" ]]; then
    DOCS+=("$path")
  fi
done < "$MANIFEST"

if [[ "${#DOCS[@]}" -eq 0 ]]; then
  echo "ERROR: pilot manifest is empty — no documents to ingest." >&2
  exit 1
fi

echo "=== Archipelago pilot corpus ingest ==="
echo "Root: $ROOT"
echo "Manifest: $MANIFEST"
echo "Documents: ${#DOCS[@]}"
echo "Tip: stop inference_server first if it holds the okf_graph.db lock."
echo

failed=0
for d in "${DOCS[@]}"; do
  if [[ ! -e "$d" ]]; then
    echo "SKIP missing: $d"
    failed=$((failed + 1))
    continue
  fi
  base="$(basename "$d")"
  log="$LOGDIR/pilot_${base%.*}.log"
  echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] START $d -> $log ==="
  if "$PY" okf_pipeline.py --add "$d" --local >"$log" 2>&1; then
    echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] DONE  $d ==="
  else
    rc=$?
    echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] FAILED $d (rc=$rc), see $log ==="
    failed=$((failed + 1))
  fi
done

echo
if [[ "$failed" -gt 0 ]]; then
  echo "=== FINISHED WITH $failed failure(s)/skip(s) ==="
  exit 1
fi
echo "=== ALL PILOT DOCS INGESTED ==="
echo "Next: ./scripts/ops/serve.sh restart && ./scripts/ops/pilot_readiness.sh"
