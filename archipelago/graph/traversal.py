"""Graph traversal engine for prerequisite resolution and mastery projection."""

from __future__ import annotations

from collections import deque
from typing import Any

from .engine import KuzuGraphEngine

NO_VALID_PEDAGOGICAL_PATH = "NO_VALID_PEDAGOGICAL_PATH"


class GraphTraversalEngine:
    """Executes directed pedagogical traversals over the concept graph."""

    def __init__(self, engine: KuzuGraphEngine) -> None:
        self.engine = engine

    def get_prerequisites(self, concept_id: str, depth: int = 2) -> list[dict[str, Any]]:
        """Retrieve upstream prerequisites: (concept)-[:REQUIRES*1..k]->(prereq)."""
        query = f"""
        MATCH (a:Concept {{id: $concept_id}})-[r:REQUIRES*1..{depth}]->(b:Concept)
        RETURN DISTINCT b.id AS id, b.name AS name, b.difficulty AS difficulty
        """
        try:
            return self.engine.execute(query, {"concept_id": concept_id})
        except Exception:
            return []

    def get_unlocks(self, concept_id: str, depth: int = 1) -> list[dict[str, Any]]:
        """Retrieve downstream unlocks via reverse-REQUIRES: (unlocked)-[:REQUIRES*1..k]->(concept)."""
        query = f"""
        MATCH (b:Concept)-[r:REQUIRES*1..{depth}]->(a:Concept {{id: $concept_id}})
        RETURN DISTINCT b.id AS id, b.name AS name, b.difficulty AS difficulty
        """
        try:
            return self.engine.execute(query, {"concept_id": concept_id})
        except Exception:
            return []

    @classmethod
    def find_pedagogical_path_in_memory(
        cls,
        source_id: str,
        target_id: str,
        edges: list[dict[str, Any]],
        max_depth: int = 6,
    ) -> list[str] | None:
        """Find the shortest directed pedagogical path from source to target concept.
        
        Path traverses forward enablement edges (reverse-REQUIRES or UNLOCKS).
        Returns list of node IDs forming the learning sequence, or None if no directed path exists.
        """
        if source_id == target_id:
            return [source_id]

        # Forward learning edges: (A unlocks B) OR (B requires A)
        forward_adj: dict[str, list[str]] = {}
        for edge in edges:
            rel = (edge.get("edge_type") or edge.get("relation") or "").upper()
            u = edge.get("from_id") or edge.get("from")
            v = edge.get("to_id") or edge.get("to")
            if not u or not v:
                continue

            if rel == "UNLOCKS":
                forward_adj.setdefault(u, []).append(v)
            elif rel == "REQUIRES":
                # If v requires u, then learning u unlocks v
                forward_adj.setdefault(v, []).append(u)

        # BFS shortest path search
        queue = deque([(source_id, [source_id])])
        visited = {source_id}

        while queue:
            curr, path = queue.popleft()
            if len(path) > max_depth + 1:
                continue

            for neighbor in forward_adj.get(curr, []):
                if neighbor == target_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None
