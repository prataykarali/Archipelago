"""HTML page routes and health/readiness endpoints.

One concern: serving the four UI shells and reporting readiness.  Health output
is computed from the live graph, never hard-coded.
"""
from __future__ import annotations

from flask import Flask, jsonify, redirect, send_from_directory

from ..config import AUTH_GATED_PAGES, ELEVATED_ROLES, PAGE_FILES, UI
from ..context import AppContext

GRAPH_PAGE_FILE = "graph.html"


def register(app: Flask, ctx: AppContext) -> None:
    """Register page and health routes on ``app``."""

    def _page(name: str):
        if name in AUTH_GATED_PAGES and ctx.auth.required():
            principal, _error = ctx.auth.principal()
            if principal is None:
                return redirect(f"/login?next=/{name}")
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
        return send_from_directory(UI, GRAPH_PAGE_FILE)

    @app.get("/library")
    @app.get("/library/")
    def library_page():
        return _page("library")

    @app.get("/login")
    def login_page():
        return _page("login")

    @app.get("/health")
    @app.get("/ready")
    @app.get("/api/health")
    @app.get("/api/readiness")
    def health():
        return jsonify({
            "ok": True,
            "mode": "inference-only",
            "concepts": len(ctx.engine.graph.nodes),
            "pearson_books": len(ctx.engine.books),
            "cache": ctx.engine.cache_info.get("source"),
            "ingestion": False,
            "cache_metrics": ctx.cache_metrics.stats(),
        })

    @app.get("/api/metrics/cache")
    def api_cache_metrics():
        """AI API budget protection metrics (Doc 03 Section 11)."""
        return jsonify(ctx.cache_metrics.stats())
