"""Chat API streaming endpoint and concept bootstrap."""
from __future__ import annotations

import json
import logging
import re
import time

from flask import Response, request, jsonify

_logger = logging.getLogger(__name__)

_MS_PER_SECOND = 1000.0

from archipelago.inference.graph_lock import graph_lock
from archipelago.auth import require_student_or_open
from archipelago.inference import state as st
from archipelago.inference.ops_metrics import record_chat_request
from archipelago.inference.routing import resolve_query_routing
from archipelago.inference.neighborhood import (
    format_connected_via,
    get_graph_neighborhood,
    get_related_edges,
)
from archipelago.inference.curriculum import (
    find_curriculum_chains, format_curriculum_paths_section,
)
from archipelago.inference.citations import (
    build_concept_citation_map, build_citation_payloads, _resolve_printed_page,
)
from archipelago.inference.book_details import find_book_by_title, format_book_details_reply
from archipelago.inference.chat_enrichment import (
    STREAM_NO_BUFFER_HEADERS,
    extract_source_docs,
)
from archipelago.inference.stream_replies import (
    stream_graph_reply,
    stream_library_reply,
)
from archipelago.inference.reply_patterns import (
    classify_reply_pattern,
    pattern_log_label,
)
from archipelago.inference.roadmap_assessment import (
    detect_learning_intent,
    generate_self_report_probes,
)
from archipelago.inference.corpus_inventory import inventory_for_books
from archipelago.inference.demo_query_books import merge_demo_citations
from archipelago.inference.synthesis import (
    build_graph_notes, format_natural_fallback,
    general_chat_reply,
    render_library_books, render_library_chapters, render_library_chapter_lookup,
    identity_reply, onboarding_reply, not_indexed_reply, enforce_sterile_prose,
    render_journal_status, render_library_catalog,
    render_physical_resources,
    render_library_info, render_catalog_stats,
)
from archipelago.inference.library_queries import (
    get_books_for_topic, clean_topic_query, get_chapters_of_book, get_chapters_containing_concept,
    clean_catalog_query, clean_catalog_topic, clean_journal_query, find_journal_status,
)
from archipelago.inference.catalog_ops import format_citation
from archipelago.inference.scope_gate import (
    OUT_OF_SCOPE_MESSAGE,
    NOT_IN_CORPUS_MESSAGE,
    IMPLEMENTATION_REFUSAL_MESSAGE,
)
from archipelago.inference.library_scope import (
    AMBIGUOUS,
    IN_SCOPE,
    classify_library_scope,
)
from archipelago.inference.aliases import _node_name, generate_aliases
from archipelago.inference.embeddings import load_embedding_model, load_aura_model

from archipelago.inference.chat_bootstrap import note_chat_metric as _note_chat_metric, init_concepts_data


import os
import threading

_ACTIVE_REQUESTS_LOCK = threading.Lock()
_ACTIVE_CHAT_REQUESTS = 0
_MAX_CONCURRENT_REQUESTS = 12


def _get_system_memory_used_percent() -> float:
    try:
        if os.path.exists("/proc/meminfo"):
            mem_info = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        mem_info[parts[0].strip()] = int(parts[1].split()[0])
            total = mem_info.get("MemTotal", 1)
            available = mem_info.get("MemAvailable", total)
            return ((total - available) / total) * 100.0
    except Exception:
        pass
    return 0.0


def _check_workload_exceeded() -> tuple[bool, str]:
    global _ACTIVE_CHAT_REQUESTS
    with _ACTIVE_REQUESTS_LOCK:
        if _ACTIVE_CHAT_REQUESTS >= _MAX_CONCURRENT_REQUESTS:
            return True, f"Active chat requests cap reached ({_ACTIVE_CHAT_REQUESTS}/{_MAX_CONCURRENT_REQUESTS})"
    mem_pct = _get_system_memory_used_percent()
    if mem_pct > 95.0:
        return True, f"System memory near capacity ({mem_pct:.1f}% used)"
    return False, ""


