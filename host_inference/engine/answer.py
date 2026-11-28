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
import time

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
from .access_profile import is_open_access_profile, strip_institutional_payload
from .citation_format import (
    SOURCE_KIND_VERIFIED_FULL_TEXT,
    citation_link,
    has_verified_full_text_citations,
    link_answer_sources,
    sanitize_citations,
)
from .constants import (
    CITATION_LINE_PREFIXES,
    HERE,
)
from .contract import contract_for, graph_decision
from .evidence_selection import (
    build_grounding_trace,
    select_catalog_passages,
    select_evidence_citations,
)
from .followups import build_follow_up_questions
from .graph import LibraryGraph
from .links import source_links
from .llm import (
    PRE_FIRST_TOKEN_BUDGET_SECONDS,
    STREAM_TOTAL_DEADLINE_SECONDS,
    fallback_config,
    last_provider_error,
    last_stream_outcome,
    provider_config,
    stream_completion,
)
from .math_guard import (
    CLAIM_STATUS_INCOMPLETE,
    audit_scientific_response,
    build_scientific_guard_guidance,
    strip_unsupported_citations,
    verify_claim_support,
)
from .nodes import node_public
from .render import clean_reply_markdown
from .reply_evidence import expanded_concept_context
from .reply_plan import (
    EPISTEMIC_UNAVAILABLE,
    build_reply_plan,
    classify_epistemic_state,
)
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

# Synthesis task cues and passage context caps.
_TASK_SYNTHESIS_CUE_RE = re.compile(
    r"\b(how\s+(?:does|do|is|are|can)|why\s+(?:does|do|is|are)|compare|versus|vs\.?|"
    r"difference\s+between|distinguish|contrast|example|worked|walk\s+through|step[-\s]by[-\s]step|"
    r"calculate|compute|derive|relocate|translate|mechanism|explain|prerequisite|prerequisites)\b",
    re.I,
)
_WORKED_EXAMPLE_CUE_RE = re.compile(
    r"\b(example|worked|walk\s+through|step[-\s]by[-\s]step|calculate|compute|trace|demonstrate|illustrate)\b",
    re.I,
)
_SOURCES_PRESENT_RE = re.compile(r"(?:^|\n)(?:\*\*Sources:\*\*|#{1,4}\s+Sources\b)", re.I)
_ABSTENTION_REASONS = frozenset({"both_missing", "unsupported", "out_of_domain"})
_PARTIAL_GROUNDING_STATUSES = frozenset({"partial", "source_linked", "general"})
MAX_CONTEXT_PASSAGES = 3
MAX_CONTEXT_PASSAGE_CHARS = 500
MIN_STREAMED_CHARS_BEFORE_DRAFT_APPEND = 80


def _should_invoke_live_synthesis(
    *,
    query: str,
    route: str,
    result: dict,
    payload: dict,
    trace: dict,
    reply_detail: str,
    reply_template_id: str,
) -> bool:
    """Decide whether live LLM synthesis is authorized without overriding abstentions."""
    if payload.get("withdrawn_notice"):
        return False
    extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
    if str(extra.get("reason") or "") in _ABSTENTION_REASONS:
        return False
    route_allowed = route in POLISHABLE_ROUTES or (
        bool(result.get("research_overlay"))
        and (reply_detail == "expanded" or bool(reply_template_id))
    )
    if not route_allowed:
        return False
    grounding_status = trace.get("grounding_status")
    if grounding_status in (None, "verified"):
        return True
    if grounding_status == "unmatched":
        return False
    if grounding_status in _PARTIAL_GROUNDING_STATUSES:
        if result.get("research_overlay") and not (
            reply_detail == "expanded" or bool(reply_template_id)
        ):
            return False
        has_anchor = bool(payload.get("anchor_concept") or result.get("anchor"))
        if has_anchor or route in {"MULTI_CONCEPT", "CROSS_DOMAIN", "RELATION"}:
            return True
        return bool(_TASK_SYNTHESIS_CUE_RE.search(query))
    return False


