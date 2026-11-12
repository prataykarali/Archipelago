"""Bounded paper discovery for review without ingesting source content."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote

import requests

SOURCE_TIMEOUT_SECONDS = 12
RESULTS_PER_TOPIC = 20
MAX_TOPIC_CHARS = 160
MAX_ABSTRACT_CHARS = 1200
OPENALEX_URL = "https://api.openalex.org/works"
SCHOLAR_URL = "https://scholar.google.com/scholar?q="
USER_AGENT = "ArchipelagoResearch/1.0 (metadata discovery)"


def _abstract(index: object) -> str:
    """Decode an OpenAlex inverted index into a short readable excerpt."""
    if not isinstance(index, dict):
        return ""
    words: dict[int, str] = {}
    for word, positions in index.items():
        if isinstance(positions, list):
            for position in positions:
                if isinstance(position, int) and 0 <= position < 1000:
                    words[position] = str(word)
    return " ".join(words[position] for position in sorted(words))[:MAX_ABSTRACT_CHARS]


def discover(topic: str) -> dict[str, object]:
    """Return source-linked OpenAlex candidates and a Scholar review link."""
    topic = " ".join(topic.split())
    if not 3 <= len(topic) <= MAX_TOPIC_CHARS:
        raise ValueError("invalid_topic")
    response = requests.get(
        OPENALEX_URL,
        params={"search": topic, "per_page": RESULTS_PER_TOPIC},
        headers={"User-Agent": USER_AGENT},
        timeout=SOURCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    items = response.json().get("results", [])
    if not isinstance(items, list):
        raise ValueError("invalid_provider_response")
    candidates = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("display_name") or "").strip()
        source_url = str(item.get("doi") or item.get("id") or "").strip()
        if not title or not source_url.startswith("https://"):
            continue
        candidates.append(
            {
                "title": title[:300],
                "source_url": source_url,
                "published_at": item.get("publication_date"),
                "abstract": _abstract(item.get("abstract_inverted_index")),
                "provider": "OpenAlex",
                "ingestion_status": "not_started",
            }
        )
    return {
        "topic": topic,
        "candidates": candidates,
        "papers": [
            {
                "title": item["title"],
                "source_url": item["source_url"],
                "source_name": item["provider"],
                "abstract": item["abstract"],
            }
            for item in candidates
        ],
        "sources": {"OpenAlex": f"ok: {len(candidates)} candidates"},
        "scholar_review_url": SCHOLAR_URL + quote(topic),
        "discovered_at": datetime.now(UTC).isoformat(),
        "ingestion_status": "not_started",
    }
