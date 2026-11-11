"""Canonical, source-backed evidence records for replies and library results."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
OPAC_SEARCH_URL = "https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-search.pl"
FIELDS = (
    "evidence_id",
    "source_type",
    "title",
    "authors",
    "publication_year",
    "doi",
    "isbn",
    "doc_id",
    "page_number",
    "printed_page",
    "section",
    "passage",
    "url",
    "source_provider",
    "retrieved_at",
    "verification_status",
    "access_status",
)


def verified_url(value: object) -> str:
    """Allow only supplied HTTPS source URLs or local resolver paths."""
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if url.startswith(("/api/page-view?", "/read?", "/open/", "/papers/")):
        return url
    return ""


def local_pdf_page(doc_id: str, page: object) -> str:
    """Return a page-view link only for a present local PDF and real page."""
    if not isinstance(page, int) or page < 1:
        return ""
    relative = str(doc_id or "").removeprefix("pdfs/").lstrip("/")
    path = (REPO_ROOT / "pdfs" / relative).resolve()
    if not path.is_relative_to(REPO_ROOT / "pdfs") or not path.is_file():
        return ""
    if page > _pdf_page_count(path):
        return ""
    return f"/api/page-view?doc_id={quote(relative, safe='')}&page={page}#page={page}"


@lru_cache(maxsize=256)
def _pdf_page_count(path: Path) -> int:
    """Read the physical PDF page count; unreadable files provide no link."""
    try:
        import fitz

        with fitz.open(path) as document:
            return len(document)
    except (ImportError, OSError, ValueError, RuntimeError):
        return 0


def evidence_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Keep supported fields, with provenance and a validated navigation target."""
    source = dict(raw)
    record: dict[str, Any] = {}
    for field in FIELDS:
        value = source.get(field)
        if value not in (None, "", []):
            record[field] = value
    for target, aliases in {
        "title": ("doc_title", "document_title", "book_title"),
        "section": ("section_title",),
        "passage": ("text_span", "text_passage", "text"),
    }.items():
        if target not in record:
            for alias in aliases:
                if source.get(alias):
                    record[target] = source[alias]
                    break
    doc_id = str(record.get("doc_id") or "")
    page = record.get("page_number")
    if page is not None and (not isinstance(page, int) or page < 1):
        record.pop("page_number", None)
        page = None
    source_type = record.get("source_type")
    if not source_type:
        source_type = (
            "ingested_pdf" if doc_id.lower().endswith(".pdf") and page else "metadata_only"
        )
        record["source_type"] = source_type
    url = verified_url(record.get("url"))
    if source_type == "ingested_pdf":
        local_url = local_pdf_page(doc_id, page)
        url = local_url or (url if url.startswith("https://") else "")
        if not url:
            record["verification_status"] = "Requires verification"
    elif (
        source_type == "scholarly_record"
        and record.get("doi")
        and record.get("verification_status") == "Verified"
    ):
        doi = str(record["doi"]).removeprefix("https://doi.org/")
        if re.fullmatch(r"10\.\d{4,9}/\S+", doi, re.I):
            url = url or f"https://doi.org/{quote(doi, safe='/')}"
    if url:
        record["url"] = url
    else:
        record.pop("url", None)
    record.setdefault(
        "verification_status",
        "Verified"
        if url and source_type in {"ingested_pdf", "scholarly_record"}
        else "Metadata only",
    )
    record.setdefault("access_status", "Available" if url else "Requires verification")
    return record


def catalog_search_url(title: str) -> str:
    """Return an OPAC search action, never a claimed matching record."""
    return f"{OPAC_SEARCH_URL}?q={quote(title, safe='')}"


def retain_observations(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate exact reports while preserving disagreeing source observations."""
    seen: set[tuple[object, ...]] = set()
    kept: list[dict[str, Any]] = []
    for raw in records:
        normalized = evidence_record(raw)
        key = (
            normalized.get("source_provider"),
            normalized.get("retrieved_at"),
            normalized.get("doc_id"),
            normalized.get("url"),
            raw.get("available_copies"),
            raw.get("total_copies"),
            str(normalized.get("passage") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append({**raw, **normalized})
    return kept
