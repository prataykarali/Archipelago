"""Primary chat inference route: 3-tier guardrailed graph synthesis pipeline."""

from __future__ import annotations

import logging
from typing import Any

from flask import Response, jsonify, request

from archipelago.api import engine_state as state
from archipelago.api.contract_handlers import direct_intent_reply, guardrail_text
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
from archipelago.core.contract import (
    GRAPH_SYNTHESIS,
    GUARDRAIL_INTERCEPT,
    contract_for,
    graph_decision,
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


def _score_query(term: str) -> tuple[float, Any]:
    """Scoring callback handed to the router for anchor resolution."""
    hits = state._retriever.resolve_anchor(term, top_k=ANCHOR_TOP_K)
    if hits:
        cid, score = hits[0]
        name = concept_name(cid)
        exact = term.strip().lower() in (cid.lower(), name.lower())
        return score, {"id": cid, "exact_alias": exact}
    return 0.0, None


def _contract_payload(status: str, contract: str, **fields: Any) -> dict[str, Any]:
    """Stamp every chat response with its contract and graph-render decision.

    The UI draws the in-chat graph from ``render_graph``.  Deriving it here, from
    the contract, rather than leaving each branch to remember, is what makes the
    show/hide protocol deterministic.
    """
    decision = graph_decision(contract)
    return {
        "status": status,
        "contract": contract,
        "render_graph": decision.render,
        "render_rule": decision.rule,
        **fields,
    }


def _handle_mcq_diagnostic(norm_q: str):
    """Contract type 4: the diagnostic MCQ payload for a learning request."""
    anchor_hits = state._retriever.resolve_anchor(norm_q, top_k=ANCHOR_TOP_K)
    anchor_id = anchor_hits[0][0] if anchor_hits else DEFAULT_ANCHOR
    anchor_label = concept_name(anchor_id)
    prereqs = state._retriever.get_upstream_prerequisites(anchor_id, max_hops=1)
    mcq_payload = state._synthesis.generate_diagnostic_mcq(anchor_label, prereqs)
    return jsonify(
        _contract_payload(
            "success",
            contract_for("mcq_diagnostic"),
            intent=QueryIntent.MCQ_DIAGNOSTIC.value,
            quiz=mcq_payload,
        )
    ), SUCCESS_STATUS


def _handle_direct_intents(intent: str | None, norm_q: str):
    """Answer a non-graph contract intent; ``None`` when the pipeline continues."""
    if not intent:
        return None

    reply = direct_intent_reply(intent, norm_q)
    if reply is not None:
        return jsonify(reply), SUCCESS_STATUS

    if intent == QueryIntent.MCQ_DIAGNOSTIC.value:
        return _handle_mcq_diagnostic(norm_q)

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
            _contract_payload(
                "rejected",
                GUARDRAIL_INTERCEPT,
                tier=tier,
                text=routing_result.get("message") or SECURITY_BOUNDARY_MESSAGE,
                citations=[],
                topology=None,
            )
        ), REJECTED_STATUS

    if route == "out_of_scope":
        # A guardrail intercept and a plain scope deflection share this pipeline
        # stage but not their wording: the former owes the reader an explanation
        # of *why* code or a recipe is out of bounds.
        body = OUT_OF_SCOPE_MESSAGE
        if intent == GUARDRAIL_INTERCEPT:
            body = guardrail_text(norm_q)
        return jsonify(
            _contract_payload(
                "out_of_scope",
                GUARDRAIL_INTERCEPT,
                tier=tier,
                intent=intent,
                text=body,
                citations=[],
                topology=None,
            )
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
            _contract_payload(
                "suggest_topics",
                contract_for("suggest_topics"),
                tier=tier,
                intent=QueryIntent.TOPIC_SUGGESTION.value,
                **suggestion_payload,
            )
        ), SUCCESS_STATUS

    # Step 4: Tier 1 Execute (GRAPH_SYNTHESIS)
    resolved = _resolve_anchor(routing_result, norm_q)
    anchor_id = resolved["anchor_id"]

    if not anchor_id:
        candidates = state._retriever.suggest_topics(norm_q, top_k=MAX_TOPIC_SUGGEST_FALLBACK)
        return jsonify(
            _contract_payload(
                "suggest_topics",
                contract_for("suggest_topics"),
                tier=RoutingTier.TIER_2_SUGGEST.value,
                **state._synthesis.generate_topic_suggestions(norm_q, candidates),
            )
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
        _contract_payload(
            "success",
            GRAPH_SYNTHESIS,
            tier=tier,
            intent=QueryIntent.GRAPH_SYNTHESIS.value,
            **response_data,
        )
    ), SUCCESS_STATUS
