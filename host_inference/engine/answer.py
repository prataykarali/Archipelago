"""The hosted inference engine: routing, streaming and payload assembly.

One concern: given a raw query, decide the route and produce a grounded reply
plus the graph payload the chat UI renders.  Reply *composition* lives in
:mod:`engine.compose`; the diagnostic/personalized-QnA flow lives in
:mod:`engine.diagnostics`.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from demo_cards import match_demo
from library_index import Catalog
from remote_cache import hydrate, load_books

from . import (
    catalogue,
    citations,
    compose,
    diagnostics,
    ingestion_view,
    inventory,
    inventory_card,
    telemetry,
)
from .constants import (
    CITATION_LINE_PREFIXES,
    CODE_MESSAGE,
    HERE,
    HIJACK_MESSAGE,
    KILL_SWITCH,
    OOD_MESSAGE,
    PASSING_MENTIONS,
    SHELF,
    UNINDEXED_CURRICULUM_MESSAGE,
)
from .contract import contract_for, graph_decision
from .conversation import ACADEMIC_QUERY, GREETING_PREFIX, conversational_reply
from .graph import LibraryGraph
from .inspector import build_trace
from .links import source_links
from .llm import grounded_completion, provider_config
from .nodes import node_public
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
from .privacy import inference_context
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


class Engine:
    """Load the exported graph and answer library questions from it."""

    def __init__(self, graph_path: Path | None = None):
        self.cache_info = hydrate()
        path = graph_path or (HERE / "cache" / "okf_graph.json")
        if not path.is_file():
            path = HERE.parent / "okf_graph.json"
        self.graph = LibraryGraph(path)
        self.books = load_books()
        self.catalog = Catalog(self.graph.nodes, self.books)

    def best_book(self, cid: str) -> dict | None:
        """Match a Pearson copy only when the retrieved document title is that book."""
        record = self.graph.cite_record(cid, getattr(self.graph, "_query", ""))
        stem = re.sub(r"\.pdf$", "", (record.get("doc_id") or "").split("/")[-1].lower())
        stem = stem.replace("_", " ").replace("-", " ")
        tokens = set(re.findall(rf"[a-z]{{{BOOK_TITLE_TOKEN_MIN_LEN},}}", stem))
        if not tokens:
            return None
        best = None
        best_score = 0
        for book in self.books:
            title = (book.get("title") or "").lower()
            score = sum(1 for tok in tokens if tok in title)
            if score > best_score:
                best, best_score = book, score
        return best if best_score >= BOOK_TITLE_MIN_OVERLAP else None

    def pearson_line(self, cid: str, page: int = 1) -> str:
        """Exact-source link lines (Hugging Face, then Pearson) for ``cid``."""
        book = self.best_book(cid)
        record = self.graph.cite_record(cid, getattr(self.graph, "_query", ""))
        return source_links(record, book, page)

    def answer(self, query: str) -> dict:
        """Route ``query`` and return grounded text plus the graph payload."""
        query = (query or "").strip()
        self.graph._query = query
        route, text, anchor, extra = self._route(query)
        graph = self.graph
        anchor_ok = bool(anchor and anchor in graph.nodes)
        pres = [node_public(graph.nodes[c]) for c in (graph.prereqs(anchor, 2)[:NEIGHBOUR_NODE_LIMIT] if anchor else [])]
        unl = [node_public(graph.nodes[c]) for c in (graph.unlocks(anchor, 2)[:NEIGHBOUR_NODE_LIMIT] if anchor else [])]
        rel = [node_public(graph.nodes[c]) for c in (graph.related(anchor) if anchor else [])]
        payload = {
            "anchor_concept": node_public(graph.nodes[anchor]) if anchor_ok else None,
            "prerequisites": pres if anchor_ok else [],
            "unlocks": unl if anchor_ok else [],
            "related_concepts": rel if anchor_ok else [],
            "citations": extra.get("citations") or (
                [extra["citation"]] if extra.get("citation") else (
                    [graph.cite_record(anchor, query)] if anchor_ok else []
                )
            ),
            "routing": {"route": route, "score": extra.get("score", 1.0), "reason": extra.get("reason", route)},
        }
        if anchor_ok:
            payload["citations"] = citations.citation_bundle(graph, anchor, payload["citations"])

        # The graph-render protocol is decided from the contract, not from which
        # branch of the router ran, so it cannot vary with query phrasing.
        contract = contract_for(route)
        decision = graph_decision(route)
        payload["contract"] = contract
        payload["render_graph"] = decision.render
        payload["render_rule"] = decision.rule
        payload["logs"] = [{"step": "Hosted inference", "status": "ok", "details": route}]

        if extra.get("hide_graph") or not decision.render:
            payload["render_graph"] = False
            payload["related_concepts"] = []
            payload["anchor_concept"] = None
            payload["prerequisites"] = []
            payload["unlocks"] = []

        # Contract type 5 carries its projection alongside the reply text.
        if extra.get("projection"):
            payload.update(extra["projection"])

        # Contract: a grounded concept answer closes with the physical holdings.
        # Skipped for administrative and location-only answers, which must not
        # carry a concept card (see the graph-render protocol).
        if anchor_ok and decision.render:
            concept = graph.nodes[anchor]
            cards = inventory_card.attach_inventory(
                payload,
                anchor,
                graph.label(anchor),
                str(concept.get("summary") or ""),
                catalogue.load_catalogue(),
            )
            # Append section 4 of the master template to the reply text itself,
            # so the holdings survive as prose for any client that renders plain
            # text. The card is never allowed to displace the explanation.
            if cards:
                text = text + "\n" + inventory_card.render_inventory_section(cards)

        # A citation whose only supporting document was withdrawn upstream must
        # say so in the reply, not just omit its link. The UI reads
        # ``withdrawn_notice`` and renders it in place of the answer, so a
        # student is told the title left the record rather than being shown an
        # unciteable source list.
        notices = [
            citation.get("notice")
            for citation in payload["citations"]
            if isinstance(citation, dict) and citation.get("withdrawn")
        ]
        if notices:
            payload["withdrawn_notice"] = notices[0]
            payload["text_override"] = notices[0]

        payload["inspector"] = build_trace(graph, payload, route, contract, extra)
        return {"route": route, "contract": contract, "text": text, "payload": payload, "anchor": anchor, "extra": extra}

    def stream_chat(self, query: str):
        """Yield metadata first, then a validated grounded reply with provider failover."""
        result = self.answer(query)
        route = result["route"]
        grounded_text = result["text"]
        payload = result["payload"]

        can_polish = route in POLISHABLE_ROUTES
        safe_text = inference_context(self.graph, payload)
        config = provider_config() if can_polish and safe_text else None
        # The graph and source links render as soon as this metadata arrives.
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        polished, _used = grounded_completion(config, safe_text) if config else ("", None)
        answer_text = polished or grounded_text
        link_lines = citations.source_link_lines(payload.get("citations") or [])
        link_lines.extend(
            line for line in grounded_text.splitlines() if line.startswith(CITATION_LINE_PREFIXES)
        )
        missing_links = [line for line in dict.fromkeys(link_lines) if line not in answer_text]
        yield answer_text
        if missing_links:
            yield "\n\n### Source pages\n" + "\n".join(missing_links)

    def _route_shelf_query(self, query: str, best_score: float) -> tuple[str, str, str | None, dict]:
        """Answer a physical-location question from the institutional catalogue.

        Contract type 2 (``CATALOG_SHELF_ROUTING``). Returns a
        ``CATALOG_SHELF_ROUTING`` route with the shelf card, or an honest
        "not indexed" reply — never a fabricated location.
        """
        requested = inventory.extract_title(query)
        records = catalogue.load_catalogue()
        record, score = inventory.best_record(records, requested)
        confidence = inventory.match_confidence(score)

        if record is None or confidence == "none":
            # No holding. Record the demand so the acquisition desk can see it.
            telemetry.log_demand(requested)
            text = inventory.no_record_reply(requested)
            return (
                "CATALOG_SHELF_ROUTING",
                text,
                None,
                {
                    "hide_graph": True,
                    "reason": "shelf_not_indexed",
                    "score": best_score,
                    "inventory": {"title": requested, "held": False},
                },
            )

        text = inventory.shelf_card(
            record,
            requested=requested,
            confidence=confidence,
        )
        return (
            "CATALOG_SHELF_ROUTING",
            text,
            None,
            {
                "hide_graph": True,
                "reason": "catalogue_match",
                "score": best_score,
                "inventory": {
                    "title": record.get("title", ""),
                    "isbn": record.get("isbn", ""),
                    "available": record.get("available_copies", 0),
                    "total": record.get("total_copies", 0),
                    "held": True,
                    "confidence": confidence,
                    "reader_url": catalogue.reader_link(record),
                },
            },
        )

    def _route(self, query: str) -> tuple[str, str, str | None, dict]:
        graph = self.graph
        if not query or len(query) < MIN_QUERY_LEN:
            return "EMPTY", "Ask a library question of at least two characters.", None, {"hide_graph": True, "reason": "empty"}
        small_talk = conversational_reply(query)
        if small_talk:
            return "CONVERSATION", small_talk, None, {"hide_graph": True, "reason": "conversation"}
        query = GREETING_PREFIX.sub("", query)
        if INJECTION.search(query):
            return "PERSONA_LOCK", HIJACK_MESSAGE, None, {"hide_graph": True, "reason": "injection"}
        if CODE_TRAP.search(query):
            return "CODE_TRAP", CODE_MESSAGE, None, {"hide_graph": True, "reason": "procedural"}

        # Contract type 3 is tested before the canned demo cards. A combined
        # hours-plus-access sentence ("how do I access IEEE off-campus, and what
        # are library Sunday hours?") matched a demo card on the word "access"
        # and was answered with a fixed paragraph about the Pearson bookshelf —
        # losing both the schedule and the access instructions.
        wants_hours = bool(SCHEDULE_RE.search(query))
        wants_access = bool(AUTH_RE.search(query)) and not SHELF_RE.search(query)
        if wants_hours or wants_access:
            route = "SCHEDULE" if wants_hours and not wants_access else "AUTH_GATEWAY"
            return route, compose.admin_card(query, wants_hours, wants_access), None, {
                "hide_graph": True,
                "reason": "schedule_sheet" if wants_hours else "auth_gateway",
            }

        # Contract type 5: the uploaded-paper flow. Must precede the concept
        # path, since "extract the OKF nodes from my uploaded paper" has no
        # curriculum similarity and was deflected as out-of-domain.
        if INGEST_RE.search(query) and not SHELF_RE.search(query):
            text, projection = ingestion_view.ingestion_reply(query, graph)
            return "INGESTION_ANALYSIS", text, None, {
                "reason": "uploaded_okf_projection",
                "projection": projection,
                "hide_graph": False,
            }

        if SHELF_RE.search(query):
            return self._route_shelf_query(query, 1.0)

        demo = match_demo(query, self.books)
        if demo and not DIAG_RE.search(query):
            # Keep the curated explanation but attach its indexed concept so
            # the normal graph appears without a second "tell me" request.
            demo_anchor = next(iter(graph.phrase_hits(query)), None)
            return "DEMO", demo["text"], demo_anchor, {
                "hide_graph": not bool(demo_anchor),
                "reason": "demo_prompt",
                "citations": demo["citations"],
                "score": 1.0,
            }
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
        if catalog_hit and not SHELF_RE.search(query) and not learning_request and not relational_request:
            return "BOOK_PAGE", catalog_hit["text"], None, {
                "hide_graph": True,
                "reason": "catalog_book",
                "citation": catalog_hit["citation"],
                "score": 0.9,
            }

        ranked = graph.rank(query, top_k=RANK_TOP_K)
        if not ranked:
            return "ACADEMIC_UNINDEXED", "No concepts are indexed yet. Ask a librarian to ingest this material.", None, {
                "hide_graph": True, "reason": "empty_corpus",
            }
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

        if SHELF_RE.search(query):
            shelf_id = anchors[0] if anchors else ("third_normal_form" if "3nf" in query.lower() else None)
            if shelf_id and shelf_id in SHELF:
                return "CATALOG_SHELF", compose.shelf(self, shelf_id), shelf_id, {"score": best_score, "reason": "shelf"}
            if shelf_id:
                return "CATALOG_SHELF", compose.shelf_generic(self, shelf_id), shelf_id, {"score": best_score, "reason": "shelf_generic"}
            # No concept anchor: the question is about a *book*, not a concept.
            # Consult the institutional catalogue before giving up, otherwise
            # every "where is a physical copy of X" hit the OOD kill switch even
            # with the title catalogued.
            return self._route_shelf_query(query, best_score)

        domains = compose.domain_pair(self, query)
        if domains and any(token in query.lower() for token in ("compare", "versus", "vs", "difference", "with")):
            (left_id, left_name), (right_id, right_name) = domains
            return "CROSS_DOMAIN", compose.matrix(self, left_id, right_id, left_name, right_name), left_id, {"score": max(best_score, 0.8), "reason": "cross_domain"}

        pair = compose.split_pair(query)
        if pair:
            left_text, right_text = pair
            left_id, left_ok = compose.resolve_fragment(self, left_text)
            right_id, right_ok = compose.resolve_fragment(self, right_text)
            if left_ok and right_ok and left_id != right_id:
                path = graph.shortest(left_id, right_id, limit=SHORTEST_PATH_LIMIT)
                if path is None:
                    return "DISCONNECTED", compose.disconnected(self, left_id, right_id), left_id, {"score": best_score, "reason": "no_path"}
                if any(token in query.lower() for token in COMPARE_CUES):
                    return "CROSS_DOMAIN", compose.matrix(self, left_id, right_id), left_id, {"score": best_score, "reason": "cross_domain"}
                return "RELATION", compose.relation(self, left_id, right_id, path), left_id, {"score": best_score, "reason": "shortest_path"}
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
                return "CATALOG_DEPTH", text, None, {"hide_graph": True, "score": best_score, "reason": "missing_parameter"}
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
                return "CATALOG_DEPTH", text, target, {"score": best_score, "reason": "missing_parameter"}

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
            if ACADEMIC_QUERY.search(query):
                return "ACADEMIC_UNINDEXED", (
                    "I couldn't ground that question in the currently indexed academic sources. "
                    "Try the concept name, or ask a librarian to add a relevant source."
                ), None, {"hide_graph": True, "score": best_score, "reason": "academic_not_indexed"}
            return "GUARDRAIL_INTERCEPT", OOD_MESSAGE, None, {
                "hide_graph": True,
                "score": best_score,
                "reason": "cosine_below_0.75",
            }

        if DIAG_RE.search(query) and anchors:
            target = anchors[0]
            return "MCQ_DIAGNOSTIC", diagnostics.diagnostic_intro(self, target), target, {"score": best_score, "reason": "diagnostic"}

        if RELATE_RE.search(query) and len(anchors) >= 2:
            a, b = anchors[0], anchors[1]
            path = graph.shortest(a, b, limit=SHORTEST_PATH_LIMIT)
            if path is None:
                return "DISCONNECTED", compose.disconnected(self, a, b), a, {"score": best_score, "reason": "no_path", "hide_graph": False}
            if any(token in query.lower() for token in COMPARE_CUES_DBMS):
                return "CROSS_DOMAIN", compose.matrix(self, a, b), a, {"score": best_score, "reason": "cross_domain"}
            return "RELATION", compose.relation(self, a, b, path), a, {"score": best_score, "reason": "shortest_path"}

        if len(anchors) >= 2 and any(token in query.lower() for token in ("compare", "versus", "vs", "difference", "and")):
            return "CROSS_DOMAIN", compose.matrix(self, anchors[0], anchors[1]), anchors[0], {"score": best_score, "reason": "multi_anchor"}

        target = anchors[0] if anchors else best_id
        return "GRAPH_SYNTHESIS", compose.synthesis(self, target), target, {"score": max(best_score, 0.93 if hits else best_score), "reason": "graph_synthesis"}

    # ── diagnostics / personalized-QnA (implemented in engine.diagnostics) ──

    def mcq_for(self, concept_id: str, slot: int = 0) -> dict:
        """Build one diagnostic MCQ for ``concept_id`` at prerequisite slot ``slot``."""
        return diagnostics.mcq_for(self, concept_id, slot)

    def diagnostic_payload(self, concept_id: str) -> dict:
        """Full diagnostic checkpoint payload for the personalized-QnA flow."""
        return diagnostics.diagnostic_payload(self, concept_id)

    def adaptive_step(self, body: dict) -> dict:
        """Advance one adaptive-quiz step and return the personalized graph."""
        return diagnostics.adaptive_step(self, body)
