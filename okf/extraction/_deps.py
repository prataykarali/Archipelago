"""Late-bound access to this package namespace (monkeypatch contract)."""

from __future__ import annotations

from typing import Any

import okf.extraction as _pkg


def __getattr__(name: str) -> Any:
    """Resolve ``name`` against the live package namespace."""
    return getattr(_pkg, name)
