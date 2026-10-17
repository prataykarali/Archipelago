"""Read-only live scholarly discovery for chat and library pages."""

from __future__ import annotations

from flask import jsonify, request
from flask.typing import ResponseReturnValue

from archipelago.inference import state as st
from archipelago.scholarly.access import ResearchCapability, require_research
from archipelago.scholarly.discovery.orchestrator import DiscoveryOrchestrator
from archipelago.scholarly.pipeline.routes import _store, register_research_routes

MAX_QUERY_CHARS = 200
MAX_RESULTS_PER_SOURCE = 5


@st.app.get("/api/scholarly/discover")
@require_research(ResearchCapability.SEARCH)
def scholarly_discover() -> ResponseReturnValue:
    """Return source-labeled live records and fallback links without ingestion."""
    query = request.args.get("q", "").strip()
    if not query or len(query) > MAX_QUERY_CHARS:
        return jsonify({"error": "q must contain 1 to 200 characters"}), 400
    if _store() is None:
        return jsonify({"error": "research_disabled"}), 503
    candidates, sources = DiscoveryOrchestrator().discover_with_status(
        query, limit_per_source=MAX_RESULTS_PER_SOURCE
    )
    return jsonify(
        {
            "query": query,
            "source_status": sources,
            "candidates": [
                {"paper": item["paper"].model_dump(mode="json"), "source": item.get("source")}
                for item in candidates
            ],
        }
    )


register_research_routes(st.app)
