"""Scholarly discovery and manifest synchronization components.

Exports are loaded on demand so ``python -m ...scheduler`` executes only once.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["CloudSyncPipeline", "HarvestScheduler", "ParallelHarvester"]

_MODULES = {
    "CloudSyncPipeline": "cloud_sync",
    "HarvestScheduler": "scheduler",
    "ParallelHarvester": "parallel_harvester",
}


def __getattr__(name: str) -> Any:
    """Load a public pipeline class without importing sibling entrypoints."""
    module_name = _MODULES.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, name)
