"""Normalize query words for alias and ranking lookups."""

from __future__ import annotations


def _clean_query_words(text: str | None) -> set[str]:
    """Strip punctuation and simple trailing plurals from query words."""
    result: set[str] = set()
    for word in (text or "").lower().split():
        cleaned = word.strip("?,.!-:;()[]{}\"'")
        stem = cleaned[:-1] if cleaned.endswith("s") and len(cleaned) > 3 else cleaned
        for token in (cleaned, stem):
            if len(token) > 1:
                result.add(token)
    return result
