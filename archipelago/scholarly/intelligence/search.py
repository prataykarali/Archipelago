"""Bounded scholarly discovery and transparent ranking."""

from __future__ import annotations

from datetime import UTC, datetime
import math
import re
from typing import Any

from archipelago.scholarly.discovery.canonicalizer import normalize_title
from archipelago.scholarly.discovery.orchestrator import DiscoveryOrchestrator
from archipelago.scholarly.pipeline.relevance import relevance_score

from .enrichment import enrich_authors, venue_observation

DEFAULT_TOP_K = 20
MAX_TOP_K = 50
SOURCE_MULTIPLIER = 2
MAX_QUERY_CHARS = 200
RECENCY_YEARS = 5
RECENCY_WEIGHT = 0.25
CITATION_WEIGHT = 0.05
CITATION_NORMALIZER = 1000
VERSION_SUFFIX = re.compile(r"/v\d+$", re.IGNORECASE)
VALID_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
QUERY_MODIFIERS = re.compile(r"\b(latest|recent|newest|papers|studies|research)\b", re.IGNORECASE)
MIN_RELEVANCE = 0.2


def _version_key(row: dict[str, Any]) -> tuple[str, str, str, int | None] | None:
    """Unify explicit DOI versions only with matching title, author and year."""
    doi = row.get("doi") or ""
    if not VERSION_SUFFIX.search(doi):
        return None
    authors = row.get("authors") or []
    if not authors or not row.get("year"):
        return None
    return (
        VERSION_SUFFIX.sub("", doi.casefold()),
        normalize_title(row["title"]),
        authors[0]["name"].casefold().strip(),
        row["year"],
    )


