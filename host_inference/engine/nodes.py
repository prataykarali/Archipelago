"""Public projection of an internal graph node.

The UI and the API contract speak in terms of a small, stable node shape.  This
module is the single place that decides which internal fields are exposed.
"""
from __future__ import annotations

DEFAULT_DIFFICULTY = "intermediate"
DEFAULT_CONCEPT_TYPE = "concept"


def node_public(node: dict) -> dict:
    """Return the public, UI-facing view of one internal graph node."""
    return {
        "id": node["id"],
        "label": node.get("label") or node.get("name") or node["id"],
        "name": node.get("name") or node.get("label") or node["id"],
        "summary": (node.get("summary") or "").strip(),
        "difficulty": node.get("difficulty") or DEFAULT_DIFFICULTY,
        "concept_type": node.get("concept_type") or DEFAULT_CONCEPT_TYPE,
    }


# Privately used name kept for the original call sites in engine.py.
_node_public = node_public
