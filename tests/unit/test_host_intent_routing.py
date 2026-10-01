"""Intent-routing tests: which replies carry an in-chat graph, and which do not.

The chat UI renders the interactive concept graph only when the reply payload has
an ``anchor_concept``.  So the backend's routing decision *is* the UI behaviour:
graph-shaped routes must expose an anchor plus prerequisites/unlocks, and
factual routes (schedules, portals, refusals) must suppress it.  These tests pin
that contract against the real exported graph.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
GRAPH = HOST / "cache" / "okf_graph.json"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(not GRAPH.is_file(), reason="hosted concept graph is not present"),
]

# Routes that must never draw a concept graph in the chat.
FACTUAL_ROUTES = {"SCHEDULE", "AUTH_GATEWAY", "PASSING_MENTION", "OOD_KILL", "PERSONA_LOCK", "CODE_TRAP", "EMPTY"}
# Routes that must always draw one.
GRAPH_ROUTES = {"GRAPH_SYNTHESIS", "RELATION", "CROSS_DOMAIN", "DISCONNECTED", "MCQ_DIAGNOSTIC"}


@pytest.fixture(scope="module")
def engine():
    import engine as hosted_engine

    return hosted_engine.Engine()


def test_graph_reply_exposes_anchor_prerequisites_and_citations(engine):
    result = engine.answer("explain BERT")
    payload = result["payload"]
    assert result["route"] in GRAPH_ROUTES
    assert payload["anchor_concept"], "graph route must expose an anchor for the in-chat graph"
    assert payload["prerequisites"] or payload["unlocks"]
    assert payload["citations"], "a grounded reply must carry at least one exact-source citation"


def test_schedule_reply_hides_the_graph(engine):
    result = engine.answer("library opening hours")
    assert result["route"] == "SCHEDULE"
    payload = result["payload"]
    assert payload["anchor_concept"] is None
    assert payload["prerequisites"] == []
    assert payload["unlocks"] == []


@pytest.mark.parametrize("query", ["library opening hours", "tell me about taylor swift"])
def test_factual_routes_never_expose_an_anchor(engine, query):
    result = engine.answer(query)
    assert result["route"] in FACTUAL_ROUTES
    assert result["payload"]["anchor_concept"] is None


def test_empty_query_is_refused_without_graph(engine):
    result = engine.answer("")
    assert result["route"] == "EMPTY"
    assert result["payload"]["anchor_concept"] is None
