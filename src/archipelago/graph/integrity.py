"""Graph integrity validator enforcing Directed Acyclic Graph (DAG) invariants."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


@dataclass
class GraphIntegrityReport:
    """Report detailing the structural integrity of the concept dependency graph."""

    total_nodes: int
    total_edges: int
    is_dag: bool
    cycles_detected: list[list[str]]
    self_loops: list[str]
    reciprocal_cycles: list[tuple[str, str]]
    orphan_nodes: list[str]

    @property
    def is_valid(self) -> bool:
        """A graph is valid if it is a strictly compliant DAG without self-loops."""
        return self.is_dag and len(self.self_loops) == 0 and len(self.reciprocal_cycles) == 0


class GraphIntegrityValidator:
    """Validates structural DAG integrity using Kahn's algorithm."""

    DIFFICULTY_RANKS = {
        "foundational": 1,
        "intermediate": 2,
        "advanced": 3,
        "expert": 4,
    }

    @classmethod
    def check_self_loops(cls, edges: list[dict[str, Any]]) -> list[str]:
        """Detect self-referencing edges (A -> A)."""
        loops: list[str] = []
        for edge in edges:
            u = edge.get("from_id") or edge.get("from")
            v = edge.get("to_id") or edge.get("to")
            if u and v and u == v:
                loops.append(u)
        return loops

    @classmethod
    def check_reciprocal_cycles(cls, edges: list[dict[str, Any]], edge_type: str = "REQUIRES") -> list[tuple[str, str]]:
        """Detect mutual dependencies (A REQUIRES B and B REQUIRES A)."""
        typed_edges = set()
        for edge in edges:
            rel = edge.get("edge_type") or edge.get("relation") or ""
            if rel.upper() == edge_type.upper():
                u = edge.get("from_id") or edge.get("from")
                v = edge.get("to_id") or edge.get("to")
                if u and v:
                    typed_edges.add((u, v))

        reciprocal: list[tuple[str, str]] = []
        seen = set()
        for (u, v) in typed_edges:
            if (v, u) in typed_edges and (v, u) not in seen:
                reciprocal.append((u, v))
                seen.add((u, v))
        return reciprocal

    @classmethod
    def run_kahn_dag_sort(
        cls, nodes: list[str] | set[str], edges: list[dict[str, Any]], edge_type: str = "REQUIRES"
    ) -> tuple[bool, list[str]]:
        """Run Kahn's topological sort algorithm to detect directed cycles.
        
        Returns:
            (is_dag, topological_order_or_unvisited_nodes)
        """
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = defaultdict(int)
        all_active_nodes = set(nodes)

        for edge in edges:
            rel = edge.get("edge_type") or edge.get("relation") or ""
            if rel.upper() == edge_type.upper():
                u = edge.get("from_id") or edge.get("from")
                v = edge.get("to_id") or edge.get("to")
                if u and v:
                    adj[u].append(v)
                    in_degree[v] += 1
                    all_active_nodes.add(u)
                    all_active_nodes.add(v)

        for node in all_active_nodes:
            if node not in in_degree:
                in_degree[node] = 0

        queue = deque([n for n in all_active_nodes if in_degree[n] == 0])
        topo_order: list[str] = []

        while queue:
            curr = queue.popleft()
            topo_order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        is_dag = len(topo_order) == len(all_active_nodes)
        if not is_dag:
            unvisited = [n for n in all_active_nodes if n not in set(topo_order)]
            return False, unvisited

        return True, topo_order

    @classmethod
    def find_orphans(cls, nodes: list[str] | set[str], edges: list[dict[str, Any]]) -> list[str]:
        """Detect nodes with zero connected edges (in-degree = 0 and out-degree = 0)."""
        connected = set()
        for edge in edges:
            u = edge.get("from_id") or edge.get("from")
            v = edge.get("to_id") or edge.get("to")
            if u:
                connected.add(u)
            if v:
                connected.add(v)

        return sorted([n for n in nodes if n not in connected])

    @classmethod
    def validate_graph(
        cls, concepts: dict[str, Any] | list[str], edges: list[dict[str, Any]]
    ) -> GraphIntegrityReport:
        """Execute the complete structural graph validation suite."""
        node_ids = list(concepts.keys()) if isinstance(concepts, dict) else list(concepts)
        
        self_loops = cls.check_self_loops(edges)
        reciprocal = cls.check_reciprocal_cycles(edges, edge_type="REQUIRES")
        is_dag, unvisited = cls.run_kahn_dag_sort(node_ids, edges, edge_type="REQUIRES")
        orphans = cls.find_orphans(node_ids, edges)

        return GraphIntegrityReport(
            total_nodes=len(node_ids),
            total_edges=len(edges),
            is_dag=is_dag,
            cycles_detected=[unvisited] if not is_dag else [],
            self_loops=self_loops,
            reciprocal_cycles=reciprocal,
            orphan_nodes=orphans,
        )
