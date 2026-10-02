"""The six deterministic response contracts, and the graph-render protocol.

One concern: naming what a reply *is*, independently of how the engine happened to
reach it.  The router emits fine-grained internal routes (``SCHEDULE``,
``RELATION``, ``CATALOG_SHELF`` …); the published contract speaks in six types.
Keeping the two vocabularies apart — and mapping one onto the other here — is
what lets an auditor ask "did that answer honour contract type 3?" without first
having to know the engine's internal route names.

Two invariants are enforced from this module, not from the router:

* every route maps to exactly one contract type, so no reply can be unclassifiable;
* whether the in-chat graph is drawn is a *pure function of the contract*, so the
  rendering protocol in the spec is deterministic rather than emergent.
"""
from __future__ import annotations

from typing import NamedTuple

# ── The six contract types ────────────────────────────────────────────────────
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

#: Ordered so an audit report reads in the same order as the published table.
CONTRACT_TITLES = {
    GRAPH_SYNTHESIS: "Pedagogical Graph Traversal",
    CATALOG_SHELF_ROUTING: "Physical Shelf & Catalog Routing",
    AUTH_GATEWAY: "Administrative & E-Resource Auth",
    MCQ_DIAGNOSTIC: "Diagnostic & Adaptive Learning",
    INGESTION_ANALYSIS: "Live Paper Ingestion & Analysis",
    GUARDRAIL_INTERCEPT: "Guardrail & Scope Intercept",
}


# ── Route → contract ──────────────────────────────────────────────────────────
# Every internal route the engine can emit must appear here.  ``scripts/audit_
# routing.py`` fails if a new route is added without a mapping, so this table
# cannot silently drift from the router.
ROUTE_CONTRACT = {
    # 1. Pedagogical graph traversal.
    "GRAPH_SYNTHESIS": GRAPH_SYNTHESIS,
    "RELATION": GRAPH_SYNTHESIS,
    "CROSS_DOMAIN": GRAPH_SYNTHESIS,
    "DISCONNECTED": GRAPH_SYNTHESIS,
    # 2. Physical shelf and catalog routing.
    "CATALOG_SHELF": CATALOG_SHELF_ROUTING,
    "CATALOG_SHELF_ROUTING": CATALOG_SHELF_ROUTING,
    # 3. Administrative schedules and e-resource authentication.
    "SCHEDULE": AUTH_GATEWAY,
    "AUTH_GATEWAY": AUTH_GATEWAY,
    # 4. Diagnostic and adaptive learning.
    "MCQ_DIAGNOSTIC": MCQ_DIAGNOSTIC,
    # A curriculum request for a topic we have not ingested is still a curriculum
    # intent — the honest answer is "not indexed", not "you are off topic", and it
    # is still contract type 4 rather than a scope deflection.
    "CURRICULUM_UNINDEXED": MCQ_DIAGNOSTIC,
    # 5. Live ingestion and analysis of an uploaded paper.
    "INGESTION_ANALYSIS": INGESTION_ANALYSIS,
    # 6. Guardrail and scope intercept.
    "GUARDRAIL_INTERCEPT": GUARDRAIL_INTERCEPT,
    # Refusals are contract type 6 by definition: the spec lists code generation
    # and prompt-injection attempts as GUARDRAIL_INTERCEPT examples, so a
    # dedicated code-trap route is a *reason* under type 6, not a seventh type.
    "CODE_TRAP": GUARDRAIL_INTERCEPT,
    "PERSONA_LOCK": GUARDRAIL_INTERCEPT,
    "PASSING_MENTION": GUARDRAIL_INTERCEPT,
    "EMPTY": GUARDRAIL_INTERCEPT,
    # Not a concept answer, so it borrows no concept graph; still a catalog lookup.
    "BOOK_PAGE": CATALOG_SHELF_ROUTING,
    # Honest "the corpus does not contain the parameter you asked for".
    "CATALOG_DEPTH": GRAPH_SYNTHESIS,
    # Canned blurbs are concept answers, so they honour the concept contract.
    "DEMO": GRAPH_SYNTHESIS,
}


class GraphDecision(NamedTuple):
    """Whether the in-chat graph is drawn for a reply, and why."""

    render: bool
    rule: str


#: Contracts that draw the concept graph.  Everything else renders tabular
#: metadata or credential cards only — the spec's "DO NOT SHOW GRAPH" branch.
GRAPH_CONTRACTS = frozenset({GRAPH_SYNTHESIS, MCQ_DIAGNOSTIC, INGESTION_ANALYSIS})

#: Why each graph contract is allowed to draw, for the audit trail.
GRAPH_RULES = {
    GRAPH_SYNTHESIS: "multi_hop_concept_query",
    MCQ_DIAGNOSTIC: "personalized_learning_path",
    INGESTION_ANALYSIS: "uploaded_okf_projection",
}

#: Why each non-graph contract suppresses the graph, for the audit trail.
NO_GRAPH_RULES = {
    CATALOG_SHELF_ROUTING: "physical_location_lookup",
    AUTH_GATEWAY: "administrative_or_credential_query",
    GUARDRAIL_INTERCEPT: "out_of_domain_or_refusal",
}


def contract_for(route: str) -> str:
    """Contract type for an internal engine route.

    Raises on an unmapped route rather than defaulting to a plausible-looking
    guess: an unknown route means the router grew a behaviour the contract has
    not signed off, and that must fail loudly in an audit rather than be silently
    labelled.
    """
    try:
        return ROUTE_CONTRACT[route]
    except KeyError:
        raise KeyError(
            f"route {route!r} has no contract mapping; add it to ROUTE_CONTRACT"
        ) from None


def graph_decision(route: str) -> GraphDecision:
    """Deterministic show/hide decision for the in-chat graph.

    A pure function of the route, so the protocol is testable in isolation and
    cannot vary with query phrasing or load.
    """
    contract = contract_for(route)
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
