"""Chat API streaming endpoint — validation, cache, gateway, routing dispatch."""

from __future__ import annotations

import json

from flask import Response, jsonify, request

from archipelago.auth import require_student_or_open
from archipelago.core.intent import IntentCategory, classify_query_intent
from archipelago.core.multi_hop import extract_concept_mentions
from archipelago.inference import state as st
from archipelago.inference.rate_limit import check_chat_rate_limit, rate_limit_response
from archipelago.inference.routes.chat.part02_simple_routes import (
    handle_identity,
    handle_onboarding,
    handle_out_of_scope,
    handle_roadmap_between,
    handle_roadmap_quiz,
    handle_roadmap_quiz_eval,
    handle_small_talk,
)
from archipelago.inference.routes.chat.part03_library_routes import (
    handle_library_book_details,
    handle_library_books,
    handle_library_chapter_lookup,
    handle_library_chapters,
    handle_library_holdings,
    handle_library_hours,
    handle_library_materials,
    handle_library_resources,
)
from archipelago.inference.routes.chat.part04_fallback_routes import (
    handle_general_chat,
    handle_low_similarity_reject,
)
from archipelago.inference.routes.chat.part05_graph_path import handle_graph_path
from archipelago.inference.routing import resolve_query_routing

ROUTE_ALIASES = {
    "library_resource_lookup": "library_holdings",
    "library_journal_status": "library_holdings",
    "library_catalog_stats": "library_holdings",
}

ROUTE_HANDLERS = {
    "out_of_scope": handle_out_of_scope,
    "identity": handle_identity,
    "roadmap_quiz": handle_roadmap_quiz,
    "roadmap_quiz_eval": handle_roadmap_quiz_eval,
    "roadmap_between": handle_roadmap_between,
    "onboarding": handle_onboarding,
    "small_talk": handle_small_talk,
    "library_book_details": handle_library_book_details,
    "library_resources": handle_library_resources,
    "library_hours": handle_library_hours,
    "library_materials": handle_library_materials,
    "library_holdings": handle_library_holdings,
    "library_books": handle_library_books,
    "library_chapters": handle_library_chapters,
    "library_chapter_lookup": handle_library_chapter_lookup,
    "low_similarity_reject": handle_low_similarity_reject,
    "general_chat": handle_general_chat,
}


