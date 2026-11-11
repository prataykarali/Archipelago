"""Fail closed if a Vercel release cannot load the institutional corpus."""

from __future__ import annotations

import os

from flask import Flask, Response
from hostapp.factory import build_context, create_app

MINIMUM_LIVE_CONCEPTS = 520
MINIMUM_LIVE_PEARSON_BOOKS = 40


def create_vercel_app() -> Flask:
    """Build the app only with the existing full Supabase corpus."""
    os.environ["ARCHIPELAGO_ENV"] = "production"
    context = build_context()
    engine = context.engine
    graph = engine.graph
    if (
        engine.cache_info.get("source") != "supabase"
        or getattr(graph, "corpus_source", None) != "full"
        or len(graph.nodes) < MINIMUM_LIVE_CONCEPTS
        or len(engine.books) < MINIMUM_LIVE_PEARSON_BOOKS
    ):
        raise RuntimeError("Release blocked: the full institutional corpus is unavailable")
    expected_graph = os.environ.get("ARCHIPELAGO_EXPECTED_GRAPH_VERSION", "").strip()
    if expected_graph and graph.graph_version != expected_graph:
        raise RuntimeError(
            "Release blocked: hosted graph version differs from approved publication"
        )
    app = create_app(context)

    @app.after_request
    def release_headers(response: Response) -> Response:
        response.headers["X-Archipelago-Release"] = (
            os.environ.get("ARCHIPELAGO_RELEASE_SHA") or "unversioned"
        )
        return response

    return app