def validate_options(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate user filters without accepting arbitrary provider URLs."""
    topic = str(payload.get("topic") or "").strip()
    top_k = payload.get("top_k", DEFAULT_TOP_K)
    if not 3 <= len(topic) <= MAX_QUERY_CHARS:
        raise ValueError("invalid_topic")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= MAX_TOP_K:
        raise ValueError("invalid_top_k")
    start = payload.get("year_from")
    end = payload.get("year_to")
    current = datetime.now(UTC).year
    if any(
        v is not None
        and (isinstance(v, bool) or not isinstance(v, int) or not 1800 <= v <= current + 1)
        for v in (start, end)
    ):
        raise ValueError("invalid_year")
    if start and end and start > end:
        raise ValueError("invalid_year_range")
    sort = payload.get("sort", "relevance")
    if sort not in {"relevance", "newest"}:
        raise ValueError("invalid_sort")
    oa = payload.get("open_access")
    if oa is not None and not isinstance(oa, bool):
        raise ValueError("invalid_open_access")
    return {
        "topic": topic,
        "top_k": top_k,
        "year_from": start,
        "year_to": end,
        "sort": sort,
        "open_access": oa,
        "paper_type": str(payload.get("paper_type") or "").strip()[:80],
        "field": str(payload.get("field") or "").strip()[:80],
        "venue": str(payload.get("venue") or "").strip()[:120],
    }


def discover(
    payload: dict[str, Any], orchestrator: DiscoveryOrchestrator | None = None
) -> dict[str, Any]:
    """Return source-linked, filtered papers without PDF or GPU work."""
    options = validate_options(payload)
    engine = orchestrator or DiscoveryOrchestrator()
    search_query = " ".join(QUERY_MODIFIERS.sub(" ", options["topic"]).split()) or options["topic"]
    candidates, sources = engine.discover_with_status(
        search_query, min(MAX_TOP_K, options["top_k"] * SOURCE_MULTIPLIER)
    )
    rows: list[dict[str, Any]] = []
    current_year = datetime.now(UTC).year
    latest = options["sort"] == "newest" or any(
        word in options["topic"].casefold() for word in ("latest", "recent", "newest")
    )
    for candidate in candidates:
        paper = candidate["paper"]
        year = (
            int(paper.publication_date[:4])
            if paper.publication_date and paper.publication_date[:4].isdigit()
            else None
        )
        metadata = candidate.get("source_metadata") or {}
        if options["year_from"] and (year is None or year < options["year_from"]):
            continue
        if options["year_to"] and (year is None or year > options["year_to"]):
            continue
        if (
            options["open_access"] is not None
            and paper.is_open_access is not options["open_access"]
        ):
            continue
        if (
            options["paper_type"]
            and options["paper_type"].casefold() not in (paper.publication_type or "").casefold()
        ):
            continue
        if options["venue"] and options["venue"].casefold() not in (paper.venue or "").casefold():
            continue
        fields = " ".join(
            str(value) for value in (metadata.get("topics") or metadata.get("keywords") or [])
        )
        if options["field"] and options["field"].casefold() not in fields.casefold():
            continue
        relevance, reasons = relevance_score(candidate, search_query)
        if relevance < MIN_RELEVANCE:
            continue
        recency = max(0.0, 1 - (current_year - year) / RECENCY_YEARS) if year else 0.0
        citation_value = candidate.get("citation_count")
        citation_signal = (
            min(1.0, math.log1p(citation_value) / math.log1p(CITATION_NORMALIZER))
            if isinstance(citation_value, int) and citation_value >= 0
            else 0.0
        )
        score = relevance + (
            recency * RECENCY_WEIGHT if latest else citation_signal * CITATION_WEIGHT
        )
        if latest and year:
            reasons.append(f"publication year {year}")
        if not latest and citation_value is not None:
            reasons.append("small citation visibility signal; not a quality rating")
        if not paper.abstract:
            reasons.append("abstract unavailable; ranking uses title")
        provenance = [candidate.get("provenance")]
        provenance.extend(entry.get("provenance") for entry in candidate.get("merge_history", []))
        source_links = [p.model_dump(mode="json") for p in provenance if hasattr(p, "model_dump")]
        citation_observations = [
            {"provider": candidate.get("source"), "count": candidate.get("citation_count")}
        ] + [
            {"provider": entry.get("source"), "count": entry.get("citation_count")}
            for entry in candidate.get("merge_history", [])
        ]
        citation_observations = [
            entry for entry in citation_observations if isinstance(entry["count"], int)
        ]
        citation_observation = max(
            citation_observations, key=lambda entry: entry["count"], default=None
        )
        doi = paper.identifiers.doi
        valid_doi = doi if doi and VALID_DOI.fullmatch(doi) else None
        review = list(candidate.get("identity_review") or [])
        if doi and not valid_doi:
            review.append("invalid_doi_from_provider")
        rows.append(
            {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "year": year,
                "publication_date": paper.publication_date,
                "doi": valid_doi,
                "identifiers": paper.identifiers.model_dump(mode="json"),
                "authors": [a.model_dump(mode="json") for a in paper.authors],
                "venue": paper.venue,
                "publication_type": paper.publication_type,
                "abstract": paper.abstract,
                "is_open_access": paper.is_open_access,
                "url": next(
                    (p.get("source_url") for p in source_links if p.get("source_url")), None
                ),
                "citation_count": citation_observation["count"] if citation_observation else None,
                "citation_provider": citation_observation["provider"]
                if citation_observation
                else None,
                "citation_observations": citation_observations,
                "references": metadata.get("referenced_works") or [],
                "source_metadata": metadata,
                "retraction_status": metadata.get("retraction_status"),
                "provenance": source_links,
                "relevance_score": round(score, 4),
                "topic_relevance": round(relevance, 4),
                "recency_signal": round(recency, 4),
                "citation_signal": round(citation_signal, 4),
                "ranking_reasons": reasons,
                "evidence_status": "REFERENCE_METADATA_AVAILABLE"
                if metadata.get("referenced_works")
                else "ABSTRACT_AVAILABLE"
                if paper.abstract
                else "METADATA_ONLY",
                "identity_review": review,
            }
        )
    versioned: dict[tuple[str, str, str, int | None], dict[str, Any]] = {}
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = _version_key(row)
        if key is None:
            unique.append(row)
            continue
        prior = versioned.get(key)
        if prior is None or (row["doi"] or "") > (prior["doi"] or ""):
            versioned[key] = row
    rows = unique + list(versioned.values())
    rows.sort(key=lambda row: (row["relevance_score"], row["publication_date"] or ""), reverse=True)
    selected = rows[: options["top_k"]]
    for rank, row in enumerate(selected, 1):
        row["rank"] = rank
    retrieved_at = datetime.now(UTC).isoformat()
    for row in selected:
        row["venue_details"] = venue_observation(row, retrieved_at)
    return {
        "schema": "archipelago.research_intelligence.v1",
        "options": options,
        "retrieved_at": retrieved_at,
        "sources": sources,
        "candidate_count": len(candidates),
        "filtered_count": len(rows),
        "papers": selected,
        "author_observations": enrich_authors(selected) if orchestrator is None else [],
    }