def _format_retrieved_passages(citations: list[dict]) -> str:
    """Format sanitized retrieved passage excerpts for live synthesis grounding."""
    snippets: list[str] = []
    for cite in citations:
        if not isinstance(cite, dict) or cite.get("withdrawn"):
            continue
        passage = str(cite.get("text_passage") or cite.get("passage") or "").strip()
        if not passage:
            continue
        eid = str(cite.get("evidence_id") or "S?")
        title = str(cite.get("doc_title") or cite.get("title") or cite.get("doc_id") or "Source")
        kind = str(cite.get("source_kind") or "metadata_only_record")
        page = cite.get("page_number")
        page_note = f", p.{page}" if isinstance(page, int) and page > 0 else ""
        snippets.append(
            f"[{eid} | {kind} | {title}{page_note}]: {redact_for_model(passage[:MAX_CONTEXT_PASSAGE_CHARS])}"
        )
        if len(snippets) >= MAX_CONTEXT_PASSAGES:
            break
    return "\n".join(snippets)


class Engine:
    """Load the exported graph and answer library questions from it."""

    def __init__(self, graph_path: Path | None = None):
        self.cache_info = hydrate()
        if graph_path:
            path = graph_path
        elif (CACHE / "okf_graph.json").is_file():
            path = CACHE / "okf_graph.json"
        elif (HERE / "fixtures" / "okf_graph.json").is_file():
            path = HERE / "fixtures" / "okf_graph.json"
        elif (HERE / "okf_graph.json").is_file():
            path = HERE / "okf_graph.json"
        else:
            path = HERE / "fixtures" / "okf_graph.json"
        self.graph = LibraryGraph(path)
        self.books = load_books()
        self.catalog = Catalog(self.graph.nodes, self.books)

    def best_book(self, cid: str) -> dict | None:
        """Match a Pearson copy only when the retrieved document title is that book."""
        if is_open_access_profile():
            return None
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
            score = sum(1 for tok in tokens if re.search(rf"\b{re.escape(tok)}\b", title))
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
        start_time = time.perf_counter()
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
        initial_cites = extra.get("citations") or (
            [extra["citation"]] if extra.get("citation") else []
        )
        evidence_retrieval_ms: float | None = None
        if anchor_ok and (
            not initial_cites or not any(c.get("url") for c in initial_cites if isinstance(c, dict))
        ):
            t_ev_start = time.perf_counter()
            if not initial_cites:
                initial_cites = select_evidence_citations(graph, anchor, query)
            has_withdrawn_cite = any(
                isinstance(c, dict) and c.get("withdrawn") for c in initial_cites
            )
            if not has_withdrawn_cite and (
                not initial_cites
                or not any(c.get("url") for c in initial_cites if isinstance(c, dict))
            ):
                catalog_cites = select_catalog_passages(
                    self.catalog,
                    query,
                    concept_label=graph.label(anchor),
                    anchor_cid=anchor or "",
                    chunk_index=getattr(graph, "_chunk_provenance_index", None),
                )
                if catalog_cites:
                    initial_cites = catalog_cites
            evidence_retrieval_ms = round((time.perf_counter() - t_ev_start) * 1000, 1)

        payload = {
            "anchor_concept": node_public(graph.nodes[anchor]) if anchor_ok else None,
            "prerequisites": pres if anchor_ok else [],
            "unlocks": unl if anchor_ok else [],
            "related_concepts": rel if anchor_ok else [],
            "citations": initial_cites,
            "routing": {
                "route": route,
                "score": extra.get("score", 1.0),
                "reason": extra.get("reason", route),
            },
        }

        # The graph-render protocol is decided from the contract, not from which
        # branch of the router ran, so it cannot vary with query phrasing.
        contract_route = "GENERAL_EXPLANATION" if route == "CAPABILITY_INQUIRY" else route
        contract = contract_for(contract_route)
        decision = graph_decision(contract_route)
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
        has_verified_relationships = anchor_ok and bool(pres or unl or rel)
        if (
            extra.get("hide_graph")
            or not decision.render
            or (
                route
                in {
                    "GENERAL_EXPLANATION",
                    "RELATION",
                    "CROSS_DOMAIN",
                    "MULTI_CONCEPT",
                    "RESEARCH_TOPIC",
                }
                and not learning_graph_requested
                and not has_verified_relationships
            )
        ):
            payload["anchor_concept"] = None
            payload["prerequisites"] = []
            payload["unlocks"] = []
            if extra.get("hide_graph") or (
                not learning_graph_requested and not has_verified_relationships
            ):
                payload["render_graph"] = False
                payload["render_rule"] = "no_verified_graph_for_answer"

        if extra.get("intent_category"):
            payload["intent_category"] = extra["intent_category"]
        if extra.get("conversational_intent"):
            payload["conversational_intent"] = extra["conversational_intent"]
        if extra.get("multi_hop"):
            payload["multi_hop"] = extra["multi_hop"]

        if route == "MCQ_DIAGNOSTIC" and anchor_ok:
            payload["diagnostic_mcqs"] = self.diagnostic_payload(anchor).get("mcqs", [])
        else:
            payload["diagnostic_mcqs"] = []

        # Contract type 5 carries its projection alongside the reply text.
        if extra.get("projection"):
            payload.update(extra["projection"])
        shelf_record = {} if is_open_access_profile() else (extra.get("inventory") or {})
        if shelf_record.get("title"):
            payload["inventory"] = [
                {
                    "title": shelf_record.get("title", ""),
                    "author": shelf_record.get("author", ""),
                    "isbn": shelf_record.get("isbn", ""),
                    "confidence": shelf_record.get("status", "OPAC"),
                    "reader_url": shelf_record.get("reader_url")
                    or shelf_record.get("source_url")
                    or "",
                }
            ]
        if shelf_record.get("digital_available"):
            payload["digital_resources"] = [
                {
                    "title": shelf_record["title"],
                    "isbn": shelf_record.get("isbn", ""),
                    "reader_url": shelf_record.get("reader_url", ""),
                    "resource_type": "institutional_e_book",
                }
            ]

        # Attach matching institutional catalogue / inventory cards whenever
        # relevant records exist for the concept or query topic (never in open_access mode).
        oa_only = is_open_access_profile()
        if anchor_ok and decision.render and not oa_only:
            concept = graph.nodes[anchor]
            cards = inventory_card.attach_inventory(
                payload,
                anchor,
                graph.label(anchor),
                str(concept.get("summary") or ""),
                catalogue.load_catalogue(),
            )
            if cards and "### Institutional e-books" not in text:
                text = text + "\n" + inventory_card.render_inventory_section(cards)
        elif route in {"GENERAL_EXPLANATION", "DISCONNECTED", "MULTI_CONCEPT"} and (
            not payload.get("anchor_concept")
            or not payload.get("citations")
            or not payload.get("inventory_cards")
        ):
            # Fallback: find closest OKF node / textbook source for general queries
            _FILLER = {
                "what",
                "how",
                "why",
                "when",
                "where",
                "which",
                "who",
                "are",
                "is",
                "explain",
                "define",
                "tell",
                "about",
                "does",
                "the",
                "and",
                "for",
                "with",
                "from",
                "into",
                "concept",
                "concepts",
                "related",
                "topic",
                "topics",
                "give",
                "show",
                "list",
                "between",
                "compare",
            }
            q_tokens = {
                tok for tok in re.findall(r"[a-z0-9]{3,}", query.lower()) if tok not in _FILLER
            }
            scored_cids: list[tuple[int, str]] = []
            summary_cids: list[tuple[int, str]] = []
            if q_tokens:
                for cid, node in graph.nodes.items():
                    lbl = graph.label(cid).lower()
                    cid_l = cid.lower().replace("_", " ")
                    summary_l = str(node.get("summary") or "").lower()
                    score = 0
                    for tok in q_tokens:
                        if tok in lbl or tok in cid_l:
                            score += 10
                        elif tok in summary_l:
                            score += 1
                    if score >= 10:
                        scored_cids.append((score, cid))
                    elif score >= 1:
                        summary_cids.append((score, cid))
            scored_cids.sort(key=lambda item: (-item[0], item[1]))
            summary_cids.sort(key=lambda item: (-item[0], item[1]))
            if not scored_cids and summary_cids:
                scored_cids = summary_cids[:4]
            # Only genuinely resolved anchor concepts from the canonical router may set anchor_concept.
            # Do NOT silently invent or substitute an anchor concept for unmatched questions.
            # Furthermore, unindexed/unmatched queries must NOT attach synthetic fallback citations.
            if not payload.get("anchor_concept"):
                payload["anchor_concept"] = None
                payload["render_graph"] = False
                payload["render_rule"] = "no_verified_concept_match"
                payload["prerequisites"] = []
                payload["unlocks"] = []
                payload["related_concepts"] = []
                payload["citations"] = []
            elif not payload.get("citations") or not any(
                c.get("label") or c.get("doc_id") or c.get("url")
                for c in (payload.get("citations") or [])
                if isinstance(c, dict)
            ):
                if scored_cids:
                    cites = select_evidence_citations(graph, scored_cids[0][1], query)
                    if cites:
                        payload["citations"] = cites
                if not payload.get("citations"):
                    anchor_obj = payload.get("anchor_concept") or {}
                    cites = select_catalog_passages(
                        self.catalog,
                        query,
                        concept_label=str(anchor_obj.get("label") or ""),
                        anchor_cid=str(anchor_obj.get("id") or ""),
                        chunk_index=getattr(graph, "_chunk_provenance_index", None),
                    )
                    if cites:
                        payload["citations"] = cites
                if not oa_only and not payload.get("inventory"):
                    cards = inventory_card.attach_inventory(
                        payload,
                        "general",
                        query,
                        query,
                        catalogue.load_catalogue(),
                    )
                    if cards and "### Institutional e-books" not in text:
                        text = text + "\n" + inventory_card.render_inventory_section(cards)
            elif not oa_only and not payload.get("inventory") and not payload.get("inventory_cards"):
                cards = inventory_card.attach_inventory(
                    payload,
                    "general",
                    query,
                    query,
                    catalogue.load_catalogue(),
                )
                if cards and "### Institutional e-books" not in text:
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

        strip_institutional_payload(payload)
        payload["citations"] = sanitize_citations(
            payload.get("citations"), open_access_only=oa_only
        )
        evidence_backed = has_verified_full_text_citations(payload["citations"])
        payload["evidence_backed"] = evidence_backed
        payload["verified_citation_count"] = sum(
            1
            for c in payload["citations"]
            if isinstance(c, dict) and c.get("source_kind") == SOURCE_KIND_VERIFIED_FULL_TEXT
        )
        payload["follow_up_questions"] = build_follow_up_questions(
            graph,
            payload,
            query,
            route,
            reason=str(extra.get("reason") or ""),
        )

        # Populate instrumentation trace & grounding status for SIGIR Demo Inspector
        latency_s = round(time.perf_counter() - start_time, 2)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        anchor_id = (
            (payload.get("anchor_concept") or {}).get("id")
            if payload.get("anchor_concept")
            else None
        )
        anchor_lbl = (
            (payload.get("anchor_concept") or {}).get("label")
            or (payload.get("anchor_concept") or {}).get("name")
            if payload.get("anchor_concept")
            else None
        )
        hops = (
            2
            if (anchor_id and (payload.get("prerequisites") or payload.get("unlocks")))
            else (1 if anchor_id else 0)
        )
        payload["trace"] = build_grounding_trace(
            route=route,
            anchor_id=anchor_id,
            anchor_label=anchor_lbl,
            hops=hops,
            citations=payload.get("citations") or [],
            provider=str(payload.get("provider") or ""),
            latency_s=latency_s,
            latency_ms=latency_ms,
        )
        payload["trace"]["evidence_backed"] = evidence_backed
        epistemic = classify_epistemic_state(payload, route, query)
        payload["epistemic_state"] = epistemic["primary_state"]
        payload["epistemic_contract"] = epistemic
        payload["trace"]["epistemic_state"] = epistemic["primary_state"]

        linked_text = clean_reply_markdown(link_answer_sources(text, payload["citations"]), query)
        text, stripped_markers = strip_unsupported_citations(linked_text, payload["citations"])
        claim_support = verify_claim_support(text, payload["citations"], stream_status="complete")
        if stripped_markers:
            claim_support["stripped_unsupported_markers"] = stripped_markers
        payload["claim_support"] = claim_support
        payload["trace"]["claim_support_status"] = claim_support["status"]
        return {
            "route": route,
            "contract": contract,
            "text": text,
            "payload": payload,
            "anchor": anchor,
            "extra": extra,
            "intent_category": extra.get("intent_category") or route,
            "evidence_retrieval_ms": evidence_retrieval_ms,
        }

    def stream_chat(
        self,
        query: str,
        previous_answer: str = "",
        prepared: dict | None = None,
        reply_template_id: str = "",
        reply_detail: str = "standard",
        request_deadline: float | None = None,
    ):
        """Stream a provider answer under a bounded end-to-end deadline."""
        t_stream_entry = time.perf_counter()
        deadline = (
            request_deadline
            if request_deadline is not None
            else (t_stream_entry + STREAM_TOTAL_DEADLINE_SECONDS)
        )
        result = prepared if prepared is not None else self.answer(query)
        route = result["route"]
        grounded_text = result["text"]
        payload = result["payload"]
        oa_only = is_open_access_profile()
        if isinstance(payload.get("citations"), list):
            payload["citations"] = sanitize_citations(
                payload["citations"], open_access_only=oa_only
            )
        evidence_backed = has_verified_full_text_citations(payload.get("citations"))
        payload["evidence_backed"] = evidence_backed
        plan = build_reply_plan(query, route, payload, reply_template_id)
        payload["reply_plan"] = plan
        payload["reply_template"] = plan["primary_template"]
        payload["epistemic_state"] = plan["epistemic_state"]
        payload["epistemic_contract"] = plan["epistemic_contract"]
        trace = payload.setdefault("trace", {})
        trace["template_id"] = plan["primary_template"]["id"]
        trace["evidence_backed"] = evidence_backed
        trace["epistemic_state"] = plan["epistemic_state"]

        can_polish = _should_invoke_live_synthesis(
            query=query,
            route=route,
            result=result,
            payload=payload,
            trace=trace,
            reply_detail=reply_detail,
            reply_template_id=reply_template_id,
        )
        config = provider_config() if can_polish else None

        if not can_polish:
            det_claim = payload.get("claim_support") or verify_claim_support(
                grounded_text, payload.get("citations") or [], stream_status="complete"
            )
            payload["synthesis_mode"] = "verified_deterministic"
            payload["provider"] = ""
            payload["provider_status"] = "not_invoked"
            payload["fallback_reason"] = None
            payload["model"] = {"provider": "deterministic", "model": ""}
            trace.update(
                provider="deterministic",
                provider_status="not_invoked",
                fallback_reason=None,
                model="",
                synthesis_mode=payload["synthesis_mode"],
                template_influenced=False,
                claim_support_status=det_claim["status"],
            )
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            yield grounded_text
            yield (
                "\n[STREAM_META:"
                + json.dumps(
                    {
                        "provider_status": "not_invoked",
                        "fallback_reason": None,
                        "stream_status": "complete",
                        "provider_ttft_ms": None,
                        "epistemic_state": plan["epistemic_state"],
                        "claim_support_status": det_claim["status"],
                        "validated": bool(det_claim["validated"]),
                    }
                )
                + "]\n"
            )
            return

        safe_text = redact_for_model(grounded_text)
        retrieved_passages = _format_retrieved_passages(payload.get("citations") or [])
        if (
            reply_detail != "expanded"
            and SHORT_DEFINITION_RE.match(query)
            and not _TASK_SYNTHESIS_CUE_RE.search(query)
            and not retrieved_passages
            and result.get("anchor")
            and result["anchor"] in self.graph.nodes
        ):
            anchor_node = self.graph.nodes[result["anchor"]]
            safe_text = redact_for_model(str(anchor_node.get("summary") or grounded_text))
        if retrieved_passages:
            safe_text += "\n\nRetrieved source passages:\n" + retrieved_passages
        if route in {"DISCONNECTED", "MULTI_CONCEPT"}:
            safe_text += (
                "\n\nGuidance: Explain all requested concepts, their mathematical or conceptual "
                "relationship, and a concise worked example. Clearly separate general explanation "
                "from stored graph edges and do not fabricate graph links."
            )
        if route == "GENERAL_EXPLANATION":
            safe_text += (
                "\n\nGuidance: Provide a direct, technically accurate foundational explanation "
                "with a concise worked example where helpful. Label general foundational knowledge "
                "clearly and never fabricate local textbook citations."
            )
        if _WORKED_EXAMPLE_CUE_RE.search(query):
            safe_text += (
                "\n\nGuidance: Include a concrete worked example or step-by-step calculation. "
                "Explicitly label independently derived illustrative examples as "
                "'Illustrative example (independently derived)' vs. source-supported claims."
            )
        if not evidence_backed:
            safe_text += (
                "\n\nGuidance: Zero verified full-text PDF passages were retrieved for this query "
                "(only concept summary or metadata records exist). State this explicitly in a "
                "brief Limitations note and never fabricate citations, page numbers, or links."
            )
        safe_text += f"\n\nEpistemic state: {plan['epistemic_state']}."
        sci_guidance = build_scientific_guard_guidance(
            query,
            evidence_backed=evidence_backed,
            citations=payload.get("citations") or [],
        )
        if sci_guidance:
            safe_text += "\n\nScientific verification guardrails:\n" + sci_guidance
        if reply_detail == "expanded":
            concept_context = expanded_concept_context(payload)
            if concept_context:
                safe_text += (
                    "\n\nIndexed concept context (edge claims pending review):\n" + concept_context
                )
        link_lines = [
            line for line in grounded_text.splitlines() if line.startswith(CITATION_LINE_PREFIXES)
        ]
        if result.get("research_overlay"):
            link_lines.extend(
                line
                for line in grounded_text.splitlines()
                if line.startswith("[") and " Source: https://" in line
            )
        if not oa_only:
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
        wait_started = time.perf_counter()
        rem_total = max(0.05, deadline - wait_started)
        ft_deadline = wait_started + min(PRE_FIRST_TOKEN_BUDGET_SECONDS, rem_total * 0.6)
        candidates = (config, fallback_config(config)) if config else ()
        for candidate in candidates:
            if candidate is None:
                continue
            if time.perf_counter() >= ft_deadline:
                break
            try:
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
                            first_token_deadline=ft_deadline,
                            total_deadline=deadline,
                        )
                    )
                elif previous_answer:
                    attempt = iter(
                        stream_completion(
                            candidate,
                            safe_text,
                            query,
                            previous_answer,
                            first_token_deadline=ft_deadline,
                            total_deadline=deadline,
                        )
                    )
                else:
                    attempt = iter(
                        stream_completion(
                            candidate,
                            safe_text,
                            query,
                            first_token_deadline=ft_deadline,
                            total_deadline=deadline,
                        )
                    )
            except TypeError:
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
            provider_err = last_provider_error()
            err_reason = (
                "provider_not_configured"
                if config is None
                else str((provider_err or {}).get("error_type") or "unavailable")
            )
            prov_status = "not_configured" if config is None else "unavailable"
            has_evidence = bool(payload.get("citations")) and bool(payload.get("anchor_concept"))
            payload["synthesis_mode"] = "provider_unavailable_fallback"
            payload["provider"] = "unavailable"
            payload["provider_status"] = prov_status
            payload["fallback_reason"] = err_reason
            payload["provider_unavailable"] = True
            payload["provider_error"] = err_reason
            payload["model"] = {"provider": "unavailable", "model": ""}
            trace.update(
                provider="unavailable",
                provider_status=prov_status,
                fallback_reason=err_reason,
                model="",
                synthesis_mode=payload["synthesis_mode"],
                provider_error=err_reason,
                template_influenced=False,
                **({} if has_evidence else {"grounding_status": "abstained"}),
            )
            payload["logs"].append(
                {
                    "step": "AI provider",
                    "status": "error",
                    "details": (
                        f"Provider unavailable ({err_reason}); "
                        + (
                            "showing grounded draft"
                            if has_evidence
                            else "insufficient indexed evidence — abstaining"
                        )
                    ),
                }
            )
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            if has_evidence:
                yield (
                    "> **Live AI synthesis unavailable** "
                    f"(`{err_reason}`) — showing grounded deterministic draft below.\n\n"
                )
                yield grounded_text
            else:
                yield (
                    "> **Live AI synthesis unavailable** "
                    f"(`{err_reason}`): the local corpus has insufficient indexed evidence to "
                    "answer this question deterministically without live synthesis."
                )
            yield (
                "\n[STREAM_META:"
                + json.dumps(
                    {
                        "provider_status": prov_status,
                        "fallback_reason": err_reason,
                        "stream_status": "fallback_grounded" if has_evidence else "abstained",
                        "provider_ttft_ms": None,
                    }
                )
                + "]\n"
            )
            return

        provider_ttft_ms = round((time.perf_counter() - wait_started) * 1000, 1)
        payload["synthesis_mode"] = (
            "xkiro_synthesis"
            if selected["provider"] == "xkiro"
            else f"{selected['provider']}_fallback"
        )
        payload["provider"] = selected["provider"]
        payload["provider_status"] = "streaming"
        payload["fallback_reason"] = (
            "primary_provider_failover" if selected["provider"] != "xkiro" else None
        )
        payload["model"] = {"provider": selected["provider"], "model": selected["model"]}
        trace.update(
            provider=selected["provider"],
            provider_status="streaming",
            fallback_reason=payload["fallback_reason"],
            model=selected["model"],
            synthesis_mode=payload["synthesis_mode"],
            template_influenced=bool(reply_detail == "expanded" or reply_template_id),
        )
        payload["logs"].append(
            {"step": selected["provider"], "status": "ok", "details": selected["model"]}
        )
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        streamed_chunks: list[str] = [first_token]
        yielded_len = len(first_token)
        yield first_token
        hit_stream_deadline = False
        if stream is not None:
            for tok in stream:
                if time.perf_counter() >= deadline:
                    hit_stream_deadline = True
                    break
                streamed_chunks.append(tok)
                yielded_len += len(tok)
                yield tok
        outcome = last_stream_outcome()
        mid_stream_err = last_provider_error()
        outcome_status = (
            "stream_deadline_exceeded"
            if hit_stream_deadline
            else str((outcome or {}).get("status") or "")
        )
        if outcome_status == "truncated_token_limit":
            fr = str((outcome or {}).get("finish_reason") or "length")
            yield f"\n[STREAM_TRUNCATED:{fr}]\n"
            yield (
                "\n\n> **Response truncated (token limit reached):** "
                "the provider stopped before completing the answer; showing partial unvalidated response."
            )
            yield (
                "\n[STREAM_META:"
                + json.dumps(
                    {
                        "provider_status": "truncated_token_limit",
                        "fallback_reason": payload["fallback_reason"],
                        "stream_status": "truncated_token_limit",
                        "finish_reason": fr,
                        "provider_ttft_ms": provider_ttft_ms,
                        "epistemic_state": EPISTEMIC_UNAVAILABLE,
                        "claim_support_status": CLAIM_STATUS_INCOMPLETE,
                        "validated": False,
                    }
                )
                + "]\n"
            )
            return
        if (
            outcome_status
            in {
                "incomplete_eof",
                "stream_interrupted_timeout",
                "stream_interrupted",
                "stream_deadline_exceeded",
            }
            or outcome_status.startswith("provider_")
            or mid_stream_err
        ):
            err_kind = (
                outcome_status
                or str((mid_stream_err or {}).get("error_type") or "stream_interrupted")
            )
            yield f"\n[STREAM_INCOMPLETE:{err_kind}]\n"
            yield (
                "\n\n> **Incomplete stream:** live synthesis ended unexpectedly "
                f"(`{err_kind}`) before completion; partial output is unvalidated."
            )
            yield (
                "\n[STREAM_META:"
                + json.dumps(
                    {
                        "provider_status": err_kind,
                        "fallback_reason": err_kind,
                        "stream_status": "incomplete_stream",
                        "provider_ttft_ms": provider_ttft_ms,
                        "epistemic_state": EPISTEMIC_UNAVAILABLE,
                        "claim_support_status": CLAIM_STATUS_INCOMPLETE,
                        "validated": False,
                    }
                )
                + "]\n"
            )
            return
        emitted_text = "".join(streamed_chunks)
        if yielded_len < MIN_STREAMED_CHARS_BEFORE_DRAFT_APPEND and grounded_text:
            yield "\n\n" + grounded_text
            emitted_text += "\n\n" + grounded_text
        sci_audit = audit_scientific_response(
            emitted_text,
            query=query,
            citations=payload.get("citations") or [],
            evidence_backed=evidence_backed,
        )
        if sci_audit["qualification_note"]:
            yield sci_audit["qualification_note"]
        claim_report = verify_claim_support(
            emitted_text,
            payload.get("citations") or [],
            stream_status="complete",
        )
        if claim_report["unsupported_markers"]:
            markers_str = ", ".join(claim_report["unsupported_markers"])
            yield (
                "\n\n> **Claim support notice:** inline citation marker(s) "
                f"`{markers_str}` could not be verified against retrieved full-text passages."
            )
        source_lines = list(
            dict.fromkeys(
                f"- {citation_link(citation)}"
                for citation in payload.get("citations", [])
                if citation_link(citation)
            )
        )
        if source_lines and not _SOURCES_PRESENT_RE.search(emitted_text):
            yield "\n\n**Sources:**\n" + "\n".join(source_lines)
        unique_link_lines = [
            line
            for line in link_lines
            if line not in emitted_text and not any(line in s for s in source_lines)
        ]
        if unique_link_lines:
            yield "\n\n" + "\n".join(unique_link_lines)
        yield (
            "\n[STREAM_META:"
            + json.dumps(
                {
                    "provider_status": "complete",
                    "fallback_reason": payload["fallback_reason"],
                    "stream_status": "complete",
                    "finish_reason": (outcome or {}).get("finish_reason"),
                    "provider_ttft_ms": provider_ttft_ms,
                    "epistemic_state": plan["epistemic_state"],
                    "claim_support_status": claim_report["status"],
                    "math_validation_passed": sci_audit["passed"],
                    "validated": bool(claim_report["validated"] and sci_audit["passed"]),
                }
            )
            + "]\n"
        )

    def _route_shelf_query(
        self, query: str, best_score: float
    ) -> tuple[str, str, str | None, dict]:
        """Answer a physical-location question from the institutional catalogue.

        Contract type 2 (``CATALOG_SHELF_ROUTING``). Returns a
        ``CATALOG_SHELF_ROUTING`` route with the shelf card, or an honest
        "not indexed" reply — never a fabricated location.
        """
        requested = inventory.extract_title(query)
        opac_holding = None
        try:
            from hostapp import koha_bridge  # type: ignore[import-not-found]
        except ImportError:
            try:
                from ..hostapp import koha_bridge  # type: ignore[import-not-found]
            except ImportError:
                koha_bridge = None
        if koha_bridge is not None and hasattr(koha_bridge, "lookup_chat_library_holding"):
            try:
                opac_holding = koha_bridge.lookup_chat_library_holding(requested or query)
            except Exception:
                opac_holding = None
        if isinstance(opac_holding, dict) and opac_holding.get("title"):
            title = str(opac_holding.get("title") or requested)
            author = str(opac_holding.get("author") or "").strip()
            call_num = str(opac_holding.get("call_number") or "Check OPAC record").strip()
            library_name = str(opac_holding.get("library") or "UEM Kolkata Library").strip()
            status = str(opac_holding.get("status") or "See OPAC record").strip()
            source_mode = str(opac_holding.get("source_mode") or "LIVE_OPAC")
            checked = str(
                opac_holding.get("checked_at") or opac_holding.get("snapshot_updated_at") or ""
            ).strip()
            opac_url = str(opac_holding.get("url") or "https://uemk-opac.l2c2.co.in/").strip()
            lines = [f"**{title}**" + (f" by {author}" if author else "")]
            lines.append(f"- **Library:** {library_name}")
            lines.append(f"- **Call number:** `{call_num}`")
            lines.append(f"- **Availability:** {status}")
            lines.append(
                f"- **Source:** {source_mode}" + (f" (checked {checked})" if checked else "")
            )
            lines.append(f"- **OPAC record:** [{opac_url}]({opac_url})")
            return (
                "CATALOG_SHELF_ROUTING",
                "\n".join(lines),
                None,
                {
                    "hide_graph": True,
                    "reason": "opac_holding_match",
                    "score": best_score,
                    "inventory": {
                        "title": title,
                        "held": True,
                        "source_mode": source_mode,
                        "opac_holding": opac_holding,
                    },
                },
            )

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
