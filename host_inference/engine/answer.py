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
    route_logic,
    telemetry,
)
from .citation_format import citation_link, link_answer_sources
from .constants import (
    CITATION_LINE_PREFIXES,
    HERE,
)
from .contract import contract_for, graph_decision
from .graph import LibraryGraph
from .links import source_links
from .llm import fallback_config, provider_config, stream_completion
from .nodes import node_public
from .reply_evidence import expanded_concept_context
from .reply_plan import build_reply_plan
from .routing_constants import (
    ANCHOR_LIMIT as ANCHOR_LIMIT,
)
from .routing_constants import (
    BOOK_TITLE_MIN_OVERLAP as BOOK_TITLE_MIN_OVERLAP,
)
from .routing_constants import (
    BOOK_TITLE_TOKEN_MIN_LEN as BOOK_TITLE_TOKEN_MIN_LEN,
)
from .routing_constants import (
    COMPARE_CUES as COMPARE_CUES,
)
from .routing_constants import (
    COMPARE_CUES_DBMS as COMPARE_CUES_DBMS,
)
from .routing_constants import (
    MIN_QUERY_LEN as MIN_QUERY_LEN,
)
from .routing_constants import (
    NEIGHBOUR_NODE_LIMIT as NEIGHBOUR_NODE_LIMIT,
)
from .routing_constants import (
    POLISHABLE_ROUTES as POLISHABLE_ROUTES,
)
from .routing_constants import (
    RANK_TOP_K as RANK_TOP_K,
)
from .routing_constants import (
    SHORT_DEFINITION_RE as SHORT_DEFINITION_RE,
)
from .routing_constants import (
    SHORTEST_PATH_LIMIT as SHORTEST_PATH_LIMIT,
)
from .routing_constants import (
    SOURCE_LOOKUP_RE as SOURCE_LOOKUP_RE,
)
from .routing_constants import (
    WHERE_IS_RE as WHERE_IS_RE,
)


