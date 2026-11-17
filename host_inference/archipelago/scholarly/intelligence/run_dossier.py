"""Source-backed paper and topic detail payloads for an intelligence run."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .ranking_preview import preview_run
from .standard_validation import distinct_standard_papers
from .workbook_standard import _valid_author_name

EXTRACTION_FIELDS = ("methods", "datasets", "evaluation_metrics", "claims")


def _extractions(items: Any, title: str, abstract: str) -> list[dict[str, str]]:
    """Keep named facts backed by exact title or abstract evidence."""
    if not isinstance(items, list):
        return []
    normalized_title = " ".join(title.casefold().split())
    normalized_abstract = " ".join(abstract.casefold().split())
    facts: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if isinstance(item, dict):
            name = str(
                item.get("name") or item.get("claim") or item.get("normalized_value") or ""
            ).strip()
            evidence = str(item.get("evidence") or item.get("exact_evidence") or "").strip()
            location = str(item.get("location") or "").strip()
        elif isinstance(item, str):
            name, evidence, location = item.strip(), "", ""
        else:
            continue
        normalized_evidence = " ".join(evidence.casefold().split())
        if (
            not name
            or not normalized_evidence
            or not (
                normalized_evidence in normalized_title
                or normalized_evidence in normalized_abstract
            )
        ):
            continue
        if (name.casefold(), evidence.casefold()) in seen:
            continue
        seen.add((name.casefold(), evidence.casefold()))
        facts.append({"name": name, "evidence": evidence, "location": location})
    return facts


def _https(raw: Any) -> str | None:
    return raw if isinstance(raw, str) and raw.startswith("https://") else None


def _paper_detail(paper: dict[str, Any], index: int, values: list[Any]) -> dict[str, Any]:
    title = str(paper.get("title") or "")
    abstract = str(paper.get("abstract") or "")
    sources = []
    seen: set[tuple[str, str]] = set()
    for source in paper.get("provenance") or []:
        if not isinstance(source, dict):
            continue
        name = str(source.get("source_type") or "").replace("_", " ").title()
        url = _https(source.get("source_url"))
        if not name or not url or (name, url) in seen:
            continue
        seen.add((name, url))
        sources.append({"name": name, "url": url})
    return {
        "index": index,
        "title": title,
        "authors": [
            str(author["name"])
            for author in paper.get("authors") or []
            if isinstance(author, dict) and _valid_author_name(author)
        ],
        "year": paper.get("year"),
        "venue": str(paper.get("venue") or ""),
        "publication_type": str(paper.get("publication_type") or ""),
        "doi": str(paper.get("doi") or ""),
        "url": _https(paper.get("url") or paper.get("oa_url")),
        "abstract": abstract,
        "evidence_status": str(paper.get("evidence_status") or ""),
        "sources": sources,
        "extracted": {
            field: _extractions(paper.get(field), title, abstract) for field in EXTRACTION_FIELDS
        },
        "rankable_values": values,
        "provider_metrics": {
            label: value
            for label, value in (
                ("Citation count", paper.get("citation_count")),
                ("Citations per year", paper.get("citations_per_year")),
                ("OpenAlex FWCI", paper.get("fwci")),
                (
                    "OpenAlex citation percentile",
                    (paper.get("citation_normalized_percentile") or {}).get("value"),
                ),
                ("Reference count", paper.get("reference_count")),
                ("Semantic Scholar influential citations", paper.get("influential_citations")),
                ("Open access", paper.get("is_open_access")),
            )
            if value is not None
        },
    }


def build_run_dossier(run: dict[str, Any]) -> dict[str, Any]:
    """Align paper details and topic totals to the cleansed standard workbook."""
    preview = preview_run(run)
    valid_papers = [
        paper
        for paper in distinct_standard_papers(run.get("papers") or [])
        if any(_valid_author_name(author) for author in paper.get("authors") or [])
    ]
    ranking_rows = preview["sheets"]["Papers"]["rows"]
    if len(valid_papers) != len(ranking_rows):
        raise ValueError("dossier_workbook_mismatch")
    papers = [
        _paper_detail(paper, index, ranking_rows[index]["values"])
        for index, paper in enumerate(valid_papers)
    ]
    extracted_counts: dict[str, dict[str, int]] = {}
    for field in EXTRACTION_FIELDS:
        counts = Counter(
            fact["name"]
            for paper in papers
            for fact in {entry["name"]: entry for entry in paper["extracted"][field]}.values()
        )
        extracted_counts[field] = dict(counts.most_common())
    years = Counter(str(paper["year"]) for paper in papers if paper["year"])
    providers = Counter(
        source["name"]
        for paper in papers
        for source in {s["name"]: s for s in paper["sources"]}.values()
    )
    return {
        "topic": preview["topic"],
        "retrieved_at": preview["retrieved_at"],
        "paper_count": len(papers),
        "author_count": len(preview["sheets"]["Authors"]["rows"]),
        "paper_headers": preview["sheets"]["Papers"]["headers"],
        "extracted_counts": extracted_counts,
        "years": dict(sorted(years.items(), reverse=True)),
        "providers": dict(providers.most_common()),
        "papers": papers,
    }
