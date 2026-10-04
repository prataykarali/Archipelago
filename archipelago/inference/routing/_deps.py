"""Late-bound routing collaborators, preserving both public patch boundaries."""
from __future__ import annotations

from archipelago.inference import intent_gate, ranking, scope_gate
import archipelago.inference.routing as _routing

_MODULES = (ranking, intent_gate, scope_gate)
_ORIGINALS: dict = {}


def __getattr__(name: str):
    """Prefer explicit routing overrides, otherwise resolve the current collaborator."""
    value = getattr(_routing, name)
    for module in _MODULES:
        if not hasattr(module, name):
            continue
        current = getattr(module, name)
        original = _ORIGINALS.setdefault(name, value)
        return current if value is original else value
    return value
