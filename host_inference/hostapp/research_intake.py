"""Fetch bounded, source-linked research metadata and institutional pages."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from xml.etree.ElementTree import ParseError

import requests

from .research_providers import arxiv_papers, europe_pmc_papers, semantic_scholar_papers

HTTP_TIMEOUT_SECONDS = 12
PAPERS_PER_SOURCE = 30
TARGET_PAPERS = 100
MAX_PAGE_BYTES = 3_000_000
MAX_CONTENT_CHARS = 12_000
MAX_TITLE_CHARS = 300
MAX_ROBOTS_BYTES = 100_000
SOURCE_USER_AGENT = "ArchipelagoResearch/1.0 (+academic metadata intake)"
ALLOWED_COLLEGE_HOSTS = frozenset(
    {
        "uem.edu.in",
        "iem.edu.in",
        "faculty.iem.edu.in",
        "ceds.iem.edu.in",
        "www.iemcrp.com",
        "iemcrp.com",
        "uemk-opac.l2c2.co.in",
        "iemgurukul-opac.l2c2.co.in",
    }
)
HTML_SPACE = re.compile(r"\s+")


def _plain(value: object, limit: int = MAX_CONTENT_CHARS) -> str:
    """Collapse whitespace and cap untrusted source text."""
    return HTML_SPACE.sub(" ", str(value or "")).strip()[:limit]


def _key(kind: str, identifier: str) -> str:
    return sha256(f"{kind}:{identifier.lower().strip()}".encode()).hexdigest()


class PageText(HTMLParser):
    """Collect visible title, headings and paragraphs from a bounded HTML page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._active = ""
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self._ignored += 1
        if not self._ignored and tag in {"title", "h1", "h2", "h3", "p", "li"}:
            self._active = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self._ignored = max(0, self._ignored - 1)
        if tag == self._active:
            self._active = ""

    def handle_data(self, data: str) -> None:
        if self._ignored or not self._active:
            return
        value = _plain(data, MAX_TITLE_CHARS)
        if not value:
            return
        if self._active == "title" and not self.title:
            self.title = value
        elif len(" ".join(self.parts)) < MAX_CONTENT_CHARS:
            self.parts.append(value)


