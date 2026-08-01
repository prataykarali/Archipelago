from __future__ import annotations

from typing import Any


def render_citation_from_payload(payload: dict[str, Any]) -> str:
    """Render a single citation payload into a Markdown inline link.

    Args:
        payload: Citation payload containing doc_id, page_number, topic, evidence_id.

    Returns:
        Formatted Markdown citation string.
    """
    from urllib.parse import quote
    from archipelago.inference.synthesis import prettify_doc_title

    eid = payload.get("evidence_id", "S1")
    topic = payload.get("topic", "Source")
    doc_id = payload.get("doc_id", "")
    page = payload.get("page_number", 1)

    encoded_doc = quote(doc_id, safe="")
    encoded_topic = quote(topic, safe="")
    url = f"/api/page-view?doc_id={encoded_doc}&page={page}&highlight={encoded_topic}#page={page}"

    doc_name = prettify_doc_title(doc_id)
    return f"[{eid}: {topic} | {doc_name}, PDF page {page}]({url})"
