"""Bounded interactive graph neighborhood for the graph page and chat.

One concern: returning a small, renderable slice of the concept graph rather
than ever shipping the whole graph to the browser.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from ..context import AppContext

MAX_NODES_DEFAULT = 30
MAX_NODES_CEILING = 100
MAX_NODES_FLOOR = 2
GRAPH_DEPTH = 2
SUMMARY_CHAR_LIMIT = 600
DEFAULT_KIND = "concept"
MAX_PUBLIC_SUMMARY_CHARS = 600
GRAPH_HUB_LIMIT = 12
GRAPH_HUB_EDGE_LIMIT = 24
MAX_SOURCE_DOCUMENT_NODES = 3
GLOBAL_PAGE_SIZE = 60
GLOBAL_PAGE_CEILING = 100


def _full_graph_payload(graph: Any) -> dict[str, Any]:
    """Project the complete institutional graph without source passage text."""
    nodes = []
    documents: dict[str, dict[str, Any]] = {}
    for node_id, node in graph.nodes.items():
        sources = node.get("sources") or []
        linked_docs: set[str] = set()
        for source in sources:
            if not isinstance(source, dict):
                continue
            doc_id = str(source.get("doc_id") or "").strip()
            if not doc_id or doc_id in linked_docs:
                continue
            linked_docs.add(doc_id)
            row = documents.setdefault(
                doc_id,
                {
                    "id": doc_id,
                    "title": PurePosixPath(doc_id).name.removesuffix(".pdf").replace("_", " "),
                    "concepts": 0,
                    "concept_ids": [],
                },
            )
            row["concepts"] = int(row["concepts"]) + 1
            row["concept_ids"].append(node_id)
        source_documents = []
        seen_sources: set[str] = set()
        for source in sources:
            if not isinstance(source, dict):
                continue
            doc_id = str(source.get("doc_id") or "").strip()
            if not doc_id or doc_id in seen_sources:
                continue
            seen_sources.add(doc_id)
            source_documents.append(
                {
                    "id": doc_id,
                    "title": PurePosixPath(doc_id).name.removesuffix(".pdf").replace("_", " "),
                    "page_number": source.get("page_number"),
                }
            )
            if len(source_documents) == MAX_SOURCE_DOCUMENT_NODES:
                break
        degree = len(graph.out.get(node_id, [])) + len(graph.inn.get(node_id, []))
        nodes.append(
            {
                "data": {
                    "id": node_id,
                    "name": graph.label(node_id),
                    "summary": str(node.get("summary") or "")[:MAX_PUBLIC_SUMMARY_CHARS],
                    "kind": str(
                        node.get("concept_type")
                        or node.get("type")
                        or node.get("kind")
                        or DEFAULT_KIND
                    ),
                    "difficulty": str(node.get("difficulty") or ""),
                    "degree": degree,
                    "source_count": len(linked_docs),
                    "source_documents": source_documents,
                }
            }
        )
    edges = []
    seen: set[tuple[str, str, str]] = set()
    for source, neighbors in graph.out.items():
        for relation, target in neighbors:
            key = (source, target, relation)
            if target not in graph.nodes or key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "data": {
                        "id": f"{source}:{relation}:{target}",
                        "source": source,
                        "target": target,
                        "rel_label": relation,
                        "source_ref": str(
                            (getattr(graph, "edge_records", {}).get(key) or {}).get("source") or ""
                        ),
                    }
                }
            )
    return {
        "nodes": nodes,
        "edges": edges,
        "documents": sorted(documents.values(), key=lambda row: str(row["title"]).casefold()),
        "counts": {
            "concepts": len(nodes),
            "relationships": len(edges),
            "documents": len(documents),
        },
        "corpus_source": getattr(graph, "corpus_source", "unknown"),
        "graph_version": getattr(graph, "graph_version", "unknown"),
        "last_sync": getattr(graph, "last_sync", None),
    }


def register(app: Flask, ctx: AppContext) -> None:
    """Register the graph neighborhood route on ``app``."""

    @app.get("/api/graph/hubs")  # type: ignore[misc]
    def graph_hubs() -> ResponseReturnValue:
        """Return prominent saved concepts for the academic graph entry view."""
        payload = _full_graph_payload(ctx.engine.graph)
        nodes = sorted(
            (item for item in payload["nodes"] if item["data"]["degree"] > 0),
            key=lambda item: (-item["data"]["degree"], item["data"]["name"]),
        )[:GRAPH_HUB_LIMIT]
        ids = {item["data"]["id"] for item in nodes}
        candidates = [
            item
            for item in payload["edges"]
            if item["data"]["source"] in ids and item["data"]["target"] in ids
        ]
        edges = sorted(candidates, key=lambda row: row["data"]["id"])[:GRAPH_HUB_EDGE_LIMIT]
        return jsonify({"nodes": nodes, "edges": edges, "counts": payload["counts"]})

    @app.get("/api/research/graph/full")  # type: ignore[misc]
    def graph_full() -> ResponseReturnValue:
        """Return every indexed concept and relationship for the staff canvas."""
        return jsonify(_full_graph_payload(ctx.engine.graph))

    @app.get("/api/graph/page")  # type: ignore[misc]
    def graph_global_page() -> ResponseReturnValue:
        """Page every exported concept while leaving focused routes unchanged."""
        payload = _full_graph_payload(ctx.engine.graph)
        try:
            offset = max(0, int(request.args.get("offset", 0)))
            size = max(
                1, min(GLOBAL_PAGE_CEILING, int(request.args.get("limit", GLOBAL_PAGE_SIZE)))
            )
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_pagination"}), 400
        query = (request.args.get("q") or "").casefold().strip()
        nodes = sorted(payload["nodes"], key=lambda row: row["data"]["id"])
        if query:
            document_hits = {
                cid
                for document in payload["documents"]
                if query in str(document["title"]).casefold()
                for cid in document["concept_ids"]
            }
            nodes = [
                row
                for row in nodes
                if query
                in " ".join(
                    str(row["data"].get(key) or "") for key in ("id", "name", "summary")
                ).casefold()
                or row["data"]["id"] in document_hits
            ]
        page_nodes = nodes[offset : offset + size]
        page_ids = {row["data"]["id"] for row in page_nodes}
        relation = (request.args.get("relation") or "").upper()
        edges = [
            row
            for row in payload["edges"]
            if row["data"]["source"] in page_ids
            and row["data"]["target"] in page_ids
            and (not relation or row["data"]["rel_label"] == relation)
        ]
        return jsonify(
            {
                "nodes": page_nodes,
                "edges": edges,
                "counts": payload["counts"],
                "corpus_source": payload["corpus_source"],
                "offset": offset,
                "graph_version": payload["graph_version"],
                "last_sync": payload["last_sync"],
                "next_offset": offset + size if offset + size < len(nodes) else None,
                "matched_total": len(nodes),
            }
        )

    @app.get("/api/research/graph/subgraph")  # type: ignore[misc]
    @app.get("/api/graph/subgraph")  # type: ignore[misc]
    def graph_subgraph() -> ResponseReturnValue:
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
            max_nodes = max(
                MAX_NODES_FLOOR,
                min(MAX_NODES_CEILING, int(request.args.get("max_nodes") or MAX_NODES_DEFAULT)),
            )
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
            neighbors = [
                (current, neighbor, relation) for relation, neighbor in graph.out.get(current, [])
            ]
            neighbors.extend(
                (neighbor, current, relation) for relation, neighbor in graph.inn.get(current, [])
            )
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
            source_documents = {
                str(source.get("doc_id"))
                for source in node.get("sources") or []
                if isinstance(source, dict) and source.get("doc_id")
            }
            visible_documents = []
            seen_documents: set[str] = set()
            for source in node.get("sources") or []:
                if not isinstance(source, dict):
                    continue
                doc_id = str(source.get("doc_id") or "")
                if not doc_id or doc_id in seen_documents:
                    continue
                seen_documents.add(doc_id)
                visible_documents.append(
                    {
                        "id": doc_id,
                        "title": PurePosixPath(doc_id).name.removesuffix(".pdf").replace("_", " "),
                        "page_number": source.get("page_number"),
                    }
                )
                if len(visible_documents) == MAX_SOURCE_DOCUMENT_NODES:
                    break
            nodes.append(
                {
                    "data": {
                        "id": node_id,
                        "name": graph.label(node_id),
                        "summary": str(node.get("summary") or "")[:SUMMARY_CHAR_LIMIT],
                        "kind": str(
                            node.get("concept_type")
                            or node.get("type")
                            or node.get("kind")
                            or DEFAULT_KIND
                        ),
                        "difficulty": str(node.get("difficulty") or ""),
                        "degree": len(graph.out.get(node_id, [])) + len(graph.inn.get(node_id, [])),
                        "source_count": len(source_documents),
                        "source_documents": visible_documents,
                    }
                }
            )
        edges = []
        seen_edges = set()
        for source, target, relation in edge_rows:
            key = (source, target, relation)
            if source not in selected_set or target not in selected_set or key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(
                {
                    "data": {
                        "id": f"{source}:{relation}:{target}",
                        "source": source,
                        "target": target,
                        "rel_label": relation,
                        "source_ref": str(
                            (getattr(graph, "edge_records", {}).get(key) or {}).get("source") or ""
                        ),
                    }
                }
            )
        return jsonify({"target_id": target_id, "nodes": nodes, "edges": edges})
