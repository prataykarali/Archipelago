"""Deterministic ranking evidence scoped to the papers in one search."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import re
from statistics import median
from typing import Any

PAPER_FIELDS = (
    "Paper Age (Years)",
    "Title Query Match (%)",
    "Verified Source Count",
    "Author Count",
    "Metadata Completeness (%)",
    "Method Reported",
    "Benchmark Reported",
    "Code Link Reported",
    "Data Link Reported",
)
AUTHOR_FIELDS = (
    "Papers in This Search",
    "First-Author Papers in This Search",
    "Last-Author Papers in This Search",
    "Mean Title Match in This Search (%)",
    "Newest Paper Year in This Search",
    "Median Paper Year in This Search",
    "Distinct Coauthor Bylines in This Search",
)
VENUE_FIELDS = (
    "Venue Papers in This Search",
    "Venue Author Bylines in This Search",
    "Venue Newest Paper Year in This Search",
    "Venue Median Paper Year in This Search",
    "Venue Mean Title Match in This Search (%)",
    "Venue Public Full-Text Links in This Search",
)
COMPLETENESS_FIELDS = 9
PERCENT = 100
STOPWORDS = frozenset({"a", "an", "and", "for", "in", "of", "on", "the", "to", "with"})
ORGANIZATION_TERMS = frozenset(
    {"association", "conference", "journal", "proceedings", "publisher", "university"}
)
YEAR_IN_NAME = re.compile(r"\b(?:19|20)\d{2}\b")


def _key(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _valid_author(author: Any) -> bool:
    if not isinstance(author, dict):
        return False
    name = str(author.get("name") or "").strip()
    words = set(re.findall(r"[a-z]+", name.casefold()))
    return bool(name) and not (YEAR_IN_NAME.search(name) and words & ORGANIZATION_TERMS)


def _authors(paper: dict[str, Any]) -> list[str]:
    return [
        str(author.get("name") or "").strip()
        for author in paper.get("authors") or []
        if _valid_author(author)
    ]


def _year(paper: dict[str, Any]) -> int | None:
    value = paper.get("year")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def author_identity_key(paper: dict[str, Any], index: int) -> str:
    """Match the standard workbook's provider-first author identity order."""
    metadata = paper.get("source_metadata") or {}
    openalex_ids = metadata.get("author_openalex_ids") or []
    openalex_id = openalex_ids[index] if index < len(openalex_ids) else None
    if openalex_id:
        return "author:" + str(openalex_id).rsplit("/", 1)[-1]
    author = paper["authors"][index]
    if author.get("orcid"):
        return "author:" + sha256(str(author["orcid"]).casefold().encode()).hexdigest()[:16]
    s2_ids = metadata.get("author_s2_ids") or []
    s2_id = s2_ids[index] if index < len(s2_ids) else None
    if s2_id:
        return f"author:s2:{s2_id}"
    value = f"{paper['paper_id']}:{index}:{author['name']}"
    return "author-unverified:" + sha256(value.casefold().encode()).hexdigest()[:16]


def ordered_author_keys(papers: list[dict[str, Any]]) -> list[str]:
    """Return author keys in the same insertion order as the standard sheet."""
    return list(
        dict.fromkeys(
            author_identity_key(paper, index)
            for paper in papers
            for index, author in enumerate(paper.get("authors") or [])
            if _valid_author(author)
        )
    )


def title_match(title: Any, topic: Any) -> float:
    """Return the share of meaningful query tokens found in a paper title."""
    words = set(re.findall(r"\w+", _key(topic)))
    terms = words - STOPWORDS or words
    if not terms:
        return 0.0
    title_words = set(re.findall(r"\w+", _key(title)))
    return round(PERCENT * len(terms & title_words) / len(terms), 1)


