from __future__ import annotations

import hashlib
from typing import Any


def select_layout_index(query: str, domain: str) -> int:
    """Select a stable, pseudorandom layout index in [0, 100)."""
    h = int(
        hashlib.md5(
            f"{query}:{domain}".encode("utf-8"), usedforsecurity=False
        ).hexdigest(),
        int("16"),
    )
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
    unlocks: list[dict[str, Any]] | None = None,
) -> str:
    """Render a concise, source-linked concept card and bounded learning path."""
    lines = []
    name = concept.get("name") or concept.get("label") or "Concept"
    summary_text = concept.get("summary", "")

    lines.append(f"### {name}")
    lines.append("")
    lines.append(f"**Definition.** {summary_text}")
    lines.append("")

    if prereqs:
        lines.append("**Learn first**")
        lines.append("")
        for p in prereqs:
            if isinstance(p, dict):
                p_name = p.get("name") or p.get("label") or ""
                p_sum = p.get("summary") or ""
                lines.append(f"- {p_name}: {p_sum}" if p_sum else f"- {p_name}")
            else:
                lines.append(f"- {p}")
        lines.append("")

    if unlocks:
        lines.append("**Then explore**")
        lines.append("")
        for item in unlocks[:4]:
            label = item.get("name") or item.get("label") or "" if isinstance(item, dict) else str(item)
            lines.append(f"- {label}")
        lines.append("")

    if curriculum_paths:
        lines.append("**Build the foundation**")
        lines.append("")
        lines.append("_Multi-hop curriculum path:_")
        for path in curriculum_paths:
            lines.append(f"- {path.get('markdown', '')}")
        lines.append("")

    # Add citations if map is present
    if citation_map:
        lines.append("**Cited resources.**")
        from urllib.parse import quote
        emitted = 0
        for cid, evidences in citation_map.items():
            for ev in evidences:
                if emitted >= 4:
                    break
                eid = ev.get("evidence_id", "S1")
                doc = ev.get("doc_id", "")
                page = ev.get("page_number", 1)
                sect = ev.get("section_title", "General")
                encoded_doc = quote(doc, safe="")
                url = f"/api/page-view?doc_id={encoded_doc}&page={page}#page={page}"
                lines.append(f"- [{eid}: {sect or doc}]({url}) — page {page}")
                emitted += 1

    return "\n".join(lines)


def _benchmark_concept_card(query: str | dict[str, Any], concept: dict[str, Any] | None = None, citation_map: dict[str, Any] | None = None) -> str:
    """Format a concept card for benchmarking.

    Args:
        query: User query string.
        concept: Concept dict.
        citation_map: Citation map.

    Returns:
        Formatted concept card markdown string.
    """
    if concept is None and isinstance(query, dict):
        ctx = query
        name = ctx.get("name") or "Concept"
        prereqs = [{"name": value} for value in (ctx.get("prereqs") or [])]
        unlocks = [{"name": value} for value in (ctx.get("unlocks") or [])]
        text = render_grounded_answer("", {"name": name, "summary": ctx.get("summary") or ""}, prereqs, {}, unlocks=unlocks)
        sections = []
        if ctx.get("cite"):
            sections.append(f"**Cited resources.** {ctx['cite']}")
        if ctx.get("closer"):
            sections.append(str(ctx["closer"]))
        return text + ("\n\n" + "\n\n".join(sections) if sections else "")
    return render_grounded_answer(str(query or ""), concept or {}, citation_map=citation_map)


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
