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

from demo_cards import match_demo, redact_for_model
from library_index import Catalog
from remote_cache import hydrate, load_books

from . import compose, diagnostics
from .constants import (
    CITATION_LINE_PREFIXES,
    CODE_MESSAGE,
    HERE,
    HIJACK_MESSAGE,
    KILL_SWITCH,
    OOD_MESSAGE,
    PASSING_MENTIONS,
    SCHEDULE,
    SHELF,
)
from .graph import LibraryGraph
from .links import source_links
from .llm import provider_config, stream_completion
from .nodes import node_public
from .patterns import (
    AUTH_RE,
    CODE_TRAP,
    DIAG_RE,
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
        tokens = {tok for tok in re.findall(rf"[a-z]{{{BOOK_TITLE_TOKEN_MIN_LEN},}}", stem)}
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
            "logs": [{"step": "Hosted inference", "status": "ok", "details": route}],
        }
        if extra.get("hide_graph"):
            payload["anchor_concept"] = None
            payload["prerequisites"] = []
            payload["unlocks"] = []

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

        return {"route": route, "text": text, "payload": payload, "anchor": anchor, "extra": extra}

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
            payload["logs"].append({"step": config["provider"], "status": "ok", "details": config["model"]})

        # Yield metadata frame immediately (< 10ms) to satisfy client watchdog and populate evidence/graph
        yield json.dumps(payload) + "\n[STREAM_START]\n"

        if not config:
            yield grounded_text
            return

        safe_text = redact_for_model(grounded_text)
        link_lines = [line for line in grounded_text.splitlines() if line.startswith(CITATION_LINE_PREFIXES)]

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

    def _route(self, query: str) -> tuple[str, str, str | None, dict]:
        graph = self.graph
        if not query or len(query) < MIN_QUERY_LEN:
            return "EMPTY", "Ask a library question of at least two characters.", None, {"hide_graph": True, "reason": "empty"}
        if INJECTION.search(query):
            return "PERSONA_LOCK", HIJACK_MESSAGE, None, {"hide_graph": True, "reason": "injection"}
        if CODE_TRAP.search(query):
            return "CODE_TRAP", CODE_MESSAGE, None, {"hide_graph": True, "reason": "procedural"}
        demo = match_demo(query, self.books)
        if demo:
            return "DEMO", demo["text"], None, {
                "hide_graph": True,
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
        if SCHEDULE_RE.search(query):
            lines = ["**Central Library schedule**", ""]
            lines.extend(SCHEDULE)
            lines.append("")
            lines.append("Source: Central Library Academic Schedule.")
            return "SCHEDULE", "\n".join(lines), None, {"hide_graph": True, "reason": "schedule_sheet"}
        if AUTH_RE.search(query) and not SHELF_RE.search(query):
            return "AUTH_GATEWAY", compose.auth_card(query), None, {"hide_graph": True, "reason": "auth_gateway"}

        catalog_hit = self.catalog.reply(query)
        if catalog_hit and not SHELF_RE.search(query):
            return "BOOK_PAGE", catalog_hit["text"], None, {
                "hide_graph": True,
                "reason": "catalog_book",
                "citation": catalog_hit["citation"],
                "score": 0.9,
            }

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

        if SHELF_RE.search(query):
            shelf_id = anchors[0] if anchors else ("third_normal_form" if "3nf" in query.lower() else None)
            if shelf_id and shelf_id in SHELF:
                return "CATALOG_SHELF", compose.shelf(self, shelf_id), shelf_id, {"score": best_score, "reason": "shelf"}
            if shelf_id:
                return "CATALOG_SHELF", compose.shelf_generic(self, shelf_id), shelf_id, {"score": best_score, "reason": "shelf_generic"}

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
            return "OOD_KILL", OOD_MESSAGE, None, {"hide_graph": True, "score": best_score, "reason": "cosine_below_0.75"}

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
