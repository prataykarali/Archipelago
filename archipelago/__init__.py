"""Archipelago — feature packages (inference, ingestion, okf, core, graph).

This is the single canonical package.  It previously extended ``__path__`` to
also load modules from a parallel ``src/archipelago`` tree; that duplicate has
been removed and every module now lives here.
"""
from __future__ import annotations

__all__: list[str] = []
