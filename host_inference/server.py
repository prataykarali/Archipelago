"""Hosted Archipelago inference entry point.

Thin shim over :mod:`hostapp`.  It exists so ``python server.py`` and
``import server`` keep working exactly as before; the application itself is
assembled by :func:`hostapp.create_app`.

Ingestion, uploads and librarian job controls are not served here.
"""
from __future__ import annotations

import os

from hostapp import create_app
from hostapp.config import DEFAULT_PORT

app = create_app()


def _resolve_bind_host() -> str:
    """Loopback by default; all interfaces only with an explicit opt-in token."""
    explicit = os.environ.get("ARCHIPELAGO_BIND_HOST", "").strip()
    if explicit:
        return explicit
    if os.environ.get("ARCHIPELAGO_TOKEN", "").strip():
        return "0.0.0.0"  # nosec B104 — explicit authenticated opt-in
    return "127.0.0.1"


if __name__ == "__main__":
    app.run(
        host=_resolve_bind_host(),
        port=int(os.environ.get("PORT", DEFAULT_PORT)),
        threaded=True,
    )
