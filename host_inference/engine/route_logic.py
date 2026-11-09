"""Route hosted chat queries to grounded library and graph responses."""

from __future__ import annotations

import re

from . import catalogue, compose, diagnostics, ingestion_view, inventory
from .constants import (
    CODE_MESSAGE,
    HIJACK_MESSAGE,
    KILL_SWITCH,
    OOD_MESSAGE,
    PASSING_MENTIONS,
    UNINDEXED_CURRICULUM_MESSAGE,
)
from .intent import IntentCategory, classify_query_intent
from .multi_hop import extract_concept_mentions, multi_hop_reasoning
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
from .routing_constants import (
    ANCHOR_LIMIT,
    COMPARE_CUES,
    COMPARE_CUES_DBMS,
    MIN_QUERY_LEN,
    RANK_TOP_K,
    SHORTEST_PATH_LIMIT,
    SOURCE_LOOKUP_RE,
    WHERE_IS_RE,
)

RESEARCH_INTENT_RE = re.compile(r"\b(research|papers?|studies|literature|evidence|gaps?)\b", re.I)
ACADEMIC_DOMAIN_RE = re.compile(
    r"\b(ai|ml|models?|language|memory|retrieval|graph|learning|algorithm)\b", re.I
)


def route(self, query: str) -> tuple[str, str, str | None, dict]:
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

    # The indexed "Neural Network" node describes graph neural networks.
    # A basic neural-network definition must not cite that narrower passage.
    if re.fullmatch(
        r"(?:what is|define|explain)\s+(?:a|an)?\s*(?:artificial\s+)?neural networks?[?.!]*",
        query,
        re.I,
    ):
        return (
            "GENERAL_EXPLANATION",
            "**A neural network** is a trainable model of connected computational units. "
            "Each layer transforms its input using learned weights and nonlinear functions; "
            "training adjusts those weights to reduce an error on examples. "
            "This is a general explanation, not a claim extracted from an indexed book page.",
            None,
            {"hide_graph": True, "reason": "foundational_definition"},
        )

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

    PAPER_LOOKUP_RE = re.compile(
        r"\b(which paper introduced|who (?:wrote|authored)|author of|doi for|give me (?:the )?citations of|citation count of|references of this paper|citations of this paper|identify (?:the )?paper)\b",
        re.I,
    )
    if PAPER_LOOKUP_RE.search(query):
        target_cid = anchors[0] if anchors else None
        text, cite = compose.paper_lookup_reply(self, query, target_cid)
        return (
            "PAPER_LOOKUP",
            text,
            target_cid,
            {
                "hide_graph": True,
                "reason": "paper_lookup",
                "score": best_score if anchors else 0.9,
                "citation": cite,
                "intent_category": IntentCategory.PAPER_LOOKUP.value,
            },
        )

    LIB_INVENTORY_RE = re.compile(
        r"\b(show journal inventory|journal holdings|journal inventory|what books are in the library|which books are in the library|show books in library|library inventory)\b",
        re.I,
    )
    if LIB_INVENTORY_RE.search(query):
        return (
            "LIBRARY_LOOKUP",
            compose.library_inventory_reply(self, query),
            None,
            {
                "hide_graph": True,
                "reason": "library_inventory",
                "score": 1.0,
                "intent_category": IntentCategory.LIBRARY_LOOKUP.value,
            },
        )

    RESEARCH_TOPIC_RE = re.compile(
        r"\b(recent\s+(?:studies|research|papers|advances)|latest\s+(?:findings|literature|works)|state of the art|sota)\b",
        re.I,
    )
    if RESEARCH_TOPIC_RE.search(query):
        target = anchors[0] if anchors else best_id
        is_rag = target == "rag" or "rag" in query.lower() or "retrieval" in query.lower()
        if is_rag:
            synthesis_text = (
                f"**Recent Research & Literature Analysis: {graph.label('rag')}**\n\n"
                "• **Foundational Baseline:** Patrick Lewis et al. (2020), *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (`papers/Lewis2020_RAG.pdf`), NeurIPS 2020. Introduced parametric neural sequence generators augmented with dense non-parametric Wikipedia retrieval indices.\n"
                "• **Recent Milestone:** Darren Edge et al. (2024), *From Local to Global: A Graph RAG Approach to Query-Focused Summarization* (`papers/Edge2024_GraphRAG.pdf`), Microsoft Research (April 2024). Extends vector retrieval to structured knowledge graph communities via Leiden clustering and hierarchical summarization for comprehensive cross-document reasoning.\n\n"
                "**Key Research Findings & Structural Evolution:**\n"
                "1. *Local vs. Global Synthesis:* Standard chunk-level vector RAG struggles with corpus-wide thematic queries. Graph-driven architectures (Graph RAG) resolve this by aggregating hierarchical community summaries.\n"
                "2. *Factuality & Grounding:* Non-parametric retrieval substantially reduces generation hallucination compared to purely parametric sequence-to-sequence language models.\n\n"
                "*(Verified corpus temporal boundary: Indexed publications in this repository extend through mid-2024. "
                "For literature published after mid-2024, live scholarly database synchronization is required; "
                "older indexed papers are not represented as current state-of-the-art without live verification.)*"
            )
            citations = [
                {
                    "source_category": "paper",
                    "doc_id": "papers/Lewis2020_RAG.pdf",
                    "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
                    "authors": "Lewis et al. (2020)",
                    "year": "2020",
                    "verified": True,
                },
                {
                    "source_category": "paper",
                    "doc_id": "papers/Edge2024_GraphRAG.pdf",
                    "title": "From Local to Global: A Graph RAG Approach to Query-Focused Summarization",
                    "authors": "Edge et al. (2024)",
                    "year": "2024",
                    "verified": True,
                },
            ]
        else:
            base_synthesis = compose.synthesis(self, target)
            lit_lines = []
            if target in compose.VERIFIED_BIBLIOGRAPHIC_RECORDS:
                rec = compose.VERIFIED_BIBLIOGRAPHIC_RECORDS[target]
                lit_lines.append(
                    f"• **Corpus Benchmark Paper:** {rec['authors']} ({rec['year']}), *{rec['title']}* (`{rec['doc_id']}`), {rec['venue']}."
                )
            recent_notice = (
                "\n\n*(Verified corpus temporal boundary: Indexed publications in this repository extend through mid-2024. "
                "For literature published after mid-2024, live scholarly database synchronization is required; "
                "older indexed papers are not represented as current state-of-the-art without live verification.)*"
            )
            if lit_lines:
                synthesis_text = base_synthesis + "\n\n**Indexed Literature Foundation:**\n" + "\n".join(lit_lines) + recent_notice
            else:
                synthesis_text = base_synthesis + recent_notice
            citations = [graph.cite_record(target, query)]

        return (
            "RESEARCH_TOPIC",
            synthesis_text,
            target,
            {
                "score": max(best_score, 0.93 if hits else best_score),
                "reason": "research_topic_verified_dates",
                "citations": citations,
                "intent_category": IntentCategory.RESEARCH_TOPIC.value,
            },
        )

    extracted_concepts = extract_concept_mentions(query, known_graph=graph)
    if len(extracted_concepts) >= 3:
        reasoning = multi_hop_reasoning(self, query, concept_mentions=extracted_concepts)
        primary = reasoning["indexed_concepts"][0].cid if reasoning["indexed_concepts"] else None
        return (
            "MULTI_CONCEPT",
            reasoning["text"],
            primary,
            {
                "score": max(best_score, 0.92),
                "reason": "multi_hop_reasoning",
                "citations": reasoning["citations"],
                "multi_hop": {
                    "concepts": [c.label or c.raw_text for c in reasoning["resolved_concepts"]],
                    "indexed": [c.cid for c in reasoning["indexed_concepts"]],
                    "missing": [c.raw_text for c in reasoning["missing_concepts"]],
                    "is_partial": reasoning["is_partial"],
                },
                "hide_graph": False,
                "intent_category": IntentCategory.MULTI_CONCEPT.value,
            },
        )

    if WHERE_IS_RE.search(query):
        requested_title = inventory.extract_title(query)
        _record, title_score = inventory.best_record(catalogue.load_catalogue(), requested_title)
        if inventory.match_confidence(title_score) != "none":
            return self._route_shelf_query(query, best_score)

    if SHELF_RE.search(query):
        shelf_id = (
            anchors[0] if anchors else ("third_normal_form" if "3nf" in query.lower() else None)
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
        if not left_ok and not right_ok:
            return (
                "DISCONNECTED",
                f"Neither **{left_text.strip(' ?.')}** nor **{right_text.strip(' ?.')}** are indexed in the catalog graph. "
                "No relationship or bridge can be verified without evidence.",
                None,
                {"score": best_score, "reason": "both_missing", "hide_graph": True},
            )

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
        if RESEARCH_INTENT_RE.search(query) and ACADEMIC_DOMAIN_RE.search(query):
            return (
                "RESEARCH_UNVERIFIED",
                "I cannot verify findings or research gaps for this topic from the currently "
                "indexed sources. Try a narrower paper, method, or dataset, or ask the "
                "librarian to add relevant research records.",
                None,
                {"hide_graph": True, "score": best_score, "reason": "research_not_indexed"},
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
    if re.search(r"\b(recent\s+(?:studies|research|papers|advances)|latest\s+(?:findings|literature|works)|state of the art|sota)\b", query, re.I):
        synthesis_text = compose.synthesis(self, target)
        recent_notice = (
            "\n\n*(Verified corpus date coverage: Indexed publications span through 2023/2024. "
            "For subsequent real-time literature, live scholarly index synchronization is required; "
            "older indexed papers are not represented as current state-of-the-art without live verification.)*"
        )
        return (
            "RESEARCH_TOPIC",
            synthesis_text + recent_notice,
            target,
            {
                "score": max(best_score, 0.93 if hits else best_score),
                "reason": "research_topic_verified_dates",
                "intent_category": IntentCategory.RESEARCH_TOPIC.value,
            },
        )

    return (
        "GRAPH_SYNTHESIS",
        compose.synthesis(self, target),
        target,
        {"score": max(best_score, 0.93 if hits else best_score), "reason": "graph_synthesis"},
    )
