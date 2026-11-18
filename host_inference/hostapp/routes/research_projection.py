"""Staff-only access to the saved research graph and its JSON export."""

from __future__ import annotations

from flask import Flask, jsonify, make_response, request
from flask.typing import ResponseReturnValue
import requests

from ..context import AppContext
from ..research_intake_store import list_graph_records
from ..research_projection import project_research_graph

STAFF_ROLES = frozenset({"faculty", "librarian", "administrator"})


def register(app: Flask, ctx: AppContext) -> None:
    """Expose the projected research graph without granting browser DB access."""

    @app.before_request  # type: ignore[misc]
    def projection_auth_guard() -> ResponseReturnValue | None:
        if request.path not in {
            "/api/research/graph/ingested",
            "/api/research/graph/papers",
            "/api/research/graph/export",
        }:
            return None
        principal = getattr(request, "archipelago_principal", None)
        if principal is None and getattr(ctx, "auth", None) is not None:
            principal, _err = ctx.auth.principal()
            if isinstance(principal, dict) and principal.get("id"):
                request.archipelago_principal = principal  # type: ignore[attr-defined]
        if principal is not None and principal.get("role") not in STAFF_ROLES:
            return jsonify({"error": "forbidden"}), 403
        if principal is None and getattr(ctx, "auth", None) is not None and ctx.auth.required():
            return jsonify({"error": "unauthorized"}), 401
        return None

    @app.after_request  # type: ignore[misc]
    def projection_private_cache_headers(response):
        if request.path in {
            "/api/research/graph/ingested",
            "/api/research/graph/papers",
            "/api/research/graph/export",
        }:
            response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Vary"] = "Authorization, Cookie"
        return response

    def payload() -> dict[str, object]:
        records, truncated = list_graph_records()
        concepts = {
            concept_id: {**node, "label": ctx.engine.graph.label(concept_id)}
            for concept_id, node in ctx.engine.graph.nodes.items()
        }
        graph = project_research_graph(records, concepts)
        graph["truncated"] = truncated
        return graph

    @app.get("/api/research/graph/ingested")  # type: ignore[misc]
    def ingested_graph() -> ResponseReturnValue:
        try:
            return jsonify(payload())
        except (requests.RequestException, RuntimeError, ValueError):
            app.logger.exception("Research graph projection unavailable")
            return jsonify({"error": "graph_unavailable"}), 503

    @app.get("/api/research/graph/papers")  # type: ignore[misc]
    def paper_graph() -> ResponseReturnValue:
        """Keep scholarly topic and paper nodes separate from the academic graph."""
        try:
            records, truncated = list_graph_records()
            graph = project_research_graph(
                [
                    record
                    for record in records
                    if record.get("kind") == "paper"
                    and (record.get("metadata") or {}).get("ingestion_pipeline") == "local_indra_v3"
                ],
                {},
            )
            graph["truncated"] = truncated
            return jsonify(graph)
        except (requests.RequestException, RuntimeError, ValueError):
            app.logger.exception("Scholarly paper graph unavailable")
            return jsonify({"error": "graph_unavailable"}), 503

    @app.get("/api/research/graph/export")  # type: ignore[misc]
    def export_graph() -> ResponseReturnValue:
        try:
            response = make_response(jsonify(payload()))
        except (requests.RequestException, RuntimeError, ValueError):
            app.logger.exception("Research graph export unavailable")
            return jsonify({"error": "graph_unavailable"}), 503
        response.headers["Content-Disposition"] = (
            'attachment; filename="archipelago-research-graph.json"'
        )
        return response
