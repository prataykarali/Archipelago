"""Clean generated citation markers against supplied evidence records."""

from __future__ import annotations

import re
from typing import Any

from archipelago.inference.citations.part03_render import render_citation_from_payload

_MARKER = re.compile(r"\[(S\d+)(?:\s*:[^\]]*)?\](?:\([^)]*\))?")


def render_clean_citation_output(body: str, payloads: list[dict[str, Any]]) -> str:
    """Link valid inline markers and add one deduplicated Sources listing."""
    by_id = {str(p.get("evidence_id")): p for p in payloads if p.get("evidence_id")}
    text = re.split(r"\n\s*(?:Source Citations:|\*\*Sources:\*\*)", body, maxsplit=1)[0]
    counts: dict[str, int] = {}

    def replace(match: re.Match[str]) -> str:
        eid = match.group(1)
        if eid not in by_id:
            return ""
        counts[eid] = counts.get(eid, 0) + 1
        return render_citation_from_payload(by_id[eid]) if counts[eid] <= 2 else ""

    text = _MARKER.sub(replace, text).rstrip()
    lines = []
    seen = set()
    for payload in payloads:
        key = (
            payload.get("doc_id"),
            payload.get("page_number"),
            payload.get("doi"),
            payload.get("url"),
        )
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {render_citation_from_payload(payload)}")
    return text + ("\n\n**Sources:**\n" + "\n".join(lines) if lines else "")


def format_citation_block(payloads: list[dict[str, Any]]) -> str:
    """Format cited evidence as clickable Markdown lines."""
    return "\n".join(f"- {render_citation_from_payload(p)}" for p in payloads)


def format_inline_citation(payload: dict[str, Any]) -> str:
    """Render one supplied citation beside its claim."""
    return render_citation_from_payload(payload)
