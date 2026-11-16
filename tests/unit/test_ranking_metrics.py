"""Check citation windows and venue comparability in ranking exports."""

from __future__ import annotations

from archipelago.scholarly.intelligence.ranking_metrics import (
    author_recent_citations,
    comparable_venue_metrics,
    openalex_citation_percentile,
)


def test_recent_citations_use_retrieval_year_and_do_not_invent_missing_counts() -> None:
    metrics = {
        "counts_by_year": [
            {"year": 2019, "cited_by_count": 90},
            {"year": 2024, "cited_by_count": 8},
            {"year": 2026, "cited_by_count": 12},
        ]
    }
    assert author_recent_citations(metrics, 2026) == 20
    assert author_recent_citations({"counts_by_year": []}, 2026) is None


def test_repository_metrics_are_not_presented_as_journal_rankings() -> None:
    repository = {
        "id": "https://openalex.org/S1",
        "provider": "openalex",
        "venue_category": "preprint_repository",
        "works_count": 1000,
        "h_index": 50,
    }
    assert all(value is None for value in comparable_venue_metrics(repository).values())


def test_percentile_requires_a_valid_openalex_fraction() -> None:
    assert openalex_citation_percentile({"citation_normalized_percentile": {"value": 0.95}}) == 0.95
    assert openalex_citation_percentile({"citation_normalized_percentile": {"value": 95}}) is None
