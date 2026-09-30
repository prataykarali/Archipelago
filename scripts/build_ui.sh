#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "Building library_showcase_3d.js from books_showcase_src.tsx..."
npx esbuild books_showcase_src.tsx \
  --bundle \
  --outfile=ui/chat/library_showcase_3d.js \
  --external:three

echo "Done. Output: ui/chat/library_showcase_3d.js"