@st.app.route("/api/chat", methods=["POST"])
@require_student_or_open
def api_chat():
    """Student-facing chat. No librarian upload/delete privileges."""
    from flask import Response
    req_data = request.get_json() or {}
    raw_query = (req_data.get("query") or req_data.get("message") or "").strip()
    # --- Security: Input sanitization ---
    # 1. Max query length to prevent DoS via huge payloads
    _MAX_QUERY_LEN = 2000
    if len(raw_query) > _MAX_QUERY_LEN:
        raw_query = raw_query[:_MAX_QUERY_LEN]
    # 2. Detect and reject HTML/script injection payloads
    _had_html_tags = bool(re.search(r"<\s*(?:script|img|iframe|object|embed|svg|link|style|form|input|meta|body|div|on\w+)\b", raw_query, re.IGNORECASE))
    # 3. Strip HTML/script tags to prevent reflected XSS
    query = re.sub(r"<[^>]*>", "", raw_query).strip()
    mode = req_data.get("mode", "rag_synthesis")
    history = req_data.get("history", [])
    t0 = time.perf_counter()

    if not query or _had_html_tags:
        if _had_html_tags:
            return jsonify({"error": "HTML/script payloads are not accepted"}), 400
        return jsonify({"error": "Query cannot be empty"}), 400

    is_overloaded, overload_reason = _check_workload_exceeded()
    if is_overloaded:
        _logger.warning(f"Workload exceeded: {overload_reason}")
        def generate_overload_stream():
            payload = {
                "anchor_concept": None,
                "prerequisites": [],
                "unlocks": [],
                "citations": [],
                "related_concepts": [],
                "routing": {"route": "workload_exceeded", "score": 0.0, "reason": overload_reason},
                "logs": [{
                    "step": "Workload Gate",
                    "status": "Capacity limit reached",
                    "details": overload_reason,
                }],
            }
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            yield (
                "⚠️ **Workload Exceeded**: The library server is processing peak queries right now. "
                "Please hold on a moment and retry your request!"
            )
        return Response(generate_overload_stream(), mimetype="text/plain")

    try:
        # Default product path: embedder ranking + graph traversal + natural reply.
        # conversational_agent uses the same smart router (domain → graph, chitchat → free chat).
        if mode in ("rag_synthesis", "conversational_agent"):
            scope_decision = classify_library_scope(query, history=history)
            if scope_decision.status != IN_SCOPE:
                route = "library_ambiguous" if scope_decision.status == AMBIGUOUS else "out_of_scope"
                response_text = scope_decision.response or OUT_OF_SCOPE_MESSAGE
                _note_chat_metric(
                    query,
                    route=route,
                    reason=scope_decision.reason,
                    t0=t0,
                    routing_ms=(time.perf_counter() - t0) * _MS_PER_SECOND,
                    slots={"intent": scope_decision.intent, "intent_method": "library_scope"},
                    score=scope_decision.confidence,
                )

                def generate_scope_boundary():
                    payload = {
                        "anchor_concept": None,
                        "prerequisites": [],
                        "unlocks": [],
                        "citations": [],
                        "related_concepts": [],
                        "routing": {
                            "route": route,
                            "score": scope_decision.confidence,
                            "reason": scope_decision.reason,
                        },
                        "logs": [{
                            "step": "Pass 0: Library Scope Gate",
                            "status": scope_decision.status,
                            "details": (
                                f"intent={scope_decision.intent}; "
                                f"matched_terms={','.join(scope_decision.matched_terms) or 'none'}; "
                                f"reason={scope_decision.reason}"
                            ),
                        }],
                    }
                    yield json.dumps(payload) + "\n[STREAM_START]\n"
                    yield response_text

                return Response(generate_scope_boundary(), mimetype="text/plain")

            # Check for multi-topic relationship query (e.g. "how X and Y are related", "X vs Y")
            from archipelago.inference.relationship_linking import evaluate_relationship_query
            rel_eval = evaluate_relationship_query(query)
            if rel_eval:
                def generate_relationship_stream():
                    payload = {
                        "anchor_concept": rel_eval.get("anchor_concept"),
                        "prerequisites": rel_eval.get("prerequisites") or [],
                        "unlocks": rel_eval.get("unlocks") or [],
                        "citations": rel_eval.get("citations") or [],
                        "related_concepts": rel_eval.get("related_concepts") or [],
                        "routing": {"route": "relationship_eval", "score": 1.0, "reason": rel_eval["status"]},
                        "logs": [{
                            "step": "Multi-Topic Relationship Evaluation",
                            "status": rel_eval["status"],
                            "details": "Evaluated relationship query for topics.",
                        }],
                    }
                    yield json.dumps(payload) + "\n[STREAM_START]\n"
                    yield rel_eval["reply"]
                return Response(generate_relationship_stream(), mimetype="text/plain")

            routing = resolve_query_routing(query, history=history)
            route = routing["route"]
            routing_ms = (time.perf_counter() - t0) * _MS_PER_SECOND
            _note_chat_metric(
                query,
                route=route,
                reason=str(routing.get("reason") or ""),
                t0=t0,
                routing_ms=routing_ms,
                slots=routing.get("slots") if isinstance(routing.get("slots"), dict) else {},
                score=routing.get("score") if isinstance(routing.get("score"), (int, float)) else None,
            )
            # Explicit synthesis flag still honored; default ON so answers are natural.
            wants_synthesis = req_data.get("synthesis", True) not in (False, "off", "none", 0, "0")

            # ── Out of Scope / defensive refusals (3 generic messages only) ─
            if route == "out_of_scope":
                reason = routing.get("reason", "out_of_scope_topic") or ""
                rl = reason.lower()
                intent_meta = (routing.get("slots") or {})
                if "implementation" in rl:
                    out_msg = IMPLEMENTATION_REFUSAL_MESSAGE
                    detail = (
                        f"Intent gate blocked implementation "
                        f"(intent={intent_meta.get('intent')}, "
                        f"method={intent_meta.get('intent_method')})."
                    )
                elif "not_in_corpus" in rl or "entity" in rl:
                    out_msg = NOT_IN_CORPUS_MESSAGE
                    detail = (
                        f"Intent gate: entity/trivia not grounded in corpus "
                        f"(intent={intent_meta.get('intent')})."
                    )
                elif "meta" in rl:
                    # Same sterile boundary as OOS — do not leak constraints
                    out_msg = OUT_OF_SCOPE_MESSAGE
                    detail = "Intent gate blocked meta / system-prompt extraction."
                else:
                    out_msg = OUT_OF_SCOPE_MESSAGE
                    detail = (
                        f"Out of AIML library scope "
                        f"(intent={intent_meta.get('intent')}, reason={reason})."
                    )

                closest = intent_meta.get("closest_concepts") or []
                # Soft "maybe you meant" bridge on every reject flavor that has
                # plausible graph neighbors — not just corpus misses.
                closest = [c for c in closest if c][:3]
                if closest:
                    bridge = ", ".join(f"**{c}**" for c in closest)
                    out_msg = (
                        f"{out_msg}\n\nIf you were after something nearby, the closest "
                        f"concepts on our shelves are: {bridge}."
                    )

                def generate_out_of_scope():
                    payload = {
                        "anchor_concept": None,
                        "prerequisites": [],
                        "unlocks": [],
                        "citations": [],
                        "related_concepts": [],
                        "routing": {"route": route, "score": 0.0, "reason": reason},
                        "logs": [{
                            "step": "Pass 1: Intent Gate & Scope",
                            "status": "Out of Scope",
                            "details": detail,
                        }],
                    }
                    yield json.dumps(payload) + "\n[STREAM_START]\n"
                    yield out_msg
                return Response(generate_out_of_scope(), mimetype="text/plain")

            from archipelago.inference.routes_chat_library import handle_library_route
            lib_resp = handle_library_route(route, query, routing, history, wants_synthesis)
            if lib_resp is not None:
                return lib_resp


            # ── Learning Roadmap self-report probes (Track B — only when prereqs > 2)
            lr_concept_id, is_lr = detect_learning_intent(query)
            if is_lr and lr_concept_id and lr_concept_id in st.CONCEPTS_DATA:
                from archipelago.inference.roadmap_assessment import has_sufficient_prereqs_for_assessment
                if has_sufficient_prereqs_for_assessment(lr_concept_id):
                    lr_cdata = st.CONCEPTS_DATA[lr_concept_id]
                    lr_name = lr_cdata.get("label") or lr_cdata.get("name") or lr_concept_id
                    lr_probes = generate_self_report_probes(lr_concept_id)
                    # Ranked book/paper for the target hop (S15)
                    try:
                        from archipelago.inference.unified_ranking import rank_resources
                        hop_books = rank_resources(lr_name, limit=2)
                    except Exception:
                        hop_books = []

                    def generate_roadmap_assessment():
                        payload = {
                            "anchor_concept": {"id": lr_concept_id, "label": lr_name},
                            "prerequisites": [],
                            "unlocks": [],
                            "citations": [],
                            "related_concepts": routing.get("related") or [],
                            "mode": "roadmap_probe",
                            "roadmap_probe": True,
                            "roadmap_data": {
                                "target_concept_id": lr_concept_id,
                                "target_concept_name": lr_name,
                                "mode": "self_report",
                                "probes": lr_probes,
                                "questions": lr_probes,  # back-compat UI key
                                "total_questions": len(lr_probes),
                                "total_probes": len(lr_probes),
                                "ranked_for_target": hop_books,
                            },
                            "routing": {
                                "route": "learning_roadmap",
                                "score": routing.get("score"),
                                "reason": "learning_roadmap_self_report",
                            },
                            "logs": [{
                                "step": "Learning Roadmap Assessment",
                                "status": "Self-report probes",
                                "details": (
                                    f"Detected learning intent for '{lr_name}' (prereqs > 2). "
                                    f"Generated {len(lr_probes)} self-report probes."
                                ),
                            }],
                        }
                        yield json.dumps(payload) + "\n[STREAM_START]\n"
                        intro = (
                            f"Great — let me build a personalized learning path to **{lr_name}**.\n\n"
                            f"I've got **{len(lr_probes)} quick self-checks** on foundational concepts. "
                            f"Select any options you already know (or **None of these**):\n\n"
                        )
                        if hop_books:
                            top = hop_books[0]
                            intro += (
                                f"**Shelf tip for this target:** "
                                f"{top.get('title') or 'see ranking'} "
                                f"({top.get('kind') or 'resource'})"
                            )
                        yield intro

                    return Response(generate_roadmap_assessment(), mimetype="text/plain")
                # If prereqs <= 2, fall through to graph path directly!
                routing["anchor_id"] = lr_concept_id
                routing["route"] = "graph_strong"

            # Learning intent but target not in graph yet
            if is_lr and lr_concept_id and lr_concept_id not in st.CONCEPTS_DATA:
                def generate_missing_target():
                    payload = {
                        "anchor_concept": None,
                        "prerequisites": [],
                        "unlocks": [],
                        "citations": [],
                        "related_concepts": [],
                        "mode": "roadmap_missing",
                        "routing": {
                            "route": "learning_roadmap",
                            "score": 0.0,
                            "reason": "target_not_in_graph",
                        },
                        "logs": [{
                            "step": "Learning Roadmap",
                            "status": "Not indexed",
                            "details": f"Target '{lr_concept_id}' not in CONCEPTS_DATA",
                        }],
                    }
                    yield json.dumps(payload) + "\n[STREAM_START]\n"
                    yield (
                        f"I don't have **{lr_concept_id.replace('_', ' ')}** in the "
                        f"indexed concept graph yet — so I can't build a prerequisite "
                        f"path. Try a pilot topic (LoRA, RAG, attention, transformers) "
                        f"or ask the librarian to ingest more domain docs."
                    )

                return Response(generate_missing_target(), mimetype="text/plain")

            # ── Library Routes (books, chapters, catalog, info, citations, reject) ──
            from archipelago.inference.routes_chat_library import handle_library_route
            lib_resp = handle_library_route(route, query, routing, history, wants_synthesis)
            if lib_resp is not None:
                return lib_resp


            # ── General chat (low similarity / chitchat) ──────────────────────
            if route == "general_chat":
                def generate_general():
                    payload = {
                        "anchor_concept": None,
                        "prerequisites": [],
                        "unlocks": [],
                        "citations": [],
                        "related_concepts": routing.get("related") or [],
                        "routing": {"route": route, "score": routing.get("score"), "reason": routing.get("reason")},
                        "logs": [{
                            "step": "Pass 1: Intent & Embedder Gate",
                            "status": "General chat",
                            "details": f"Similarity too low for graph grounding. Free conversational reply.",
                        }],
                    }
                    yield json.dumps(payload) + "\n[STREAM_START]\n"
                    yield general_chat_reply(query, history)
                return Response(generate_general(), mimetype="text/plain")

            # ── Graph path (strong or soft domain) ────────────────────────────
            from archipelago.inference.routes_chat_graph import handle_graph_route
            return handle_graph_route(route, query, routing, history, wants_synthesis)
        else:
            return jsonify({"error": f"Invalid mode: {mode}"}), 400
    except Exception as exc:
        _logger.exception(f"Unhandled exception in api_chat: {exc}")
        def generate_error_safeguard():
            payload = {
                "anchor_concept": None,
                "prerequisites": [],
                "unlocks": [],
                "citations": [],
                "related_concepts": [],
                "routing": {"route": "error_safeguard", "score": 0.0, "reason": str(exc)},
                "logs": [{
                    "step": "Error Safeguard",
                    "status": "Recovered",
                    "details": f"Handled exception: {exc}",
                }],
            }
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            yield (
                "I encountered a transient issue processing your request. "
                "The library is active — please rephrase your query or ask about an indexed concept!"
            )
        return Response(generate_error_safeguard(), mimetype="text/plain")

