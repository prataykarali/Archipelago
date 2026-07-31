from __future__ import annotations

from typing import Any
from urllib.parse import quote


def format_lineage_string(doc_id: str, chunk_id: str, page_number: int) -> str:
    """Format a standard lineage string."""
    return f"[doc_id: {doc_id} → {chunk_id} → page {page_number}]"


def build_lineage_metadata(
    doc_id: str,
    chunk_id: str,
    page_number: int,
    text_fragment: str,
    topic: str | None = None,
    highlight: str | None = None,
    evidence_id: str | None = None,
) -> dict[str, Any]:
    """Build metadata dict for frontend PDF viewer linking (/api/page-view)."""
    page = int(page_number) if page_number else 1
    if page < 1:
        page = 1
    hl = (highlight or text_fragment or topic or "")[:200]
    encoded = quote(doc_id or "", safe="")
    hl_q = quote(hl, safe="")
    url = f"/api/page-view?doc_id={encoded}&page={page}&highlight={hl_q}#page={page}"
    lineage = format_lineage_string(doc_id, chunk_id, page)
    title = (doc_id or "Source").rsplit("/", 1)[-1]
    return {
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "page_number": page,
        "highlight": hl,
        "url": url,
        "page_url": url,
        "title": title,
        "lineage": lineage,
        "evidence_id": evidence_id,
        "topic": topic,
    }


def okf_tooltip_fields(concept: dict[str, Any]) -> dict[str, Any]:
    """Extract and format tooltip fields for Pyvis visualization."""
    label = concept.get("label") or concept.get("name") or ""
    c_type = concept.get("concept_type") or ""
    diff = concept.get("difficulty") or ""
    sum_text = concept.get("summary") or ""

    prereqs = []
    for p in concept.get("prerequisites") or []:
        if isinstance(p, dict):
            prereqs.append(p.get("name") or p.get("id") or "")
        else:
            prereqs.append(str(p))

    unlocks = []
    for u in concept.get("unlocks") or []:
        if isinstance(u, dict):
            unlocks.append(u.get("name") or u.get("id") or "")
        else:
            unlocks.append(str(u))

    related = []
    for r in concept.get("related_to") or []:
        if isinstance(r, dict):
            related.append(r.get("name") or r.get("id") or "")
        else:
            related.append(str(r))

    tags = [str(t) for t in concept.get("tags") or []]

    return {
        "concept_name": label,
        "concept_type": c_type,
        "difficulty": diff,
        "summary": sum_text,
        "prerequisites": prereqs,
        "unlocks": unlocks,
        "related_to": related,
        "tags": tags,
    }
