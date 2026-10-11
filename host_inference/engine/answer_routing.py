"""The hosted inference engine: routing, streaming and payload assembly.

One concern: given a raw query, decide the route and produce a grounded reply
plus the graph payload the chat UI renders.  Reply *composition* lives in
:mod:`engine.compose`; the diagnostic/personalized-QnA flow lives in
:mod:`engine.diagnostics`.
"""

from __future__ import annotations

import re

from demo_cards import match_demo

from . import (
    catalogue,
    compose,
    diagnostics,
    ingestion_view,
    inventory,
)
from .constants import (
    CODE_MESSAGE,
    HIJACK_MESSAGE,
    KILL_SWITCH,
    OOD_MESSAGE,
    PASSING_MENTIONS,
    SHELF,
    UNINDEXED_CURRICULUM_MESSAGE,
)
from .patterns import (
    AUTH_RE,
    CODE_TRAP,
    DIAG_RE,
    INGEST_RE,
    INJECTION,
    PARAM_RE,
    RELATE_RE,
    SCHEDULE_RE,
    SHELF_RE,
)
from .render import neighborhood_block

# Routing thresholds and caps.
MIN_QUERY_LEN = 2
RANK_TOP_K = 6
ANCHOR_LIMIT = 3
NEIGHBOUR_NODE_LIMIT = 6
SHORTEST_PATH_LIMIT = 6
# Book-title token match: at least this many distinctive tokens must overlap.
BOOK_TITLE_MIN_OVERLAP = 2
BOOK_TITLE_TOKEN_MIN_LEN = 5
# Grounded routes whose draft is worth sending to the LLM for phrasing.
POLISHABLE_ROUTES = frozenset({"GRAPH_SYNTHESIS", "RELATION", "CROSS_DOMAIN", "BOOK_PAGE", "DEMO"})
# Comparison cue words that flip a relation reply into a comparative matrix.
COMPARE_CUES = ("compare", "versus", "vs", "difference")
COMPARE_CUES_DBMS = ("compare", "versus", "vs", "difference", "dbms", "b+")
SOURCE_LOOKUP_RE = re.compile(
    r"\b(?:open|download|page|pages|chapter|book|textbook|paper|pdf|"
    r"dataset|pearson|hugging\s*face|source|citation)\b",
    re.I,
)
WHERE_IS_RE = re.compile(r"^where\s+(?:is|are)\s+", re.I)


