"""Staff-only access to the saved research graph and its JSON export."""

from __future__ import annotations

from flask import Flask, jsonify, make_response
from flask.typing import ResponseReturnValue
import requests

from ..context import AppContext
from ..research_intake_store import list_graph_records
from ..research_projection import project_research_graph


def register(app: Flask, ctx: AppContext) -> None:
    """Expose the projected research graph without granting browser DB access."""

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
