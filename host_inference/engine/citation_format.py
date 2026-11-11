"""Render hosted citations from resolver records, without guessing pages."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def _safe_link(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if url.startswith(("/read?", "/api/page-view?", "/open/", "/papers/")):
        return url
    return ""


def citation_link(record: dict) -> str:
    """Make an inline link to a source already resolved by the graph."""
    label = str(record.get("label") or "").strip()
    if not label:
        return ""
    url = _safe_link(record.get("url") or record.get("pdf_url"))
    if record.get("withdrawn") or not url:
        return label
    title = str(record.get("doc_title") or record.get("title") or record.get("doc_id") or "Source")
    page = record.get("page_number")
    page_text = f", PDF p.{page}" if isinstance(page, int) and page > 0 else ""
    eid = record.get("evidence_id") or re.match(r"\[(S\d+):", label)
    if isinstance(eid, re.Match):
        eid = eid.group(1)
    return f"[{eid}: {title}{page_text}]({url})" if eid else label


def link_answer_sources(text: str, citations: list[dict]) -> str:
    """Replace only supplied citation labels and list every distinct source."""
    body = text
    lines = []
    seen = set()
    for record in citations:
        label = record.get("label")
        rendered = citation_link(record)
        if label and rendered:
            body = body.replace(str(label), rendered)
        key = (record.get("doc_id"), record.get("page_number"), record.get("url"))
        if rendered and key not in seen:
            seen.add(key)
            lines.append(f"- {rendered}")
    return body + ("\n\n**Sources:**\n" + "\n".join(lines) if lines else "")
