"""Calculate citation observations from source-reported counts only."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

ROUND_DIGITS = 4
MAX_YEAR_AGE = 1
SetObservation = Callable[..., None]
ParseNumber = Callable[[object], int | float | None]


def add_citation_observations(
    parameters: dict[str, dict[str, dict[str, Any]]],
    record: dict[str, Any],
    year: int | None,
    set_observation: SetObservation,
    parse_number: ParseNumber,
) -> None:
    """Preserve observed citation counts and derive age and velocity explicitly."""
    metadata = record.get("metadata") or {}
    _set = set_observation
    _number = parse_number
    citations = _number(metadata.get("citation_count"))
    references = _number(metadata.get("reference_count"))
    _set(
        parameters,
        "citation_metrics",
        "citation_count",
        citations,
        record,
        pointer="/metadata/citation_count",
    )
    _set(
        parameters,
        "citation_metrics",
        "reference_count",
        references,
        record,
        pointer="/metadata/reference_count",
    )
    _set(
        parameters,
        "citation_metrics",
        "influential_citations",
        _number(metadata.get("influential_citations")),
        record,
        pointer="/metadata/influential_citations",
    )
    if citations is not None and year is not None:
        age = max(MAX_YEAR_AGE, datetime.now(UTC).year - year + MAX_YEAR_AGE)
        _set(
            parameters,
            "citation_metrics",
            "age_normalized_citations",
            round(citations / age, ROUND_DIGITS),
            record,
            formula="citation_count / max(1, current_year - publication_year + 1)",
        )
        _set(
            parameters,
            "citation_metrics",
            "citations_per_year",
            round(citations / age, ROUND_DIGITS),
            record,
            formula="citation_count / max(1, current_year - publication_year + 1)",
        )
    history = metadata.get("counts_by_year") or []
    annual = sorted(
        (
            (row.get("year"), _number(row.get("cited_by_count")))
            for row in history
            if isinstance(row, dict)
        ),
        key=lambda pair: str(pair[0]),
    )
    annual = [
        (year_value, count)
        for year_value, count in annual
        if isinstance(year_value, int) and count is not None
    ]
    if annual:
        latest_year, latest_count = annual[-1]
        _set(
            parameters,
            "citation_metrics",
            "citation_velocity",
            latest_count,
            record,
            formula=f"verified citations in calendar year {latest_year}",
        )
        if len(annual) >= 2:
            _set(
                parameters,
                "citation_metrics",
                "recent_citation_growth",
                annual[-1][1] - annual[-2][1],
                record,
                formula="latest reported annual citations - previous reported annual citations",
            )
    if len(annual) >= 2 and annual[-1][0] - annual[-2][0] == 1:
        _set(
            parameters,
            "citation_metrics",
            "citation_acceleration",
            annual[-1][1] - annual[-2][1],
            record,
            formula="latest annual citations - previous annual citations",
        )
