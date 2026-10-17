"""Staff-only view of the hosted knowledge graph and ingestion capability."""

from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, redirect, send_from_directory
from werkzeug.wrappers import Response

from ..config import ELEVATED_ROLES, UI
from ..context import AppContext

STUDIO = UI / "studio"
ALLOWED_ASSET_PREFIXES = ("js/", "styles/")
SOURCE_FIELDS = ("doc_id", "chunk_id", "page_number", "section_title", "text_passage")
NODE_FIELDS = ("concept_type", "summary", "difficulty", "tags", "prerequisites", "unlocks")


def register(app: Flask, ctx: AppContext) -> None:
    """Register the staff page, its assets, and the graph projection it reads."""

    def staff_access() -> tuple[dict[str, Any] | None, tuple[Response, int] | None]:
        principal, _error = ctx.auth.principal()
        if principal is None:
            return None, (jsonify({"error": "unauthorized"}), 401)
        if principal.get("role") not in ELEVATED_ROLES:
            return None, (jsonify({"error": "forbidden"}), 403)
        return principal, None

    @app.get("/studio")
    @app.get("/studio/")
    def studio_page() -> Response | tuple[Response, int]:
        principal, denied = staff_access()
        if denied:
            if principal is None and denied[1] == 401:
                return redirect("/login?next=/studio")
            return denied
        return send_from_directory(STUDIO, "index.html")

    @app.get("/studio/assets/<path:filename>")
    def studio_asset(filename: str) -> Response | tuple[Response, int]:
        _principal, denied = staff_access()
        if denied:
            return denied
        if not filename.startswith(ALLOWED_ASSET_PREFIXES):
            return jsonify({"error": "not_found"}), 404
        return send_from_directory(STUDIO, filename)

    @app.get("/api/studio/graph")
    def studio_graph() -> Response | tuple[Response, int]:
        _principal, denied = staff_access()
        if denied:
            return denied
        graph = ctx.engine.graph
        nodes = []
        for node_id, node in graph.nodes.items():
            sources = [
                {field: source[field] for field in SOURCE_FIELDS if field in source}
                for source in node.get("sources") or []
                if isinstance(source, dict)
            ]
            projected = {
                "id": node_id,
                "label": graph.label(node_id),
                "sources": sources,
            }
            projected.update({field: node[field] for field in NODE_FIELDS if field in node})
            nodes.append(projected)
        edges = [
            {"source": source, "target": target, "relation": relation.lower()}
            for source, neighbors in graph.out.items()
            for relation, target in neighbors
        ]
        return jsonify(
            {
                "nodes": nodes,
                "edges": edges,
                "corpus_source": getattr(graph, "corpus_source", "unknown"),
                "read_only": True,
            }
        )
