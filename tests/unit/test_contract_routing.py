"""Regression tests for the six response contracts.

These pin the *contract* each prompt family must land under, not the engine's
internal route names.  ``SCHEDULE`` and ``AUTH_GATEWAY`` are both contract type
3; asserting on the route string instead would break every time the router is
refactored while telling us nothing about whether a student got their hours.

Two stacks are covered because both ship: the hosted engine (``host_inference``,
deployed alone to the cloud) and the library server (``archipelago``). They have
separate routers and have drifted apart before, which is exactly what this file
exists to prevent.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = REPO_ROOT / "host_inference"
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

pytestmark = pytest.mark.unit
pytest_plugins = ("tests.unit.contract_routing_fixtures",)

CONTRACT_TYPES = (
    "GRAPH_SYNTHESIS",
    "CATALOG_SHELF_ROUTING",
    "AUTH_GATEWAY",
    "MCQ_DIAGNOSTIC",
    "INGESTION_ANALYSIS",
    "GUARDRAIL_INTERCEPT",
)

# ── Probes, verbatim from the published contract table ────────────────────────
PROBES: dict[str, list[str]] = {
    "GRAPH_SYNTHESIS": [
        "What foundational math must I master before studying Self-Attention?",
        "How does Softmax connect to Self-Attention?",
        "Explain BERT",
    ],
    "CATALOG_SHELF_ROUTING": [
        "Where can I find a physical copy of 'Database System Concepts' on campus?",
        "What is the call number for Database System Concepts?",
        "How many copies of Operating System Internals are available?",
    ],
    "AUTH_GATEWAY": [
        "How do I access IEEE Xplore off-campus, and what are library Sunday hours?",
        "What are the library opening hours?",
        "library Sunday hours",
        "How do I log in to Scopus?",
        "What time does the circulation desk open?",
    ],
    "MCQ_DIAGNOSTIC": [
        "I want to learn RAG",
        "Show learning roadmap for BERT",
        "What should I study first for LoRA?",
        "Teach me about third normal form",
    ],
    "INGESTION_ANALYSIS": [
        "Analyze this uploaded PDF and extract its Open Knowledge Format (OKF) nodes.",
        "Extract the OKF nodes from my uploaded paper",
        "Ingest this document into the graph",
    ],
    "GUARDRAIL_INTERCEPT": [
        "Write a Python web scraper",
        "What is a good recipe for lasagna?",
        "Tell me a joke",
    ],
}

#: Substrings that prove the right *content* answered, not just the right route.
CONTENT_REQUIREMENTS = {
    (
        "AUTH_GATEWAY",
        "How do I access IEEE Xplore off-campus, and what are library Sunday hours?",
    ): ("24",),
    ("AUTH_GATEWAY", "library Sunday hours"): ("24",),
    ("AUTH_GATEWAY", "What are the library opening hours?"): ("24",),
    ("AUTH_GATEWAY", "What time does the circulation desk open?"): ("24",),
    ("CATALOG_SHELF_ROUTING", "What is the call number for Database System Concepts?"): ("ISBN",),
}


# ── 1. Contract classification, both stacks ───────────────────────────────────


#: Flattened ``(contract, prompt)`` pairs — pytest cannot parametrize a second
#: argument over a dict comprehension, and one flat list keeps the two stacks'
#: case tables provably identical.
PROBE_CASES: list[tuple[str, str]] = [
    (contract_type, prompt) for contract_type in CONTRACT_TYPES for prompt in PROBES[contract_type]
]


@pytest.mark.parametrize(("contract", "prompt"), PROBE_CASES)
def test_hosted_engine_honours_every_contract(hosted_engine, contract, prompt):
    result = hosted_engine.answer(prompt)
    assert result["contract"] == contract, (
        f"{prompt!r} routed under {result['route']} ({result['contract']}), expected {contract}"
    )


@pytest.mark.parametrize(("contract", "prompt"), PROBE_CASES)
def test_library_server_honours_every_contract(library_client, contract, prompt):
    body = library_client.post("/api/chat", json={"query": prompt}).get_json() or {}
    assert body.get("contract") == contract, (
        f"{prompt!r} answered as {body.get('contract')!r} (status "
        f"{body.get('status')!r}), expected {contract}"
    )


# ── 2. Content, not just routing ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("contract", "prompt", "needles"),
    [(c, p, n) for (c, p), n in CONTENT_REQUIREMENTS.items()],
)
def test_hosted_answers_carry_the_required_content(hosted_engine, contract, prompt, needles):
    text = hosted_engine.answer(prompt)["text"].lower()
    for needle in needles:
        assert needle.lower() in text, f"{prompt!r} omitted {needle!r}"


def test_hours_and_access_are_answered_in_one_reply(hosted_engine):
    """The combined question must not lose either half to the other route."""
    result = hosted_engine.answer(
        "How do I access IEEE Xplore off-campus, and what are library Sunday hours?"
    )
    text = result["text"].lower()
    assert "24" in text, "the schedule half was dropped"
    assert "ieee" in text, "the access half was dropped"


def test_combined_hours_and_access_keeps_both_halves(library_client):
    body = (
        library_client.post(
            "/api/chat",
            json={
                "query": "How do I access IEEE Xplore off-campus, and what are library Sunday hours?"
            },
        ).get_json()
        or {}
    )
    text = str(body.get("text") or "").lower()
    assert "24" in text, "the schedule half was dropped"
    assert "ieee" in text or "e-resource" in text, "the access half was dropped"


# ── 3. Graph-render protocol ──────────────────────────────────────────────────

#: Contracts that draw the in-chat concept graph.
GRAPH_CONTRACTS = {"GRAPH_SYNTHESIS", "MCQ_DIAGNOSTIC", "INGESTION_ANALYSIS"}
#: Contracts that must never draw one.
NO_GRAPH_CONTRACTS = {"CATALOG_SHELF_ROUTING", "AUTH_GATEWAY", "GUARDRAIL_INTERCEPT"}


@pytest.mark.parametrize("contract", sorted(NO_GRAPH_CONTRACTS))
def test_non_graph_contracts_never_expose_an_anchor(hosted_engine, contract):
    for prompt in PROBES[contract]:
        payload = hosted_engine.answer(prompt)["payload"]
        assert payload["render_graph"] is False, f"{prompt!r} should not draw a graph"
        assert payload["anchor_concept"] is None
        assert payload["prerequisites"] == []
        assert payload["unlocks"] == []


@pytest.mark.parametrize("contract", sorted(NO_GRAPH_CONTRACTS))
def test_library_non_graph_contracts_suppress_the_graph(library_client, contract):
    for prompt in PROBES[contract]:
        body = library_client.post("/api/chat", json={"query": prompt}).get_json() or {}
        assert body.get("render_graph") is False, f"{prompt!r} should not draw a graph"
        assert body.get("topology") is None


def test_render_decision_is_a_pure_function_of_the_route():
    """The protocol must not depend on phrasing, so grade it in isolation."""
    from host_inference.engine import contract

    for route, mapped in contract.ROUTE_CONTRACT.items():
        decision = contract.graph_decision(route)
        expected = mapped in GRAPH_CONTRACTS
        assert decision.render is expected, f"{route} -> {mapped} drew {decision.render}"
        assert decision.rule


def test_every_emitted_route_has_a_contract_mapping():
    """An unmapped route means the router grew behaviour nobody signed off."""
    from host_inference.engine import contract

    for route in _hosted_routes_seen_in_code():
        assert route in contract.ROUTE_CONTRACT, f"route {route!r} is unmapped"


def test_library_statuses_all_map_to_a_contract():
    from archipelago.core import contract

    for status in ("success", "rejected", "out_of_scope", "suggest_topics"):
        assert contract.contract_for(status) in contract.CONTRACT_TYPES


def test_unknown_route_raises_rather_than_guessing():
    from host_inference.engine import contract

    with pytest.raises(KeyError):
        contract.contract_for("A_ROUTE_THAT_DOES_NOT_EXIST")


def _hosted_routes_seen_in_code() -> set[str]:
    """Every route literal the router can return, read from the source."""
    import re

    source = (HOST_DIR / "engine" / "answer.py").read_text(encoding="utf-8")
    return set(re.findall(r'return\s+"([A-Z_]{3,})"\s*,', source))


# ── 4. Contract parity between the two stacks ─────────────────────────────────


def test_contract_tables_agree_between_stacks():
    """The two modules are duplicated by necessity; they must not diverge.

    The hosted build ships without the ``archipelago`` package, so the tables
    cannot be shared at runtime. This test is the enforcement mechanism.
    """
    from archipelago.core import contract as library_contract
    from host_inference.engine import contract as hosted_contract

    assert library_contract.CONTRACT_TYPES == hosted_contract.CONTRACT_TYPES
    assert library_contract.GRAPH_CONTRACTS == hosted_contract.GRAPH_CONTRACTS
    assert library_contract.CONTRACT_TITLES == hosted_contract.CONTRACT_TITLES
    for contract_type in hosted_contract.CONTRACT_TYPES:
        left = library_contract.graph_decision(contract_type)
        right = hosted_contract.graph_decision(contract_type)
        assert left == right, f"{contract_type} renders differently per stack"
