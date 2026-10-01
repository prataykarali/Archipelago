"""The shared application context handed to every route registrar.

One concern: carrying the collaborators (engine, auth, rate limiter, inventory
store, caches) so routes depend on an injected object rather than module
globals.  Tests can build a context with fakes and register routes against it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AppContext:
    """Collaborators shared by the hosted app's routes."""

    engine: Any
    auth: Any
    limiter: Any
    inventory: Any
    cache_service: Any
    cache_metrics: Any
    request_dedup: Any
