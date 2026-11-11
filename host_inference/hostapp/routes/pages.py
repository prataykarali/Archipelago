"""HTML page routes and health/readiness endpoints.

One concern: serving the four UI shells and reporting readiness.  Health output
is computed from the live graph, never hard-coded.
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, redirect, request, send_from_directory

from ..config import AUTH_GATED_PAGES, ELEVATED_ROLES, PAGE_FILES, UI
from ..context import AppContext
from ..page_fragments import assembled_page
from ..research_pages import PAGE_DETAILS
from .ingest import _worker_available

GRAPH_PAGE_FILE = "graph.html"
RESEARCH_ORIGIN = "https://archipelago-librarian.vercel.app"

#: Concept count below which the deployment is provably running the tracked
#: fixture rather than the library's full corpus.  The fixture is ~59 concepts;
#: the real corpus is 500+.  Kept here so the readiness report and the threshold
#: that produced it are stated together.
FULL_CORPUS_MIN_CONCEPTS = 200


def register(app: Flask, ctx: AppContext) -> None:
    """Register page and health routes on ``app``."""

    def _page(name: str):
        if name in AUTH_GATED_PAGES and ctx.auth.required():
            principal, _error = ctx.auth.principal()
            if principal is None:
                return redirect(f"/login?next=/{name}")
        if name in {"chat", "library"}:
            return assembled_page(UI, PAGE_FILES[name])
        return send_from_directory(UI, PAGE_FILES[name])

    @app.get("/")
    @app.get("/landing")
    def landing():
        return _page("landing")

    @app.get("/chat")
    @app.get("/chat/")
    def chat_page():
        return _page("chat")

    @app.get("/graph")
    def graph_page():
        if ctx.auth.required():
            principal, _error = ctx.auth.principal()
            if principal is None:
                return redirect("/login?next=/graph")
            if principal.get("role") not in ELEVATED_ROLES:
                return redirect("/chat")
        return redirect(f"{RESEARCH_ORIGIN}/academic/graph")

    @app.get("/research")
    @app.get("/research/")
    def research_page():
        return redirect(f"{RESEARCH_ORIGIN}{request.full_path.rstrip('?')}")

    @app.get("/research/<page>")
    def research_subpage(page: str):
        if page not in PAGE_DETAILS:
            return jsonify({"error": "not_found"}), 404
        return redirect(f"{RESEARCH_ORIGIN}{request.full_path.rstrip('?')}")

    @app.get("/library")
    @app.get("/library/")
    def library_page():
        # The catalogue details page is a public entry point even when chat
        # sessions are required elsewhere in the deployment.
        return assembled_page(UI, PAGE_FILES["library"])

    @app.get("/login")
    def login_page():
        return _page("login")

    @app.get("/health")
    @app.get("/ready")
    @app.get("/api/health")
    @app.get("/api/readiness")
    def health():
        # ``ok`` means the process is up and serving — it must stay true for the
        # platform's health check to pass. Whether the *corpus* is the full one is
        # reported separately in ``corpus``, because a deployment running the
        # tracked fixture is healthy and yet answering a much narrower library,
        # and an operator must be able to tell those apart from outside.
        graph = ctx.engine.graph
        concepts = len(graph.nodes)
        # Read the marker defensively: tests and alternate engines supply their
        # own graph objects, and readiness must never be the thing that 500s.
        source = getattr(graph, "corpus_source", None) or (
            "fixture" if concepts < FULL_CORPUS_MIN_CONCEPTS else "full"
        )
        return jsonify(
            {
                "ok": True,
                "mode": "inference-only",
                "concepts": concepts,
                "corpus": {
                    "concepts": concepts,
                    "full": source == "full",
                    "source": source,
                },
                "pearson_books": len(ctx.engine.books),
                "cache": ctx.engine.cache_info.get("source"),
                "ingestion": _worker_available(),
                "research_intake": {
                    "enabled": bool(
                        os.getenv("SUPABASE_URL")
                        and (
                            os.getenv("SUPABASE_SECRET_KEY")
                            or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                        )
                    ),
                    "scope": "scholarly_metadata_and_institutional_html",
                },
                "cache_metrics": ctx.cache_metrics.stats(),
            }
        )

    @app.get("/api/metrics/cache")
    def api_cache_metrics():
        """AI API budget protection metrics (Doc 03 Section 11)."""
        return jsonify(ctx.cache_metrics.stats())
