"""Fail closed if a Vercel release cannot load the institutional corpus."""

from __future__ import annotations

import os
import re

from flask import Flask, Response
from hostapp.factory import build_context, create_app
from hostapp.runtime_state import install_shutdown_handlers

MINIMUM_LIVE_CONCEPTS = 520
MINIMUM_LIVE_PEARSON_BOOKS = 40
RESEARCH_SUPABASE_URL = "https://edokbtmhztkhndmxetpy.supabase.co"
RESEARCH_PROJECT_ID = "edokbtmhztkhndmxetpy"
_SAFE_SHA_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def resolve_release_sha() -> str:
    """Resolve the deployed release SHA from explicit or Vercel Git env vars."""
    for env_key in ("ARCHIPELAGO_RELEASE_SHA", "VERCEL_GIT_COMMIT_SHA"):
        candidate = (os.environ.get(env_key) or "").strip()
        if candidate and _SAFE_SHA_RE.fullmatch(candidate):
            return candidate
    return "unversioned"


def create_vercel_app() -> Flask:
    """Build the app only with the existing full Supabase corpus."""
    if (
        os.environ.get("VERCEL")
        and os.environ.get("SUPABASE_URL", "").rstrip("/") != RESEARCH_SUPABASE_URL
    ):
        raise RuntimeError("Release blocked: Supabase project is not Research Staging")
    research_dsn = os.environ.get("ARCHIPELAGO_RESEARCH_DATABASE_URL", "")
    if os.environ.get("VERCEL") and research_dsn and RESEARCH_PROJECT_ID not in research_dsn:
        raise RuntimeError("Release blocked: research database URL is not staging scoped")
    os.environ["ARCHIPELAGO_ENV"] = "production"
    install_shutdown_handlers()
    context = build_context()
    engine = context.engine
    graph = engine.graph
    if (
        engine.cache_info.get("source") not in {"supabase", "bundled", "fallback", "local"}
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
    app.debug = False
    app.config["DEBUG"] = False

    @app.after_request
    def release_headers(response: Response) -> Response:
        response.headers["X-Archipelago-Release"] = resolve_release_sha()
        return response

    return app
