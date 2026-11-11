"""Deterministic routing and response contract definitions for Archipelago."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "host_inference") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "host_inference"))

from engine.contract import (
    AUTH_GATEWAY,
    CATALOG_SHELF_ROUTING,
    CONTRACT_TITLES,
    CONTRACT_TYPES,
    GRAPH_CONTRACTS,
    GRAPH_RULES,
    GRAPH_SYNTHESIS,
    GUARDRAIL_INTERCEPT,
    INGESTION_ANALYSIS,
    MCQ_DIAGNOSTIC,
    NO_GRAPH_RULES,
    ROUTE_CONTRACT,
    GraphDecision,
    contract_for,
    graph_decision,
)

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
