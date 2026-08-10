#!/usr/bin/env bash
# One-command pilot launch for Archipelago.
#
#   ARCHIPELAGO_LIBRARIAN_TOKEN='change-me' ./scripts/ops/start_pilot.sh
#
# What it does:
#   1. Requires ARCHIPELAGO_LIBRARIAN_TOKEN (or --allow-open for local dev only).
#   2. Starts the 3 services via serve.sh (inference :5151, graph :5150, chat :5152)
#   3. Runs the 7-query demo gate (scripts/ops/demo_check.sh)
#   4. Prints the pilot URL table
#
# Exits non-zero if any service fails to come up or any demo query fails.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ALLOW_OPEN=0
for arg in "$@"; do
  case "$arg" in
    --allow-open|--dev) ALLOW_OPEN=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

echo "=== Archipelago pilot launch ==="

if [[ -z "${ARCHIPELAGO_LIBRARIAN_TOKEN:-}" && -z "${ARCHIPELAGO_TOKEN:-}" ]]; then
  if [[ "$ALLOW_OPEN" == "1" ]]; then
    echo ""
    echo "  WARNING: --allow-open in effect, librarian endpoints are OPEN."
    echo "           Local dev only. NEVER on a shared machine."
    echo ""
  else
    cat >&2 <<'EOF'
ERROR: ARCHIPELAGO_LIBRARIAN_TOKEN is not set.

A librarian token is REQUIRED for pilot/demo deployments. Students use the
chat UI without any token; only librarian upload/delete needs it.

For local development WITHOUT a token, pass --allow-open:
    ./scripts/ops/start_pilot.sh --allow-open

For shared machines / presentations:
    export ARCHIPELAGO_LIBRARIAN_TOKEN="$(openssl rand -hex 24)"
    ./scripts/ops/start_pilot.sh
EOF
    exit 2
  fi
fi

./scripts/ops/serve.sh start || { echo "ERROR: services failed to start"; exit 1; }

echo ""
echo "Running 7-query demo gate (proves routing is live, not stale) ..."
if ./scripts/ops/demo_check.sh; then
  DEMO=OK
else
  DEMO=FAILED
fi

cat <<'EOF'

Pilot URLs
  Student    http://localhost:5152            query only (no token, no upload)
  Librarian  http://localhost:5150            Librarian tab: upload / delete / manual nodes
  API        http://localhost:5151            backend

After a restart, hard-refresh browsers (Ctrl+Shift+R).
Ollama (localhost:11434) is optional — without it, chat uses template answers.

Pilot scope: chat over the pilot PDFs + seed concepts; prereqs / related /
books for topics in the graph. Not in scope: perfect textbooks for every
topic, or "any PDF becomes a perfect knowledge graph". See PILOT_LAUNCH.md.
EOF

if [[ "$DEMO" == "FAILED" ]]; then
  echo "WARNING: demo gate FAILED — a running process is stale or answering from"
  echo "the wrong tree. Try: ./scripts/ops/serve.sh restart && ./scripts/ops/demo_check.sh"
  exit 1
fi
