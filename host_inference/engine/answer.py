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

from demo_cards import redact_for_model
from library_index import Catalog
from remote_cache import CACHE, hydrate, load_books

from . import (
    catalogue,
    diagnostics,
    inventory,
    inventory_card,
    telemetry,
)
from .answer_routing import RoutingMixin
from .constants import (
    CITATION_LINE_PREFIXES,
    HERE,
)
from .contract import contract_for, graph_decision
from .graph import LibraryGraph
from .links import source_links
from .llm import provider_config, stream_completion
from .nodes import node_public

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


class Engine(RoutingMixin):
    """Load the exported graph and answer library questions from it."""

    def __init__(self, graph_path: Path | None = None):
        self.cache_info = hydrate()
        path = graph_path or (CACHE / "okf_graph.json")
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
        pres = [
            node_public(graph.nodes[c])
            for c in (graph.prereqs(anchor, 2)[:NEIGHBOUR_NODE_LIMIT] if anchor else [])
        ]
        unl = [
            node_public(graph.nodes[c])
            for c in (graph.unlocks(anchor, 2)[:NEIGHBOUR_NODE_LIMIT] if anchor else [])
        ]
        rel = [node_public(graph.nodes[c]) for c in (graph.related(anchor) if anchor else [])]
        payload = {
            "anchor_concept": node_public(graph.nodes[anchor]) if anchor_ok else None,
            "prerequisites": pres if anchor_ok else [],
            "unlocks": unl if anchor_ok else [],
            "related_concepts": rel if anchor_ok else [],
            "citations": extra.get("citations")
            or (
                [extra["citation"]]
                if extra.get("citation")
                else ([graph.cite_record(anchor, query)] if anchor_ok else [])
            ),
            "routing": {
                "route": route,
                "score": extra.get("score", 1.0),
                "reason": extra.get("reason", route),
            },
        }

        # The graph-render protocol is decided from the contract, not from which
        # branch of the router ran, so it cannot vary with query phrasing.
        contract = contract_for(route)
        decision = graph_decision(route)
        payload["contract"] = contract
        payload["render_graph"] = decision.render
        payload["render_rule"] = decision.rule
        payload["logs"] = [{"step": "Hosted inference", "status": "ok", "details": route}]

        if extra.get("hide_graph") or not decision.render:
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

        return {
            "route": route,
            "contract": contract,
            "text": text,
            "payload": payload,
            "anchor": anchor,
            "extra": extra,
        }

    def stream_chat(self, query: str):
        """Yield the metadata frame immediately, then stream tokens from XKIRO.

        Falls back to the grounded draft when no provider is configured or the
        stream produced no tokens.
        """
        result = self.answer(query)
        route = result["route"]
        grounded_text = result["text"]
        payload = result["payload"]

        can_polish = route in POLISHABLE_ROUTES
        config = provider_config() if can_polish else None
        if config:
            payload["model"] = {"provider": config["provider"], "model": config["model"]}
            payload["logs"].append(
                {"step": config["provider"], "status": "ok", "details": config["model"]}
            )

        # Yield metadata frame immediately (< 10ms) to satisfy client watchdog and populate evidence/graph
        yield json.dumps(payload) + "\n[STREAM_START]\n"

        if not config:
            yield grounded_text
            return

        safe_text = redact_for_model(grounded_text)
        link_lines = [
            line for line in grounded_text.splitlines() if line.startswith(CITATION_LINE_PREFIXES)
        ]

        streamed_tokens = 0
        for delta in stream_completion(config, safe_text):
            streamed_tokens += 1
            yield delta

        if streamed_tokens > 0:
            if link_lines:
                yield "\n\n" + "\n".join(link_lines)
        else:
            # Fallback to grounded text if stream connection failed or produced 0 tokens
            yield grounded_text

    def _route_shelf_query(
        self, query: str, best_score: float
    ) -> tuple[str, str, str | None, dict]:
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

    def mcq_for(self, concept_id: str, slot: int = 0) -> dict:
        """Build one diagnostic MCQ for ``concept_id`` at prerequisite slot ``slot``."""
        return diagnostics.mcq_for(self, concept_id, slot)

    def diagnostic_payload(self, concept_id: str) -> dict:
        """Full diagnostic checkpoint payload for the personalized-QnA flow."""
        return diagnostics.diagnostic_payload(self, concept_id)

    def adaptive_step(self, body: dict) -> dict:
        """Advance one adaptive-quiz step and return the personalized graph."""
        return diagnostics.adaptive_step(self, body)