class RoutingMixin:
    """Select the grounded response route for a query."""

    def _route(self, query: str) -> tuple[str, str, str | None, dict]:
        graph = self.graph
        if not query or len(query) < MIN_QUERY_LEN:
            return (
                "EMPTY",
                "Ask a library question of at least two characters.",
                None,
                {"hide_graph": True, "reason": "empty"},
            )
        if INJECTION.search(query):
            return "PERSONA_LOCK", HIJACK_MESSAGE, None, {"hide_graph": True, "reason": "injection"}
        if CODE_TRAP.search(query):
            return "CODE_TRAP", CODE_MESSAGE, None, {"hide_graph": True, "reason": "procedural"}

        # ── Conversational greetings ──────────────────────────────────────
        _GREETING_RE = re.compile(
            r"^(h(i|ey|ello|owdy)|good\s*(morning|afternoon|evening|day)|"
            r"yo\b|sup\b|what'?s?\s*up|who are you|help|what can you do|"
            r"thanks?|thank\s*you|bye|goodbye|see ya)[\s?!.]*$",
            re.I,
        )
        if _GREETING_RE.match(query):
            text = (
                "Hello! I'm **Archipelago**, your AI librarian and academic tutor. "
                "I can explain concepts from the indexed CS/AI/ML corpus, show "
                "prerequisite graphs, find textbook pages, check library hours, "
                "look up e-resource credentials, and build personalized learning "
                "roadmaps.\n\n"
                "Try asking about **LoRA**, **RAG**, **BERT**, **Attention**, "
                "**3NF**, or any indexed topic!"
            )
            return "GREETING", text, None, {"hide_graph": True, "reason": "greeting"}

        # Contract type 3: schedule + access portals.
        wants_hours = bool(SCHEDULE_RE.search(query))
        wants_access = bool(AUTH_RE.search(query)) and not SHELF_RE.search(query)
        if wants_hours or wants_access:
            route = "SCHEDULE" if wants_hours and not wants_access else "AUTH_GATEWAY"
            return (
                route,
                compose.admin_card(query, wants_hours, wants_access),
                None,
                {
                    "hide_graph": True,
                    "reason": "schedule_sheet" if wants_hours else "auth_gateway",
                },
            )

        # Contract type 5: uploaded-paper flow.
        if INGEST_RE.search(query) and not SHELF_RE.search(query):
            text, projection = ingestion_view.ingestion_reply(query, graph)
            return (
                "INGESTION_ANALYSIS",
                text,
                None,
                {
                    "reason": "uploaded_okf_projection",
                    "projection": projection,
                    "hide_graph": False,
                },
            )

        demo = match_demo(query, self.books)
        if demo and not DIAG_RE.search(query):
            # Resolve anchor so the in-chat graph card renders for demo replies.
            hits = graph.phrase_hits(query)
            demo_anchor = hits[0] if hits else None
            if not demo_anchor:
                ranked = graph.rank(query, top_k=1)
                if ranked and ranked[0][0] >= 0.5:
                    demo_anchor = ranked[0][1]
            return (
                "DEMO",
                demo["text"],
                demo_anchor,
                {
                    "reason": "demo_prompt",
                    "citations": demo["citations"],
                    "score": 1.0,
                },
            )
        if any(term in query.lower() for term in PASSING_MENTIONS):
            entity = next(term.strip() for term in PASSING_MENTIONS if term in query.lower())
            text = (
                f"The library texts mention {entity} in passing as a dataset benchmark or infrastructure instance, "
                "but do not contain the theoretical documentation required to explain it. "
                "I cannot use external knowledge to fill in the gaps."
            )
            return "PASSING_MENTION", text, None, {"hide_graph": True, "reason": "passing_mention"}

        catalog_hit = self.catalog.reply(query)
        # A learning request ("I want to learn X", "Teach me Y") is a
        # curriculum intent, not a book lookup. The catalog matcher fires on
        # the title words alone, so it used to swallow every curriculum prompt
        # before the diagnostic check could see it. Curriculum wins.
        # A relational prompt ("how does Softmax connect to Self-Attention?")
        # is the same story: the matcher saw "Attention" in a catalogue title
        # and answered with a book page instead of a traversal path.
        learning_request = bool(DIAG_RE.search(query))
        relational_request = bool(RELATE_RE.search(query))
        if (
            catalog_hit
            and SOURCE_LOOKUP_RE.search(query)
            and not SHELF_RE.search(query)
            and not learning_request
            and not relational_request
        ):
            return (
                "BOOK_PAGE",
                catalog_hit["text"],
                None,
                {
                    "hide_graph": True,
                    "reason": "catalog_book",
                    "citation": catalog_hit["citation"],
                    "score": 0.9,
                },
            )

        ranked = graph.rank(query, top_k=RANK_TOP_K)
        best_score, best_id = ranked[0]
        hits = graph.phrase_hits(query)
        anchors = []
        for cid in hits:
            if cid not in anchors:
                anchors.append(cid)
        for score, cid in ranked:
            if score >= KILL_SWITCH and cid not in anchors:
                anchors.append(cid)
            if len(anchors) >= ANCHOR_LIMIT:
                break

        if WHERE_IS_RE.search(query):
            requested_title = inventory.extract_title(query)
            _record, title_score = inventory.best_record(
                catalogue.load_catalogue(), requested_title
            )
            if inventory.match_confidence(title_score) != "none":
                return self._route_shelf_query(query, best_score)

        if SHELF_RE.search(query):
            shelf_id = (
                anchors[0] if anchors else ("third_normal_form" if "3nf" in query.lower() else None)
            )
            if shelf_id and shelf_id in SHELF:
                return (
                    "CATALOG_SHELF",
                    compose.shelf(self, shelf_id),
                    shelf_id,
                    {"score": best_score, "reason": "shelf"},
                )
            if shelf_id:
                return (
                    "CATALOG_SHELF",
                    compose.shelf_generic(self, shelf_id),
                    shelf_id,
                    {"score": best_score, "reason": "shelf_generic"},
                )
            # No concept anchor: the question is about a *book*, not a concept.
            # Consult the institutional catalogue before giving up, otherwise
            # every "where is a physical copy of X" hit the OOD kill switch even
            # with the title catalogued.
            return self._route_shelf_query(query, best_score)

        domains = compose.domain_pair(self, query)
        if domains and any(
            token in query.lower() for token in ("compare", "versus", "vs", "difference", "with")
        ):
            (left_id, left_name), (right_id, right_name) = domains
            return (
                "CROSS_DOMAIN",
                compose.matrix(self, left_id, right_id, left_name, right_name),
                left_id,
                {"score": max(best_score, 0.8), "reason": "cross_domain"},
            )

        pair = compose.split_pair(query)
        if pair:
            left_text, right_text = pair
            left_id, left_ok = compose.resolve_fragment(self, left_text)
            right_id, right_ok = compose.resolve_fragment(self, right_text)
            if left_ok and right_ok and left_id != right_id:
                path = graph.shortest(left_id, right_id, limit=SHORTEST_PATH_LIMIT)
                if path is None:
                    return (
                        "DISCONNECTED",
                        compose.disconnected(self, left_id, right_id),
                        left_id,
                        {"score": best_score, "reason": "no_path"},
                    )
                if any(token in query.lower() for token in COMPARE_CUES):
                    return (
                        "CROSS_DOMAIN",
                        compose.matrix(self, left_id, right_id),
                        left_id,
                        {"score": best_score, "reason": "cross_domain"},
                    )
                return (
                    "RELATION",
                    compose.relation(self, left_id, right_id, path),
                    left_id,
                    {"score": best_score, "reason": "shortest_path"},
                )
            if left_ok ^ right_ok:
                known = left_id if left_ok else right_id
                missing = right_text if left_ok else left_text
                text = (
                    f"**{graph.label(known)}** is an indexed catalog node. "
                    f"**{missing.strip(' ?.')}** is not. "
                    "No pedagogical prerequisite connects them, and I will not invent a bridge.\n\n"
                    f"{neighborhood_block(graph, known)}"
                )
                return "DISCONNECTED", text, known, {"score": best_score, "reason": "one_sided"}

        if PARAM_RE.search(query):
            target = anchors[0] if anchors and anchors[0] in graph.nodes else None
            if target is None:
                text = (
                    "The active catalog does not contain a concept node for that implementation parameter. "
                    "I will not invent a memory formula or version-specific constant. "
                    "Ask for a concept that is indexed, such as LoRA, BERT, or third normal form."
                )
                return (
                    "CATALOG_DEPTH",
                    text,
                    None,
                    {"hide_graph": True, "score": best_score, "reason": "missing_parameter"},
                )
            summary = (graph.nodes.get(target) or {}).get("summary") or ""
            if not re.search(r"\d", summary):
                parent = graph.prereqs(target, 1)
                parent_name = graph.label(parent[0]) if parent else graph.label(target)
                text = (
                    f"**{graph.label(target)}** is an indexed catalog node. "
                    "The active catalog chunks do not contain the specific implementation parameter you asked for. "
                    "I will not guess a number that is not in the retrieved text. "
                    f"The closest indexed prerequisite is **{parent_name}**."
                )
                return (
                    "CATALOG_DEPTH",
                    text,
                    target,
                    {"score": best_score, "reason": "missing_parameter"},
                )

        if best_score < KILL_SWITCH and not hits:
            # Distinguish "we have not indexed this syllabus topic" from "you are
            # off-topic". Both are below the similarity threshold, but only the
            # second deserves a scope deflection.
            if DIAG_RE.search(query):
                subject = inventory.extract_title(query) or "That topic"
                return (
                    "CURRICULUM_UNINDEXED",
                    UNINDEXED_CURRICULUM_MESSAGE.format(subject=subject),
                    None,
                    {"hide_graph": True, "score": best_score, "reason": "curriculum_not_indexed"},
                )
            return (
                "GUARDRAIL_INTERCEPT",
                OOD_MESSAGE,
                None,
                {
                    "hide_graph": True,
                    "score": best_score,
                    "reason": "cosine_below_0.75",
                },
            )

        if DIAG_RE.search(query) and anchors:
            target = anchors[0]
            return (
                "MCQ_DIAGNOSTIC",
                diagnostics.diagnostic_intro(self, target),
                target,
                {"score": best_score, "reason": "diagnostic"},
            )

        if RELATE_RE.search(query) and len(anchors) >= 2:
            a, b = anchors[0], anchors[1]
            path = graph.shortest(a, b, limit=SHORTEST_PATH_LIMIT)
            if path is None:
                return (
                    "DISCONNECTED",
                    compose.disconnected(self, a, b),
                    a,
                    {"score": best_score, "reason": "no_path", "hide_graph": False},
                )
            if any(token in query.lower() for token in COMPARE_CUES_DBMS):
                return (
                    "CROSS_DOMAIN",
                    compose.matrix(self, a, b),
                    a,
                    {"score": best_score, "reason": "cross_domain"},
                )
            return (
                "RELATION",
                compose.relation(self, a, b, path),
                a,
                {"score": best_score, "reason": "shortest_path"},
            )

        if len(anchors) >= 2 and any(
            token in query.lower() for token in ("compare", "versus", "vs", "difference", "and")
        ):
            return (
                "CROSS_DOMAIN",
                compose.matrix(self, anchors[0], anchors[1]),
                anchors[0],
                {"score": best_score, "reason": "multi_anchor"},
            )

        target = anchors[0] if anchors else best_id
        return (
            "GRAPH_SYNTHESIS",
            compose.synthesis(self, target),
            target,
            {"score": max(best_score, 0.93 if hits else best_score), "reason": "graph_synthesis"},
        )

    # ── diagnostics / personalized-QnA (implemented in engine.diagnostics) ──
