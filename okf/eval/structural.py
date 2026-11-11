"""Structural graph audit for cycles, orphans, and provenance."""

from __future__ import annotations

import logging
from typing import Any

from okf.eval._base import *  # noqa: F403
from okf.query_rows import query_rows

logger = logging.getLogger(__name__)


def structural_audit(db: Any) -> dict[str, Any]:
    """Checks self-edges, full cycle detection with paths, orphan count/percentage, edge provenance, connected components."""
    import kuzu

    conn = db if hasattr(db, "execute") else kuzu.Connection(db)

    # 1. Self-edges
    self_edges = []
    for rel_table in ["REQUIRES", "UNLOCKS", "RELATED"]:
        try:
            rows = query_rows(
                conn,
                f"MATCH (a:Concept)-[r:{rel_table}]->(b:Concept) WHERE a.id = b.id RETURN a.name",
            )
            for row in rows:
                self_edges.append({"concept": row[0], "relation": rel_table})
        except Exception as exc:
            logger.debug("Self-edge query failed for %s: %s", rel_table, exc)

    # 2. Orphans count/percentage
    total_concepts = int(next(query_rows(conn, "MATCH (c:Concept) RETURN count(c)"), [0])[0])

    rows = query_rows(
        conn,
        "MATCH (c:Concept) WHERE NOT (c)-[:REQUIRES|UNLOCKS|RELATED]-(:Concept) RETURN c.id, c.name",
    )
    orphans = []
    for row in rows:
        orphans.append({"id": row[0], "name": row[1]})
    orphan_count = len(orphans)
    orphan_pct = orphan_count / total_concepts if total_concepts > 0 else 0.0

    # 3. Edge provenance
    edge_provenance_issues = []
    for rel_table in ["REQUIRES", "UNLOCKS", "RELATED"]:
        try:
            rows = query_rows(
                conn,
                f"MATCH (a:Concept)-[r:{rel_table}]->(b:Concept) RETURN a.name, b.name, r.source",
            )
            for row in rows:
                src_node, dst_node, source_val = row[0], row[1], row[2]
                if not source_val or not isinstance(source_val, str) or ":" not in source_val:
                    edge_provenance_issues.append(
                        {
                            "from": src_node,
                            "to": dst_node,
                            "edge_type": rel_table,
                            "provenance": source_val,
                        }
                    )
        except Exception as exc:
            logger.debug("Provenance query failed for %s: %s", rel_table, exc)

    # 4. Cycle detection
    # Retrieve dependency edges (X -> Y means X is learned before Y)
    all_nodes: set[str] = set()
    edges: list[tuple[str, str]] = []
    try:
        for row in query_rows(
            conn, "MATCH (a:Concept)-[r:REQUIRES]->(b:Concept) RETURN a.id, b.id"
        ):
            u, v = row[0], row[1]
            all_nodes.add(u)
            all_nodes.add(v)
            edges.append((v, u))  # dependency v -> u
    except Exception as exc:
        logger.debug("REQUIRES query failed: %s", exc)

    try:
        for row in query_rows(conn, "MATCH (a:Concept)-[r:UNLOCKS]->(b:Concept) RETURN a.id, b.id"):
            u, v = row[0], row[1]
            all_nodes.add(u)
            all_nodes.add(v)
            edges.append((u, v))  # dependency u -> v
    except Exception as exc:
        logger.debug("UNLOCKS query failed: %s", exc)

    try:
        for row in query_rows(conn, "MATCH (c:Concept) RETURN c.id"):
            all_nodes.add(row[0])
    except Exception as exc:
        logger.debug("Concept listing failed: %s", exc)

    adj: dict[str, list[str]] = {n: [] for n in all_nodes}
    for src, dst in edges:
        adj[src].append(dst)

    visited: dict[str, int] = {}
    parent: dict[str, str] = {}
    cycles: list[list[str]] = []

    def dfs_cycle(node: str) -> None:
        visited[node] = 1
        for neighbor in adj.get(node, []):
            if visited.get(neighbor, 0) == 1:
                path = []
                curr = node
                while curr != neighbor:
                    path.append(curr)
                    curr = parent[curr]
                path.append(neighbor)
                path.reverse()
                path.append(neighbor)
                cycles.append(path)
            elif visited.get(neighbor, 0) == 0:
                parent[neighbor] = node
                dfs_cycle(neighbor)
        visited[node] = 2

    for node in all_nodes:
        if visited.get(node, 0) == 0:
            dfs_cycle(node)

    # 5. Connected components
    undirected_adj: dict[str, list[str]] = {n: [] for n in all_nodes}
    try:
        rows = query_rows(
            conn, "MATCH (a:Concept)-[r:REQUIRES|UNLOCKS|RELATED]->(b:Concept) RETURN a.id, b.id"
        )
        for row in rows:
            u, v = row[0], row[1]
            undirected_adj[u].append(v)
            undirected_adj[v].append(u)
    except Exception as exc:
        logger.debug("Connected-components query failed: %s", exc)

    visited_cc = set()
    components = []
    for node in all_nodes:
        if node not in visited_cc:
            comp = []
            queue = [node]
            visited_cc.add(node)
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for neighbor in undirected_adj.get(curr, []):
                    if neighbor not in visited_cc:
                        visited_cc.add(neighbor)
                        queue.append(neighbor)
            components.append(comp)

    return {
        "self_edges": self_edges,
        "cycles": cycles,
        "orphan_count": orphan_count,
        "orphan_percentage": orphan_pct,
        "orphans": orphans,
        "edge_provenance_issues": edge_provenance_issues,
        "connected_components_count": len(components),
        "connected_components": components,
    }
