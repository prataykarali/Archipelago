#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "Checking the hand-written library showcase assets..."
for asset in book_cover_canvases.js library_showcase_3d.js; do
  node --check "ui/chat/$asset"
  node --check "host_inference/ui/$asset"
  cmp "ui/chat/$asset" "host_inference/ui/$asset"
done

echo "Library showcase assets are valid and in sync."
