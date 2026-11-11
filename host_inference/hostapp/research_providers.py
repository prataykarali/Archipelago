"""Additional public scholarly APIs for hosted research discovery."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import os
import re
from typing import Any
from xml.etree import ElementTree

import requests

SOURCE_TIMEOUT_SECONDS = 10
SOURCE_RESULTS = 20
MAX_ABSTRACT_CHARS = 12000
SPACE = re.compile(r"\s+")
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _plain(value: object, limit: int = MAX_ABSTRACT_CHARS) -> str:
    return SPACE.sub(" ", str(value or "")).strip()[:limit]


def _record(
    *,
    provider: str,
    identifier: str,
    title: str,
    source_url: str,
    abstract: str,
    topic: str,
    user_id: str | None,
    published: str | None,
    doi: str = "",
    pdf_url: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, object] | None:
    if not title or not source_url.startswith("https://"):
        return None
    normalized = doi.lower().removeprefix("https://doi.org/") or identifier
    return {
        "record_key": sha256(f"paper:{normalized.lower()}".encode()).hexdigest(),
        "kind": "paper",
        "title": _plain(title, 300),
        "source_url": source_url,
        "source_name": provider,
        "topic": topic,
        "content": _plain(abstract),
        "published_at": published,
        "metadata": {
            **(extra_metadata or {}),
            "doi": doi,
            "open_access_pdf": pdf_url,
            "has_abstract": bool(abstract),
            "source_timestamp": datetime.now(UTC).isoformat(),
        },
        "updated_by": user_id,
    }


def arxiv_papers(topic: str, user_id: str | None) -> list[dict[str, object]]:
    """Find engineering and science preprints through arXiv's Atom API."""
    response = requests.get(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": f"all:{topic}",
            "start": 0,
            "max_results": SOURCE_RESULTS,
            "sortBy": "relevance",
            "sortOrder": "descending",
        },
        headers={"User-Agent": "ArchipelagoResearch/1.0 (academic discovery)"},
        timeout=SOURCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    records = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        identifier = _plain(entry.findtext("atom:id", default="", namespaces=ARXIV_NS), 500)
        source_url = identifier.replace("http://", "https://", 1)
        pdf_url = next(
            (
                link.get("href", "").replace("http://", "https://", 1)
                for link in entry.findall("atom:link", ARXIV_NS)
                if link.get("type") == "application/pdf"
            ),
            None,
        )
        published = _plain(entry.findtext("atom:published", default="", namespaces=ARXIV_NS), 10)
        record = _record(
            provider="arXiv",
            identifier=source_url,
            source_url=source_url,
            title=entry.findtext("atom:title", default="", namespaces=ARXIV_NS),
            abstract=entry.findtext("atom:summary", default="", namespaces=ARXIV_NS),
            topic=topic,
            user_id=user_id,
            published=published or None,
            doi=_plain(entry.findtext("arxiv:doi", default="", namespaces=ARXIV_NS), 300),
            pdf_url=pdf_url,
            extra_metadata={
                "arxiv_id": source_url.rstrip("/").rsplit("/", 1)[-1],
                "authors": [
                    {"name": author.findtext("atom:name", default="", namespaces=ARXIV_NS)}
                    for author in entry.findall("atom:author", ARXIV_NS)
                ],
                "revision_dates": [
                    _plain(entry.findtext("atom:updated", default="", namespaces=ARXIV_NS))
                ],
            },
        )
        if record:
            records.append(record)
    return records


def europe_pmc_papers(topic: str, user_id: str | None) -> list[dict[str, object]]:
    """Find biomedical papers and open-access full-text links."""
    response = requests.get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={"query": topic, "format": "json", "pageSize": SOURCE_RESULTS, "resultType": "core"},
        headers={"User-Agent": "ArchipelagoResearch/1.0 (academic discovery)"},
        timeout=SOURCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("resultList", {}).get("result", [])
    if not isinstance(items, list):
        raise ValueError("Unexpected Europe PMC response")
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        doi = _plain(item.get("doi"), 300)
        identifier = f"{item.get('source', 'MED')}/{item.get('id', '')}"
        source_url = (
            f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/{identifier}"
        )
        full_text = item.get("fullTextUrlList") or {}
        links = full_text.get("fullTextUrl", []) if isinstance(full_text, dict) else []
        pdf_url = next(
            (
                link.get("url")
                for link in links
                if isinstance(link, dict)
                and link.get("documentStyle") == "pdf"
                and link.get("availability") == "Open access"
            ),
            None,
        )
        record = _record(
            provider="Europe PMC",
            identifier=identifier,
            source_url=source_url,
            title=_plain(item.get("title"), 300),
            abstract=_plain(item.get("abstractText")),
            topic=topic,
            user_id=user_id,
            published=_plain(item.get("firstPublicationDate"), 10) or None,
            doi=doi,
            pdf_url=pdf_url,
            extra_metadata={
                "authors": [{"name": _plain(item.get("authorString"))}]
                if item.get("authorString")
                else [],
                "venue": item.get("journalTitle"),
                "paper_type": item.get("pubType"),
                "citation_count": item.get("citedByCount"),
                "is_open_access": item.get("isOpenAccess") == "Y"
                if item.get("isOpenAccess") in {"Y", "N"}
                else None,
            },
        )
        if record:
            records.append(record)
    return records


def semantic_scholar_papers(topic: str, user_id: str | None) -> list[dict[str, object]]:
    """Query Semantic Scholar when a server-side API key is configured."""
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if not key:
        return []
    response = requests.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={
            "query": topic,
            "limit": SOURCE_RESULTS,
            "fields": "title,abstract,year,externalIds,openAccessPdf,url,authors,citationCount,referenceCount,influentialCitationCount,publicationTypes,journal,isOpenAccess",
        },
        headers={"User-Agent": "ArchipelagoResearch/1.0", "x-api-key": key},
        timeout=SOURCE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("data", [])
    if not isinstance(items, list):
        raise ValueError("Unexpected Semantic Scholar response")
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ids: dict[str, Any] = item.get("externalIds") or {}
        doi = _plain(ids.get("DOI"), 300)
        paper_id = _plain(item.get("paperId"), 100)
        pdf = item.get("openAccessPdf") or {}
        record = _record(
            provider="Semantic Scholar",
            identifier=paper_id,
            source_url=f"https://doi.org/{doi}" if doi else _plain(item.get("url"), 500),
            title=_plain(item.get("title"), 300),
            abstract=_plain(item.get("abstract")),
            topic=topic,
            user_id=user_id,
            published=f"{item['year']}-01-01" if isinstance(item.get("year"), int) else None,
            doi=doi,
            pdf_url=pdf.get("url") if isinstance(pdf, dict) else None,
            extra_metadata={
                "authors": [
                    {"name": author.get("name"), "id": author.get("authorId")}
                    for author in item.get("authors") or []
                    if isinstance(author, dict)
                ],
                "citation_count": item.get("citationCount"),
                "reference_count": item.get("referenceCount"),
                "influential_citations": item.get("influentialCitationCount"),
                "venue": (item.get("journal") or {}).get("name")
                if isinstance(item.get("journal"), dict)
                else None,
                "paper_type": item.get("publicationTypes"),
                "is_open_access": item.get("isOpenAccess"),
            },
        )
        if record:
            records.append(record)
    return records
