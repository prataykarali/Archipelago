"""Markdown rendering helpers shared by the grounded reply builders."""
from __future__ import annotations

from .graph import LibraryGraph

# How many upstream / downstream neighbours a one-line lineage shows.
LINEAGE_NEIGHBOURS = 2
# How many neighbours the multi-line neighborhood block lists.
NEIGHBOURHOOD_LIMIT = 4


def arrow(left: str, rel: str, right: str) -> str:
    """Render a labelled dependency arrow in TeX."""
    return f"{left} $\\xrightarrow{{{rel}}}$ {right}"


def lineage(graph: LibraryGraph, cid: str) -> str:
    """One-line ``prereq → node → unlock`` sequence, degrading gracefully."""
    pres = graph.prereqs(cid, 1)[:LINEAGE_NEIGHBOURS]
    unl = graph.unlocks(cid, 1)[:LINEAGE_NEIGHBOURS]
    label = graph.label(cid)
    if pres and unl:
        return arrow(graph.label(pres[0]), "REQUIRES", label) + " " + arrow(label, "UNLOCKS", graph.label(unl[0]))
    if pres:
        return arrow(graph.label(pres[0]), "REQUIRES", label)
    if unl:
        return arrow(label, "UNLOCKS", graph.label(unl[0]))
    return f"{label} (indexed catalog node; no REQUIRES or UNLOCKS edge is stored)"


def neighborhood_block(graph: LibraryGraph, cid: str) -> str:
    """One markdown bullet summarising a node's direct neighborhood."""
    pres = ", ".join(graph.label(x) for x in graph.prereqs(cid, 1)[:NEIGHBOURHOOD_LIMIT]) or "none indexed"
    unl = ", ".join(graph.label(x) for x in graph.unlocks(cid, 1)[:NEIGHBOURHOOD_LIMIT]) or "none indexed"
    return f"- **{graph.label(cid)}** prerequisites: {pres}. Unlocks: {unl}."


# Privately used names kept for the original call sites in engine.py.
_arrow = arrow
_lineage = lineage
_neighborhood_block = neighborhood_block
