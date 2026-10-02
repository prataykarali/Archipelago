"""The six response contracts and the graph-render protocol (library server).

Duplicated deliberately from ``host_inference/engine/contract.py``: the hosted
cloud build ships ``host_inference`` alone, without the ``archipelago`` package,
so the two cannot share a module at runtime.  They are kept honest by
``tests/unit/test_contract_parity.py``, which asserts the two tables are
byte-identical — a change to one without the other fails CI rather than
silently splitting the product's behaviour in two.

One concern: naming what a reply *is*, independently of how the router reached
it, and deciding — deterministically — whether the in-chat graph is drawn.
"""
from __future__ import annotations

from typing import NamedTuple

GRAPH_SYNTHESIS = "GRAPH_SYNTHESIS"
CATALOG_SHELF_ROUTING = "CATALOG_SHELF_ROUTING"
AUTH_GATEWAY = "AUTH_GATEWAY"
MCQ_DIAGNOSTIC = "MCQ_DIAGNOSTIC"
INGESTION_ANALYSIS = "INGESTION_ANALYSIS"
GUARDRAIL_INTERCEPT = "GUARDRAIL_INTERCEPT"

CONTRACT_TYPES = (
    GRAPH_SYNTHESIS,
    CATALOG_SHELF_ROUTING,
    AUTH_GATEWAY,
    MCQ_DIAGNOSTIC,
    INGESTION_ANALYSIS,
    GUARDRAIL_INTERCEPT,
)

CONTRACT_TITLES = {
    GRAPH_SYNTHESIS: "Pedagogical Graph Traversal",
    CATALOG_SHELF_ROUTING: "Physical Shelf & Catalog Routing",
    AUTH_GATEWAY: "Administrative & E-Resource Auth",
    MCQ_DIAGNOSTIC: "Diagnostic & Adaptive Learning",
    INGESTION_ANALYSIS: "Live Paper Ingestion & Analysis",
    GUARDRAIL_INTERCEPT: "Guardrail & Scope Intercept",
}

#: Library-server statuses, which are the library server's counterpart of the
#: hosted engine's internal route names.
ROUTE_CONTRACT = {
    # 1. Pedagogical graph traversal.
    "success": GRAPH_SYNTHESIS,
    "graph_synthesis": GRAPH_SYNTHESIS,
    # 2. Physical shelf and catalog routing.
    "catalog_shelf_routing": CATALOG_SHELF_ROUTING,
    # 3. Administrative schedules and e-resource authentication.
    "auth_gateway": AUTH_GATEWAY,
    # 4. Diagnostic and adaptive learning.
    "mcq_diagnostic": MCQ_DIAGNOSTIC,
    # 5. Live ingestion and analysis of an uploaded paper.
    "ingestion_analysis": INGESTION_ANALYSIS,
    # 6. Guardrail and scope intercept. Every refusal the server can emit lands
    # here: scope deflection, prompt-injection rejection, code generation.
    "rejected": GUARDRAIL_INTERCEPT,
    "out_of_scope": GUARDRAIL_INTERCEPT,
    "guardrail_intercept": GUARDRAIL_INTERCEPT,
    # A 0.50-0.75 similarity answer is a corpus-boundary suggestion, not a
    # grounded concept answer, so it borrows no concept graph.
    "suggest_topics": GUARDRAIL_INTERCEPT,
}

#: Contract type → whether the in-chat concept graph may be drawn.
GRAPH_CONTRACTS = frozenset({GRAPH_SYNTHESIS, MCQ_DIAGNOSTIC, INGESTION_ANALYSIS})

GRAPH_RULES = {
    GRAPH_SYNTHESIS: "multi_hop_concept_query",
    MCQ_DIAGNOSTIC: "personalized_learning_path",
    INGESTION_ANALYSIS: "uploaded_okf_projection",
}

NO_GRAPH_RULES = {
    CATALOG_SHELF_ROUTING: "physical_location_lookup",
    AUTH_GATEWAY: "administrative_or_credential_query",
    GUARDRAIL_INTERCEPT: "out_of_domain_or_refusal",
}


class GraphDecision(NamedTuple):
    """Whether the in-chat graph is drawn for a reply, and why."""

    render: bool
    rule: str


def contract_for(route: str) -> str:
    """Contract type for a library-server status.

    Raises on an unmapped status rather than guessing: an unknown status means
    the route table grew a behaviour the contract has not signed off.
    """
    try:
        return ROUTE_CONTRACT[route]
    except KeyError:
        raise KeyError(
            f"status {route!r} has no contract mapping; add it to ROUTE_CONTRACT"
        ) from None


def graph_decision(contract: str) -> GraphDecision:
    """Deterministic show/hide decision, keyed by contract type."""
    if contract in GRAPH_CONTRACTS:
        return GraphDecision(True, GRAPH_RULES[contract])
    return GraphDecision(False, NO_GRAPH_RULES[contract])


__all__ = [
    "AUTH_GATEWAY",
    "CATALOG_SHELF_ROUTING",
    "CONTRACT_TITLES",
    "CONTRACT_TYPES",
    "GRAPH_CONTRACTS",
    "GRAPH_RULES",
    "GRAPH_SYNTHESIS",
    "GUARDRAIL_INTERCEPT",
    "INGESTION_ANALYSIS",
    "MCQ_DIAGNOSTIC",
    "NO_GRAPH_RULES",
    "ROUTE_CONTRACT",
    "GraphDecision",
    "contract_for",
    "graph_decision",
]