def fetch_college_page(url: str, user_id: str | None) -> dict[str, object]:
    """Fetch one approved institutional HTTPS page without following redirects."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_COLLEGE_HOSTS:
        raise ValueError("Use an HTTPS page from the approved IEM or UEM sites.")
    robots_url = f"{parsed.scheme}://{parsed.hostname}/robots.txt"
    robots_response = requests.get(
        robots_url,
        timeout=HTTP_TIMEOUT_SECONDS,
        allow_redirects=False,
        headers={"User-Agent": SOURCE_USER_AGENT},
    )
    if robots_response.status_code != 200 or len(robots_response.content) > MAX_ROBOTS_BYTES:
        raise ValueError("The source's crawl policy could not be verified.")
    robots = RobotFileParser()
    robots.parse(robots_response.text.splitlines())
    if not robots.can_fetch(SOURCE_USER_AGENT, url):
        raise ValueError("The source does not allow this page to be fetched.")
    response = requests.get(
        url,
        timeout=HTTP_TIMEOUT_SECONDS,
        allow_redirects=False,
        stream=True,
        headers={"User-Agent": SOURCE_USER_AGENT},
    )
    try:
        response.raise_for_status()
        if not response.headers.get("Content-Type", "").lower().startswith("text/html"):
            raise ValueError("The source did not return an HTML page.")
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=8192):
            size += len(chunk)
            if size > MAX_PAGE_BYTES:
                raise ValueError("The institutional page exceeds the intake limit.")
            chunks.append(chunk)
    finally:
        response.close()
    parser = PageText()
    parser.feed(b"".join(chunks).decode(response.encoding or "utf-8", errors="replace"))
    content = _plain(" ".join(parser.parts))
    if len(content) < 80:
        raise ValueError("The page has too little readable text to ingest.")
    return {
        "record_key": _key("institutional_page", url),
        "kind": "institutional_page",
        "title": _plain(parser.title or parsed.path or parsed.hostname, MAX_TITLE_CHARS),
        "source_url": url,
        "source_name": parsed.hostname,
        "topic": "",
        "content": content,
        "published_at": None,
        "metadata": {
            "content_type": "text/html",
            "extracted_chars": len(content),
            "source_timestamp": datetime.now(UTC).isoformat(),
            "active": True,
        },
        "updated_by": user_id,
    }


def _openalex_abstract(index: object) -> str:
    if not isinstance(index, dict):
        return ""
    words: dict[int, str] = {}
    for word, positions in index.items():
        if isinstance(positions, list):
            for position in positions:
                if isinstance(position, int) and 0 <= position < 1000:
                    words[position] = str(word)
    return _plain(" ".join(words[i] for i in sorted(words)))


def _paper_record(
    item: dict[str, Any], provider: str, topic: str, user_id: str | None
) -> dict[str, object] | None:
    if provider == "OpenAlex":
        title = _plain(item.get("display_name"), MAX_TITLE_CHARS)
        doi = _plain(item.get("doi"), 300)
        source_url = doi or _plain(item.get("id"), 500)
        content = _openalex_abstract(item.get("abstract_inverted_index"))
        publication_date = item.get("publication_date")
        oa = item.get("best_oa_location") or {}
        pdf_url = oa.get("pdf_url") if isinstance(oa, dict) else None
        location = item.get("primary_location") or {}
        source = location.get("source") or {} if isinstance(location, dict) else {}
        authorships = item.get("authorships") or []
        authors = [
            {
                "name": (entry.get("author") or {}).get("display_name"),
                "orcid": (entry.get("author") or {}).get("orcid"),
            }
            for entry in authorships
            if isinstance(entry, dict) and isinstance(entry.get("author"), dict)
        ]
        institutions = sorted(
            {
                str(institution["display_name"])
                for entry in authorships
                if isinstance(entry, dict)
                for institution in entry.get("institutions") or []
                if isinstance(institution, dict) and institution.get("display_name")
            }
        )
        metadata = {
            "authors": authors,
            "institutions": institutions,
            "venue": source.get("display_name") if isinstance(source, dict) else None,
            "paper_type": item.get("type"),
            "keywords": [
                keyword.get("display_name")
                for keyword in item.get("keywords") or []
                if isinstance(keyword, dict) and keyword.get("display_name")
            ],
            "citation_count": item.get("cited_by_count"),
            "reference_count": item.get("referenced_works_count"),
            "referenced_works": item.get("referenced_works"),
            "counts_by_year": item.get("counts_by_year"),
            "is_open_access": (item.get("open_access") or {}).get("is_oa"),
        }
    else:
        titles = item.get("title") or []
        title = _plain(titles[0] if isinstance(titles, list) and titles else "", MAX_TITLE_CHARS)
        doi = _plain(item.get("DOI"), 300)
        source_url = f"https://doi.org/{doi}" if doi else _plain(item.get("URL"), 500)
        content = _plain(re.sub(r"<[^>]+>", " ", str(item.get("abstract") or "")))
        published = item.get("published") or {}
        parts = published.get("date-parts") if isinstance(published, dict) else None
        publication_date = None
        if isinstance(parts, list) and parts and isinstance(parts[0], list):
            date_parts = parts[0]
            if date_parts and isinstance(date_parts[0], int):
                publication_date = f"{date_parts[0]:04d}-{(date_parts[1] if len(date_parts) > 1 else 1):02d}-{(date_parts[2] if len(date_parts) > 2 else 1):02d}"
        pdf_url = None
        container_titles = item.get("container-title") or []
        metadata = {
            "authors": [
                {
                    "name": " ".join(filter(None, (author.get("given"), author.get("family")))),
                    "orcid": author.get("ORCID"),
                }
                for author in item.get("author") or []
                if isinstance(author, dict)
            ],
            "venue": container_titles[0]
            if isinstance(container_titles, list) and container_titles
            else None,
            "publisher": item.get("publisher"),
            "paper_type": item.get("type"),
            "keywords": item.get("subject"),
            "citation_count": item.get("is-referenced-by-count"),
            "reference_count": item.get("references-count"),
            "is_open_access": None,
        }
    if not title or not source_url.startswith("https://"):
        return None
    identifier = doi.lower().removeprefix("https://doi.org/") if doi else source_url
    return {
        "record_key": _key("paper", identifier),
        "kind": "paper",
        "title": title,
        "source_url": source_url,
        "source_name": provider,
        "topic": topic,
        "content": content,
        "published_at": publication_date,
        "metadata": {
            **metadata,
            "doi": doi,
            "open_access_pdf": pdf_url,
            "has_abstract": bool(content),
            "source_timestamp": datetime.now(UTC).isoformat(),
        },
        "updated_by": user_id,
    }


def discover_papers(
    topic: str, user_id: str | None
) -> tuple[list[dict[str, object]], dict[str, str]]:
    """Search broad and subject-specific scholarly indexes for any topic."""
    providers: tuple[tuple[str, str, dict[str, str | int]], ...] = (
        (
            "OpenAlex",
            "https://api.openalex.org/works",
            {"search": topic, "per_page": PAPERS_PER_SOURCE},
        ),
        (
            "Crossref",
            "https://api.crossref.org/works",
            {"query.bibliographic": topic, "rows": PAPERS_PER_SOURCE},
        ),
    )
    records: dict[str, dict[str, object]] = {}
    status: dict[str, str] = {}
    for provider, url, params in providers:
        try:
            response = requests.get(
                url,
                params=params,
                timeout=HTTP_TIMEOUT_SECONDS,
                headers={"User-Agent": "ArchipelagoResearch/1.0 (academic discovery)"},
            )
            response.raise_for_status()
            payload = response.json()
            items = (
                payload.get("results", [])
                if provider == "OpenAlex"
                else payload.get("message", {}).get("items", [])
            )
            if not isinstance(items, list):
                raise ValueError("Unexpected provider response")
            for item in items:
                if not isinstance(item, dict):
                    continue
                record = _paper_record(item, provider, topic, user_id)
                if record:
                    key = str(record["record_key"])
                    previous = records.get(key)
                    if not previous or len(str(record["content"])) > len(str(previous["content"])):
                        records[key] = record
            status[provider] = f"ok: {len(items)} fetched"
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            status[provider] = f"unavailable: {type(exc).__name__}"
    additional = (
        ("arXiv", arxiv_papers),
        ("Europe PMC", europe_pmc_papers),
        ("Semantic Scholar", semantic_scholar_papers),
    )
    with ThreadPoolExecutor(max_workers=len(additional)) as pool:
        futures = [(name, pool.submit(fetch, topic, user_id)) for name, fetch in additional]
        for name, future in futures:
            try:
                rows = future.result()
                for record in rows:
                    key = str(record["record_key"])
                    previous = records.get(key)
                    if not previous or len(str(record["content"])) > len(str(previous["content"])):
                        records[key] = record
                status[name] = (
                    f"ok: {len(rows)} fetched"
                    if rows or name != "Semantic Scholar"
                    else "not configured"
                )
            except (
                requests.RequestException,
                ValueError,
                TypeError,
                AttributeError,
                ParseError,
            ) as exc:
                status[name] = f"unavailable: {type(exc).__name__}"
    by_provider: dict[str, list[dict[str, object]]] = {}
    for record in records.values():
        by_provider.setdefault(str(record["source_name"]), []).append(record)
    selected: list[dict[str, object]] = []
    provider_order = ("OpenAlex", "Crossref", "arXiv", "Europe PMC", "Semantic Scholar")
    while len(selected) < TARGET_PAPERS and any(by_provider.values()):
        for provider in provider_order:
            group = by_provider.get(provider)
            if group:
                selected.append(group.pop(0))
                if len(selected) == TARGET_PAPERS:
                    break
    return selected, status
