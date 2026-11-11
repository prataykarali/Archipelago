"""Read a small set of public Koha pages for the daily library display."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
from opac_live import (
    MAX_PAGE_BYTES,
    OPAC_HOST,
    OPAC_ORIGIN,
    REQUEST_TIMEOUT_SECONDS,
    SEARCH_PATH,
    USER_AGENT,
    _book_id,
    _fetch,
    _text,
)
import requests

SECTION_PAGES = {
    "journals": ("Journals", "59"),
    "magazines": ("Magazines", "63"),
    "ndli_club": ("NDLI Club", "67"),
    "library_notice": ("Library Notice", "69"),
}
PAGE_PATH = "/cgi-bin/koha/opac-page.pl"
MAX_SECTION_TEXT_CHARS = 600
MAX_SECTION_LINKS = 20
MAX_ARRIVALS = 20


def _public_link(href: str) -> str:
    """Keep only HTTPS links that the library page actually contains."""
    url = urljoin(OPAC_ORIGIN, href)
    parsed = urlparse(url)
    return url if parsed.scheme == "https" and parsed.hostname else ""


def _arrivals_query() -> dict[str, str]:
    """Read the current New Arrivals search parameters from the OPAC homepage."""
    response = requests.get(
        OPAC_ORIGIN,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=False,
    )
    response.raise_for_status()
    if response.is_redirect or len(response.content) > MAX_PAGE_BYTES:
        raise ValueError("Unexpected OPAC homepage response")
    soup = BeautifulSoup(response.content, "html.parser")
    for anchor in soup.select("a[href]"):
        if "new arrivals" not in _text(anchor).lower():
            continue
        url = urljoin(OPAC_ORIGIN, str(anchor.get("href") or ""))
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != OPAC_HOST or parsed.path != SEARCH_PATH:
            raise ValueError("Unexpected OPAC arrivals link")
        return {key: values[0] for key, values in parse_qs(parsed.query).items() if values}
    raise ValueError("OPAC has no New Arrivals link")


def fetch_daily_opac() -> dict[str, object]:
    """Fetch four public library sections and one arrivals results page."""
    sections: list[dict[str, object]] = []
    for key, (label, page_id) in SECTION_PAGES.items():
        soup, source_url = _fetch(PAGE_PATH, {"page_id": page_id})
        content = soup.select_one(f"#page_{page_id}")
        if content is None:
            raise ValueError(f"OPAC section {page_id} has no content")
        links = []
        seen: set[str] = set()
        for anchor in content.select("a[href]"):
            url = _public_link(str(anchor.get("href") or ""))
            if not url or url in seen:
                continue
            seen.add(url)
            links.append({"title": _text(anchor) or urlparse(url).hostname, "url": url})
            if len(links) >= MAX_SECTION_LINKS:
                break
        sections.append(
            {
                "key": key,
                "title": label,
                "summary": _text(content)[:MAX_SECTION_TEXT_CHARS],
                "links": links,
                "source_url": source_url,
            }
        )
    soup, arrivals_url = _fetch(SEARCH_PATH, _arrivals_query())
    arrivals: list[dict[str, str]] = []
    for anchor in soup.select(".searchresults a.title")[:MAX_ARRIVALS]:
        record_url = urljoin(OPAC_ORIGIN, str(anchor.get("href") or ""))
        identifier = _book_id(record_url)
        if identifier:
            arrivals.append(
                {
                    "biblionumber": identifier,
                    "title": _text(anchor),
                    "source_url": f"{OPAC_ORIGIN}/cgi-bin/koha/opac-detail.pl?biblionumber={identifier}",
                }
            )
    if not arrivals:
        raise ValueError("OPAC arrivals page has no records")
    content = {"sections": sections, "new_arrivals": arrivals, "new_arrivals_url": arrivals_url}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return {
        **content,
        "sha256": digest,
        "checked_at": datetime.now(UTC).isoformat(),
        "scope": "public_opac_pages_and_first_arrivals_page",
        "host": OPAC_HOST,
    }
