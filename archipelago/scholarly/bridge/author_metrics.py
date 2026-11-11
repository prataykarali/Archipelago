"""Fetch first-author bibliometrics from OpenAlex without guessing missing indices."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import requests

AUTHOR_REQUEST_TIMEOUT_SECONDS = 8
AUTHOR_WORKERS = 4
OPENALEX_AUTHOR_PREFIX = "https://openalex.org/A"


def _fetch_author(author_id: str) -> dict[str, Any] | None:
    if not author_id.startswith(OPENALEX_AUTHOR_PREFIX):
        return None
    try:
        response = requests.get(
            f"https://api.openalex.org/authors/{author_id.rsplit('/', 1)[-1]}",
            headers={"User-Agent": "Archipelago-Research/2.1 (author metric evidence)"},
            timeout=AUTHOR_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        author = response.json()
    except (requests.RequestException, ValueError):
        return None
    if author.get("id") != author_id:
        return None
    return {
        "author_id": author_id,
        "name": author.get("display_name"),
        "h_index": (author.get("summary_stats") or {}).get("h_index"),
        "i10_index": (author.get("summary_stats") or {}).get("i10_index"),
        "total_citations": author.get("cited_by_count"),
        "publication_count": author.get("works_count"),
        "source_timestamp": datetime.now(UTC).isoformat(),
        "source_url": author_id,
    }


def first_author_metrics(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return source-reported metrics for each unique first OpenAlex author."""
    ids = {
        values[0]
        for item in items
        if (values := (item.get("source_metadata") or {}).get("author_openalex_ids") or [])
        and isinstance(values[0], str)
    }
    with ThreadPoolExecutor(max_workers=AUTHOR_WORKERS) as pool:
        results = list(pool.map(_fetch_author, sorted(ids)))
    return {item["author_id"]: item for item in results if item}
