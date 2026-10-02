"""Chat route handlers: low-similarity reject and general chat fallbacks."""

from __future__ import annotations

import json

from flask import Response

from archipelago.inference import state as st
from archipelago.inference.routes.chat.part00_shared import with_holdings
from archipelago.inference.synthesis import (
    enforce_sterile_prose,
    general_chat_reply,
    not_indexed_reply,
)


def handle_low_similarity_reject(query, history, routing, wants_synthesis):
    """Honest not-indexed reply when similarity is below threshold."""
    sterile = bool((routing.get("slots") or {}).get("sterile"))

    def generate_reject():
        closest = (routing.get("slots") or {}).get("closest_concepts") or []
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": routing.get("related") or [],
            "routing": {
                "route": routing["route"],
                "score": routing.get("score"),
                "reason": routing.get("reason"),
            },
            "logs": [
                {
                    "step": "Pass 1: Intent & Embedder Gate",
                    "status": "Not indexed",
                    "details": (
                        f"Highest similarity score ({float(routing.get('score') or 0):.3f}) "
                        f"is below the rejection threshold ({st.REJECT_SIMILARITY_THRESHOLD}) "
                        f"with no strong lexical/alias surface hit."
                    ),
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        reply = not_indexed_reply(query, closest, natural=wants_synthesis and not sterile)
        if sterile:
            reply = enforce_sterile_prose(reply, fallback=reply)
        yield with_holdings(query, reply)

    return Response(generate_reject(), mimetype="text/plain")


def handle_general_chat(query, history, routing, wants_synthesis):
    """Free conversational reply for low-similarity / chitchat queries."""

    def generate_general():
        payload = {
            "anchor_concept": None,
            "prerequisites": [],
            "unlocks": [],
            "citations": [],
            "related_concepts": routing.get("related") or [],
            "routing": {
                "route": routing["route"],
                "score": routing.get("score"),
                "reason": routing.get("reason"),
            },
            "logs": [
                {
                    "step": "Pass 1: Intent & Embedder Gate",
                    "status": "General chat",
                    "details": (
                        f"Similarity too low for graph grounding "
                        f"(score={float(routing.get('score') or 0):.3f} < soft "
                        f"{st.DOMAIN_SOFT_THRESHOLD}). Free conversational reply."
                    ),
                }
            ],
        }
        yield json.dumps(payload) + "\n[STREAM_START]\n"
        yield with_holdings(query, general_chat_reply(query, history))

    return Response(generate_general(), mimetype="text/plain")
