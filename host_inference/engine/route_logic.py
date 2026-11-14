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
    EXPLOIT_ACTION_RE,
    INGEST_RE,
    INJECTION,
    PARAM_RE,
    RELATE_RE,
    SCHEDULE_RE,
    SHELF_RE,
)
from .render import neighborhood_block
from .route_research import research_topic_reply
from .route_special_books import special_book_reply
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
    r"(?:\ba\*|\b(?:"
    r"ai|ml|dl|os|dbms|nlp|ir|rag|llm|llms|svm|cnn|rnn|lstm|gan|vae|bert|gpt|dpo|rlhf|tlb|dag|np|"
    r"models?|language|memory|retrieval|graph|graphs|learning|algorithm|algorithms|heuristic|admissible|"
    r"complexity|asymptotic|big-o|amortized|recursion|recursive|dynamic programming|topological|"
    r"heap|heaps|tree|trees|trie|binary|array|arrays|stack|queue|linked list|hash(?:ing)?|sort(?:ing)?|"
    r"dijkstra|bellman|bfs|dfs|shortest path|spanning tree|np-complete|np-hard|decidable|undecidable|"
    r"automata|automaton|turing|dfa|nfa|grammar|grammars|cfg|chomsky|pumping lemma|kleene|"
    r"compiler|compilers|lexer|lexical|parser|parsing|syntax|semantic|ast|code generation|register allocation|"
    r"operating system|process|processes|thread|threads|scheduling|deadlock|banker|mutex|semaphore|concurrency|synchronization|"
    r"virtual memory|pag(?:ing|ng)|page replacement|thrashing|filesystem|file system|inode|syscall|"
    r"database|sql|acid|transaction|transactions|serializability|normalization|b-tree|b\+ tree|relational algebra|"
    r"network|networks|tcp|udp|ip|http|dns|routing|congestion|flow control|osi|mac|packet|packets|socket|"
    r"distributed|consensus|paxos|raft|cap theorem|replication|sharding|vector clock|federated|"
    r"architecture|cpu|cache|caches|pipeline|pipelining|risc|isa|alu|instruction|hazard|"
    r"cryptography|encryption|decryption|rsa|aes|tls|ssl|authentication|cybersecurity|vulnerability|xss|sql injection|"
    r"matrix|matrices|vector|vectors|eigenvalue|eigenvector|svd|determinant|rank|linear algebra|orthogonality|"
    r"probability|bayes|bayesian|distribution|variance|covariance|expectation|markov|hypothesis|regression|"
    r"calculus|derivative|gradient|jacobian|hessian|integral|optimization|convex|"
    r"neural|backpropagation|tr[a]?nsformer|tr[a]?nsformers|att[e]?ntion|embedding|embeddings|tokenization|"
    r"computer vision|convolution|pooling|dense|layer|layers|parameter|parameters|weight|weights|bias|biases|"
    r"activation|loss|regularization|dropout|kernel|krnel|perceptron|epoch|epochs|batch|"
    r"bm25|tf-idf|quantization|lora|qlora|fine-tuning|software engineering|testing|design pattern|solid"
    r")\b)",
    re.I,
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
    if EXPLOIT_ACTION_RE.search(query):
        return (
            "GUARDRAIL_INTERCEPT",
            "I cannot provide instructions for bypassing authentication or performing cyberattacks. "
            "I can, however, explain defensive concepts such as SQL injection prevention, parameterized queries, and secure authentication.",
            None,
            {"hide_graph": True, "reason": "security_abuse_guardrail"},
        )
    if classify_query_intent(query) == IntentCategory.RESEARCH_INTELLIGENCE:
        return (
            "RESEARCH_INTELLIGENCE",
            "Research intelligence runs in the authorized [research pipeline](/research). "
            "Open a topic or author record there to request bibliometric analysis. "
            "This chat has not calculated metrics for the request.",
            None,
            {
                "hide_graph": True,
                "reason": "delegated_to_research_pipeline",
                "intent_category": IntentCategory.RESEARCH_INTELLIGENCE.value,
            },
        )

    # ── Conversational greetings ──────────────────────────────────────
    _GREETING_RE = re.compile(
        r"^(h(i|ey|ello|owdy)|good\s*(morning|afternoon|evening|day)|"
        r"yo\b|sup\b|what'?s?\s*up|who are you|help|what can you do|"
        r"thanks?|thank\s*you|bye|goodbye|see ya)[\s?!.]*$",
        re.I,
    )
    if _GREETING_RE.match(query):
        text = (
            "Hello! I'm **Archipelago**, your AI academic knowledge assistant. "
            "I can explain concepts across Computer Science (Operating Systems, DBMS, "
            "Data Structures & Algorithms, Networks, Compilers, Theory of Computation, "
            "Mathematics, and AI/ML), show prerequisite roadmaps, check institutional "
            "library catalog holdings and OPAC availability, look up research papers, "
            "and verify citations with exact page provenance.\n\n"
            "Try asking about **Operating Systems** (context switches, semaphores, deadlocks), "
            "**Database Systems** (B+ trees, ACID, 3NF), **Algorithms** (BFS vs DFS), "
            "**Computer Networks** (TCP congestion control), or **AI & Deep Learning** (Transformers, BERT, LoRA, RAG)!"
        )
        return "GREETING", text, None, {"hide_graph": True, "reason": "greeting"}

    clean_query = re.sub(r"\s*\([Ee]arlier user topics?:.*?\)", "", query or "").strip()
    if classify_query_intent(clean_query) == IntentCategory.CAPABILITY_INQUIRY:
        concept_count = len(getattr(graph, "nodes", {}) or {})
        text = (
            "Here is what **Archipelago** currently covers:\n\n"
            "- **Academic domains:** Computer Science (Operating Systems, Database Systems, "
            "Data Structures & Algorithms, Computer Networks, Compilers, Theory of Computation), "
            "Mathematics for Machine Learning, and AI & Deep Learning.\n"
            "- **Indexed books & PDFs:** Selected CS/AI textbooks and lecture PDFs with exact page-level citations.\n"
            f"- **Knowledge graph:** `{concept_count}` indexed concepts (concept nodes, not textbooks) "
            "linked by prerequisite, unlocks, and related-concept edges.\n"
            "- **Research Intelligence:** Saved scholarly paper collections, citation networks, and "
            "bibliometric runs (kept separate from the academic concept graph).\n"
            "- **Institutional library catalogue:** Live UEM Kolkata OPAC lookup with authorized "
            "Koha export snapshot fallback for physical holdings.\n"
            "- **Interactive learning:** Concept topology graphs, prerequisite roadmaps, and adaptive diagnostic quizzes."
        )
        return (
            "CAPABILITY_INQUIRY",
            text,
            None,
            {
                "hide_graph": True,
                "reason": "capability_inquiry",
                "score": 1.0,
                "intent_category": IntentCategory.CAPABILITY_INQUIRY.value,
            },
        )
    prior_match = re.search(r"\([Ee]arlier user topics?:\s*(.+?)\)", query or "")
    prior_topics = [t.strip() for t in prior_match.group(1).split(";") if t.strip()] if prior_match else []
    shelf_query = clean_query
    if prior_topics and re.search(r"\b(?:this|that|the)\s+book\b", clean_query, re.I):
        shelf_query = re.sub(
            r"\b(?:this|that|the)\s+book\b",
            prior_topics[-1],
            clean_query,
            count=1,
            flags=re.I,
        )

    # The indexed "Neural Network" node describes graph neural networks.
    # A basic neural-network definition must not cite that narrower passage.
    if re.fullmatch(
        r"(?:what is|define|explain)\s+(?:a|an)?\s*(?:artificial\s+)?neural networks?[?.!]*",
        clean_query,
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
    wants_hours = bool(SCHEDULE_RE.search(clean_query))
    wants_access = bool(AUTH_RE.search(clean_query)) and not SHELF_RE.search(clean_query)
    if wants_hours or wants_access:
        route = "SCHEDULE" if wants_hours and not wants_access else "AUTH_GATEWAY"
        return (
            route,
            compose.admin_card(clean_query, wants_hours, wants_access),
            None,
            {
                "hide_graph": True,
                "reason": "schedule_sheet" if wants_hours else "auth_gateway",
            },
        )

    # Contract type 5: uploaded-paper flow.
    if INGEST_RE.search(clean_query) and not SHELF_RE.search(clean_query):
        text, projection = ingestion_view.ingestion_reply(clean_query, graph)
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

    if any(term in clean_query.lower() for term in PASSING_MENTIONS):
        entity = next(term.strip() for term in PASSING_MENTIONS if term in clean_query.lower())
        text = (
            f"The library texts mention {entity} in passing as a dataset benchmark or infrastructure instance, "
            "but do not contain the theoretical documentation required to explain it. "
            "I cannot use external knowledge to fill in the gaps."
        )
        return "PASSING_MENTION", text, None, {"hide_graph": True, "reason": "passing_mention"}

    catalog_hit = self.catalog.reply(clean_query)
    # A learning request ("I want to learn X", "Teach me Y") is a
    # curriculum intent, not a book lookup. The catalog matcher fires on
    # the title words alone, so it used to swallow every curriculum prompt
    # before the diagnostic check could see it. Curriculum wins.
    # A relational prompt ("how does Softmax connect to Self-Attention?")
    # is the same story: the matcher saw "Attention" in a catalogue title
    # and answered with a book page instead of a traversal path.
    learning_request = bool(DIAG_RE.search(clean_query))
    relational_request = bool(RELATE_RE.search(clean_query))
    explain_request = bool(
        re.search(r"\b(?:explain|what\s+is|define|how\s+do|how\s+does)\b", clean_query, re.I)
    )
    if (
        catalog_hit
        and SOURCE_LOOKUP_RE.search(clean_query)
        and not SHELF_RE.search(clean_query)
        and not learning_request
        and not relational_request
        and not explain_request
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
        r"\b(show journal inventory|journal holdings|journal inventory|"
        r"what books are in the library|which books are in the library|show books in library|library inventory|"
        r"(?:what|which|show)\s+(?:os|dbms|dsa|algorithm|algorithms|database|databases|network|networks|operating\s+system|operating\s+systems)\s+(?:and\s+\w+\s+)?(?:books?|textbooks?)\b|"
        r"(?:what|which)\s+(?:os|dbms|dsa|algorithms?|database|databases|network|operating\s+system)s?\s+(?:and\s+\w+\s+)?(?:books?|textbooks?)\s+(?:do we have|are available|in the library)\b|"
        r"(?:os|dbms|dsa|algorithms?|database|network|operating\s+system)s?\s+(?:and\s+\w+\s+)?(?:books?|textbooks?)\s+(?:available|in\s+the\s+library))\b",
        re.I,
    )
    if LIB_INVENTORY_RE.search(clean_query):
        return (
            "LIBRARY_LOOKUP",
            compose.library_inventory_reply(self, clean_query),
            None,
            {
                "hide_graph": True,
                "reason": "library_inventory",
                "score": 1.0,
                "intent_category": IntentCategory.LIBRARY_LOOKUP.value,
            },
        )

    _CATALOG_AVAILABILITY_RE = re.compile(
        r"\b(?:is|are)\s+.+?\s+available\s+in\s+(?:the\s+)?(?:uem|uemk|campus|university)?\s*library\b"
        r"|\bdo\s+you\s+have\s+(?:any\s+)?books?\s+(?:about|on|for)\b",
        re.I,
    )
    if _CATALOG_AVAILABILITY_RE.search(clean_query):
        return self._route_shelf_query(shelf_query, best_score)

    special_book = special_book_reply(clean_query)
    if special_book is not None:
        return special_book

    research_topic = research_topic_reply(self, query, anchors, best_id, best_score, hits)
    if research_topic is not None:
        return research_topic

    _RESOURCE_CLAUSE_RE = re.compile(
        r"\s+(?:and|,)\s+(?:show|suggest|recommend|list|find|give(?:\s+me)?)\s+"
        r"(?:a\s+|an\s+|the\s+|relevant\s+|actual\s+|indexed\s+|any\s+|some\s+)*"
        r"(?:library\s+resources?|indexed\s+books?|books?|textbooks?|reading\s+resources?|references?)\b.*$",
        re.I,
    )
    concept_query = _RESOURCE_CLAUSE_RE.sub("", clean_query).strip() or clean_query
    extracted_concepts = extract_concept_mentions(concept_query, known_graph=graph)
    is_compare_or_relate = bool(RELATE_RE.search(clean_query)) or any(
        token in clean_query.lower() for token in COMPARE_CUES
    )
    is_single_unified_node = bool(
        len(extracted_concepts) == 2 and anchors and anchors[0] == "eigenvalues_and_eigenvectors"
    )
    if len(extracted_concepts) >= 3 or (
        len(extracted_concepts) == 2
        and not is_compare_or_relate
        and not is_single_unified_node
        and not learning_request
    ):
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
                    "paths": [
                        {
                            "source": source,
                            "target": target,
                            "hops": [hop.__dict__ for hop in path.hops],
                            "inferred_documents": path.shared_documents,
                        }
                        for (source, target), path in reasoning["paths"].items()
                    ],
                },
                "hide_graph": not bool(
                    (
                        primary
                        and (
                            graph.prereqs(primary, 1)
                            or graph.unlocks(primary, 1)
                            or graph.related(primary)
                        )
                    )
                    or re.search(r"\b(prerequisites?|roadmap|learning path|study plan)\b", query, re.I)
                ),
                "intent_category": IntentCategory.MULTI_CONCEPT.value,
            },
        )

    if WHERE_IS_RE.search(query):
        requested_title = inventory.extract_title(query)
        _record, title_score = inventory.best_record(catalogue.load_catalogue(), requested_title)
        if inventory.match_confidence(title_score) != "none":
            return self._route_shelf_query(shelf_query, best_score)

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
        return self._route_shelf_query(shelf_query, best_score)

    domains = compose.domain_pair(self, query)
    if domains and any(
        token in query.lower()
        for token in ("compare", "versus", "vs", "difference", "differ", "different")
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
            if any(token in query.lower() for token in COMPARE_CUES):
                return (
                    "CROSS_DOMAIN",
                    compose.matrix(self, left_id, right_id),
                    left_id,
                    {"score": best_score, "reason": "cross_domain"},
                )
            path = graph.shortest(left_id, right_id, limit=SHORTEST_PATH_LIMIT)
            if path is None:
                return (
                    "DISCONNECTED",
                    compose.disconnected(self, left_id, right_id),
                    left_id,
                    {"score": best_score, "reason": "no_path"},
                )
            return (
                "RELATION",
                compose.relation(self, left_id, right_id, path),
                left_id,
                {"score": best_score, "reason": "shortest_path"},
            )
        _is_compare = any(token in clean_query.lower() for token in COMPARE_CUES) and not re.search(
            r"\b(connect(?:ed)?|relat(?:e|ed|es|ion|ionship))\b", clean_query, re.I
        )
        _academic_compare = bool(
            left_ok
            or right_ok
            or anchors
            or ACADEMIC_DOMAIN_RE.search(clean_query)
            or re.search(
                r"\b(fcfs|sjf|scheduling|supervised|reinforcement|page|normalization|acid|lr|parsing|eigen|gradient|backprop|bfs|dfs|mutex|semaphore|tcp|udp)\b",
                clean_query,
                re.I,
            )
        )
        if _is_compare and _academic_compare:
            known_ids = [cid for cid in (left_id, right_id, *anchors[:2]) if cid and cid in graph.nodes]
            known_ids = list(dict.fromkeys(known_ids))
            parts = [compose.synthesis(self, cid) for cid in known_ids[:2]]
            draft = "\n\n".join(parts) if parts else ""
            note = (
                f"Compare **{left_text.strip(' ?.')}** and **{right_text.strip(' ?.')}** clearly, "
                "include a concrete worked example, and label general foundational knowledge separately from indexed catalog citations."
            )
            return (
                "GENERAL_EXPLANATION",
                f"{draft}\n\n{note}".strip(),
                known_ids[0] if known_ids else None,
                {"score": max(best_score, 0.8), "reason": "academic_comparison_general"},
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
                "Ask for an indexed academic concept across Operating Systems, DBMS, Algorithms, Networks, or Machine Learning."
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
        if ACADEMIC_DOMAIN_RE.search(query):
            return (
                "GENERAL_EXPLANATION",
                f"**{query.strip(' ?.')}** is a foundational academic topic that is not currently indexed "
                "as a standalone concept node in the local catalog. This explanation uses general "
                "foundational knowledge rather than local catalog citations.",
                None,
                {"hide_graph": True, "score": best_score, "reason": "academic_general_not_indexed"},
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

    if len(anchors) >= 2 and any(token in query.lower() for token in COMPARE_CUES):
        return (
            "CROSS_DOMAIN",
            compose.matrix(self, anchors[0], anchors[1]),
            anchors[0],
            {"score": best_score, "reason": "multi_anchor"},
        )

    target = anchors[0] if anchors else best_id
    if re.search(
        r"\b(recent\s+(?:studies|research|papers|advances)|latest\s+(?:findings|literature|works)|state of the art|sota)\b",
        query,
        re.I,
    ):
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
