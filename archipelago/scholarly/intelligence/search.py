"""Bounded scholarly discovery with conservative topic eligibility."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from archipelago.scholarly.discovery.canonicalizer import normalize_title
from archipelago.scholarly.discovery.orchestrator import DiscoveryOrchestrator

from .enrichment import enrich_authors, venue_observation
from .extraction import extract_evidence

DEFAULT_TOP_K = 20
MAX_TOP_K = 100
SOURCE_MULTIPLIER = 2
MAX_QUERY_CHARS = 200
VERSION_SUFFIX = re.compile(r"/v\d+$", re.IGNORECASE)
VALID_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
QUERY_MODIFIERS = re.compile(r"\b(latest|recent|newest|papers|studies|research)\b", re.IGNORECASE)
TOPIC_STOPWORDS = frozenset({"a", "an", "and", "for", "in", "of", "on", "the", "with", "to"})
TOPIC_ALIASES = {
    "graph neural networks": "gnn",
    "retrieval augmented generation": "rag",
    "bengali": "bangla",
    "speech recognition": "asr",
    "continual learning": "lifelong learning",
}


def topic_matches(topic: str, title: str, abstract: str | None, fields: str = "") -> bool:
    """Require the named research concepts in provider title, abstract or fields."""
    evidence = re.sub(r"[^\w]+", " ", " ".join((title, abstract or "", fields)).casefold())
    query = re.sub(r"[^\w]+", " ", QUERY_MODIFIERS.sub(" ", topic).casefold()).strip()
    if not query:
        return False
    alias_matched = False
    for phrase, alias in TOPIC_ALIASES.items():
        if phrase in query and re.search(rf"\b{re.escape(alias)}\b", evidence):
            query = query.replace(phrase, " ")
            alias_matched = True
    terms = [word for word in query.split() if word not in TOPIC_STOPWORDS]
    return (bool(terms) or alias_matched) and all(
        re.search(rf"\b{re.escape(word)}s?\b", evidence) for word in terms
    )


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
    sort = payload.get("sort", "newest")
    if sort not in {"relevance", "newest", "provider"}:
        raise ValueError("invalid_sort")
    oa = payload.get("open_access")
    if oa is not None and not isinstance(oa, bool):
        raise ValueError("invalid_open_access")
    return {
        "topic": topic,
        "top_k": top_k,
        "year_from": start,
        "year_to": end,
        "sort": "newest" if sort == "relevance" else sort,
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
        if not topic_matches(options["topic"], paper.title, paper.abstract, fields):
            continue
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
        found = extract_evidence(paper.title, paper.abstract)
        fetched = [p.get("fetched_at") for p in source_links if p.get("fetched_at")]
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
                "topics": metadata.get("topics") or metadata.get("keywords") or [],
                "research_field": metadata.get("research_domain"),
                "methods": metadata.get("methods") or found["methods"],
                "datasets": metadata.get("datasets") or found["datasets"],
                "evaluation_metrics": metadata.get("evaluation_metrics") or found["evaluation_metrics"],
                "author_ids": metadata.get("author_openalex_ids") or [],
                "publisher": metadata.get("publisher"),
                "license": paper.license,
                "oa_url": paper.oa_url,
                "retrieved_at": max(fetched) if fetched else None,
                "retraction_status": metadata.get("retraction_status"),
                "provenance": source_links,
                "source": candidate.get("source"),
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
    if options["sort"] == "newest":
        rows.sort(key=lambda row: (row["publication_date"] or "", row["paper_id"]), reverse=True)
    selected = rows[: options["top_k"]]
    for position, row in enumerate(selected, 1):
        row["collection_order"] = position
    retrieved_at = datetime.now(UTC).isoformat()
    for row in selected:
        row["venue_details"] = venue_observation(row, retrieved_at)
        row["retrieved_at"] = row["retrieved_at"] or retrieved_at
    return {
        "schema": "archipelago.research_intelligence.v1",
        "options": options,
        "retrieved_at": retrieved_at,
        "sources": sources,
        "candidate_count": len(candidates),
        "filtered_count": len(rows),
        "ordering": "publication_date_desc" if options["sort"] == "newest" else "provider_returned",
        "papers": selected,
        "author_observations": enrich_authors(selected) if orchestrator is None else [],
    }
