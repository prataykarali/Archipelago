"""Normalize existing catalog feeds into versioned academic observations."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import re
from typing import Any

from .store import AcademicStore

_EDITION = re.compile(r"\b(\d+)(?:st|nd|rd|th)?\s+(?:ed(?:ition)?|e)\b", re.I)
_SPACE = re.compile(r"\s+")


def _plain(value: Any) -> str:
    return _SPACE.sub(" ", str(value or "")).strip()


def _revision(row: dict[str, Any]) -> str:
    """Hash only source-backed metadata; retrieval time is not a revision."""
    content = {
        key: value for key, value in row.items() if key not in {"retrieved_at", "checked_at"}
    }
    return sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()


def normalize_koha(row: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    """Use Koha's stable bibliographic number and edition-aware identity."""
    source_id = _plain(row.get("biblionumber"))
    title = _plain(row.get("Title"))
    if not source_id.isdigit() or not title:
        raise ValueError("Koha record needs a numeric biblionumber and title")
    isbn = re.sub(r"[^0-9X]", "", _plain(row.get("isbn")).upper())
    edition_match = _EDITION.search(title)
    edition = _plain(row.get("Edition")) or (edition_match.group(1) if edition_match else "")
    identity = f"isbn:{isbn}:edition:{edition}" if isbn else f"koha:{source_id}"
    copy_count = _plain(row.get("No. of copies"))
    available = _plain(row.get("Available Copies"))
    return {
        "provider": "koha_export",
        "source_id": source_id,
        "title": title,
        "isbn": isbn,
        "edition": edition,
        "identity_key": identity,
        "revision": _revision(row),
        "availability_status": "catalog_snapshot" if copy_count or available else "metadata_only",
    }, row


def normalize_opac(row: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    """Treat public arrivals as metadata, never as a live holding count."""
    source_id = _plain(row.get("biblionumber"))
    title = _plain(row.get("title"))
    if not source_id.isdigit() or not title:
        raise ValueError("OPAC record needs a numeric biblionumber and title")
    return {
        "provider": "opac_arrivals",
        "source_id": source_id,
        "title": title,
        "isbn": "",
        "edition": "",
        "identity_key": f"koha:{source_id}",
        "revision": _revision(row),
        "availability_status": "metadata_only",
    }, row


def normalize_pearson(row: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    """Retain licensed bookshelf metadata without implying extractable text."""
    source_id = _plain(row.get("id"))
    title = _plain(row.get("title"))
    if not source_id or not title:
        raise ValueError("Pearson record needs an id and title")
    isbn = re.sub(r"[^0-9X]", "", _plain(row.get("isbn")).upper())
    edition_match = _EDITION.search(title)
    edition = _plain(row.get("edition")) or (edition_match.group(1) if edition_match else "")
    identity = f"isbn:{isbn}:edition:{edition}" if isbn else f"pearson:{source_id}"
    public_metadata = {
        key: value
        for key, value in row.items()
        if key not in {"subscription_id", "reader_base_url"}
    }
    return {
        "provider": "pearson_bookshelf",
        "source_id": source_id,
        "title": title,
        "isbn": isbn,
        "edition": edition,
        "identity_key": identity,
        "revision": _revision(public_metadata),
        "availability_status": "licensed_metadata_only",
    }, public_metadata


NORMALIZERS = {
    "koha_export": normalize_koha,
    "opac_arrivals": normalize_opac,
    "pearson_bookshelf": normalize_pearson,
}


def reconcile(
    store: AcademicStore, provider: str, rows: list[dict[str, Any]], *, complete: bool = False
) -> dict[str, Any]:
    """Apply a successful source batch; absence never implies withdrawal."""
    if provider not in NORMALIZERS:
        raise ValueError("Unsupported academic source")
    if not rows:
        store.provider_result(provider, error="empty_response")
        return {"provider": provider, "status": "unavailable", "counts": {}}
    normalized = [NORMALIZERS[provider](row) for row in rows]
    seen: set[str] = set()
    for record, _payload in normalized:
        key = record["source_id"]
        if key in seen:
            raise ValueError(f"Duplicate source identifier: {key}")
        seen.add(key)
    counts: Counter[str] = Counter()
    for record, payload in normalized:
        counts[store.observe(record, payload)] += 1
    store.provider_result(provider)
    return {
        "provider": provider,
        "status": "complete" if complete else "partial",
        "counts": dict(counts),
    }
