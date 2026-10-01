"""Hosted Archipelago application package.

This package was split out of a single ``server.py``.  ``server.py`` remains a
thin shim so ``python server.py`` and ``import server`` keep working, while the
implementation lives in focused modules:

* :mod:`hostapp.config`          — env loading, roots, public-API and rate policy
* :mod:`hostapp.security`        — auth guard and rate limiter
* :mod:`hostapp.inventory_store` — holdings validation and persistence
* :mod:`hostapp.context`         — the injected :class:`AppContext`
* :mod:`hostapp.middleware`      — request guard, headers, error handlers
* :mod:`hostapp.routes`          — one module per route group
* :mod:`hostapp.factory`         — :func:`create_app`
"""
from __future__ import annotations

from .context import AppContext
from .factory import CONTEXT_KEY, build_context, create_app

__all__ = ["AppContext", "CONTEXT_KEY", "build_context", "create_app"]
