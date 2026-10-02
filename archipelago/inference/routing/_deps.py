"""Late-bound access to the routing package's own namespace.

The routing pipeline historically lived in a single module, so callers (and
tests) monkeypatch attributes on ``archipelago.inference.routing`` itself and
expect the pipeline to see the patch.  After the package split, every
cross-module call resolves through this shim at *call time* instead of binding
the name at import time — preserving that contract.

Usage inside the package::

    from . import _deps as _rt

    ranked = _rt.rank_concepts(query, top_k=10)
"""
from __future__ import annotations

import archipelago.inference.routing as _routing


def __getattr__(name: str):
    """Resolve ``name`` against the live routing package namespace."""
    return getattr(_routing, name)
