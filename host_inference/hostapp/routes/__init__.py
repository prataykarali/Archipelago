"""Route registry for the hosted Archipelago app.

One concern: registering every route group against a Flask app and its context.
Adding a feature means adding one module and one line here.
"""
from __future__ import annotations

from flask import Flask

from ..context import AppContext
from . import auth, chat, diagnostics, graph, library, pages, reader, static

MODULES = (pages, graph, auth, library, reader, static, chat, diagnostics)


def register_routes(app: Flask, ctx: AppContext) -> None:
    """Register all hosted route groups on ``app``."""
    for module in MODULES:
        module.register(app, ctx)
