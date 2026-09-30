"""Compatibility entrypoint for the canonical root graph service."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from graph_server import app  # noqa: E402

if __name__ == "__main__":
    port = int(__import__("os").environ.get("ARCHIPELAGO_GRAPH_PORT", __import__("os").environ.get("PORT", "5150")))
    app.run(host=__import__("os").environ.get("ARCHIPELAGO_BIND", "127.0.0.1"), port=port, debug=False)
