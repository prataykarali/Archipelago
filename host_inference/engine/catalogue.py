"""Read the institutional catalogue for the hosted inference service.

The hosted app runs on AntDeploy without the institution's KùzuDB, so it loads
the catalogue from the same export the library computer populates from. Two
sources, merged:

- ``data/catalogs/pearson_bookshelf.json`` — the institutional book list, with
  ISBN, reader deep-links, and domain;
- ``host_inference/cache/pearson_bookshelf.json`` — the hosted copy.

Falls back to an empty catalogue rather than raising: an unavailable catalogue
degrades the shelf card to an honest "not indexed", it does not take the chat
down.
"""

from __future__ import annotations

from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Any

from remote_cache import CACHE

logger = logging.getLogger(__name__)

# Searched in order; the first readable file wins. Host-relative paths only, so
# the service is portable between the library computer and the cloud.
CATALOGUE_PATHS = (
    CACHE / "pearson_bookshelf.json",
    Path("data/catalogs/pearson_bookshelf.json"),
    Path("host_inference/cache/pearson_bookshelf.json"),
    Path("../data/catalogs/pearson_bookshelf.json"),
)


def _candidate_roots() -> list[Path]:
    """Directories to search, most specific first."""
    roots: list[Path] = [Path.cwd()]
    here = Path(__file__).resolve()
    # services/engines/ -> host_inference -> repo root
    for parent in here.parents:
        roots.append(parent)
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.add(root)
            unique.append(root)
    return unique


def find_catalogue_file() -> Path | None:
    """First existing catalogue export, or None."""
    for root in _candidate_roots():
        for relative in CATALOGUE_PATHS:
            candidate = root / relative
            if candidate.is_file():
                return candidate
    return None


def _normalise(book: dict[str, Any]) -> dict[str, Any]:
    """Project one export entry onto the fields a shelf card needs."""
    title = str(book.get("title") or "").strip()
    return {
        "title": title,
        "author": str(book.get("author") or "").strip(),
        # Pearson exports carry ISBN rather than a Koha call number. It is the
        # only stable shelf identifier the hosted service has.
        "biblionumber": str(book.get("isbn") or "").strip(),
        "publisher": "Pearson eLibrary",
        "isbn": str(book.get("isbn") or "").strip(),
        "domain": str(book.get("domain") or "").strip(),
        # This e-resource export does not establish physical holdings.
        "total_copies": 0,
        "available_copies": 0,
        "barcodes": [],
        "page_count": int(book.get("page_count") or 0),
        "subscription_id": str(book.get("subscription_id") or "").strip(),
        "reader_base_url": str(book.get("reader_base_url") or "").strip(),
        "external_id": str(book.get("id") or "").strip(),
        "cover_url": str(book.get("cover_url") or "").strip(),
    }


def load_catalogue() -> list[dict[str, Any]]:
    """Every catalogue record, de-duplicated on title+ISBN.

    Cached: the export is static for the life of a deployment, and this is read
    on the shelf-routing path of every query.
    """
    return _load_catalogue_cached()


@lru_cache(maxsize=1)
def _load_catalogue_cached() -> tuple[dict[str, Any], ...]:
    path = find_catalogue_file()
    if path is None:
        logger.info("No catalogue export found; shelf cards will report 'not indexed'")
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable catalogue export %s: %s", path, exc)
        return ()

    books = payload.get("books", []) if isinstance(payload, dict) else []
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for book in books:
        if not isinstance(book, dict):
            continue
        record = _normalise(book)
        if not record["title"]:
            continue
        key = (record["title"].lower(), record["isbn"])
        records.setdefault(key, record)
    logger.info("Loaded %d catalogue records from %s", len(records), path.name)
    return tuple(records.values())


def clear_cache() -> None:
    """Drop the cached catalogue (after a librarian repopulates it)."""
    _load_catalogue_cached.cache_clear()


def catalogue_size() -> int:
    """Number of catalogue records available to the shelf router."""
    return len(_load_catalogue_cached())


def reader_link(record: dict[str, Any], page: int = 1) -> str:
    """Deep link into the Pearson reader for a catalogue record."""
    base = str(record.get("reader_base_url") or "")
    if not base:
        return ""
    return f"{base}#page={page}" if page > 1 else base


__all__ = [
    "CATALOGUE_PATHS",
    "catalogue_size",
    "clear_cache",
    "find_catalogue_file",
    "load_catalogue",
    "reader_link",
]
