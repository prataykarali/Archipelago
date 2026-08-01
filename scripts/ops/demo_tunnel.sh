#!/bin/bash
# Archipelago demo launcher — locked-down tunnel mode.
cd "$(dirname "$0")/../.."
TOKEN=$(cat ~/.archipelago_demo_token 2>/dev/null)
if [ -z "$TOKEN" ]; then
  TOKEN=$(openssl rand -hex 16)
  echo "$TOKEN" > ~/.archipelago_demo_token
  chmod 600 ~/.archipelago_demo_token
fi
export ARCHIPELAGO_SERVE_UI=1
export ARCHIPELAGO_LIBRARIAN_TOKEN="$TOKEN"
export ARCHIPELAGO_PDF_BASE_URL="${DEMO_PUBLIC_URL:-https://treason-reversing-snooze.ngrok-free.dev}"
exec .venv/bin/python -m archipelago.apps.inference_app
