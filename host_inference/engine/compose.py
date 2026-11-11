"""Grounded reply composition for the hosted librarian engine.

One concern: turning graph facts into the specific prose protocols
(synthesis, relation chain, comparative matrix, shelf card, auth card).
"""

from __future__ import annotations

import re

from .compose_catalog import (
    VERIFIED_BIBLIOGRAPHIC_RECORDS as VERIFIED_BIBLIOGRAPHIC_RECORDS,
)
from .compose_catalog import library_inventory_reply as library_inventory_reply
from .compose_catalog import paper_lookup_reply as paper_lookup_reply
from .constants import KILL_SWITCH, PORTALS, SCHEDULE, SHELF
from .multi_hop import VERIFIED_CONCEPT_FOUNDATIONS
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
    clean_q = re.sub(r"\s*\([Ee]arlier user topics?:.*?\)", "", query or "").strip()
    patterns = (
        r"how (?:does|do|are|is)\s+(.+?)\s+(?:connect|relate|connected|related)\s+(?:to|with)\s+(.+)",
        r"how (?:are|is|do)\s+(.+?)\s+and\s+(.+?)\s+(?:connected|related)",
        r"relation(?:ship)? between\s+(.+?)\s+and\s+(.+)",
        r"compare\s+(.+?)\s+(?:with|and|to|versus|vs\.?)\s+(.+)",
        r"difference between\s+(.+?)\s+and\s+(.+)",
        r"how (?:does|do)\s+(.+?)\s+(?:differ|contrast)\s+(?:from|with)\s+(.+)",
        r"how (?:is|are)\s+(.+?)\s+different\s+(?:from|to|than)\s+(.+)",
        r"(.+?)\s+(?:versus|vs\.?)\s+(.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, clean_q, re.I)
        if match:
            g1, g2 = match.group(1).strip(), match.group(2).strip()
            # If the second fragment has multiple coordinated items, do not treat as a simple pair
            if re.search(r"\b(and|with|versus|vs\.?)\b|,", g2, re.I):
                return None
            return g1, g2
    return None


def resolve_fragment(engine, fragment: str) -> tuple[str | None, bool]:
    """Resolve a query fragment to a known concept id (phrase hit, else cosine)."""
    hits = engine.graph.phrase_hits(fragment)
    if hits:
        return hits[0], True
    frag_norm = fragment.strip().lower()
    if frag_norm.endswith("s") and not frag_norm.endswith("ss"):
        hits_sing = engine.graph.phrase_hits(frag_norm[:-1])
        if hits_sing:
            return hits_sing[0], True
    ranked = engine.graph.rank(fragment, top_k=1)
    if ranked and ranked[0][0] >= KILL_SWITCH:
        return ranked[0][1], True
    return None, False


def synthesis(engine, cid: str) -> str:
    """Put the answer first and show only relevant verified follow-on detail."""
    graph = engine.graph
    node = graph.nodes[cid]
    foundation = VERIFIED_CONCEPT_FOUNDATIONS.get(cid)
    summary = foundation or (node.get("summary") or "Indexed catalog concept.").strip()
    cite = graph.citation(cid)
    formula = graph.formula(cid)
    query = str(getattr(graph, "_query", ""))
    lines = [f"**{graph.label(cid)}.** {summary} {cite}".strip()]
    if formula and re.search(r"\b(equation|formula|math|derive|how|explain)\b", query, re.I):
        lines.extend(["", "**How it works.**", formula])
    if re.search(r"\b(prerequisite|learning path|roadmap|before|after|connect)\b", query, re.I):
        lines.extend(["", "**Verified learning path.**", lineage(graph, cid)])
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


def matrix(
    engine, a: str, b: str, left_name: str | None = None, right_name: str | None = None
) -> str:
    """Render the comparative matrix for two concepts."""
    graph = engine.graph
    left = left_name or graph.label(a)
    right = right_name or graph.label(b)

    def cell(cid: str) -> str:
        return (graph.nodes[cid].get("summary") or graph.label(cid)).strip()[:MATRIX_CELL_CHARS]

    pair_set = {a, b}
    if {"semaphore", "condition_variable"}.issubset(pair_set):
        is_left_sem = a == "semaphore"
        data_l = (
            "Integer counter state representing available resource units; persists across calls."
            if is_left_sem
            else "Stateless wait queue of blocked threads; maintains no counter or history."
        )
        data_r = (
            "Stateless wait queue of blocked threads; maintains no counter or history."
            if is_left_sem
            else "Integer counter state representing available resource units; persists across calls."
        )
        search_l = (
            "sem_wait() decrements and blocks if <= 0; sem_post() increments and wakes one waiter."
            if is_left_sem
            else "pthread_cond_wait() atomically unlocks associated mutex and sleeps until signaled."
        )
        search_r = (
            "pthread_cond_wait() atomically unlocks associated mutex and sleeps until signaled."
            if is_left_sem
            else "sem_wait() decrements and blocks if <= 0; sem_post() increments and wakes one waiter."
        )
        io_l = (
            "Self-contained primitive; does not require an external mutex to modify count."
            if is_left_sem
            else "Strictly requires an external mutex lock and a while(!condition) re-check loop."
        )
        io_r = (
            "Strictly requires an external mutex lock and a while(!condition) re-check loop."
            if is_left_sem
            else "Self-contained primitive; does not require an external mutex to modify count."
        )
        recall_l = (
            "Guaranteed wake-up even if signal occurs before wait (memory of signal)."
            if is_left_sem
            else "Lost-wake-up if signaled when no thread is actively blocked on the condition variable."
        )
        recall_r = (
            "Lost-wake-up if signaled when no thread is actively blocked on the condition variable."
            if is_left_sem
            else "Guaranteed wake-up even if signal occurs before wait (memory of signal)."
        )
        cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
    elif {"semaphore", "mutex_lock"}.issubset(pair_set):
        is_left_sem = a == "semaphore"
        data_l = (
            r"Counting integer variable ($N \ge 0$) representing multiple resource instances."
            if is_left_sem
            else "Binary state (0 = unlocked, 1 = locked) strictly enforcing single ownership."
        )
        data_r = (
            "Binary state (0 = unlocked, 1 = locked) strictly enforcing single ownership."
            if is_left_sem
            else r"Counting integer variable ($N \ge 0$) representing multiple resource instances."
        )
        search_l = (
            "No ownership requirement: any thread can invoke sem_post() to signal."
            if is_left_sem
            else "Strict thread ownership: only the thread that called lock() may invoke unlock()."
        )
        search_r = (
            "Strict thread ownership: only the thread that called lock() may invoke unlock()."
            if is_left_sem
            else "No ownership requirement: any thread can invoke sem_post() to signal."
        )
        io_l = (
            "Signaling, thread synchronization, and producer-consumer bounded buffers."
            if is_left_sem
            else "Mutual exclusion protection for critical sections."
        )
        io_r = (
            "Mutual exclusion protection for critical sections."
            if is_left_sem
            else "Signaling, thread synchronization, and producer-consumer bounded buffers."
        )
        recall_l = (
            "Allows up to $K$ concurrent threads into the resource region."
            if is_left_sem
            else "Strictly permits exactly one thread in the critical section."
        )
        recall_r = (
            "Strictly permits exactly one thread in the critical section."
            if is_left_sem
            else "Allows up to $K$ concurrent threads into the resource region."
        )
        cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
    elif {"b_plus_tree", "hash_indexing"}.issubset(pair_set):
        is_left_tree = a == "b_plus_tree"
        data_l = (
            "Balanced multi-way search tree with linked sequential leaf pages."
            if is_left_tree
            else "Hash bucket directory with modulo mapping and collision overflow chains."
        )
        data_r = (
            "Hash bucket directory with modulo mapping and collision overflow chains."
            if is_left_tree
            else "Balanced multi-way search tree with linked sequential leaf pages."
        )
        search_l = (
            "O(log_B N) root-to-leaf descent, followed by leaf sibling pointer traversal."
            if is_left_tree
            else "O(1) expected hash computation and direct bucket lookup."
        )
        search_r = (
            "O(1) expected hash computation and direct bucket lookup."
            if is_left_tree
            else "O(log_B N) root-to-leaf descent, followed by leaf sibling pointer traversal."
        )
        io_l = (
            "Highly efficient sequential page I/O for range queries (e.g. BETWEEN, >, <)."
            if is_left_tree
            else "Random I/O per key; completely incapable of efficient range scans."
        )
        io_r = (
            "Random I/O per key; completely incapable of efficient range scans."
            if is_left_tree
            else "Highly efficient sequential page I/O for range queries (e.g. BETWEEN, >, <)."
        )
        recall_l = (
            "Guaranteed logarithmic bounds under high fanout (B >= 100)."
            if is_left_tree
            else "Degrades to O(N) linear scans under severe bucket collision or hash skew."
        )
        recall_r = (
            "Degrades to O(N) linear scans under severe bucket collision or hash skew."
            if is_left_tree
            else "Guaranteed logarithmic bounds under high fanout (B >= 100)."
        )
        cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
    elif {"breadth_first_search", "depth_first_search"}.issubset(pair_set) or {
        "bfs",
        "dfs",
    }.issubset(pair_set):
        is_left_bfs = a in ("bfs", "breadth_first_search")
        data_l = (
            "Level-by-level frontier exploration using a First-In-First-Out (FIFO) queue."
            if is_left_bfs
            else "Branch-to-leaf exploration using a Last-In-First-Out (LIFO) stack or call recursion."
        )
        data_r = (
            "Branch-to-leaf exploration using a Last-In-First-Out (LIFO) stack or call recursion."
            if is_left_bfs
            else "Level-by-level frontier exploration using a First-In-First-Out (FIFO) queue."
        )
        search_l = (
            "Systematically explores all nodes at depth d before moving to depth d+1."
            if is_left_bfs
            else "Follows a single path as deeply as possible until a dead end, then backtracks."
        )
        search_r = (
            "Follows a single path as deeply as possible until a dead end, then backtracks."
            if is_left_bfs
            else "Systematically explores all nodes at depth d before moving to depth d+1."
        )
        io_l = (
            "Guarantees finding the shortest path on unweighted graphs."
            if is_left_bfs
            else "Does not guarantee shortest path; path length depends on edge visitation order."
        )
        io_r = (
            "Does not guarantee shortest path; path length depends on edge visitation order."
            if is_left_bfs
            else "Guarantees finding the shortest path on unweighted graphs."
        )
        recall_l = (
            "Space complexity O(V) proportional to width of the graph frontier."
            if is_left_bfs
            else "Space complexity O(D) proportional to maximum depth of search tree."
        )
        recall_r = (
            "Space complexity O(D) proportional to maximum depth of search tree."
            if is_left_bfs
            else "Space complexity O(V) proportional to width of the graph frontier."
        )
        cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
    elif left_name and "B+" in left_name:
        data_l = "Ordered keys in leaf-linked pages of a B+ tree."
        data_r = "High-dimensional embedding vectors in an HNSW graph."
        search_l = "Exact descent from root to leaf, then a sequential sibling scan."
        search_r = "Greedy beam search over layered navigable small-world links."
        io_l = "Few sequential page reads once the leaf is reached."
        io_r = "Random hops through the vector index; more irregular I/O."
        recall_l = "Exact for the indexed key range."
        recall_r = "Approximate; recall depends on the beam and the graph degree."
        cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
    else:
        data_l, data_r = cell(a), cell(b)
        search_l = search_r = "Retrieved from the indexed concept summary only."
        io_l = io_r = "Textbook pages cited below."
        recall_l = recall_r = "Limited to indexed chunks; no unstated guarantee."
        cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
    lines = [
        f"**Comparative matrix: {left} × {right}**",  # noqa: RUF001
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
    return "\n".join(
        [
            f"**{graph.label(cid)}.** {card['definition']} {cite}",
            "",
            f"**Title & author.** {card['title']}, {card['author']}.",
            f"**Call number.** {card['call_number']}.",
            f"**Shelf.** {card['place']}.",
            f"**System barcode.** {card['barcode']}.",
            f"**Live availability.** {card['available']} physical copies currently on shelf (out of {card['total']} total).",
        ]
    )


def shelf_generic(engine, cid: str) -> str:
    """Render the honest 'no physical shelf card indexed' reply."""
    graph = engine.graph
    return (
        f"**{graph.label(cid)}.** {(graph.nodes[cid].get('summary') or '').strip()} {graph.citation(cid)}\n\n"
        "No separate physical shelf card is indexed for this concept. "
        "Ask at the Central Library circulation desk and search the OPAC at http://uemk-opac.l2c2.co.in."
    )


def auth_card(query: str) -> str:
    """Render sign-in links without exposing shared institutional credentials."""
    del query
    return "\n".join(
        [
            "[RENDER_AUTH_CARD]",
            "### Central Library E-Resource Access",
            "",
            "Open the institutional portal and sign in with your own campus account. "
            "This assistant does not store or reveal shared passwords.",
            "",
            "| Portal | Sign-in page |",
            "| :--- | :--- |",
            "| Pearson eLibrary | [Open Pearson](https://elibrary.in.pearson.com/) |",
            "| IEEE Xplore | [Open IEEE Xplore](https://ieeexplore.ieee.org) |",
            "| Scopus and ScienceDirect | [Open ScienceDirect](https://www.sciencedirect.com) |",
            "| SpringerLink | [Open SpringerLink](https://link.springer.com) |",
            "| National Digital Library of India | [Open NDLI](https://ndl.iitkgp.ac.in/) |",
            "| OPAC Catalogue | [Open OPAC](https://uemk-opac.l2c2.co.in) |",
        ]
    )


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
