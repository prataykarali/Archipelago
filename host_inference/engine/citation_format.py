"""Render hosted citations from resolver records, without guessing pages.

Enforces the unified 4-state source provenance contract
(``verified_full_text_passage``, ``metadata_only_record``,
``institutional_licensed``, ``unavailable_document``) alongside fine-grained
evidence states, validates D14 OA license compliance, page bounds,
printed-page-to-PDF-page mapping, and deduplication before exposing any link.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from library_index import resolve_hf_source

from .access_profile import (
    d14_canonical_oa_url,
    is_d14_approved_oa,
    is_d14_excluded_commercial,
    is_institutional_card,
    is_open_access_profile,
    is_pearson_url,
    is_restricted_artifact_path,
    lookup_d14_source,
)
from .docmap import HF_DOC_MAP
from .provenance import (
    EVIDENCE_STATE_AUTHORIZED_EXTERNAL,
    EVIDENCE_STATE_AVAILABLE_FULL_TEXT,
    EVIDENCE_STATE_LABELS,
    EVIDENCE_STATE_METADATA_ONLY,
    EVIDENCE_STATE_RELEVANT_SUPPORTING,
    EVIDENCE_STATE_RETRIEVED_UNASSESSED,
    EVIDENCE_STATE_UNAVAILABLE,
    FOLLOW_UP_ELIGIBLE_STATES,
    FULL_TEXT_EVIDENCE_STATES,
    SOURCE_KIND_INSTITUTIONAL,
    SOURCE_KIND_LABELS,
    SOURCE_KIND_METADATA_ONLY,
    SOURCE_KIND_UNAVAILABLE,
    SOURCE_KIND_VERIFIED_FULL_TEXT,
    classify_evidence_state,
    format_canonical_title,
    ostep_chapter_info,
    printed_to_pdf_page,
    resolve_page_provenance,
)
from .source_resolution import (
    SOURCE_CAT_MISSING,
    SOURCE_CAT_OA_PAPER,
    SOURCE_CAT_PEARSON,
    SOURCE_CAT_TOC_INDEX,
    is_toc_or_index_doc,
)

MAX_REASONABLE_PDF_PAGE = 2500
MAX_PAPER_PDF_PAGE = 300
_NON_PDF_EXTENSIONS = (".txt", ".md", ".json", ".html", ".htm", ".csv", ".xml")
_SOURCES_HEADER_RE = re.compile(r"(?:^|\n)(?:\*\*Sources:\*\*|#{1,4}\s+Sources\b)", re.I)
_DISALLOWED_SELF_URL_RE = re.compile(r"^(?:/chat(?:[/?#]|$)|#|javascript:|data:)", re.I)
_HF_KNOWN_TARGETS = frozenset(v.lower() for v in HF_DOC_MAP.values()) | frozenset(
    v.lower().rsplit("/", 1)[-1] for v in HF_DOC_MAP.values()
)


def _safe_link(value: object) -> str:
    url = str(value or "").strip()
    if not url or _DISALLOWED_SELF_URL_RE.match(url):
        return ""
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if url.startswith(("/read?", "/api/page-view?", "/open/", "/papers/")):
        return url
    return ""


def _safe_bibliographic_url(record: dict[str, Any], *, open_access_only: bool) -> str:
    """Return a genuine external HTTPS bibliographic/publisher URL, never /chat or /read."""
    if is_d14_excluded_commercial(record) and open_access_only:
        return ""
    for field in ("bibliographic_url", "external_url", "doi_url", "publisher_url", "arxiv_url"):
        raw = str(record.get(field) or "").strip()
        if not raw or _DISALLOWED_SELF_URL_RE.match(raw):
            continue
        parsed = urlparse(raw)
        if parsed.scheme != "https" or not parsed.netloc:
            continue
        if open_access_only and is_pearson_url(raw):
            continue
        return raw
    return ""


def _is_text_card_doc(doc_id: str) -> bool:
    """True when ``doc_id`` is a non-PDF metadata card (excluding approved D14 OA HTML/TXT)."""
    low = (doc_id or "").strip().lower()
    if not low or is_d14_approved_oa(low):
        return False
    return low.endswith(_NON_PDF_EXTENSIONS)


def _parse_positive_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    return int(text) if text.isdigit() and int(text) > 0 else None


def _page_within_bounds(page: int | None, record: dict[str, Any]) -> int | None:
    """Validate page bounds against known page_count or sensible document caps."""
    if page is None or page <= 0:
        return None
    prov_meta = resolve_page_provenance(str(record.get("doc_id") or ""), page, record.get("printed_page"))
    max_pages = _parse_positive_int(
        record.get("page_count") or record.get("total_pages") or prov_meta.get("known_page_count")
    )
    if max_pages is not None:
        return page if page <= max_pages else None
    cap = MAX_PAPER_PDF_PAGE if str(record.get("source_category") or "").strip().lower() == SOURCE_CAT_OA_PAPER else MAX_REASONABLE_PDF_PAGE
    return page if page <= cap else None


def _is_known_hf_pdf(raw_doc: str) -> bool:
    """True when ``raw_doc`` resolves to a verified HF PDF (D14 baseline, docmap, or HF index)."""
    low = (raw_doc or "").strip().lower().lstrip("/")
    if not low or not low.endswith(".pdf"):
        return False
    entry = lookup_d14_source(low)
    if entry is not None:
        return bool(entry["is_approved_oa"] and entry["origin"] == "baseline_v2_hf_cache")
    if low in _HF_KNOWN_TARGETS or low.rsplit("/", 1)[-1] in _HF_KNOWN_TARGETS:
        return True
    _repo, hf_path = resolve_hf_source(raw_doc)
    return bool(hf_path)


def _resolve_d14_external_oa_url(record: dict[str, Any], valid_page: int | None) -> str:
    """Return canonical external OA URL for ``d14_oa/*`` sources (with #page=N for PDFs)."""
    url = d14_canonical_oa_url(record)
    if not url:
        return ""
    if valid_page is not None and url.lower().endswith(".pdf") and "#page=" not in url.lower():
        return f"{url}#page={valid_page}"
    return url


def _resolve_requested_page(raw_page: object, record: dict[str, Any], doc_id: str) -> int | None:
    """Resolve explicit PDF page or map ``printed_page`` -> PDF page, bounded to document."""
    parsed = _parse_positive_int(raw_page)
    if parsed is None and record.get("printed_page") is not None:
        parsed = printed_to_pdf_page(doc_id, record.get("printed_page"))
    return _page_within_bounds(parsed, record)


def _validate_reader_url(
    url: str,
    record: dict[str, Any],
    *,
    open_access_only: bool,
) -> tuple[str, int | None, bool]:
    """Validate existence, access rights, document type, and page bounds for ``url``."""
    doc_id = str(record.get("doc_id") or "").strip()
    if is_d14_excluded_commercial(record):
        return "", None, False

    d14_entry = lookup_d14_source(record.get("source_id") or doc_id)
    if d14_entry is not None and d14_entry["is_approved_oa"] and d14_entry["origin"] == "d14_oa_acquisition":
        valid_page = _resolve_requested_page(record.get("page_number"), record, doc_id)
        ext_url = _resolve_d14_external_oa_url(record, valid_page)
        if ext_url:
            return ext_url, valid_page, True

    safe = _safe_link(url)
    if not safe:
        if d14_entry is not None and d14_entry["is_approved_oa"]:
            valid_page = _resolve_requested_page(record.get("page_number"), record, doc_id)
            if d14_entry["origin"] == "baseline_v2_hf_cache" and d14_entry["source_format"] == "pdf":
                rebuilt = f"/read?doc={quote(d14_entry['doc_id'], safe='')}"
                if valid_page is not None:
                    rebuilt += f"&page={valid_page}"
                return rebuilt, valid_page, True
            ext_url = _resolve_d14_external_oa_url(record, valid_page)
            if ext_url:
                return ext_url, valid_page, True
        return "", None, False

    if is_pearson_url(safe):
        if open_access_only:
            return "", None, False
        if safe.startswith("/open/"):
            return safe.split("?", 1)[0].split("#", 1)[0], None, True
        return "", None, False

    if safe.startswith(("/read?", "/api/page-view?")):
        parsed = urlparse(safe)
        params = parse_qs(parsed.query)
        raw_doc = unquote(
            (params.get("doc") or params.get("doc_id") or params.get("id") or [doc_id])[0]
        ).strip()
        if not raw_doc or _is_text_card_doc(raw_doc) or is_toc_or_index_doc(raw_doc):
            return "", None, False
        if open_access_only and is_restricted_artifact_path(raw_doc):
            return "", None, False
        if not raw_doc.lower().endswith(".pdf"):
            return "", None, False
        if not _is_known_hf_pdf(raw_doc) and not (doc_id and doc_id != raw_doc and _is_known_hf_pdf(doc_id)):
            return "", None, False

        raw_page = (params.get("page") or [record.get("page_number")])[0]
        valid_page = _resolve_requested_page(raw_page, record, raw_doc)
        if safe.startswith("/api/page-view?"):
            rebuilt = f"/api/page-view?doc_id={quote(raw_doc, safe='')}"
            if valid_page is not None:
                rebuilt += f"&page={valid_page}#page={valid_page}"
            return rebuilt, valid_page, True
        rebuilt = f"/read?doc={quote(raw_doc, safe='')}"
        if valid_page is not None:
            rebuilt += f"&page={valid_page}"
        return rebuilt, valid_page, True

    if safe.startswith("/papers/"):
        raw_doc = unquote(safe.removeprefix("/papers/").split("#", 1)[0].split("?", 1)[0]).strip()
        if not raw_doc or (open_access_only and is_restricted_artifact_path(raw_doc)) or not _is_known_hf_pdf(raw_doc):
            return "", None, False
        valid_page = _resolve_requested_page(record.get("page_number"), record, raw_doc)
        base_url = safe.split("#", 1)[0]
        return (f"{base_url}#page={valid_page}" if valid_page is not None else base_url), valid_page, True

    parsed = urlparse(safe)
    if parsed.scheme == "https" and parsed.netloc:
        valid_page = _resolve_requested_page(record.get("page_number"), record, doc_id)
        return safe, valid_page, True

    return "", None, False


def classify_source_kind(
    record: dict[str, Any],
    *,
    open_access_only: bool | None = None,
) -> str:
    """Classify a citation into one of the four canonical ``source_kind`` buckets."""
    oa_only = is_open_access_profile() if open_access_only is None else open_access_only
    if not isinstance(record, dict):
        return SOURCE_KIND_UNAVAILABLE
    if record.get("withdrawn") or str(record.get("source_type") or "").strip().lower() == "withdrawn":
        return SOURCE_KIND_UNAVAILABLE
    if is_d14_excluded_commercial(record):
        return SOURCE_KIND_METADATA_ONLY

    raw_url = str(record.get("url") or record.get("pdf_url") or "").strip()
    source_cat = str(record.get("source_category") or "").strip().lower()
    source_type = str(record.get("source_type") or "").strip().lower()
    doc_id = str(record.get("doc_id") or "").strip()

    if source_cat == SOURCE_CAT_PEARSON or is_institutional_card(record) or is_pearson_url(raw_url):
        return SOURCE_KIND_INSTITUTIONAL

    if (
        source_cat == SOURCE_CAT_TOC_INDEX
        or source_type in {"toc_index_only", "metadata_only", "catalog_metadata"}
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

    if doc_id.lower().endswith(".pdf") and not _is_known_hf_pdf(doc_id):
        return SOURCE_KIND_UNAVAILABLE
    if source_type in {"metadata_only", "catalog_metadata"} or record.get("reader_resolvable") is False:
        return SOURCE_KIND_METADATA_ONLY
    return SOURCE_KIND_UNAVAILABLE


def _attach_title_and_ostep(item: dict[str, Any], *, is_pearson: bool) -> None:
    """Attach clean bibliographic title and OSTEP chapter metadata."""
    doc_id = str(item.get("doc_id") or "").strip()
    raw_title = str(item.get("doc_title") or item.get("title") or "").strip()
    if is_pearson and raw_title and not raw_title.lower().endswith(".pdf") and "_" not in raw_title:
        clean_title = raw_title
    else:
        clean_title = format_canonical_title(doc_id, raw_title)
    item["doc_title"] = clean_title
    if "title" in item or not item.get("title"):
        item["title"] = clean_title
    ostep = ostep_chapter_info(doc_id)
    if ostep is not None:
        item["ostep_chapter_number"] = ostep["ostep_chapter_number"]
        item["ostep_local_file_number"] = ostep["ostep_local_file_number"]


def _attach_page_provenance(item: dict[str, Any], valid_page: int | None) -> None:
    """Attach physical PDF page vs printed page fields."""
    prov = resolve_page_provenance(str(item.get("doc_id") or "").strip(), valid_page, item.get("printed_page"))
    item.update({
        "page_number": prov["pdf_page"], "pdf_page": prov["pdf_page"], "printed_page": prov["printed_page"],
        "page_offset": prov["page_offset"], "page_display": prov["page_display"], "pages_differ": prov["pages_differ"],
    })


def _mark_non_clickable(
    item: dict[str, Any], *, source_kind: str, ev_state: str, bib_url: str = ""
) -> dict[str, Any]:
    item.update({
        "source_kind": source_kind,
        "source_kind_label": SOURCE_KIND_LABELS[source_kind],
        "url": "",
        "pdf_url": "",
        "bibliographic_url": bib_url,
        "reader_resolvable": False,
        "page_verified": False,
        "clickable": False,
        "evidence_state": ev_state,
        "evidence_state_label": EVIDENCE_STATE_LABELS[ev_state],
        "follow_up_eligible": False,
    })
    item.pop("reader_url", None)
    item.pop("open_url", None)
    _attach_page_provenance(item, None)
    return item


def sanitize_citation_record(
    record: dict[str, Any], *, open_access_only: bool | None = None
) -> dict[str, Any]:
    """Validate URL, page bounds, access rights, and attach the unified provenance contract."""
    oa_only = is_open_access_profile() if open_access_only is None else open_access_only
    item = dict(record)
    source_kind = classify_source_kind(item, open_access_only=oa_only)
    item["source_kind"] = source_kind
    item["source_kind_label"] = SOURCE_KIND_LABELS[source_kind]
    raw_url = str(item.get("url") or item.get("pdf_url") or "").strip()

    if source_kind == SOURCE_KIND_UNAVAILABLE:
        _attach_title_and_ostep(item, is_pearson=False)
        return _mark_non_clickable(item, source_kind=SOURCE_KIND_UNAVAILABLE, ev_state=EVIDENCE_STATE_UNAVAILABLE)

    if source_kind == SOURCE_KIND_METADATA_ONLY:
        _attach_title_and_ostep(item, is_pearson=False)
        bib_url = _safe_bibliographic_url(item, open_access_only=oa_only)
        return _mark_non_clickable(
            item, source_kind=SOURCE_KIND_METADATA_ONLY, ev_state=EVIDENCE_STATE_METADATA_ONLY, bib_url=bib_url
        )

    if source_kind == SOURCE_KIND_INSTITUTIONAL:
        _attach_title_and_ostep(item, is_pearson=True)
        if oa_only:
            return _mark_non_clickable(item, source_kind=SOURCE_KIND_INSTITUTIONAL, ev_state=EVIDENCE_STATE_UNAVAILABLE)
        valid_url, _page, resolvable = _validate_reader_url(raw_url, item, open_access_only=False)
        ev_state = EVIDENCE_STATE_AUTHORIZED_EXTERNAL if (valid_url and resolvable) else EVIDENCE_STATE_UNAVAILABLE
        item.update({
            "url": valid_url,
            "pdf_url": valid_url,
            "reader_resolvable": resolvable,
            "page_verified": False,
            "clickable": bool(valid_url and resolvable),
            "evidence_state": ev_state,
            "evidence_state_label": EVIDENCE_STATE_LABELS[ev_state],
            "follow_up_eligible": False,
        })
        _attach_page_provenance(item, None)
        return item

    # SOURCE_KIND_VERIFIED_FULL_TEXT
    _attach_title_and_ostep(item, is_pearson=False)
    valid_url, valid_page, resolvable = _validate_reader_url(raw_url, item, open_access_only=oa_only)
    if not resolvable or not valid_url:
        return _mark_non_clickable(item, source_kind=SOURCE_KIND_UNAVAILABLE, ev_state=EVIDENCE_STATE_UNAVAILABLE)
    item.update({"url": valid_url, "pdf_url": valid_url, "reader_resolvable": True, "page_verified": valid_page is not None, "clickable": True})
    _attach_page_provenance(item, valid_page)
    ev_state = classify_evidence_state(item, open_access_only=oa_only)
    item.update({
        "evidence_state": ev_state,
        "evidence_state_label": EVIDENCE_STATE_LABELS[ev_state],
        "follow_up_eligible": ev_state in FOLLOW_UP_ELIGIBLE_STATES,
    })
    return item


def _dedup_key(item: dict[str, Any]) -> tuple[str, ...]:
    ev_state = str(item.get("evidence_state") or "")
    doc_key = str(item.get("doc_id") or "").strip().lower().rsplit("/", 1)[-1]
    identity = doc_key or re.sub(r"[^a-z0-9]+", "", str(item.get("doc_title") or "").lower())
    if ev_state in {EVIDENCE_STATE_UNAVAILABLE, EVIDENCE_STATE_METADATA_ONLY}:
        return (ev_state, identity)
    return (ev_state, identity, str(item.get("page_number") or ""), str(item.get("canonical_passage_id") or item.get("chunk_id") or ""))


def sanitize_citations(
    citations: list[dict[str, Any]] | None, *, open_access_only: bool | None = None
) -> list[dict[str, Any]]:
    """Sanitize, deduplicate, and enforce ``open_access_only`` across all citations."""
    if not isinstance(citations, list):
        return []
    oa_only = is_open_access_profile() if open_access_only is None else open_access_only
    cleaned, seen_keys = [], set()
    for raw in citations:
        if not isinstance(raw, dict):
            continue
        item = sanitize_citation_record(raw, open_access_only=oa_only)
        if oa_only and item.get("source_kind") == SOURCE_KIND_INSTITUTIONAL:
            continue
        key = _dedup_key(item)
        if key not in seen_keys:
            seen_keys.add(key)
            cleaned.append(item)
    return cleaned


def has_verified_full_text_citations(citations: list[dict[str, Any]] | None) -> bool:
    """True only when at least one citation is a validated full-text passage."""
    return any(
        isinstance(c, dict)
        and (c.get("evidence_state") in FULL_TEXT_EVIDENCE_STATES or c.get("source_kind") == SOURCE_KIND_VERIFIED_FULL_TEXT)
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
    title = str(sanitized.get("doc_title") or sanitized.get("title") or "Source")
    if source_kind == SOURCE_KIND_INSTITUTIONAL:
        page_text = " (Pearson catalogue-only)"
    else:
        page_display = str(sanitized.get("page_display") or "").strip()
        page_text = f", {page_display}" if page_display else ""
    eid = sanitized.get("evidence_id") or re.match(r"\[(S\d+):", label)
    if isinstance(eid, re.Match):
        eid = eid.group(1)
    return f"[{eid}: {title}{page_text}]({url})" if eid else label


def link_answer_sources(text: str, citations: list[dict[str, Any]]) -> str:
    """Replace only supplied citation labels and list every distinct source without duplication."""
    body = text or ""
    lines = []
    seen: set[tuple[Any, ...]] = set()
    for record in citations:
        if not isinstance(record, dict):
            continue
        label = record.get("label")
        rendered = citation_link(record)
        if label and rendered:
            body = body.replace(str(label), rendered)
        sanitized = sanitize_citation_record(record)
        key = (_dedup_key(sanitized), rendered)
        if rendered and key not in seen:
            seen.add(key)
            lines.append(f"- {rendered}")
    if not lines or _SOURCES_HEADER_RE.search(body):
        return body
    return body + "\n\n**Sources:**\n" + "\n".join(lines)


__all__ = [
    "EVIDENCE_STATE_AUTHORIZED_EXTERNAL", "EVIDENCE_STATE_AVAILABLE_FULL_TEXT",
    "EVIDENCE_STATE_METADATA_ONLY", "EVIDENCE_STATE_RELEVANT_SUPPORTING",
    "EVIDENCE_STATE_RETRIEVED_UNASSESSED", "EVIDENCE_STATE_UNAVAILABLE",
    "MAX_PAPER_PDF_PAGE", "MAX_REASONABLE_PDF_PAGE",
    "SOURCE_KIND_INSTITUTIONAL", "SOURCE_KIND_METADATA_ONLY",
    "SOURCE_KIND_UNAVAILABLE", "SOURCE_KIND_VERIFIED_FULL_TEXT",
    "citation_link", "classify_source_kind", "has_verified_full_text_citations",
    "link_answer_sources", "sanitize_citation_record", "sanitize_citations",
]
