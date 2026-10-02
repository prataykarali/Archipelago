"""Primary chat inference route: 3-tier guardrailed graph synthesis pipeline."""

from __future__ import annotations

import logging
from typing import Any

from flask import Response, jsonify, request

from archipelago.api import engine_state as state
from archipelago.api.engine_state import (
    DEFAULT_ANCHOR,
    DEFAULT_DIFFICULTY,
    EVIDENCE_CHUNK_LIMIT,
    MAX_DOWNSTREAM_HOPS,
    MAX_TOPIC_SUGGEST_FALLBACK,
    MAX_UPSTREAM_HOPS,
    TOPIC_SUGGEST_LIMIT,
    app,
    concept_name,
    concept_node,
    ensure_engine,
)
from archipelago.core.router import (
    OUT_OF_SCOPE_MESSAGE,
    SECURITY_BOUNDARY_MESSAGE,
    QueryIntent,
    RoutingTier,
)

logger = logging.getLogger("archipelago.api")

REJECTED_STATUS = 400
SUCCESS_STATUS = 200
ANCHOR_TOP_K = 1
MIN_DUAL_ENTITIES = 2
CATALOG_SHELF_FALLBACK = (
    "The catalog shelf coordinates are located in Central Library Stack Room A (Floors 2 & 3)."
)
AUTH_GATEWAY_FALLBACK = (
    "Institutional e-resources (NDLI, IEEE Xplore, Scopus, ScienceDirect) are accessible "
    "via the Central Library Portal using your institutional SSO credentials."
)


def _score_query(term: str) -> tuple[float, Any]:
    """Scoring callback handed to the router for anchor resolution."""
    hits = state._retriever.resolve_anchor(term, top_k=ANCHOR_TOP_K)
    if hits:
        cid, score = hits[0]
        name = concept_name(cid)
        exact = term.strip().lower() in (cid.lower(), name.lower())
        return score, {"id": cid, "exact_alias": exact}
    return 0.0, None


def _catalog_shelf_answer() -> str:
    """Subject-wise holdings summary, with a stack-room fallback."""
    try:
        from archipelago.inference.catalog_ops import subject_title_counts

        counts = subject_title_counts(limit=TOPIC_SUGGEST_LIMIT)
        lines = ["### Institutional Library Holdings\n"]
        for c in counts:
            lines.append(
                f"- **{c.get('subject')}**: {c.get('title_count')} titles available in stacks"
            )
        return "\n".join(lines)
    except Exception:
        return CATALOG_SHELF_FALLBACK


def _auth_gateway_answer(norm_q: str) -> str:
    """Redacted institutional access guidance."""
    try:
        from archipelago.inference.eresource_credentials import format_credential_reply

        return format_credential_reply(norm_q)
    except Exception:
        return AUTH_GATEWAY_FALLBACK


def _handle_direct_intents(intent: str, norm_q: str):
    """Answer catalog/auth/MCQ intents directly; None when the pipeline continues."""
    if intent == QueryIntent.CATALOG_SHELF_ROUTING.value:
        return jsonify(
            {
                "status": "success",
                "intent": intent,
                "text": _catalog_shelf_answer(),
                "citations": [],
            }
        ), SUCCESS_STATUS

    if intent == QueryIntent.AUTH_GATEWAY.value:
        return jsonify(
            {
                "status": "success",
                "intent": intent,
                "text": _auth_gateway_answer(norm_q),
                "citations": [],
            }
        ), SUCCESS_STATUS

    if intent == QueryIntent.MCQ_DIAGNOSTIC.value:
        anchor_hits = state._retriever.resolve_anchor(norm_q, top_k=ANCHOR_TOP_K)
        anchor_id = anchor_hits[0][0] if anchor_hits else DEFAULT_ANCHOR
        anchor_label = concept_name(anchor_id)
        prereqs = state._retriever.get_upstream_prerequisites(anchor_id, max_hops=1)
        mcq_payload = state._synthesis.generate_diagnostic_mcq(anchor_label, prereqs)
        return jsonify(
            {
                "status": "success",
                "intent": intent,
                "quiz": mcq_payload,
            }
        ), SUCCESS_STATUS

    return None