class Engine:
    """Load the exported graph and answer library questions from it."""

    def __init__(self, graph_path: Path | None = None):
        self.cache_info = hydrate()
        if graph_path:
            path = graph_path
        elif (HERE.parent / "okf_graph.json").is_file():
            path = HERE.parent / "okf_graph.json"
        elif (CACHE / "okf_graph.json").is_file():
            path = CACHE / "okf_graph.json"
        else:
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

        learning_graph_requested = bool(
            re.search(
                r"\b(quiz|diagnostic|roadmap|learning path|prerequisite|teach me|i want to learn)\b",
                query,
                re.I,
            )
        )
        if (
            extra.get("hide_graph")
            or not decision.render
            or (
                route
                in {
                    "GRAPH_SYNTHESIS",
                    "GENERAL_EXPLANATION",
                    "RELATION",
                    "CROSS_DOMAIN",
                    "MULTI_CONCEPT",
                    "RESEARCH_TOPIC",
                }
                and not learning_graph_requested
            )
        ):
            payload["anchor_concept"] = None
            payload["prerequisites"] = []
            payload["unlocks"] = []
            if extra.get("hide_graph") or not learning_graph_requested:
                payload["render_graph"] = False
                payload["render_rule"] = "no_verified_graph_for_answer"

        if extra.get("intent_category"):
            payload["intent_category"] = extra["intent_category"]
        if extra.get("multi_hop"):
            payload["multi_hop"] = extra["multi_hop"]

        if route == "MCQ_DIAGNOSTIC" and anchor_ok:
            payload["diagnostic_mcqs"] = self.diagnostic_payload(anchor).get("mcqs", [])
        else:
            payload["diagnostic_mcqs"] = []

        # Contract type 5 carries its projection alongside the reply text.
        if extra.get("projection"):
            payload.update(extra["projection"])
        shelf_record = extra.get("inventory") or {}
        if shelf_record.get("digital_available"):
            payload["digital_resources"] = [
                {
                    "title": shelf_record["title"],
                    "isbn": shelf_record.get("isbn", ""),
                    "reader_url": shelf_record.get("reader_url", ""),
                    "resource_type": "institutional_e_book",
                }
            ]

        # Pearson catalogue records describe licensed digital books. Attach
        # them only when the user asks for reading resources, never as physical
        # shelf holdings on every concept explanation.
        wants_resources = bool(
            re.search(r"\b(books?|textbooks?|reading|library|study)\b", query, re.I)
        )
        if anchor_ok and decision.render and wants_resources:
            concept = graph.nodes[anchor]
            cards = inventory_card.attach_inventory(
                payload,
                anchor,
                graph.label(anchor),
                str(concept.get("summary") or ""),
                catalogue.load_catalogue(),
            )
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

        text = link_answer_sources(text, payload["citations"])
        return {
            "route": route,
            "contract": contract,
            "text": text,
            "payload": payload,
            "anchor": anchor,
            "extra": extra,
            "intent_category": extra.get("intent_category") or route,
        }

    def stream_chat(
        self,
        query: str,
        previous_answer: str = "",
        prepared: dict | None = None,
        reply_template_id: str = "",
        reply_detail: str = "standard",
    ):
        """Stream a provider answer for grounded questions and report failures."""
        result = prepared if prepared is not None else self.answer(query)
        route = result["route"]
        grounded_text = result["text"]
        payload = result["payload"]
        plan = build_reply_plan(query, route, payload, reply_template_id)
        payload["reply_plan"] = plan
        payload["reply_template"] = plan["primary_template"]

        can_polish = route in POLISHABLE_ROUTES or (
            bool(result.get("research_overlay"))
            and (reply_detail == "expanded" or bool(reply_template_id))
        )
        config = provider_config() if can_polish else None

        if not can_polish:
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            yield grounded_text
            return

        safe_text = redact_for_model(grounded_text)
        if reply_detail != "expanded" and SHORT_DEFINITION_RE.match(query) and result["anchor"]:
            anchor_node = self.graph.nodes[result["anchor"]]
            safe_text = redact_for_model(str(anchor_node.get("summary") or grounded_text))
        if reply_detail == "expanded":
            concept_context = expanded_concept_context(payload)
            if concept_context:
                safe_text += "\n\nVerified concept context:\n" + concept_context
        link_lines = [
            line for line in grounded_text.splitlines() if line.startswith(CITATION_LINE_PREFIXES)
        ]
        if result.get("research_overlay"):
            link_lines.extend(
                line
                for line in grounded_text.splitlines()
                if line.startswith("[") and " Source: https://" in line
            )
        source_ids = [result["anchor"]] if result.get("anchor") else []
        source_ids.extend(
            node["id"] for node in payload.get("prerequisites", [])[:2] if node.get("id")
        )
        for cid in dict.fromkeys(source_ids):
            link_lines.extend(self.pearson_line(cid).splitlines())
        link_lines = list(dict.fromkeys(line for line in link_lines if line))

        selected = None
        first_token = None
        stream = None
        candidates = (config, fallback_config(config)) if config else ()
        for candidate in candidates:
            if candidate is None:
                continue
            if reply_detail == "expanded" or reply_template_id:
                attempt = iter(
                    stream_completion(
                        candidate,
                        safe_text,
                        query,
                        previous_answer,
                        plan["primary_template"]["id"],
                        reply_detail,
                        reply_plan=plan,
                    )
                )
            elif previous_answer:
                attempt = iter(stream_completion(candidate, safe_text, query, previous_answer))
            else:
                attempt = iter(stream_completion(candidate, safe_text, query))
            first = next(attempt, None)
            if first:
                selected = candidate
                first_token = first
                stream = attempt
                break

        if selected is None:
            payload["model"] = {"provider": "unavailable", "model": ""}
            payload["logs"].append(
                {"step": "AI provider", "status": "error", "details": "No live reply received"}
            )
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            yield grounded_text
            return

        payload["model"] = {"provider": selected["provider"], "model": selected["model"]}
        payload["logs"].append(
            {"step": selected["provider"], "status": "ok", "details": selected["model"]}
        )
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield first_token
        if stream is not None:
            yield from stream
        source_lines = list(
            dict.fromkeys(
                f"- {citation_link(citation)}"
                for citation in payload.get("citations", [])
                if citation_link(citation)
            )
        )
        if source_lines:
            yield "\n\n**Sources:**\n" + "\n".join(source_lines)
        if link_lines:
            yield "\n\n" + "\n".join(link_lines)

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
                    "held": False,
                    "digital_available": True,
                    "confidence": confidence,
                    "reader_url": catalogue.reader_link(record),
                },
            },
        )

    def _route(self, query: str) -> tuple[str, str, str | None, dict]:
        """Choose a grounded route and its graph payload."""
        return route_logic.route(self, query)

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
