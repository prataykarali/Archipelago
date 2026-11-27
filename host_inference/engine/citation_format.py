"""Render hosted citations from resolver records, without guessing pages.

Enforces explicit ``source_kind`` classification and validates source existence,
access rights (``open_access_only``), document type, and page bounds before
exposing any clickable ``/read?doc=...&page=...`` link.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from library_index import resolve_hf_source

from .access_profile import is_institutional_card, is_open_access_profile, is_pearson_url
from .corpus_titles import clean_bibliographic_title
from .source_resolution import (
    SOURCE_CAT_MISSING,
    SOURCE_CAT_OA_PAPER,
    SOURCE_CAT_PEARSON,
    SOURCE_CAT_TOC_INDEX,
    is_toc_or_index_doc,
)

# Canonical 4-way citation source_kind values exposed to the UI and evaluator.
SOURCE_KIND_VERIFIED_FULL_TEXT = "verified_full_text_passage"
SOURCE_KIND_METADATA_ONLY = "metadata_only_record"
SOURCE_KIND_INSTITUTIONAL = "institutional_licensed"
SOURCE_KIND_UNAVAILABLE = "unavailable_document"

MAX_REASONABLE_PDF_PAGE = 2500
MAX_PAPER_PDF_PAGE = 300
_NON_PDF_EXTENSIONS = (".txt", ".md", ".json", ".html", ".htm", ".csv", ".xml")
_SOURCES_HEADER_RE = re.compile(r"(?:^|\n)(?:\*\*Sources:\*\*|#{1,4}\s+Sources\b)", re.I)


def _safe_link(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if url.startswith(("/read?", "/api/page-view?", "/open/", "/papers/")):
        return url
    return ""


def _is_text_card_doc(doc_id: str) -> bool:
    """True when ``doc_id`` points to a non-PDF text/metadata card that /read cannot display."""
    low = (doc_id or "").strip().lower()
    return bool(low) and low.endswith(_NON_PDF_EXTENSIONS)


def _parse_positive_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    if text.isdigit():
        num = int(text)
        return num if num > 0 else None
    return None


def _page_within_bounds(page: int | None, record: dict[str, Any]) -> int | None:
    """Validate page bounds against known page_count or sensible document caps."""
    if page is None or page <= 0:
        return None
    max_pages = _parse_positive_int(record.get("page_count") or record.get("total_pages"))
    if max_pages is not None:
        return page if page <= max_pages else None
    source_cat = str(record.get("source_category") or "").strip().lower()
    cap = MAX_PAPER_PDF_PAGE if source_cat == SOURCE_CAT_OA_PAPER else MAX_REASONABLE_PDF_PAGE
    return page if page <= cap else None


def _validate_reader_url(
    url: str,
    record: dict[str, Any],
    *,
    open_access_only: bool,
) -> tuple[str, int | None, bool]:
    """Validate existence, access rights, document type, and page bounds for ``url``.

    Returns ``(validated_url, validated_page, is_reader_resolvable)``.
    """
    safe = _safe_link(url)
    if not safe:
        return "", None, False

    if is_pearson_url(safe):
        if open_access_only:
            return "", None, False
        # Institutional /open/<id> links never carry invented PDF page numbers.
        if safe.startswith("/open/"):
            clean_open = safe.split("?", 1)[0].split("#", 1)[0]
            return clean_open, None, True
        return "", None, False

    if safe.startswith(("/read?", "/api/page-view?")):
        parsed = urlparse(safe)
        params = parse_qs(parsed.query)
        raw_doc = unquote((params.get("doc") or [str(record.get("doc_id") or "")])[0]).strip()
        if not raw_doc or _is_text_card_doc(raw_doc) or is_toc_or_index_doc(raw_doc):
            return "", None, False
        if not raw_doc.lower().endswith(".pdf"):
            return "", None, False
        _repo, hf_path = resolve_hf_source(raw_doc)
        if not hf_path:
            rec_doc = str(record.get("doc_id") or "").strip()
            if rec_doc and rec_doc != raw_doc and rec_doc.lower().endswith(".pdf"):
                _repo, hf_path = resolve_hf_source(rec_doc)
        if not hf_path:
            return "", None, False

        raw_page = _parse_positive_int(
            (params.get("page") or [record.get("page_number")])[0]
        )
        valid_page = _page_within_bounds(raw_page, record)
        rebuilt = f"/read?doc={quote(raw_doc, safe='')}"
        if valid_page is not None:
            rebuilt += f"&page={valid_page}"
        return rebuilt, valid_page, True

    parsed = urlparse(safe)
    if parsed.scheme == "https" and parsed.netloc:
        valid_page = _page_within_bounds(_parse_positive_int(record.get("page_number")), record)
        return safe, valid_page, True

    return "", None, False


def classify_source_kind(
    record: dict[str, Any],
    *,
    open_access_only: bool | None = None,
) -> str:
    """Classify a citation into one of the four explicit ``source_kind`` buckets."""
    oa_only = is_open_access_profile() if open_access_only is None else open_access_only
    if not isinstance(record, dict):
        return SOURCE_KIND_UNAVAILABLE
    if record.get("withdrawn") or str(record.get("source_type") or "").strip().lower() == "withdrawn":
        return SOURCE_KIND_UNAVAILABLE

    raw_url = str(record.get("url") or record.get("pdf_url") or "").strip()
    source_cat = str(record.get("source_category") or "").strip().lower()
    source_type = str(record.get("source_type") or "").strip().lower()
    doc_id = str(record.get("doc_id") or "").strip()

    if (
        source_cat == SOURCE_CAT_PEARSON
        or is_institutional_card(record)
        or is_pearson_url(raw_url)
    ):
        return SOURCE_KIND_INSTITUTIONAL

    if (
        source_cat == SOURCE_CAT_TOC_INDEX
        or source_type == "toc_index_only"
        or _is_text_card_doc(doc_id)
        or is_toc_or_index_doc(doc_id)
    ):
        return SOURCE_KIND_METADATA_ONLY

    if source_cat == SOURCE_CAT_MISSING:
        if doc_id.lower().endswith(".pdf"):
            return SOURCE_KIND_UNAVAILABLE
        return SOURCE_KIND_METADATA_ONLY if doc_id else SOURCE_KIND_UNAVAILABLE

    valid_url, _valid_page, resolvable = _validate_reader_url(
        raw_url, record, open_access_only=oa_only
    )
    if resolvable and valid_url:
        if source_type in {"metadata_only", "catalog_metadata"}:
            return SOURCE_KIND_METADATA_ONLY
        return SOURCE_KIND_VERIFIED_FULL_TEXT

    if doc_id.lower().endswith(".pdf"):
        _repo, hf_path = resolve_hf_source(doc_id)
        if not hf_path:
            return SOURCE_KIND_UNAVAILABLE
    if source_type in {"metadata_only", "catalog_metadata"} or record.get("reader_resolvable") is False:
        return SOURCE_KIND_METADATA_ONLY
    return SOURCE_KIND_UNAVAILABLE


def sanitize_citation_record(
    record: dict[str, Any],
    *,
    open_access_only: bool | None = None,
) -> dict[str, Any]:
    """Validate URL, page bounds, access rights, and attach explicit ``source_kind``."""
    oa_only = is_open_access_profile() if open_access_only is None else open_access_only
    item = dict(record)
    source_kind = classify_source_kind(item, open_access_only=oa_only)
    item["source_kind"] = source_kind

    raw_url = str(item.get("url") or item.get("pdf_url") or "").strip()
    if source_kind in {SOURCE_KIND_UNAVAILABLE, SOURCE_KIND_METADATA_ONLY}:
        item["url"] = ""
        item["pdf_url"] = ""
        item["reader_resolvable"] = False
        item["page_verified"] = False
        item["clickable"] = False
        if source_kind == SOURCE_KIND_UNAVAILABLE:
            item["page_number"] = None
        return item

    if source_kind == SOURCE_KIND_INSTITUTIONAL:
        if oa_only:
            item["url"] = ""
            item["pdf_url"] = ""
            item.pop("reader_url", None)
            item.pop("open_url", None)
            item["reader_resolvable"] = False
            item["page_number"] = None
            item["page_verified"] = False
            item["clickable"] = False
            return item
        valid_url, _page, resolvable = _validate_reader_url(
            raw_url, item, open_access_only=False
        )
        item["url"] = valid_url
        item["pdf_url"] = valid_url
        item["reader_resolvable"] = resolvable
        item["page_number"] = None
        item["page_verified"] = False
        item["clickable"] = bool(valid_url and resolvable)
        return item

    # SOURCE_KIND_VERIFIED_FULL_TEXT
    valid_url, valid_page, resolvable = _validate_reader_url(
        raw_url, item, open_access_only=oa_only
    )
    if not resolvable or not valid_url:
        item["source_kind"] = SOURCE_KIND_UNAVAILABLE
        item["url"] = ""
        item["pdf_url"] = ""
        item["reader_resolvable"] = False
        item["page_number"] = None
        item["page_verified"] = False
        item["clickable"] = False
        return item

    item["url"] = valid_url
    item["pdf_url"] = valid_url
    item["reader_resolvable"] = True
    item["page_number"] = valid_page
    item["page_verified"] = valid_page is not None
    item["clickable"] = True
    return item


def sanitize_citations(
    citations: list[dict[str, Any]] | None,
    *,
    open_access_only: bool | None = None,
) -> list[dict[str, Any]]:
    """Sanitize every citation record and drop institutional cards under ``open_access_only``."""
    if not isinstance(citations, list):
        return []
    oa_only = is_open_access_profile() if open_access_only is None else open_access_only
    cleaned: list[dict[str, Any]] = []
    for raw in citations:
        if not isinstance(raw, dict):
            continue
        item = sanitize_citation_record(raw, open_access_only=oa_only)
        if oa_only and item.get("source_kind") == SOURCE_KIND_INSTITUTIONAL:
            continue
        cleaned.append(item)
    return cleaned


def has_verified_full_text_citations(citations: list[dict[str, Any]] | None) -> bool:
    """True only when at least one citation is a validated ``verified_full_text_passage``."""
    return any(
        isinstance(c, dict)
        and c.get("source_kind") == SOURCE_KIND_VERIFIED_FULL_TEXT
        and bool(c.get("url"))
        and not c.get("withdrawn")
        for c in (citations or [])
    )


def citation_link(record: dict[str, Any]) -> str:
    """Make an inline link to a source only after existence, rights, and page validation."""
    if not isinstance(record, dict):
        return ""
    oa_only = is_open_access_profile()
    sanitized = sanitize_citation_record(record, open_access_only=oa_only)
    label = str(sanitized.get("label") or "").strip()
    if not label:
        return ""
    source_kind = sanitized["source_kind"]
    if oa_only and source_kind == SOURCE_KIND_INSTITUTIONAL:
        return ""
    url = str(sanitized.get("url") or "").strip()
    if sanitized.get("withdrawn") or not url or not sanitized.get("clickable"):
        return label
    raw_title = str(sanitized.get("doc_title") or sanitized.get("title") or "")
    doc_id = str(sanitized.get("doc_id") or "")
    is_pearson = source_kind == SOURCE_KIND_INSTITUTIONAL
    title = raw_title if is_pearson and raw_title else clean_bibliographic_title(doc_id, raw_title)
    page = sanitized.get("page_number")
    if is_pearson:
        page_text = " (Pearson catalogue-only)"
    else:
        page_text = f", PDF p.{page}" if isinstance(page, int) and page > 0 else ""
    eid = sanitized.get("evidence_id") or re.match(r"\[(S\d+):", label)
    if isinstance(eid, re.Match):
        eid = eid.group(1)
    return f"[{eid}: {title}{page_text}]({url})" if eid else label


def link_answer_sources(text: str, citations: list[dict[str, Any]]) -> str:
    """Replace only supplied citation labels and list every distinct source without duplication."""
    body = text or ""
    lines = []
    seen = set()
    for record in citations:
        if not isinstance(record, dict):
            continue
        label = record.get("label")
        rendered = citation_link(record)
        if label and rendered:
            body = body.replace(str(label), rendered)
        key = (record.get("doc_id"), record.get("page_number"), record.get("url"), rendered)
        if rendered and key not in seen:
            seen.add(key)
            lines.append(f"- {rendered}")
    if not lines or _SOURCES_HEADER_RE.search(body):
        return body
    return body + "\n\n**Sources:**\n" + "\n".join(lines)


__all__ = [
    "MAX_PAPER_PDF_PAGE",
    "MAX_REASONABLE_PDF_PAGE",
    "SOURCE_KIND_INSTITUTIONAL",
    "SOURCE_KIND_METADATA_ONLY",
    "SOURCE_KIND_UNAVAILABLE",
    "SOURCE_KIND_VERIFIED_FULL_TEXT",
    "citation_link",
    "classify_source_kind",
    "has_verified_full_text_citations",
    "link_answer_sources",
    "sanitize_citation_record",
    "sanitize_citations",
]
