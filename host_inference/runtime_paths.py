"""Choose a writable scratch directory for disposable hosted artifacts."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

HOST_ROOT = Path(__file__).resolve().parent
RUNTIME_CACHE_ENV = "ARCHIPELAGO_RUNTIME_CACHE_DIR"


def runtime_cache_dir() -> Path:
    """Use local cache on a workstation and scratch storage in Vercel Functions."""
    configured = os.environ.get(RUNTIME_CACHE_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if os.environ.get("VERCEL", "").strip():
        return Path(tempfile.gettempdir()) / "archipelago-cache"
    return HOST_ROOT / "cache"
