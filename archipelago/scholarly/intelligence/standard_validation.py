"""Final identity and duplicate guard for human-facing research exports."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any
from urllib.parse import urlsplit

from archipelago.scholarly.discovery.canonicalizer import normalize_title

DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
EARLIEST_YEAR = 1800


def _public_url(value: Any) -> bool:
    """Require a usable scholarly HTTP link with a hostname."""
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return False
    return parsed.scheme in {"https", "http"} and bool(parsed.hostname)


def valid_standard_paper(paper: dict[str, Any]) -> bool:
    """Keep only relevant records with identifiable authors, date, and source."""
    if paper.get("standard_eligible") is False:
        return False
    relevance = paper.get("relevance_classification") or {}
    if relevance.get("eligible") is False or relevance.get("label") == "IRRELEVANT":
        return False
    title = str(paper.get("title") or "").strip()
    if not title:
        return False
    authors = paper.get("authors") or []
    if not any(
        isinstance(author, dict) and str(author.get("name") or "").strip() for author in authors
    ):
        return False
    raw_year = paper.get("year")
    if raw_year is None:
        date = str(paper.get("publication_date") or "")
        raw_year = int(date[:4]) if date[:4].isdigit() else None
    if isinstance(raw_year, bool) or not isinstance(raw_year, int):
        return False
    if not EARLIEST_YEAR <= raw_year <= datetime.now(UTC).year:
        return False
    doi = str(paper.get("doi") or "").strip().removeprefix("https://doi.org/")
    has_doi = bool(DOI_PATTERN.fullmatch(doi))
    if not (has_doi or _public_url(paper.get("url")) or _public_url(paper.get("oa_url"))):
        return False
    provenance = paper.get("provenance") or []
    return any(
        isinstance(source, dict)
        and source.get("source_type")
        and (_public_url(source.get("source_url")) or source.get("source_record_id") or has_doi)
        for source in provenance
    )


def distinct_standard_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeated canonical works in older persisted runs."""
    output: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for paper in papers:
        if not valid_standard_paper(paper):
            continue
        ids = paper.get("identifiers") or {}
        doi = (
            str(paper.get("doi") or ids.get("doi") or "")
            .casefold()
            .removeprefix("https://doi.org/")
        )
        arxiv = str(ids.get("arxiv_id") or "").casefold()
        arxiv = re.sub(r"v\d+$", "", arxiv)
        first_author = str(paper["authors"][0].get("name") or "").casefold().strip()
        surname = (
            first_author.split(",", 1)[0].strip()
            if "," in first_author
            else first_author.rsplit(" ", 1)[-1]
        )
        title = normalize_title(str(paper["title"]))
        year = paper.get("year") or str(paper.get("publication_date") or "")[:4]
        keys = [
            f"title:{title}",
            f"title_author_year:{title}|{first_author}|{year}",
            f"title_surname_year:{title}|{surname}|{year}",
        ]
        if DOI_PATTERN.fullmatch(doi):
            keys.insert(0, f"doi:{doi}")
        if arxiv:
            keys.insert(0, f"arxiv:{arxiv}")
        for field in ("openalex_id", "semantic_scholar_id"):
            if ids.get(field):
                keys.insert(0, f"{field}:{str(ids[field]).rsplit('/', 1)[-1].casefold()}")
        existing = next((seen[key] for key in keys if key in seen), None)
        if existing is None:
            seen.update({key: len(output) for key in keys})
            output.append({**paper, "provenance": list(paper.get("provenance") or [])})
        else:
            target = output[existing]
            target["provenance"].extend(paper.get("provenance") or [])
            seen.update(dict.fromkeys(keys, existing))
    return output
