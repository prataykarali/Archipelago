"""Bounded identifier-first searches for reusable book and article evidence."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any
from urllib.parse import urlparse

from defusedxml import ElementTree as ET
import requests  # type: ignore[import-untyped]

OPEN_LIBRARY_API = "https://openlibrary.org/api/books"
CROSSREF_API = "https://api.crossref.org/works"
EUROPE_PMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
REQUEST_TIMEOUT_SECONDS = 12
MAX_JSON_BYTES = 1_000_000
MAX_XML_BYTES = 3_000_000
MAX_TOC_ITEMS = 80
MAX_TOC_TITLE_CHARS = 180
MAX_ARTICLE_CHARS = 40_000
MIN_TITLE_TOKENS = 3
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.I)
ISBN_PATTERN = re.compile(r"^(?:\d{10}|\d{13})$")
PMCID_PATTERN = re.compile(r"^PMC\d+$", re.I)
ALLOWED_ARTICLE_LICENSES = {
    "cc-by-4.0": "CC-BY-4.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0",
    "cc0-1.0": "CC0-1.0",
}


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def title_matches(wanted: str, found: str) -> bool:
    """Require a strong title overlap before joining two providers."""
    a, b = _tokens(wanted), _tokens(found)
    return len(a) >= MIN_TITLE_TOKENS and len(b) >= MIN_TITLE_TOKENS and len(a & b) / max(len(a), len(b)) >= 0.8


def _get(url: str, *, params: dict[str, str] | None = None, max_bytes: int = MAX_JSON_BYTES) -> requests.Response:
    """Fetch only configured HTTPS provider endpoints without redirecting elsewhere."""
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": "ArchipelagoAcademic/1.0 (catalog evidence discovery)"},
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=False,
    )
    if response.status_code == 404:
        return response
    response.raise_for_status()
    if response.is_redirect or len(response.content) > max_bytes:
        raise ValueError("External source redirected or exceeded size limit")
    return response


def open_library_edition(isbn: str, expected_title: str) -> dict[str, Any] | None:
    """Find an exact ISBN edition and its public catalog contents, when present."""
    isbn = re.sub(r"[^0-9X]", "", isbn.upper())
    if not ISBN_PATTERN.fullmatch(isbn):
        return None
    response = _get(
        OPEN_LIBRARY_API,
        params={"bibkeys": f"ISBN:{isbn}", "jscmd": "details", "format": "json"},
    )
    if response.status_code == 404:
        return None
    entry = response.json().get(f"ISBN:{isbn}")
    if not isinstance(entry, dict):
        return None
    details = entry.get("details") or {}
    title = str(details.get("title") or "")
    known_isbns = {str(value) for value in (details.get("isbn_10") or []) + (details.get("isbn_13") or [])}
    expected_tokens, found_tokens = _tokens(expected_title), _tokens(title)
    if isbn not in known_isbns or len(expected_tokens & found_tokens) < min(2, len(found_tokens)):
        return None
    key = str(details.get("key") or "")
    if not re.fullmatch(r"/books/OL\d+M", key):
        return None
    items = []
    for row in details.get("table_of_contents") or []:
        if isinstance(row, dict):
            heading = " ".join(str(row.get("title") or "").split())[:MAX_TOC_TITLE_CHARS]
            if heading:
                items.append({"title": heading, "page": str(row.get("pagenum") or "")})
        if len(items) >= MAX_TOC_ITEMS:
            break
    source_url = f"https://openlibrary.org{key}"
    return {
        "provider": "open_library",
        "source_id": key,
        "source_url": source_url,
        "title": title,
        "isbn": isbn,
        "status": "catalog_metadata",
        "license": "CC0-1.0",
        "license_url": "https://openlibrary.org/help/faq/using",
        "table_of_contents": items,
        "retrieved_at": datetime.now(UTC).isoformat(),
    }


def crossref_article(title: str) -> dict[str, Any] | None:
    """Resolve an exact article title to DOI metadata, without assuming access rights."""
    if len(_tokens(title)) < MIN_TITLE_TOKENS:
        return None
    response = _get(CROSSREF_API, params={"query.bibliographic": title, "rows": "5"})
    if response.status_code == 404:
        return None
    for row in response.json().get("message", {}).get("items", []):
        if not isinstance(row, dict) or row.get("type") not in {"journal-article", "proceedings-article"}:
            continue
        found_title = str((row.get("title") or [""])[0])
        doi = str(row.get("DOI") or "")
        if title_matches(title, found_title) and DOI_PATTERN.fullmatch(doi):
            return {
                "provider": "crossref",
                "source_id": doi.lower(),
                "source_url": f"https://doi.org/{doi}",
                "doi": doi,
                "title": found_title,
                "status": "metadata_only",
                "retrieved_at": datetime.now(UTC).isoformat(),
            }
    return None


def _license_from_xml(root: ET.Element) -> str | None:
    for element in root.iter():
        if element.tag.split("}")[-1] != "license":
            continue
        text = " ".join(element.itertext()).casefold()
        for marker, license_id in ALLOWED_ARTICLE_LICENSES.items():
            if marker in text or marker.replace("-", " ") in text:
                return license_id
    return None


def europe_pmc_open_article(doi: str, expected_title: str) -> dict[str, Any] | None:
    """Retrieve a matching open-access article only with an allowed XML license."""
    if not DOI_PATTERN.fullmatch(doi):
        return None
    response = _get(
        f"{EUROPE_PMC_API}/search",
        params={"query": f"DOI:{doi}", "format": "json", "resultType": "core", "pageSize": "3"},
    )
    if response.status_code == 404:
        return None
    for row in response.json().get("resultList", {}).get("result", []):
        if not isinstance(row, dict) or str(row.get("doi") or "").casefold() != doi.casefold():
            continue
        if not title_matches(expected_title, str(row.get("title") or "")) or row.get("isOpenAccess") != "Y":
            continue
        pmcid = str(row.get("pmcid") or "")
        if not PMCID_PATTERN.fullmatch(pmcid):
            continue
        xml_response = _get(f"{EUROPE_PMC_API}/{pmcid}/fullTextXML", max_bytes=MAX_XML_BYTES)
        if xml_response.status_code == 404:
            continue
        root = ET.fromstring(xml_response.content)
        license_id = _license_from_xml(root)
        if not license_id:
            continue
        sections: list[str] = []
        for element in root.iter():
            if element.tag.split("}")[-1] in {"abstract", "sec"}:
                passage = " ".join(" ".join(element.itertext()).split())
                if passage:
                    sections.append(passage)
            if sum(map(len, sections)) >= MAX_ARTICLE_CHARS:
                break
        if not sections:
            continue
        return {
            "provider": "europe_pmc",
            "source_id": pmcid,
            "source_url": f"https://europepmc.org/articles/{pmcid}",
            "doi": doi,
            "title": str(row["title"]),
            "status": "open_permitted",
            "license": license_id,
            "license_url": f"https://europepmc.org/articles/{pmcid}",
            "text": "\n\n".join(sections)[:MAX_ARTICLE_CHARS],
            "retrieved_at": datetime.now(UTC).isoformat(),
        }
    return None
