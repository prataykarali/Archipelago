"""Discover UEM repository item metadata from its public Atom feed."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from urllib.parse import urlparse

from defusedxml import ElementTree as ET
import requests

FEED_URL = "https://ds7-backend.ndl.gov.in:8443/uemk/opensearch/search?format=atom&query=*"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
REPOSITORY_HOST = "uemk.ndl.gov.in"
MAX_FEED_BYTES = 256_000
MAX_ENTRIES = 100
REQUEST_TIMEOUT_SECONDS = 15


def discover_repository_items() -> tuple[list[dict[str, str]], dict[str, object]]:
    """Return source-linked item candidates without downloading document files."""
    response = requests.get(
        FEED_URL,
        headers={"User-Agent": "ArchipelagoAcademic/1.0 (repository metadata monitor)"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    if len(response.content) > MAX_FEED_BYTES:
        raise ValueError("Repository feed exceeds size limit")
    root = ET.fromstring(response.content)
    if root.tag != f"{ATOM_NS}feed":
        raise ValueError("Invalid repository Atom feed")
    items: list[dict[str, str]] = []
    for entry in root.findall(f"{ATOM_NS}entry")[:MAX_ENTRIES]:
        title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
        updated_at = (entry.findtext(f"{ATOM_NS}updated") or "").strip()
        identifier = (entry.findtext(f"{ATOM_NS}id") or "").strip()
        parsed = urlparse(identifier)
        if (
            not title
            or parsed.hostname != REPOSITORY_HOST
            or not parsed.path.startswith("/handle/")
        ):
            continue
        items.append(
            {
                "title": title[:300],
                "source_url": f"https://{REPOSITORY_HOST}{parsed.path}",
                "updated_at": updated_at,
                "ingestion_status": "not_started",
            }
        )
    stable_items = sorted(items, key=lambda item: item["source_url"])
    metadata: dict[str, object] = {
        "source_url": FEED_URL,
        "fetched_at": datetime.now(UTC).isoformat(),
        "sha256": hashlib.sha256(json.dumps(stable_items, sort_keys=True).encode()).hexdigest(),
        "count": len(items),
    }
    return items, metadata