def paper_values(paper: dict[str, Any], topic: str, as_of_year: int) -> dict[str, Any]:
    """Compute fields available for every admitted, source-linked paper."""
    year = _year(paper)
    provenance = paper.get("provenance") or []
    sources = {
        _key(source.get("source_type"))
        for source in provenance
        if isinstance(source, dict) and source.get("source_type")
    }
    has_method = bool(paper.get("methods"))
    has_benchmark = bool(paper.get("benchmark_performance"))
    has_code = bool(paper.get("code_repo_urls"))
    has_data = bool(paper.get("dataset_repo_urls"))
    known_references = paper.get("reference_count") is not None or bool(paper.get("references"))
    evidence = (
        bool(paper.get("doi")),
        bool(paper.get("venue")),
        paper.get("citation_count") is not None,
        known_references,
        paper.get("is_open_access") is not None,
        has_method,
        has_benchmark,
        has_code,
        has_data,
    )
    return dict(
        zip(
            PAPER_FIELDS,
            (
                max(0, as_of_year - year) if year is not None else None,
                title_match(paper.get("title"), topic),
                len(sources),
                len(_authors(paper)),
                round(PERCENT * sum(evidence) / COMPLETENESS_FIELDS, 1),
                int(has_method),
                int(has_benchmark),
                int(has_code),
                int(has_data),
            ),
            strict=True,
        )
    )


def author_values(
    name: str, papers: list[dict[str, Any]], topic: str, identity_key: str | None = None
) -> dict[str, Any]:
    """Summarize byline evidence in this search; names are not global identities."""

    def positions(paper: dict[str, Any]) -> list[int]:
        return [
            index
            for index, author in enumerate(paper.get("authors") or [])
            if _valid_author(author)
            and (
                author_identity_key(paper, index) == identity_key
                if identity_key
                else _key(author.get("name")) == _key(name)
            )
        ]

    matching = [paper for paper in papers if positions(paper)]
    years = [_year(paper) for paper in matching]
    valid_years = [year for year in years if year is not None]
    coauthors = {
        _key(author.get("name"))
        for paper in matching
        for index, author in enumerate(paper.get("authors") or [])
        if _valid_author(author) and index not in positions(paper)
    }
    values = (
        len(matching),
        sum(
            next(
                index
                for index, author in enumerate(paper.get("authors") or [])
                if _valid_author(author)
            )
            in positions(paper)
            for paper in matching
        ),
        sum(
            next(
                index
                for index in range(len(paper.get("authors") or []) - 1, -1, -1)
                if _valid_author(paper["authors"][index])
            )
            in positions(paper)
            for paper in matching
        ),
        round(sum(title_match(paper.get("title"), topic) for paper in matching) / len(matching), 1)
        if matching
        else 0.0,
        max(valid_years) if valid_years else None,
        median(valid_years) if valid_years else None,
        len(coauthors),
    )
    return dict(zip(AUTHOR_FIELDS, values, strict=True))


def venue_values(name: str, papers: list[dict[str, Any]], topic: str) -> dict[str, Any]:
    """Summarize only papers at the named venue in this search."""
    matching = [paper for paper in papers if _key(name) and _key(paper.get("venue")) == _key(name)]
    years = [year for paper in matching if (year := _year(paper)) is not None]
    authors = {_key(author) for paper in matching for author in _authors(paper)}
    full_text = sum(str(paper.get("oa_url") or "").startswith("https://") for paper in matching)
    values = (
        len(matching),
        len(authors),
        max(years) if years else None,
        median(years) if years else None,
        round(sum(title_match(paper.get("title"), topic) for paper in matching) / len(matching), 1)
        if matching
        else 0.0,
        full_text,
    )
    return dict(zip(VENUE_FIELDS, values, strict=True))


def ranking_year(run: dict[str, Any]) -> int:
    """Use retrieval year so downloaded results do not change with the clock."""
    retrieved = str(run.get("retrieved_at") or "")
    return int(retrieved[:4]) if retrieved[:4].isdigit() else date.today().year


def matching_paper(title: Any, year: Any, papers: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Join an exported row to its admitted run record by title and year."""
    return next(
        (
            paper
            for paper in papers
            if _key(paper.get("title")) == _key(str(title or "").removeprefix("'"))
            and (year is None or _year(paper) == year)
        ),
        None,
    )
