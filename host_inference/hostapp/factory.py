"""Application factory for the hosted Archipelago app.

One concern: assembling the app — collaborators, middleware, routes — so tests
can build an app around fakes and production gets the real graph-backed engine.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from flask import Flask

from .config import MAX_CONTENT_LENGTH_BYTES, load_env
from .context import AppContext
from .corpus_bootstrap import provision
from .inventory_store import InventoryStore

# Local, not from archipelago: the hosted image is built from this directory
# alone, so the sibling package is not in the container. Relative import so it
# resolves however the tree is reached — flat on sys.path in the container, or
# as host_inference.hostapp from a test. tests/unit/test_host_log_redaction.py
# pins this copy to the shared one so they cannot diverge.
from .log_redaction import install_log_redaction
from .middleware import register_middleware
from .routes import register_routes
from .runtime_state import install_shutdown_handlers
from .security import AuthGuard, RateLimiter

CONTEXT_KEY = "archipelago"


class _LazyEngineProxy:
    """Defer Engine() hydration until an inference/corpus route accesses it.

    Auth, login, and HTML shell routes (/login, /chat, /api/auth/*) never block
    on cold-start graph/passage hydration.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: Any = None

    def _ensure(self) -> Any:
        inst = self._instance
        if inst is not None:
            return inst
        with self._lock:
            if self._instance is None:
                from engine import Engine

                self._instance = Engine()
            return self._instance

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ensure(), name)


def build_context() -> AppContext:
    """Build the production collaborators.

    ``Engine`` is initialized lazily on first attribute access so cold-start
    auth and HTML routes respond immediately without waiting for corpus/graph
    hydration.
    """
    from cache_service import cache_metrics, cache_service, request_dedup

    return AppContext(
        engine=_LazyEngineProxy(),
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
    install_shutdown_handlers()
    # Vercel's application directory is read-only. Its packaged graph and the
    # writable cache populated by Engine.hydrate replace boot-time provisioning.
    if not os.environ.get("VERCEL"):
        provision()
    context = ctx or build_context()
    app = Flask(__name__)
    app.debug = False
    app.config["DEBUG"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_BYTES
    app.extensions[CONTEXT_KEY] = context
    install_log_redaction(app.import_name, "hostapp", "host_inference.hostapp", "flask.app")
    register_middleware(app, context)
    register_routes(app, context)
    return app
