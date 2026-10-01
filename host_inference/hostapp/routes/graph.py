"""Bounded interactive graph neighborhood for the graph page and chat.

One concern: returning a small, renderable slice of the concept graph rather
than ever shipping the whole graph to the browser.
"""
from __future__ import annotations

from flask import Flask, jsonify, request

from ..context import AppContext

MAX_NODES_DEFAULT = 30
MAX_NODES_CEILING = 100
MAX_NODES_FLOOR = 2
GRAPH_DEPTH = 2
SUMMARY_CHAR_LIMIT = 600
DEFAULT_KIND = "concept"


def register(app: Flask, ctx: AppContext) -> None:
    """Register the graph neighborhood route on ``app``."""

    @app.get("/api/graph/subgraph")
    def graph_subgraph():
        """Return a bounded, interactive neighborhood around one concept."""
        graph = ctx.engine.graph
        target_id = (request.args.get("target_id") or "").strip()
        query = (request.args.get("q") or "").strip()
        if not target_id and query:
            ranked = graph.rank(query, top_k=1)
            target_id = ranked[0][1] if ranked else ""
        if target_id not in graph.nodes:
            return jsonify({"error": "not_found", "detail": "No matching graph concept."}), 404
        try:
            max_nodes = max(MAX_NODES_FLOOR, min(MAX_NODES_CEILING, int(request.args.get("max_nodes") or MAX_NODES_DEFAULT)))
        except (TypeError, ValueError):
            max_nodes = MAX_NODES_DEFAULT

        selected = [target_id]
        selected_set = {target_id}
        edge_rows = []
        queue = [(target_id, 0)]
        while queue and len(selected) < max_nodes:
            current, depth = queue.pop(0)
            if depth >= GRAPH_DEPTH:
                continue
            neighbors = [(current, neighbor, relation) for relation, neighbor in graph.out.get(current, [])]
            neighbors.extend((neighbor, current, relation) for relation, neighbor in graph.inn.get(current, []))
            for source, target, relation in neighbors:
                edge_rows.append((source, target, relation))
                neighbor = target if source == current else source
                if neighbor not in selected_set and len(selected) < max_nodes:
                    selected_set.add(neighbor)
                    selected.append(neighbor)
                    queue.append((neighbor, depth + 1))

        nodes = []
        for node_id in selected:
            node = graph.nodes[node_id]
            nodes.append({"data": {
                "id": node_id,
                "name": graph.label(node_id),
                "summary": str(node.get("summary") or "")[:SUMMARY_CHAR_LIMIT],
                "kind": str(node.get("type") or node.get("kind") or DEFAULT_KIND),
            }})
        edges = []
        seen_edges = set()
        for source, target, relation in edge_rows:
            key = (source, target, relation)
            if source not in selected_set or target not in selected_set or key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({"data": {
                "id": f"{source}:{relation}:{target}",
                "source": source,
                "target": target,
                "rel_label": relation,
            }})
        return jsonify({"target_id": target_id, "nodes": nodes, "edges": edges})
