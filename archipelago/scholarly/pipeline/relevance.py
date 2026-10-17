"""Paper-topic relevance shortlisting, independent of reputation and quality."""

from __future__ import annotations

from typing import Any

from archipelago.scholarly.features.feature_engine import _coverage

DEFAULT_RETAIN_LIMIT = 100
DEFAULT_SHORTLIST_LIMIT = 10
MIN_SHORTLIST_LIMIT = 5
MIN_RELEVANCE = 0.2
TITLE_WEIGHT = 0.65
ABSTRACT_WEIGHT = 0.35


def relevance_score(candidate: dict[str, Any], topic: str) -> tuple[float, list[str]]:
    """Score query coverage from title and abstract alone."""
    paper = candidate["paper"]
    title = _coverage(topic, paper.title) or 0.0
    abstract = _coverage(topic, paper.abstract or "") or 0.0
    reasons = []
    if title:
        reasons.append(f"title query coverage {title:.2f}")
    if abstract:
        reasons.append(f"abstract query coverage {abstract:.2f}")
    return TITLE_WEIGHT * title + ABSTRACT_WEIGHT * abstract, reasons


def shortlist(
    candidates: list[dict[str, Any]],
    topic: str,
    limit: int = DEFAULT_SHORTLIST_LIMIT,
) -> list[dict[str, Any]]:
    """Return grounded, relevant papers; never use citations or author metrics."""
    scored = []
    for item in candidates:
        score, reasons = relevance_score(item, topic)
        if score >= MIN_RELEVANCE:
            scored.append((score, item, reasons))
    scored.sort(key=lambda entry: (-entry[0], entry[1]["paper"].paper_id))
    return [
        {
            "rank": rank,
            "paper_id": item["paper"].paper_id,
            "title": item["paper"].title,
            "authors": [author.name for author in item["paper"].authors],
            "year": item["paper"].publication_date[:4] if item["paper"].publication_date else None,
            "venue": item["paper"].venue,
            "doi": item["paper"].identifiers.doi,
            "arxiv_id": item["paper"].identifiers.arxiv_id,
            "source_identities": [item.get("source")]
            + [history.get("source") for history in item.get("merge_history", [])],
            "access_state": item.get("access_state", "METADATA_ONLY"),
            "pipeline_state": item.get("pipeline_state", "METADATA_VALIDATED"),
            "topic_relevance_score": round(score, 4),
            "topic_relevance_reason": reasons,
        }
        for rank, (score, item, reasons) in enumerate(scored[:limit], start=1)
    ]
