"""Late-bound access to this package namespace (monkeypatch contract)."""
from __future__ import annotations

import archipelago.inference.ods_parser as _pkg


def __getattr__(name: str):
    """Resolve ``name`` against the live package namespace."""
    return getattr(_pkg, name)
