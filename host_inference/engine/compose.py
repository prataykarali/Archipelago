"""Grounded reply composition for the hosted librarian engine.

One concern: turning graph facts into the specific prose protocols
(synthesis, relation chain, comparative matrix, shelf card, auth card).
"""
from __future__ import annotations

import re

from .constants import KILL_SWITCH, PORTALS, SCHEDULE, SHELF
from .render import arrow, lineage, neighborhood_block

# Comparative matrix cells are trimmed to keep the table readable.
MATRIX_CELL_CHARS = 180


def domain_pair(engine, query: str):
    """Recognised B+ tree / vector-RAG comparison pair, or ``None``."""
    q = query.lower()
    left = right = None
    if re.search(r"\bb\+\s*tree\b|\bb-tree\b|\bdbms\b|\brelational\b", q):
        left = ("third_normal_form", "Relational B+ tree / DBMS")
    if re.search(r"\bhnsw\b|\bvector search\b|\brag\b", q):
        right = ("rag", "HNSW / vector RAG")
    graph = engine.graph
    if left and right and left[0] in graph.nodes and right[0] in graph.nodes:
        return left, right
    return None


def split_pair(query: str):
    """Split an ``X and Y`` relationship query into its two fragments."""
    patterns = (
        r"how (?:are|is) (.+?) and (.+?) connected",
        r"how (?:are|is) (.+?) (?:related|connected) to (.+)",
        r"relation(?:ship)? between (.+?) and (.+)",
        r"compare (.+?) (?:with|and|to|versus|vs\.?) (.+)",
        r"difference between (.+?) and (.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, query, re.I)
        if match:
            return match.group(1), match.group(2)
    return None


def resolve_fragment(engine, fragment: str) -> tuple[str | None, bool]:
    """Resolve a query fragment to a known concept id (phrase hit, else cosine)."""
    hits = engine.graph.phrase_hits(fragment)
    if hits:
        return hits[0], True
    ranked = engine.graph.rank(fragment, top_k=1)
    if ranked and ranked[0][0] >= KILL_SWITCH:
        return ranked[0][1], True
    return None, False


def synthesis(engine, cid: str) -> str:
    """The contract's master template, sections 1-3.

    Ordered so the answer is usable before the scaffolding is read: the direct
    definition first, then the ``REQUIRES ➔ UNLOCKS`` path, then the grounded
    detail and its page provenance.  Section 4 (physical inventory) is appended
    by :mod:`engine.inventory_card` once the catalogue has been consulted, so a
    concept with no holdings never gets an empty card.
    """
    graph = engine.graph
    node = graph.nodes[cid]
    summary = (node.get("summary") or "Indexed catalog concept.").strip()
    cite = graph.citation(cid)
    formula = graph.formula(cid)
    lines = [
        "### 1. Concept Definition",
        "",
        f"**{graph.label(cid)}.** {summary} {cite}",
        "",
        "### 2. Topological Graph Path",
        "",
        f"`REQUIRES ➔ UNLOCKS` {lineage(graph, cid)}",
    ]
    if formula:
        lines.extend(["", f"**LaTeX derivation.** {formula}"])
    lines.extend([
        "",
        "### 3. Grounded Synthesis & Page Provenance",
        "",
    ])
    if formula:
        lines.append(f"The derivation above is the indexed form for {graph.label(cid)}.")
    else:
        lines.append(f"Grounded in the catalog summary above. {cite}")
    link = engine.pearson_line(cid)
    if link:
        lines.extend(["", link])
    return "\n".join(lines)


def relation(engine, a: str, b: str, path: list[tuple[str, str]]) -> str:
    """Render the dependency chain connecting two concepts."""
    graph = engine.graph
    rendered = []
    cursor = a
    for kind, nxt in path:
        rel = "UNLOCKS" if "UNLOCKS" in kind else "REQUIRES"
        rendered.append(arrow(graph.label(cursor), rel, graph.label(nxt)))
        cursor = nxt
    hops = len(path)
    kind = "a direct dependency" if hops == 1 else f"a {hops}-hop structural bridge"
    lines = [
        f"**{graph.label(a)}** and **{graph.label(b)}** share {kind} in the catalog graph.",
        "",
        "**Traversal chain.** " + " ".join(rendered),
        "",
        f"**Document evidence.** {graph.citation(a, 1)} {graph.citation(b, 2)}",
    ]
    return "\n".join(lines)


def matrix(engine, a: str, b: str, left_name: str | None = None, right_name: str | None = None) -> str:
    """Render the comparative matrix for two concepts."""
    graph = engine.graph
    left = left_name or graph.label(a)
    right = right_name or graph.label(b)

    def cell(cid: str) -> str:
        return (graph.nodes[cid].get("summary") or graph.label(cid)).strip()[:MATRIX_CELL_CHARS]

    if left_name and "B+" in left_name:
        data_l = "Ordered keys in leaf-linked pages of a B+ tree."
        data_r = "High-dimensional embedding vectors in an HNSW graph."
        search_l = "Exact descent from root to leaf, then a sequential sibling scan."
        search_r = "Greedy beam search over layered navigable small-world links."
        io_l = "Few sequential page reads once the leaf is reached."
        io_r = "Random hops through the vector index; more irregular I/O."
        recall_l = "Exact for the indexed key range."
        recall_r = "Approximate; recall depends on the beam and the graph degree."
        cites = "[S1: Silberschatz_Database_Systems.pdf, #page=1] [S2: Lewis2020_RAG.pdf, #page=1]"
    else:
        data_l, data_r = cell(a), cell(b)
        search_l = search_r = "Retrieved from the indexed concept summary only."
        io_l = io_r = "Textbook pages cited below."
        recall_l = recall_r = "Limited to indexed chunks; no unstated guarantee."
        cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
    lines = [
        f"**Comparative matrix: {left} × {right}**",
        "",
        "| Axis | " + left + " | " + right + " |",
        "| --- | --- | --- |",
        f"| Data representation | {data_l} | {data_r} |",
        f"| Search mechanics | {search_l} | {search_r} |",
        f"| Disk I/O | {io_l} | {io_r} |",
        f"| Recall | {recall_l} | {recall_r} |",
        "",
        cites,
    ]
    return "\n".join(lines)


def disconnected(engine, a: str, b: str) -> str:
    """Render the honest 'no indexed dependency connects these' reply."""
    graph = engine.graph
    return (
        f"**{graph.label(a)}** and **{graph.label(b)}** are both indexed catalog nodes. "
        "No pedagogical prerequisite or structural dependency connects them within this corpus.\n\n"
        "Independent neighborhoods:\n"
        f"{neighborhood_block(graph, a)}\n"
        f"{neighborhood_block(graph, b)}"
    )


def shelf(engine, cid: str) -> str:
    """Render the indexed physical shelf card for ``cid``."""
    graph = engine.graph
    card = SHELF[cid]
    cite = graph.citation(cid)
    return "\n".join([
        f"**{graph.label(cid)}.** {card['definition']} {cite}",
        "",
        f"**Title & author.** {card['title']}, {card['author']}.",
        f"**Call number.** {card['call_number']}.",
        f"**Shelf.** {card['place']}.",
        f"**System barcode.** {card['barcode']}.",
        f"**Live availability.** {card['available']} physical copies currently on shelf (out of {card['total']} total).",
    ])


def shelf_generic(engine, cid: str) -> str:
    """Render the honest 'no physical shelf card indexed' reply."""
    graph = engine.graph
    return (
        f"**{graph.label(cid)}.** {(graph.nodes[cid].get('summary') or '').strip()} {graph.citation(cid)}\n\n"
        "No separate physical shelf card is indexed for this concept. "
        "Ask at the Central Library circulation desk and search the OPAC at http://uemk-opac.l2c2.co.in."
    )


def auth_card(query: str) -> str:
    """Render the institutional-access portal card."""
    lines = [
        "[RENDER_AUTH_CARD]",
        "**Institutional access.** Sign in with your own campus account. This assistant does not store or reveal passwords.",
        "",
    ]
    lines.extend(_portal_lines(query))
    lines.append(
        "If a title is paywalled outside these portals, borrow a reciprocal membership card "
        "(British Council Library or American Library) from the Central Library front desk."
    )
    return "\n".join(lines)


def admin_card(query: str, wants_hours: bool, wants_access: bool) -> str:
    """Contract type 3: the schedule and the access portals in one card.

    Students ask both halves in a single sentence ("how do I access IEEE
    off-campus, and what are library Sunday hours?").  Routing that to *either*
    the schedule sheet or the portal list silently drops half the question, and
    dropping the schedule half loses the one fact the student cannot look up.
    So: render whichever halves were actually asked for, and never a graph.
    """
    q = query.lower()
    if wants_hours and wants_access:
        lines = [
            "[RENDER_AUTH_CARD]",
            "**Institutional access.** Sign in with your own campus account. This assistant does not store or reveal passwords.",
            "",
            "**Central Library schedule**",
            "",
            *SCHEDULE,
            "",
            *[_portal_row(line) for line in _portal_lines(q)],
            "",
            "If a title is paywalled outside these portals, borrow a reciprocal membership card "
            "(British Council Library or American Library) from the Central Library front desk.",
        ]
        return "\n".join(lines)
    if wants_hours:
        lines = ["**Central Library schedule**", "", *SCHEDULE, ""]
        lines.append("Source: Central Library Academic Schedule.")
        return "\n".join(lines)
    return auth_card(query)


def _portal_rows(query: str) -> list[str]:
    """Portal bullet lines for the databases named in ``query``."""
    return [_portal_row(line) for line in _portal_lines(query)]


def _portal_row(line: str) -> str:
    """Prefix a portal description with the bullet the chat UI expects."""
    return line if line.startswith("- ") else f"- {line}"


def _portal_lines(query: str) -> list[str]:
    """The portal descriptions matching ``query``, defaulting to the core four."""
    q = query.lower()
    chosen = [row for row in PORTALS if row[0].split()[0].lower() in q or row[0].lower() in q]
    if not chosen:
        chosen = PORTALS[:4]
    return [f"**{name}.** {url} — {how}." for name, url, how in chosen]

