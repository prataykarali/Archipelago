"""Keep query relevance measurements separate from impact and quality."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ROUND_DIGITS = 4
SetObservation = Callable[..., None]
Similarity = Callable[[str, object], float | None]
Tokenize = Callable[[object], set[str]]


def add_relevance_observations(
    parameters: dict[str, dict[str, dict[str, Any]]],
    record: dict[str, Any],
    query: str | None,
    set_observation: SetObservation,
    similarity: Similarity,
    tokenize: Tokenize,
) -> None:
    """Use literal title, abstract, and keyword overlap for transparent relevance."""
    metadata = record.get("metadata") or {}
    _set = set_observation
    _similarity = similarity
    _tokens = tokenize
    topic = query or str(record.get("topic") or "")
    for field, body in (
        ("title_similarity", record.get("title")),
        ("abstract_similarity", record.get("content")),
    ):
        score = _similarity(topic, body)
        _set(parameters, "relevance", field, score, record, formula="query/body token Jaccard v1")
    keywords = metadata.get("keywords") or []
    if isinstance(keywords, list) and keywords:
        score = _similarity(topic, " ".join(str(item) for item in keywords))
        _set(
            parameters,
            "relevance",
            "keyword_overlap",
            score,
            record,
            formula="query/keyword token Jaccard v1",
        )
        query_tokens = _tokens(topic)
        keyword_tokens = _tokens(" ".join(str(item) for item in keywords))
        if query_tokens:
            _set(
                parameters,
                "relevance",
                "concept_coverage",
                round(len(query_tokens & keyword_tokens) / len(query_tokens), ROUND_DIGITS),
                record,
                formula="matched query tokens / query tokens",
            )
    _set(
        parameters,
        "relevance",
        "topic_classification",
        metadata.get("topics") or metadata.get("research_domain"),
        record,
        pointer="/metadata/topics",
    )
