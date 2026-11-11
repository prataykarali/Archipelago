"""Summarise observed OKF fields across papers saved for one research topic."""

from __future__ import annotations

from collections import Counter
from html import unescape
import re
from typing import Any

from .research_evidence_guard import valid_evidence_item
from .research_okf import build_paper_okf

PIPELINE_ID = "local_indra_v3"
VERIFIED_STATES = frozenset({"verified", "quote_matched", "abstract_quote_matched"})
CONTRACT_SECTIONS = frozenset(
    {
        "identity",
        "authors",
        "author_bibliometrics",
        "venue_metrics",
        "citation_metrics",
        "semantic_relevance",
        "graph_metrics",
        "novelty_metrics",
        "methodology",
        "datasets",
        "experiments",
        "performance",
        "efficiency",
        "claims",
        "evidence",
        "reproducibility",
        "relations",
        "integrity",
        "provenance",
    }
)
MAX_AUTHORS = 4
MAX_ABSTRACT_CHARS = 500
HTML_TAG = re.compile(r"<[^>]+>")


def _reported(value: object) -> bool:
    """Count a source value only when it is actually present."""
    if value is None or value == [] or value == {}:
        return False
    return not (
        isinstance(value, str)
        and value.strip().casefold()
        in {"", "unknown", "null", "none", "not reported", "not available"}
    )


def build_topic_overview(topic: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return aggregate counts and compact links to each full paper OKF."""
    papers = []
    providers: Counter[str] = Counter()
    years: Counter[str] = Counter()
    coverage: Counter[str] = Counter()
    access: Counter[str] = Counter()
    for row in rows:
        metadata = row.get("metadata") or {}
        if (
            row.get("kind") != "paper"
            or metadata.get("ingestion_pipeline") != PIPELINE_ID
            or metadata.get("active") is False
        ):
            continue
        okf = build_paper_okf(row, topic)
        observed = [item for item in okf["feature_observations"] if _reported(item.get("value"))]
        evidence = {
            (item.get("group"), item.get("field"), item.get("evidence_text"))
            for item in metadata.get("verified_extractions") or []
            if isinstance(item, dict)
            and item.get("verification_status") in VERIFIED_STATES
            and valid_evidence_item(item, row)
        }
        present_groups = sorted(
            name
            for name in CONTRACT_SECTIONS
            if any(_reported(field.get("value")) for field in okf[name].values())
        )
        coverage.update(present_groups)
        provider = str(row.get("source_name") or "Unspecified source")
        providers[provider] += 1
        year_value = okf["identity"].get("publication_date", {}).get("value") or row.get(
            "published_at"
        )
        year = str(year_value)[:4] if str(year_value)[:4].isdigit() else None
        if year:
            years[year] += 1
        state = str(metadata.get("access_state") or "METADATA_ONLY")
        access[state] += 1
        authors = metadata.get("authors") or []
        abstract = unescape(HTML_TAG.sub("", str(row.get("content") or ""))).strip()
        citation = okf["citation_metrics"]["citation_count"]["value"]
        papers.append(
            {
                "key": row["record_key"],
                "title": row.get("title") or "Untitled paper",
                "authors": [
                    item.get("name")
                    for item in authors
                    if isinstance(item, dict) and _reported(item.get("name"))
                ][:MAX_AUTHORS],
                "year": year,
                "venue": metadata.get("venue"),
                "doi": metadata.get("doi"),
                "source_url": row.get("source_url"),
                "provider": provider,
                "access_state": state,
                "citation_count": citation if _reported(citation) else None,
                "observed_fields": len(observed),
                "quoted_facts": len(evidence),
                "sections": present_groups,
                "abstract": abstract[:MAX_ABSTRACT_CHARS],
            }
        )
    return {
        "topic": topic,
        "paper_count": len(papers),
        "providers": dict(providers),
        "publication_years": dict(sorted(years.items())),
        "section_coverage": dict(coverage),
        "access_states": dict(access),
        "papers": papers,
    }
