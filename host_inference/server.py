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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", DEFAULT_PORT)), threaded=True)
