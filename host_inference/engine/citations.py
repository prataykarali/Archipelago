"""Code-owned canonical citation IDs (S1, S2, ...) and response validation."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from .provenance import (
    ALL_EVIDENCE_STATES,
    ALL_SOURCE_KINDS,
    EVIDENCE_STATE_LABELS,
    EVIDENCE_STATE_METADATA_ONLY,
    EVIDENCE_STATE_UNAVAILABLE,
    FOLLOW_UP_ELIGIBLE_STATES,
    SOURCE_KIND_LABELS,
    classify_evidence_state,
    d14_canonical_oa_url,
    format_canonical_title,
    is_d14_approved_oa,
    is_d14_excluded_commercial,
    resolve_page_provenance,
    source_kind_for_evidence_state,
)

SYNTHESIS_MODES = frozenset(
    {
        "xkiro_synthesis",
        "nvidia_fallback",
        "verified_deterministic",
        "provider_unavailable_fallback",
    }
)
_CITATION_TAG_RE = re.compile(r"\[([SP]\d+)\]")
_SAFE_INTERNAL_PREFIXES = (
    "/read?",
    "/api/page-view?",
    "/api/library/paper-evidence/",
    "/open/",
    "/papers/",
)
_DISALLOWED_URL_RE = re.compile(r"^(?:/chat(?:[/?#]|$)|#|javascript:|data:)", re.I)


def verified_citation_url(value: object) -> str:
    """Return a validated HTTPS or safe internal citation URL, else empty string."""
    url = str(value or "").strip()
    if not url or _DISALLOWED_URL_RE.match(url):
        return ""
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if url.startswith(_SAFE_INTERNAL_PREFIXES):
        return url
    return ""


def _canonical_dedup_key(item: dict[str, Any], ev_state: str) -> tuple[str, ...]:
    doc_key = str(item.get("doc_id") or "").strip().lower().rsplit("/", 1)[-1]
    title_key = re.sub(r"[^a-z0-9]+", "", str(item.get("doc_title") or "").lower())
    identity = doc_key or title_key
    if ev_state in {EVIDENCE_STATE_UNAVAILABLE, EVIDENCE_STATE_METADATA_ONLY}:
        return (ev_state, identity)
    return (
        ev_state,
        identity,
        str(item.get("page_number") or ""),
        str(item.get("canonical_passage_id") or item.get("chunk_id") or ""),
    )


def assign_canonical_citations(citations: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Assign code-owned canonical S1, S2, ... IDs with verified URLs and evidence states."""
    if not isinstance(citations, list):
        return []
    canonical: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, ...]] = set()
    for raw in citations:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        doc_id = str(item.get("doc_id") or "").strip()
        raw_title = str(item.get("doc_title") or item.get("title") or "").strip()
        clean_title = format_canonical_title(doc_id, raw_title) if (doc_id or raw_title) else "Source"
        item["doc_title"] = clean_title
        if "title" in item or not item.get("title"):
            item["title"] = clean_title

        ev_state = str(item.get("evidence_state") or "").strip()
        if ev_state not in ALL_EVIDENCE_STATES:
            ev_state = classify_evidence_state(item)
        if is_d14_excluded_commercial(item):
            ev_state = EVIDENCE_STATE_METADATA_ONLY
        item["evidence_state"] = ev_state
        item["evidence_state_label"] = EVIDENCE_STATE_LABELS[ev_state]
        sk = str(item.get("source_kind") or "").strip()
        if sk not in ALL_SOURCE_KINDS or is_d14_excluded_commercial(item):
            sk = source_kind_for_evidence_state(ev_state, item)
        item["source_kind"] = sk
        item["source_kind_label"] = SOURCE_KIND_LABELS[sk]
        item["follow_up_eligible"] = (
            ev_state in FOLLOW_UP_ELIGIBLE_STATES
            and not item.get("withdrawn")
            and bool(item.get("reader_resolvable", True))
        )

        if ev_state in {EVIDENCE_STATE_UNAVAILABLE, EVIDENCE_STATE_METADATA_ONLY}:
            item.pop("url", None)
            item["pdf_url"] = ""
            item["clickable"] = False
            item["reader_resolvable"] = False
        else:
            safe_url = verified_citation_url(item.get("url") or item.get("pdf_url"))
            if not safe_url and is_d14_approved_oa(item):
                safe_url = verified_citation_url(d14_canonical_oa_url(item))
            if safe_url:
                item["url"] = safe_url
            else:
                item.pop("url", None)

        page = item.get("page_number")
        valid_page = page if isinstance(page, int) and not isinstance(page, bool) and page > 0 else None
        if ev_state in {EVIDENCE_STATE_UNAVAILABLE, EVIDENCE_STATE_METADATA_ONLY}:
            valid_page = None
        prov = resolve_page_provenance(doc_id, valid_page, item.get("printed_page"))
        if valid_page is not None and not prov["page_in_bounds"]:
            prov = resolve_page_provenance(doc_id, None, item.get("printed_page"))
        item["page_number"] = prov["pdf_page"]
        item["pdf_page"] = prov["pdf_page"]
        item["printed_page"] = prov["printed_page"]
        item["page_display"] = prov["page_display"]
        item["pages_differ"] = prov["pages_differ"]

        key = _canonical_dedup_key(item, ev_state)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        eid = f"S{len(canonical) + 1}"
        item["evidence_id"] = eid
        if not item.get("label"):
            page_part = f", {prov['page_display']}" if prov["page_display"] else ""
            item["label"] = f"[{eid}: {clean_title}{page_part}]"
        canonical.append(item)
    return canonical


def validate_response_citations(
    text: str,
    citations: list[dict[str, Any]] | None,
) -> tuple[str, list[str]]:
    """Validate [S#]/[P#] tags in response text against canonical citations and strip unsupported ones."""
    valid_ids = {
        str(c.get("evidence_id"))
        for c in (citations or [])
        if isinstance(c, dict) and c.get("evidence_id")
    }
    removed: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        tag = match.group(1)
        if tag in valid_ids:
            return match.group(0)
        removed.append(tag)
        return ""

    cleaned = _CITATION_TAG_RE.sub(_replace, text)
    if removed:
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).replace(" .", ".").replace(" ,", ",")
    return cleaned, removed


def infer_synthesis_mode(
    prepared: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    """Determine canonical synthesis_mode from prepared/payload metadata."""
    for source in (payload or {}, prepared or {}):
        mode = source.get("synthesis_mode")
        if isinstance(mode, str) and mode in SYNTHESIS_MODES:
            return mode
    provider = str((payload or {}).get("provider") or (prepared or {}).get("provider") or "").casefold()
    if "xkiro" in provider:
        return "xkiro_synthesis"
    if "nvidia" in provider:
        return "nvidia_fallback"
    if provider == "fallback" or (payload or {}).get("provider_unavailable"):
        return "provider_unavailable_fallback"
    return "verified_deterministic"
