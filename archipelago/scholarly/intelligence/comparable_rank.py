"""Complete, search-scoped discovery ranking from admitted paper metadata."""

from __future__ import annotations

from typing import Any

from .search_rankings import paper_values, ranking_year, title_match
from .standard_validation import distinct_standard_papers

WEIGHTS = {"title": 0.50, "abstract": 0.25, "recency": 0.15, "sources": 0.10}
PERCENT = 100
NEUTRAL_TIE = 0.5
FIELDS = (
    "Discovery Fit Score (%)",
    "Discovery Rank",
    "Title Query Match (%)",
    "Abstract Query Match (%)",
    "Recency Within Search (%)",
    "Source Corroboration Within Search (%)",
    "Verified Source Count",
    "Author Count",
    "Abstract Reported",
    "Metadata Completeness (%)",
    "Paper Age at Retrieval (Years)",
    "DOI Reported",
    "Public Full-Text Link Reported",
    "Venue Reported",
    "Venue Papers in This Search",
    "Venue Mean Title Match in This Search (%)",
    "Venue Public Full-Text Links in This Search",
)


def _year(paper: dict[str, Any]) -> int:
    """Return the validated publication year, including date-only records."""
    value = paper.get("year")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return int(str(paper["publication_date"])[:4])


def _scaled(value: int, low: int, high: int) -> float:
    """Normalize a complete cohort measure without treating absence as zero."""
    return NEUTRAL_TIE if low == high else (value - low) / (high - low)


def comparable_papers(run: dict[str, Any]) -> list[dict[str, int | float]]:
    """Rank source-linked papers by query fit, recency and corroboration.

    The score is discovery priority within one search, not scholarly quality.
    An absent abstract contributes zero *observed query match*, explicitly
    tracked by Abstract Reported; no citation or licensed metric is imputed.
    """
    papers = distinct_standard_papers(run.get("papers") or [])
    if not papers:
        return []
    topic = str((run.get("options") or {}).get("topic") or "")
    years = [_year(paper) for paper in papers]
    source_counts = [
        int(paper_values(paper, topic, ranking_year(run))["Verified Source Count"])
        for paper in papers
    ]
    venue_groups: dict[str, list[dict[str, Any]]] = {}
    for paper in papers:
        venue = " ".join(str(paper.get("venue") or "").casefold().split())
        if venue:
            venue_groups.setdefault(venue, []).append(paper)
    rows: list[dict[str, int | float]] = []
    for paper, year, sources in zip(papers, years, source_counts, strict=True):
        base = paper_values(paper, topic, ranking_year(run))
        title = title_match(paper["title"], topic)
        abstract = title_match(paper.get("abstract") or "", topic)
        recency = round(PERCENT * _scaled(year, min(years), max(years)), 1)
        corroboration = round(PERCENT * _scaled(sources, min(source_counts), max(source_counts)), 1)
        score = round(
            WEIGHTS["title"] * title
            + WEIGHTS["abstract"] * abstract
            + WEIGHTS["recency"] * recency
            + WEIGHTS["sources"] * corroboration,
            1,
        )
        venue = " ".join(str(paper.get("venue") or "").casefold().split())
        venue_papers = venue_groups.get(venue, []) if venue else []
        rows.append(
            {
                "Discovery Fit Score (%)": score,
                "Discovery Rank": 0,
                "Title Query Match (%)": title,
                "Abstract Query Match (%)": abstract,
                "Recency Within Search (%)": recency,
                "Source Corroboration Within Search (%)": corroboration,
                "Verified Source Count": sources,
                "Author Count": int(base["Author Count"]),
                "Abstract Reported": int(bool(paper.get("abstract"))),
                "Metadata Completeness (%)": float(base["Metadata Completeness (%)"]),
                "Paper Age at Retrieval (Years)": max(0, ranking_year(run) - year),
                "DOI Reported": int(bool(paper.get("doi"))),
                "Public Full-Text Link Reported": int(
                    str(paper.get("oa_url") or "").startswith("https://")
                ),
                "Venue Reported": int(bool(venue)),
                "Venue Papers in This Search": len(venue_papers),
                "Venue Mean Title Match in This Search (%)": round(
                    sum(title_match(item.get("title"), topic) for item in venue_papers)
                    / len(venue_papers),
                    1,
                )
                if venue_papers
                else 0.0,
                "Venue Public Full-Text Links in This Search": sum(
                    str(item.get("oa_url") or "").startswith("https://") for item in venue_papers
                ),
            }
        )
    for rank, index in enumerate(
        sorted(range(len(rows)), key=lambda i: (-rows[i]["Discovery Fit Score (%)"], -years[i], i)),
        1,
    ):
        rows[index]["Discovery Rank"] = rank
    return rows
