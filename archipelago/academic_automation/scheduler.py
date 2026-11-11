"""Run configured metadata providers without starting content or GPU work."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import requests  # type: ignore[import-untyped]

from .reconcile import reconcile
from .store import AcademicStore

Source = Callable[[], list[dict[str, Any]]]


def sync_sources(store: AcademicStore, sources: dict[str, Source]) -> list[dict[str, Any]]:
    """Check sources independently; failed calls preserve known records."""
    outcomes = []
    for name, fetch in sources.items():
        try:
            rows = fetch()
            outcomes.append(reconcile(store, name, rows, complete=False))
        except (OSError, ValueError, KeyError, TypeError, requests.RequestException) as exc:
            store.provider_result(name, error=type(exc).__name__)
            outcomes.append(
                {"provider": name, "status": "unavailable", "error": type(exc).__name__}
            )
    return outcomes
