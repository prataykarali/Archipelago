"""Chat API streaming endpoint — validation, cache, gateway, routing dispatch."""

from __future__ import annotations

import json

from flask import Response, jsonify, request

from archipelago.auth import require_student_or_open
from archipelago.inference import state as st
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

    # Supabase Cache Lookup & Metrics (Zero LLM calls on cache hit)
    try:
        from archipelago.inference.cache_metrics import metrics as cache_metrics
        from archipelago.inference.cache_service import CacheService

        cache_metrics.inc_total_requests()
        cached_entry = CacheService().get_cached_response(query)
        if cached_entry:
            cache_metrics.inc_cache_hit(tokens_saved=300)

            def generate_cached():
                payload = {
                    "anchor_concept": None,
                    "prerequisites": [],
                    "unlocks": [],
                    "citations": cached_entry.get("sources") or [],
                    "related_concepts": [],
                    "routing": {"route": "cached_response", "score": 1.0, "reason": "cache_hit"},
                    "graph_data": cached_entry.get("graph_data"),
                    "roadmap": cached_entry.get("roadmap_data"),
                    "logs": [
                        {
                            "step": "Supabase Cache",
                            "status": "Hit",
                            "details": f"Cached response returned (hit #{cached_entry.get('hit_count', 1)}). Zero LLM tokens consumed.",
                        }
                    ],
                }
                yield json.dumps(payload) + "\n[STREAM_START]\n"
                yield str(cached_entry.get("response") or "") + "\n"

            return Response(generate_cached(), mimetype="text/plain")
        else:
            cache_metrics.inc_cache_miss()
    except Exception:
        pass

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
        routing = resolve_query_routing(query, history=history)
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
