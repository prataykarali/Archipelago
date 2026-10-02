"""Single source of truth for the on-disk library inventory, and its caches.

The ingestion worker calls :func:`clear_all_inventory_caches` after a document
is merged so the next request re-reads ``pdfs/upload_inventory.json``. The
worker imports it defensively (``try: … except ImportError``) because the
module was, until now, missing entirely — the import always failed and the
cache was never invalidated, so a freshly ingested book could stay invisible to
the library screens for the life of the process.

Keeping the reader here means one definition of "what the library holds":
``upload_inventory.json`` rows whose ``graph_ready`` flag is true, plus any
catalog the librarian imported.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import threading
from typing import Any

from okf.config import BASE_DIR

logger = logging.getLogger(__name__)

INVENTORY_FILENAME = "upload_inventory.json"

# Cached rows plus the file size/mtime they were derived from, so a change on
# disk invalidates the cache even if a caller forgets to clear it explicitly.
_cache_lock = threading.Lock()
_cached_rows: list[dict[str, Any]] | None = None
_cached_stamp: tuple[int, int] | None = None


def inventory_path(base_dir: Path | str | None = None) -> Path:
    """Absolute path of the upload inventory file."""
    root = Path(base_dir if base_dir is not None else BASE_DIR)
    return root / "pdfs" / INVENTORY_FILENAME


def _stamp(path: Path) -> tuple[int, int] | None:
    """(size, mtime) fingerprint, or None when the file is absent."""
    if not path.is_file():
        return None
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def read_inventory(base_dir: Path | str | None = None, use_cache: bool = True) -> list[dict[str, Any]]:
    """Return every recorded upload row.

    Never raises: a missing or corrupt inventory is an empty library, not a
    failed request.
    """
    path = inventory_path(base_dir)
    with _cache_lock:
        stamp = _stamp(path)
        if use_cache and _cached_rows is not None and stamp == _cached_stamp:
            return list(_cached_rows)

    rows: list[dict[str, Any]] = []
    stamp = _stamp(path)
    if stamp is not None:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                rows = [row for row in loaded if isinstance(row, dict)]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Unreadable upload inventory at %s: %s", path, exc)
            rows = []

    with _cache_lock:
        global _cached_rows, _cached_stamp
        _cached_rows, _cached_stamp = rows, stamp
    return list(rows)


def searchable_inventory(base_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Only rows whose document actually reached the graph.

    A metadata-only upload (title/ISBN known, body not ingested) is still in
    the library, but it must not be offered as a citable source.
    """
    return [row for row in read_inventory(base_dir) if row.get("graph_ready")]


def clear_all_inventory_caches() -> None:
    """Invalidate the cached rows so the next read hits disk."""
    global _cached_rows, _cached_stamp
    with _cache_lock:
        _cached_rows = None
        _cached_stamp = None


__all__ = [
    "INVENTORY_FILENAME",
    "clear_all_inventory_caches",
    "inventory_path",
    "read_inventory",
    "searchable_inventory",
]
