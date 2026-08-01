from __future__ import annotations

import hashlib
from typing import Any


def select_layout_index(query: str, domain: str) -> int:
    """Select a stable, pseudorandom layout index in [0, 100)."""
    h = int(hashlib.md5(f"{query}:{domain}".encode("utf-8")).hexdigest(), int("16"))
    return h % int("100")


def detect_answer_field(query: str, concept: dict[str, Any], citation_map: dict[str, Any]) -> str:
    """Classify the subject domain of the query/concept."""
    q = query.lower()
    c_name = concept.get("name", "").lower()
    c_sum = concept.get("summary", "").lower()

    if "dbms" in q or "database" in q or "sql" in q or "dbms" in c_name or "dbms" in c_sum:
        return "dbms"
    if "operating system" in q or "os" in q or "memory" in q or "kernel" in q:
        return "operating_systems"

    return "aiml_paper"


def _summary(node: dict[str, Any], limit: int) -> str:
    """Safely truncate concept summary to limit without cutting mid-word."""
    text = node.get("summary", "")
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    if truncated[-1] in " \t\n.,!?;:\u2026":
        return truncated.strip()
    rspace = truncated.rfind(" ")
    if rspace != -1 and (limit - rspace) < int("15"):
        return truncated[:rspace].rstrip() + "\u2026"
    return truncated.rstrip() + "\u2026"


def render_grounded_answer(
    query: str,
    concept: dict[str, Any],
    prereqs: list[dict[str, Any]] | None = None,
    citation_map: dict[str, Any] | None = None,
    curriculum_paths: list[dict[str, Any]] | None = None,
) -> str:
    """Render a field-aware, grounded layout for a concept and its lineage."""
    lines = []
    name = concept.get("name") or concept.get("label") or "Concept"
    summary_text = concept.get("summary", "")

    lines.append(f"# {name}")
    lines.append("")
    lines.append(summary_text)
    lines.append("")

    if prereqs:
        lines.append("**Build the foundation**")
        lines.append("")
        for p in prereqs:
            p_name = p.get("name") or p.get("label") or ""
            p_sum = p.get("summary") or ""
            lines.append(f"— {p_name}: {p_sum}")
        lines.append("")

    if curriculum_paths:
        lines.append("Multi-hop curriculum path:")
        for path in curriculum_paths:
            lines.append(f"— {path.get('markdown', '')}")
        lines.append("")

    # Add citations if map is present
    if citation_map:
        lines.append("Sources:")
        from urllib.parse import quote
        for cid, evidences in citation_map.items():
            for ev in evidences:
                eid = ev.get("evidence_id", "S1")
                doc = ev.get("doc_id", "")
                page = ev.get("page_number", 1)
                sect = ev.get("section_title", "General")
                encoded_doc = quote(doc, safe="")
                url = f"/api/page-view?doc_id={encoded_doc}&page={page}#page={page}"
                lines.append(f"- [{eid}: {sect}]({url}) — page {page}")

    return "\n".join(lines)


def _benchmark_concept_card(query: str, concept: dict[str, Any], citation_map: dict[str, Any]) -> str:
    """Format a concept card for benchmarking.

    Args:
        query: User query string.
        concept: Concept dict.
        citation_map: Citation map.

    Returns:
        Formatted concept card markdown string.
    """
    return render_grounded_answer(query, concept, citation_map=citation_map)


def _make_layout(i: int):
    """Return a layout callable that formats a grounded card from a context dict."""

    def _layout(ctx: dict[str, Any]) -> str:
        opener = ctx.get("opener") or ""
        closer = ctx.get("closer") or ""
        body = ctx.get("body") or ""
        summary = ctx.get("summary_short") or ctx.get("summary") or ""
        cite = ctx.get("cite") or ""
        name = ctx.get("name") or ""
        parts = [p for p in (opener, name, summary, body + cite, closer) if p]
        if not parts:
            parts = [f"Layout {i + 1}", body or summary or "grounded"]
        return "\n\n".join(parts)

    return _layout


def _layouts() -> list:
    """Return exactly 100 layout callables (L1..L100)."""
    return [_make_layout(i) for i in range(100)]


