"""Attach first-author metrics with author-level provenance to a paper OKF."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

SetObservation = Callable[..., None]
ParseNumber = Callable[[object], int | float | None]
ROUND_DIGITS = 4
AUTHOR_FIELDS = ("h_index", "i10_index", "total_citations", "publication_count")


def add_author_observations(
    parameters: dict[str, dict[str, dict[str, Any]]],
    record: dict[str, Any],
    set_observation: SetObservation,
    parse_number: ParseNumber,
) -> None:
    """Map one verified first-author record without treating it as a paper score."""
    author = (record.get("metadata") or {}).get("first_author_metrics") or {}
    if not isinstance(author, dict) or not author.get("author_id"):
        return
    provenance = {
        "source_api": "openalex_authors",
        "source_url": author.get("source_url"),
        "source_timestamp": author.get("source_timestamp"),
        "evidence_text": f"First author: {author.get('name') or author['author_id']}",
    }
    for field in AUTHOR_FIELDS:
        set_observation(
            parameters,
            "author_metrics",
            field,
            parse_number(author.get(field)),
            record,
            pointer=f"/metadata/first_author_metrics/{field}",
        )
        observation = parameters["author_metrics"][field]
        if observation["value"] is not None:
            observation["provenance"][0].update(provenance)
    g_idx = parse_number(author.get("g_index"))
    if g_idx is not None:
        set_observation(
            parameters,
            "author_metrics",
            "g_index",
            g_idx,
            record,
            pointer="/metadata/first_author_metrics/g_index",
        )
        parameters["author_metrics"]["g_index"]["provenance"][0].update(provenance)
    first_pub_year = parse_number(author.get("first_publication_year"))
    h_idx = parse_number(author.get("h_index"))
    if first_pub_year is not None:
        career_age = max(1, datetime.now(UTC).year - int(first_pub_year))
        set_observation(
            parameters,
            "author_metrics",
            "academic_career_age",
            career_age,
            record,
            formula="current_year - first_publication_year",
        )
        parameters["author_metrics"]["academic_career_age"]["provenance"][0].update(provenance)
        if h_idx is not None:
            set_observation(
                parameters,
                "author_metrics",
                "m_index",
                round(h_idx / career_age, ROUND_DIGITS),
                record,
                formula="h_index / academic_career_age",
            )
            parameters["author_metrics"]["m_index"]["provenance"][0].update(provenance)
    works = parse_number(author.get("publication_count"))
    total = parse_number(author.get("total_citations"))
    if works and total is not None:
        field = "average_citations_per_publication"
        set_observation(
            parameters,
            "author_metrics",
            field,
            round(total / works, ROUND_DIGITS),
            record,
            formula="first_author_total_citations / first_author_publication_count",
        )
        parameters["author_metrics"][field]["provenance"][0].update(provenance)