def _resolve_anchor(routing_result: dict, norm_q: str) -> dict:
    """Resolve the graph anchor, preferring a dual-entity shortest path."""
    dual_ents = routing_result.get("dual_entities") or []
    if len(dual_ents) >= MIN_DUAL_ENTITIES:
        anchor_hits = state._retriever.resolve_anchor(dual_ents[0], top_k=ANCHOR_TOP_K)
        if anchor_hits:
            anchor_id = anchor_hits[0][0]
            info = concept_node(anchor_id)
            return {
                "path": state._retriever.find_shortest_path(dual_ents[0], dual_ents[1]),
                "anchor_id": anchor_id,
                "anchor_name": concept_name(anchor_id, info),
                "difficulty": info.get("difficulty", DEFAULT_DIFFICULTY),
            }

    anchor_hits = state._retriever.resolve_anchor(norm_q, top_k=ANCHOR_TOP_K)
    if anchor_hits:
        anchor_id = anchor_hits[0][0]
        info = concept_node(anchor_id)
        return {
            "path": None,
            "anchor_id": anchor_id,
            "anchor_name": concept_name(anchor_id, info),
            "difficulty": info.get("difficulty", DEFAULT_DIFFICULTY),
        }

    return {"path": None, "anchor_id": None, "anchor_name": "", "difficulty": DEFAULT_DIFFICULTY}


@app.route("/api/chat", methods=["POST"])
def api_chat() -> Response:
    """Primary inference endpoint executing the complete 3-Tier Guardrailed Pipeline."""
    req_data = request.get_json(silent=True) or {}
    query = req_data.get("query") or req_data.get("message") or ""
    stream = bool(req_data.get("stream") or request.args.get("stream") == "true")

    ensure_engine()

    # Step 1: Firewall & 3-Tier Routing
    routing_result = state._router.route_query(query, retriever_fn=_score_query)
    route = routing_result["route"]
    tier = routing_result["tier"]
    intent = routing_result.get("intent")
    norm_q = routing_result.get("normalized_query", query)

    if route == "rejected":
        return jsonify(
            {
                "status": "rejected",
                "tier": tier,
                "text": routing_result.get("message") or SECURITY_BOUNDARY_MESSAGE,
                "citations": [],
                "topology": None,
            }
        ), REJECTED_STATUS

    if route == "out_of_scope":
        return jsonify(
            {
                "status": "out_of_scope",
                "tier": tier,
                "text": OUT_OF_SCOPE_MESSAGE,
                "citations": [],
                "topology": None,
            }
        ), SUCCESS_STATUS

    # Step 2: Handle Non-Graph Direct Intents
    direct = _handle_direct_intents(intent, norm_q)
    if direct is not None:
        return direct

    # Step 3: Handle Tier 2 / TOPIC_SUGGESTION
    if route == "suggest_topics" or intent == QueryIntent.TOPIC_SUGGESTION.value:
        candidates = state._retriever.suggest_topics(norm_q, top_k=TOPIC_SUGGEST_LIMIT)
        suggestion_payload = state._synthesis.generate_topic_suggestions(norm_q, candidates)
        return jsonify(
            {
                "status": "suggest_topics",
                "tier": tier,
                "intent": QueryIntent.TOPIC_SUGGESTION.value,
                **suggestion_payload,
            }
        ), SUCCESS_STATUS

    # Step 4: Tier 1 Execute (GRAPH_SYNTHESIS)
    resolved = _resolve_anchor(routing_result, norm_q)
    anchor_id = resolved["anchor_id"]

    if not anchor_id:
        candidates = state._retriever.suggest_topics(norm_q, top_k=MAX_TOPIC_SUGGEST_FALLBACK)
        return jsonify(
            {
                "status": "suggest_topics",
                "tier": RoutingTier.TIER_2_SUGGEST.value,
                **state._synthesis.generate_topic_suggestions(norm_q, candidates),
            }
        ), SUCCESS_STATUS

    prereqs = state._retriever.get_upstream_prerequisites(anchor_id, max_hops=MAX_UPSTREAM_HOPS)
    unlocks = state._retriever.get_downstream_unlocks(anchor_id, max_hops=MAX_DOWNSTREAM_HOPS)
    chunks = state._retriever.get_evidence_chunks(anchor_id, max_chunks=EVIDENCE_CHUNK_LIMIT)

    # Step 5: Isolated Context Assembly
    payload = state._assembler.assemble_payload(
        query=norm_q,
        anchor_name=resolved["anchor_name"],
        difficulty=resolved["difficulty"],
        prerequisites=prereqs,
        unlocks=unlocks,
        chunks=chunks,
        path=resolved["path"],
    )

    # Step 6: Local SLM Synthesis
    if stream:
        return Response(
            state._synthesis.synthesize_response(payload, stream=True), mimetype="text/event-stream"
        )

    response_data = state._synthesis.synthesize_response(payload, stream=False)
    return jsonify(
        {
            "status": "success",
            "tier": tier,
            "intent": QueryIntent.GRAPH_SYNTHESIS.value,
            **response_data,
        }
    ), SUCCESS_STATUS
