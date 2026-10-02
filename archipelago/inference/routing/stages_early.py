"""Early routing stages: library intent, suggested demos, social short-circuits."""
from __future__ import annotations

from archipelago.inference.intent_gate import (
    INTENT_OUT_OF_DOMAIN,
    INTENT_SOCIAL,
    REASON_OUT_OF_SCOPE,
)

from . import _deps as _rt
from .constants import _SUGGESTED_QUERY_ANCHORS, _TECHNICAL_MARKERS


def early_route(q_raw: str, library: dict | None) -> dict | None:
    """Library intents, demo suggested queries, and personal-dataset blocks."""
    if library:
        lib_intent = library["intent"]
        lib_route = lib_intent
        return {
            "anchor_id": None,
            "score": 1.0,
            "related": [],
            "slots": {key: value for key, value in library.items() if key != "raw"},
            "scope": "yes",
            "route": lib_route,
            "reason": lib_intent,
        }

    from archipelago.inference.demo_query_books import match_demo_query_key
    suggested_key = match_demo_query_key(q_raw)
    suggested_anchor = _SUGGESTED_QUERY_ANCHORS.get(suggested_key or "")
    if suggested_anchor:
        from archipelago.inference.intent_gate import classify_intent as classify_suggested_intent
        suggested_intent = classify_suggested_intent(q_raw)
        suggested_block = _rt.intent_to_block_reason(suggested_intent["intent"], suggested_intent["score"])
        if suggested_block:
            return {
                "anchor_id": None,
                "score": suggested_intent["score"],
                "related": [],
                "slots": {
                    "intent": suggested_intent["intent"],
                    "intent_method": suggested_intent["method"],
                    "suggested_query": suggested_key,
                },
                "scope": "no",
                "route": "out_of_scope",
                "reason": suggested_block,
            }
        return {
            "anchor_id": suggested_anchor,
            "score": 1.0,
            "related": [],
            "slots": {"suggested_query": suggested_key},
            "scope": "yes",
            "route": "graph_strong",
            "reason": "suggested_query_grounded_route",
        }

    if "my dataset" in q_raw.lower() or "my data" in q_raw.lower():
        return {
            "anchor_id": None,
            "score": 1.0,
            "related": [],
            "slots": {"intent": INTENT_OUT_OF_DOMAIN, "intent_method": "direct_block"},
            "scope": "no",
            "route": "out_of_scope",
            "reason": REASON_OUT_OF_SCOPE,
        }

    return None


def social_short_circuit(q_raw: str, q: str, search_q: str) -> dict | None:
    """Pure greetings and identity asks short-circuit before intent/LLM."""
    del q  # kept in the signature for pipeline symmetry
    # Pure greetings short-circuit BEFORE intent/LLM (cheap + stable)
    if _rt._is_chitchat(q_raw) and not _TECHNICAL_MARKERS.search(search_q or q_raw):
        return {
            "anchor_id": None,
            "score": 1.0,
            "related": [],
            "slots": {"intent": INTENT_SOCIAL, "intent_method": "chitchat_short_circuit"},
            "scope": "yes",
            "route": "general_chat",
            "reason": "chitchat",
        }

    # Identity short-circuit BEFORE the intent gate: "who are you" style asks
    # are self-introduction requests, never entity trivia about a person — the
    # embedder cannot tell them apart, so we route on the deterministic matcher.
    if _rt._is_identity(q_raw) and not _TECHNICAL_MARKERS.search(search_q or q_raw):
        return {
            "anchor_id": None,
            "score": 1.0,
            "related": [],
            "slots": {"intent": INTENT_SOCIAL, "intent_method": "identity_short_circuit"},
            "scope": "yes",
            "route": "identity",
            "reason": "identity",
        }

    return None
