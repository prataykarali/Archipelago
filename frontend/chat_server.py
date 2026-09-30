"""Compatibility entrypoint for the canonical root chat service."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chat_server import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("ARCHIPELAGO_CHAT_PORT", os.environ.get("PORT", "5152")))
    app.run(host=os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1"), port=port, debug=False)
