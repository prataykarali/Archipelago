"""Bounded, user-triggered reads of public Koha catalogue pages."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
import requests

OPAC_ORIGIN = "https://uemk-opac.l2c2.co.in"
OPAC_HOST = "uemk-opac.l2c2.co.in"
SEARCH_PATH = "/cgi-bin/koha/opac-search.pl"
DETAIL_PATH = "/cgi-bin/koha/opac-detail.pl"
REQUEST_TIMEOUT_SECONDS = 12
MAX_PAGE_BYTES = 2_000_000
MAX_QUERY_CHARS = 100
MAX_RESULTS = 20
MAX_HOLDINGS = 300
MAX_REDIRECTS = 3
USER_AGENT = "ArchipelagoAcademic/1.0 (user-triggered catalogue lookup)"
BIB_PATTERN = re.compile(r"^\d{1,9}$")


def _text(element: object) -> str:
    """Return normalized visible text from a Beautiful Soup element."""
    if element is None:
        return ""
    return " ".join(element.get_text(" ", strip=True).split())  # type: ignore[attr-defined]


def _fetch(path: str, params: dict[str, str]) -> tuple[BeautifulSoup, str]:
    """Fetch one public page and reject redirects outside the Koha catalogue."""
    url = f"{OPAC_ORIGIN}{path}"
    for _ in range(MAX_REDIRECTS + 1):
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        if not response.is_redirect:
            break
        url = urljoin(response.url, response.headers.get("Location", ""))
        parsed_redirect = urlparse(url)
        if (
            parsed_redirect.scheme != "https"
            or parsed_redirect.hostname != OPAC_HOST
            or not parsed_redirect.path.startswith("/cgi-bin/koha/opac-")
        ):
            raise ValueError("Unexpected OPAC redirect")
        params = {}
    else:
        raise ValueError("Too many OPAC redirects")
    response.raise_for_status()
    parsed = urlparse(response.url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != OPAC_HOST
        or not parsed.path.startswith("/cgi-bin/koha/opac-")
    ):
        raise ValueError("Unexpected OPAC redirect")
    if len(response.content) > MAX_PAGE_BYTES:
        raise ValueError("OPAC page exceeds size limit")
    return BeautifulSoup(response.content, "html.parser"), response.url


def _book_id(url: str) -> str:
    """Extract a valid Koha biblionumber from an OPAC record URL."""
    parsed = urlparse(url)
    if parsed.hostname != OPAC_HOST or parsed.path != DETAIL_PATH:
        return ""
    value = parse_qs(parsed.query).get("biblionumber", [""])[0]
    return value if BIB_PATTERN.fullmatch(value) else ""


def _record(soup: BeautifulSoup, source_url: str) -> dict[str, object]:
    """Parse bibliographic fields and per-copy statuses from a detail page."""
    heading = soup.select_one("h1.title")
    if heading is None:
        raise ValueError("OPAC record has no title")
    title = " ".join(heading.find_all(string=True, recursive=False)).strip()
    if not title:
        title = _text(heading)
    holdings = []
    for row in soup.select("#holdingst tbody tr")[:MAX_HOLDINGS]:
        cells = {
            name: _text(row.select_one(f"td.{name}"))
            for name in ("itype", "location", "call_no", "status", "date_due", "barcode")
        }
        holdings.append(
            {
                "item_type": cells["itype"],
                "library": cells["location"],
                "call_number": cells["call_no"].split("( Browse shelf", 1)[0].strip(),
                "status": cells["status"],
                "due_date": cells["date_due"],
                "barcode": cells["barcode"],
            }
        )
    return {
        "biblionumber": _book_id(source_url),
        "title": title,
        "author": _text(soup.select_one(".author .resource_list")),
        "isbn": _text(soup.select_one('.isbn [property="isbn"]')),
        "publisher": _text(soup.select_one(".publisher_name")),
        "year": _text(soup.select_one(".publisher_date")),
        "subjects": [_text(item) for item in soup.select(".subjects a.subject")],
        "holdings": holdings,
        "holdings_truncated": len(soup.select("#holdingst tbody tr")) > MAX_HOLDINGS,
        "source_url": source_url,
        "fetched_at": datetime.now(UTC).isoformat(),
    }


def lookup_book(biblionumber: str) -> dict[str, object]:
    """Get one live public catalogue record by its exact Koha ID."""
    if not BIB_PATTERN.fullmatch(biblionumber):
        raise ValueError("Invalid Koha book ID")
    soup, url = _fetch(DETAIL_PATH, {"biblionumber": biblionumber})
    record = _record(soup, url)
    if record["biblionumber"] != biblionumber:
        raise ValueError("OPAC returned another book ID")
    return record


def search_books(query: str) -> dict[str, object]:
    """Search one public results page and return source-linked book candidates."""
    query = " ".join(query.split())
    if not 2 <= len(query) <= MAX_QUERY_CHARS:
        raise ValueError("Search query must be 2-100 characters")
    soup, source_url = _fetch(SEARCH_PATH, {"q": query})
    redirected_id = _book_id(source_url)
    if redirected_id:
        record = _record(soup, source_url)
        return {"query": query, "results": [record], "fetched_at": record["fetched_at"]}
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(".searchresults a.title")[:MAX_RESULTS]:
        href = urljoin(OPAC_ORIGIN, str(anchor.get("href") or ""))
        identifier = _book_id(href)
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        summary = anchor.find_parent(class_="title_summary")
        results.append(
            {
                "biblionumber": identifier,
                "title": _text(anchor),
                "availability": _text(summary.select_one(".availability")) if summary else "",
                "source_url": f"{OPAC_ORIGIN}{DETAIL_PATH}?biblionumber={identifier}",
            }
        )
    return {"query": query, "results": results, "fetched_at": datetime.now(UTC).isoformat()}
