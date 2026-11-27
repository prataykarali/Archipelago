"""Markdown rendering helpers shared by the grounded reply builders."""

from __future__ import annotations

import re

from .graph import LibraryGraph

# How many upstream / downstream neighbours a one-line lineage shows.
LINEAGE_NEIGHBOURS = 2
# How many neighbours the multi-line neighborhood block lists.
NEIGHBOURHOOD_LIMIT = 4

_MALFORMED_HEADING_SPACE_RE = re.compile(r"(?m)^(#{1,6})([^\s#])")
_MALFORMED_HEADING_BOLD_RE = re.compile(r"(?m)^(#{1,6})\s+\*\*(.+?)\*\*\s*$")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_BPLUS_QUERY_RE = re.compile(r"\bb\+\s*[-\s]?trees?\b", re.I)
_B_TREE_STRIPPED_RE = re.compile(r"\bB\s+([Tt]rees?)\b")
_INSTITUTIONAL_SECTION_RE = re.compile(
    r"(?:\n*---\n*)?###\s+Institutional e-books\b[\s\S]*?(?=\n\*\*Sources:\*\*|\n###\s+|\Z)",
    re.I,
)
_SOURCES_SECTION_RE = re.compile(
    r"\n*\*\*Sources:\*\*\n(?:- [^\n]+\n?)+",
    re.I,
)


def arrow(left: str, rel: str, right: str) -> str:
    """Render a labelled dependency arrow in TeX."""
    return f"{left} $\\xrightarrow{{{rel}}}$ {right}"


def lineage(graph: LibraryGraph, cid: str) -> str:
    """One-line ``prereq --UNLOCKS--> node --UNLOCKS--> unlock`` sequence."""
    pres = graph.prereqs(cid, 1)[:LINEAGE_NEIGHBOURS]
    unl = graph.unlocks(cid, 1)[:LINEAGE_NEIGHBOURS]
    label = graph.label(cid)
    if pres and unl:
        return (
            arrow(graph.label(pres[0]), "UNLOCKS", label)
            + " "
            + arrow(label, "UNLOCKS", graph.label(unl[0]))
        )
    if pres:
        return arrow(label, "REQUIRES", graph.label(pres[0]))
    if unl:
        return arrow(label, "UNLOCKS", graph.label(unl[0]))
    return f"{label} (indexed catalog node; no REQUIRES or UNLOCKS edge is stored)"


def neighborhood_block(graph: LibraryGraph, cid: str) -> str:
    """One markdown bullet summarising a node's direct neighborhood."""
    pres = (
        ", ".join(graph.label(x) for x in graph.prereqs(cid, 1)[:NEIGHBOURHOOD_LIMIT])
        or "none indexed"
    )
    unl = (
        ", ".join(graph.label(x) for x in graph.unlocks(cid, 1)[:NEIGHBOURHOOD_LIMIT])
        or "none indexed"
    )
    return f"- **{graph.label(cid)}** prerequisites: {pres}. Unlocks: {unl}."


def normalize_markdown_headings(text: str) -> str:
    """Repair malformed markdown headings and collapse excessive blank lines."""
    if not text:
        return ""
    cleaned = _MALFORMED_HEADING_SPACE_RE.sub(r"\1 \2", text)
    cleaned = _MALFORMED_HEADING_BOLD_RE.sub(r"\1 \2", cleaned)
    cleaned = _MULTI_BLANK_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def preserve_special_terms(text: str, query: str = "") -> str:
    """Preserve special characters in technical terms like ``B+ Tree``."""
    if not text:
        return ""
    if query and _BPLUS_QUERY_RE.search(query):
        text = _B_TREE_STRIPPED_RE.sub(r"B+ \1", text)
    return text


def deduplicate_sections(text: str) -> str:
    """Ensure institutional catalogue and ``**Sources:**`` sections appear at most once."""
    if not text:
        return ""
    seen_inst = False

    def _keep_first_inst(match: re.Match[str]) -> str:
        nonlocal seen_inst
        if seen_inst:
            return ""
        seen_inst = True
        return match.group(0)

    seen_src = False

    def _keep_first_src(match: re.Match[str]) -> str:
        nonlocal seen_src
        if seen_src:
            return ""
        seen_src = True
        return match.group(0)

    cleaned = _INSTITUTIONAL_SECTION_RE.sub(_keep_first_inst, text)
    cleaned = _SOURCES_SECTION_RE.sub(_keep_first_src, cleaned)
    return _MULTI_BLANK_RE.sub("\n\n", cleaned).strip()


def clean_reply_markdown(text: str, query: str = "") -> str:
    """Apply heading normalization, special-term preservation, and section deduplication."""
    return deduplicate_sections(preserve_special_terms(normalize_markdown_headings(text), query))


# Privately used names kept for the original call sites in engine.py.
_arrow = arrow
_lineage = lineage
_neighborhood_block = neighborhood_block
