"""Typed, attributed ranking fields for human-readable research exports."""

from __future__ import annotations

import math
from typing import Any

RECENT_CITATION_YEARS = 5
EARLIEST_RESEARCH_YEAR = 1800
OPENALEX_VENUE_CATEGORIES = frozenset({"peer_reviewed_journal", "peer_reviewed_conference"})


def nonnegative_number(value: Any) -> int | float | None:
    """Accept observed finite counts and rates without inventing zeroes."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return int(value) if isinstance(value, int) else float(value)


def relevance_score(paper: dict[str, Any]) -> float | None:
    """Return the query-specific relevance confidence when present."""
    relevance = paper.get("relevance_classification") or {}
    value = nonnegative_number(relevance.get("confidence"))
    return float(value) if value is not None and value <= 1 else None


def openalex_citation_percentile(paper: dict[str, Any]) -> float | None:
    """Convert OpenAlex's zero-to-one percentile to an Excel percentage."""
    observation = paper.get("citation_normalized_percentile")
    if not isinstance(observation, dict):
        return None
    value = nonnegative_number(observation.get("value"))
    return float(value) if value is not None and value <= 1 else None


def author_recent_citations(metrics: dict[str, Any], as_of_year: int) -> int | None:
    """Sum OpenAlex citations over five calendar years including retrieval year."""
    counts = metrics.get("counts_by_year")
    if not isinstance(counts, list) or not counts:
        return None
    earliest = as_of_year - RECENT_CITATION_YEARS + 1
    observed = [
        row
        for row in counts
        if isinstance(row, dict)
        and isinstance(row.get("year"), int)
        and earliest <= row["year"] <= as_of_year
    ]
    if not observed:
        return None
    total = 0
    for row in observed:
        value = row.get("cited_by_count")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return None
        total += value
    return total


def author_average_citations(metrics: dict[str, Any]) -> float | None:
    """Divide indexed citations by indexed works from one provider."""
    citations = nonnegative_number(metrics.get("citation_count"))
    publications = nonnegative_number(metrics.get("publication_count"))
    if citations is None or publications is None or publications == 0:
        return None
    return round(citations / publications, 2)


def author_m_quotient(metrics: dict[str, Any], as_of_year: int) -> float | None:
    """Divide h-index by inclusive indexed publishing years."""
    h_index = nonnegative_number(metrics.get("h_index"))
    earliest = metrics.get("earliest_year")
    if (
        h_index is None
        or not isinstance(earliest, int)
        or not EARLIEST_RESEARCH_YEAR <= earliest <= as_of_year
    ):
        return None
    return round(h_index / (as_of_year - earliest + 1), 2)


def comparable_venue_metrics(details: dict[str, Any]) -> dict[str, int | float | None]:
    """Expose OpenAlex source metrics only for verified journal/conference types."""
    keys = (
        "works_count",
        "cited_by_count",
        "h_index",
        "i10_index",
        "openalex_2yr_mean_citedness",
    )
    if (
        details.get("provider") != "openalex"
        or details.get("venue_category") not in OPENALEX_VENUE_CATEGORIES
        or not details.get("id")
    ):
        return dict.fromkeys(keys)
    return {key: nonnegative_number(details.get(key)) for key in keys}
