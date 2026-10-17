"""Choose writable disposable paths for the hosted runtime."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

HOST_ROOT = Path(__file__).resolve().parent
VERCEL_ENV_KEYS = ("VERCEL", "VERCEL_ENV")


def cache_dir() -> Path:
    """Return the writable cache directory for this deployment."""
    if any(os.getenv(key) for key in VERCEL_ENV_KEYS):
        return Path(tempfile.gettempdir()) / "archipelago-cache"
    return HOST_ROOT / "cache"
