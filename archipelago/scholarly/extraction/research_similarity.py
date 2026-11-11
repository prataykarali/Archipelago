"""Simple token overlap for explicitly scoped research relevance."""

from __future__ import annotations

import re

TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
ROUND_DIGITS = 4


def tokens(value: object) -> set[str]:
    """Return normalized word tokens."""
    return set(TOKEN.findall(str(value or "").casefold()))


def similarity(query: str, body: object) -> float | None:
    """Calculate Jaccard overlap for nonempty token sets."""
    query_tokens = tokens(query)
    body_tokens = tokens(body)
    if not query_tokens or not body_tokens:
        return None
    return round(len(query_tokens & body_tokens) / len(query_tokens | body_tokens), ROUND_DIGITS)
