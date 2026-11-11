"""Normalize query terms for lexical and fuzzy graph retrieval."""

from __future__ import annotations

import re

_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "by",
    "at",
    "is",
    "are",
    "was",
    "were",
    "what",
    "which",
    "how",
    "why",
    "explain",
    "tell",
    "me",
    "about",
    "something",
    "vaguely",
    "related",
    "concept",
    "topic",
    "information",
}


def _clean_query_tokens(text: str) -> str:
    """Filter generic noise words and stopwords before lexical matching."""
    tokens = re.findall(r"\w+", text.lower())
    meaningful = [token for token in tokens if token not in _STOPWORDS]
    return " ".join(meaningful) if meaningful else text.strip().lower()
