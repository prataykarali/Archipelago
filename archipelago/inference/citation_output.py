from __future__ import annotations

import os
from typing import Any


def render_clean_citation_output(body: str, payloads: list[dict[str, Any]]) -> str:
    """Format body text with plain text citation links and a summary block."""
    import re

    # Remove markdown link syntax [S1](...) -> [S1]
    body_clean = re.sub(r"\[(S\d+)\]\([^)]+\)", r"[\1]", body)

    # Strip any /api/page-view, doc_id=, chunk_
    body_clean = re.sub(r"/api/page-view\S*", "", body_clean)
    body_clean = re.sub(r"doc_id=\S*", "", body_clean)
    body_clean = re.sub(r"chunk_\S*", "", body_clean)

    # Limit repeat count of [S#] to 2 in the body
    for p in payloads:
        eid = p.get("evidence_id")
        if not eid:
            continue
        pattern = re.compile(rf"\[{eid}\]")
        matches = list(pattern.finditer(body_clean))
        if len(matches) > 2:
            new_body = ""
            last_idx = 0
            count = 0
            for m in matches:
                start, end = m.span()
                new_body += body_clean[last_idx:start]
                if count < 2:
                    new_body += f"[{eid}]"
                    count += 1
                last_idx = end
            new_body += body_clean[last_idx:]
            body_clean = new_body

    # Append the "Source Citations:" section
    cite_lines = ["\n\nSource Citations:"]
    for p in payloads:
        eid = p.get("evidence_id", "S1")
        doc_id = p.get("doc_id", "")
        doc_name = os.path.basename(doc_id)
        page = p.get("page_number")
        if page is None:
            page = 1
        cite_lines.append(f"[{eid}] {doc_name}, Page {page}")

    return body_clean + "\n".join(cite_lines)


def format_citation_block(payloads: list[dict[str, Any]]) -> str:
    """Format a list of citation payloads into a Markdown reference block."""
    if not payloads:
        return ""
    lines = []
    for i, p in enumerate(payloads, start=1):
        topic = p.get("topic", "Source")
        doc_id = p.get("doc_id", "")
        page = p.get("page_number", 1)
        lines.append(f"[S{i}] **{topic}** — {doc_id}, p.{page}")
    return "\n".join(lines)


def format_inline_citation(payload: dict[str, Any]) -> str:
    """Format a single citation payload as an inline citation marker."""
    eid = payload.get("evidence_id", "S1")
    topic = payload.get("topic", "")
    return f"[{eid}: {topic}]"
