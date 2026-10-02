"""WSGI entrypoint for the hosted app.

Gunicorn's ``module:factory`` form is ambiguous across versions — 26.x calls the
callable with arguments, so ``hostapp.factory:create_app`` fails at request time
with ``create_app() takes from 0 to 1 positional arguments but 2 were given``.
Exposing a module-level ``application`` object sidesteps the question entirely:
gunicorn imports the module once per worker and serves the object it finds.

Boot cost is unchanged — ``create_app()`` provisions the corpus and builds the
engine, exactly as it did when the factory was referenced directly.
"""
from __future__ import annotations

from .factory import create_app

#: The WSGI callable gunicorn serves.
application = create_app()

__all__ = ["application"]
