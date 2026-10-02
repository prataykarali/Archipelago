"""Application factory for the hosted Archipelago app.

One concern: assembling the app — collaborators, middleware, routes — so tests
can build an app around fakes and production gets the real graph-backed engine.
"""
from __future__ import annotations

from flask import Flask

from archipelago.middleware.log_redaction import install_log_redaction

from .config import MAX_CONTENT_LENGTH_BYTES, load_env
from .context import AppContext
from .corpus_bootstrap import provision
from .inventory_store import InventoryStore
from .middleware import register_middleware
from .routes import register_routes
from .security import AuthGuard, RateLimiter

CONTEXT_KEY = "archipelago"


def build_context() -> AppContext:
    """Build the production collaborators.

    ``Engine`` is imported lazily so a test can substitute it before the app is
    created.
    """
    from cache_service import cache_metrics, cache_service, request_dedup
    from engine import Engine

    return AppContext(
        engine=Engine(),
        auth=AuthGuard(),
        limiter=RateLimiter(),
        inventory=InventoryStore(),
        cache_service=cache_service,
        cache_metrics=cache_metrics,
        request_dedup=request_dedup,
    )


def create_app(ctx: AppContext | None = None) -> Flask:
    """Create and configure the hosted Flask app.

    Provisions the concept graph first: every corpus artifact is gitignored, so a
    fresh build has none, and an engine built against an empty graph answers
    "not indexed" to everything while ``/api/readiness`` still reports healthy.
    Boot fetch, then the tracked fixture; never raises.

    Args:
        ctx: Optional pre-built context. Tests pass fakes; production omits it
            and gets :func:`build_context`.

    Returns:
        A configured :class:`flask.Flask` app with all routes registered.
    """
    load_env()
    # Scrub tokens/credentials from access logs before any record is emitted.
    install_log_redaction()
    provision()
    context = ctx or build_context()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_BYTES
    app.extensions[CONTEXT_KEY] = context
    register_middleware(app, context)
    register_routes(app, context)
    return app