@st.app.route("/api/chat", methods=["POST"])
@require_student_or_open
def api_chat():
    """Student-facing chat. No librarian upload/delete privileges."""
    req_data = request.get_json() or {}
    query = (req_data.get("query") or req_data.get("message") or "").strip()
    mode = req_data.get("mode", "rag_synthesis")
    history = req_data.get("history", [])

    if not query:
        return jsonify({"error": "Query cannot be empty"}), 400
    if len(query) < 2:
        return jsonify({"error": "Query too short (minimum 2 characters)"}), 400
    if len(query) > 500:
        return jsonify({"error": "Query exceeds maximum limit of 500 characters"}), 400

    # Every question runs against current retrieval and synthesis. Limit requests
    # before any provider call; the client supplied session id is not a rate key.
    allowed, limit_info = check_chat_rate_limit(request)
    if not allowed:
        return rate_limit_response(limit_info if isinstance(limit_info, dict) else None)

    # Gateway Interceptor & Subagents (Zero LLM API calls for attacks, code-gen, homework)
    from archipelago.inference.orchestration.subagents import AuthGatewayAgent, OrchestratorAgent

    interceptor = OrchestratorAgent().intercept(query)
    if interceptor.get("status") == "denied":

        def generate_denied():
            payload = {
                "anchor_concept": None,
                "prerequisites": [],
                "unlocks": [],
                "citations": [],
                "related_concepts": [],
                "routing": {
                    "route": "gateway_blocked",
                    "score": 1.0,
                    "reason": interceptor.get("reason"),
                },
                "logs": [
                    {
                        "step": "Gateway Firewall",
                        "status": "Blocked",
                        "details": interceptor.get("reason"),
                    }
                ],
            }
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            yield interceptor.get("reason") + "\n"

        return Response(generate_denied(), mimetype="text/plain")

    # Check institutional auth gateway card
    auth_card = AuthGatewayAgent().require_auth(query)
    if "[RENDER_AUTH_CARD]" in auth_card:

        def generate_auth():
            payload = {
                "anchor_concept": None,
                "prerequisites": [],
                "unlocks": [],
                "citations": [],
                "related_concepts": [],
                "routing": {
                    "route": "auth_gateway",
                    "score": 1.0,
                    "reason": "institutional_paywall",
                },
                "logs": [
                    {
                        "step": "Auth Gateway",
                        "status": "Success",
                        "details": "Institutional authentication card triggered.",
                    }
                ],
            }
            yield json.dumps(payload) + "\n[STREAM_START]\n"
            yield auth_card + "\n"

        return Response(generate_auth(), mimetype="text/plain")

    # Default product path: embedder ranking + graph traversal + natural reply.
    # conversational_agent uses the same smart router (domain → graph, chitchat → free chat).
    if mode in ("rag_synthesis", "conversational_agent"):
        from archipelago.inference.multi_anchor import query_anchor_ids, resolve_followup_query

        if history and not st.CONCEPTS_DATA:
            from archipelago.inference.routes.chat.part07_init import init_concepts_data

            init_concepts_data()
        resolved_query = resolve_followup_query(query, history)
        intent_category = classify_query_intent(
            resolved_query, extracted_concepts=extract_concept_mentions(resolved_query)
        )
        if intent_category == IntentCategory.RESEARCH_INTELLIGENCE:

            def generate_research_handoff():
                yield (
                    json.dumps(
                        {
                            "anchor_concept": None,
                            "subgraph": None,
                            "prerequisites": [],
                            "unlocks": [],
                            "diagnostic_mcqs": [],
                            "citations": [],
                            "routing": {
                                "route": "research_intelligence",
                                "reason": "delegated_to_research_pipeline",
                            },
                            "intent_category": IntentCategory.RESEARCH_INTELLIGENCE.value,
                            "logs": [
                                {
                                    "step": "Research intelligence",
                                    "status": "Delegated",
                                    "details": "Authorized research pipeline",
                                }
                            ],
                        }
                    )
                    + "\n[STREAM_START]\n"
                )
                yield "Research intelligence runs in the authorized [research pipeline](/research). Open a topic or author record there to request bibliometric analysis. This chat has not calculated metrics for the request."

            return Response(generate_research_handoff(), mimetype="text/plain")
        if intent_category in (
            IntentCategory.PAPER_LOOKUP,
            IntentCategory.MULTI_CONCEPT,
            IntentCategory.RESEARCH_TOPIC,
        ):
            if not st.CONCEPTS_DATA:
                from archipelago.inference.routes.chat.part07_init import init_concepts_data

                init_concepts_data()
            anchors = query_anchor_ids(resolved_query)
            if anchors or intent_category == IntentCategory.PAPER_LOOKUP:
                return handle_graph_path(
                    resolved_query,
                    history,
                    {
                        "route": "graph_strong",
                        "anchor_id": anchors[0] if anchors else None,
                        "related": [],
                        "score": 1.0 if anchors else 0.0,
                        "reason": "intent_aware_exact_match",
                        "slots": {},
                    },
                    wants_synthesis=False,
                )
        routing = resolve_query_routing(query, history=history)
        if intent_category == IntentCategory.LIBRARY_LOOKUP and routing.get("route") in (
            "out_of_scope",
            "low_similarity_reject",
        ):
            return handle_library_holdings(query, history, {"route": "library_holdings"}, False)
        route = ROUTE_ALIASES.get(routing["route"], routing["route"])
        if route == "library_info":
            slots = routing.get("slots") or {}
            route = (
                "library_resources"
                if (slots.get("resource_access") or slots.get("resource_key"))
                else "library_hours"
            )
        # Explicit synthesis flag still honored; default ON so answers are natural.
        wants_synthesis = req_data.get("synthesis", True) not in (False, "off", "none", 0, "0")

        handler = ROUTE_HANDLERS.get(route)
        if handler is not None:
            return handler(query, history, routing, wants_synthesis)
        return handle_graph_path(query, history, routing, wants_synthesis)

    return jsonify({"error": f"Invalid mode: {mode}"}), 400
