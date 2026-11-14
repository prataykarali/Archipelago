"""Code-owned canonical citation IDs (S1, S2, ...) and response validation."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

SYNTHESIS_MODES = frozenset(
    {
        "xkiro_synthesis",
        "nvidia_fallback",
        "verified_deterministic",
        "provider_unavailable_fallback",
    }
)
_CITATION_TAG_RE = re.compile(r"\[([SP]\d+)\]")
_SAFE_INTERNAL_PREFIXES = ("/read?", "/api/page-view?", "/api/library/paper-evidence/", "/open/", "/papers/")


def verified_citation_url(value: object) -> str:
    """Return a validated HTTPS or safe internal citation URL, else empty string."""
    url = str(value or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if url.startswith(_SAFE_INTERNAL_PREFIXES):
        return url
    return ""


def assign_canonical_citations(citations: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Assign code-owned canonical S1, S2, ... IDs with verified URLs and page numbers."""
    if not isinstance(citations, list):
        return []
    canonical: list[dict[str, Any]] = []
    for index, raw in enumerate(citations, start=1):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        eid = f"S{index}"
        item["evidence_id"] = eid
        safe_url = verified_citation_url(item.get("url") or item.get("pdf_url"))
        if safe_url:
            item["url"] = safe_url
        else:
            item.pop("url", None)
        page = item.get("page_number")
        item["page_number"] = page if isinstance(page, int) and not isinstance(page, bool) and page > 0 else None
        if not item.get("label"):
            title = str(item.get("doc_title") or item.get("title") or item.get("doc_id") or "Source")
            page_part = f", p.{item['page_number']}" if item["page_number"] else ""
            item["label"] = f"[{eid}: {title}{page_part}]"
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
