"""5-Stage local inference pipeline for Archipelago.

Re-exports pipeline execution functions from synthesis_pipeline while maintaining
backwards compatibility and maintaining module size <= 500 lines.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from archipelago.inference import synthesis_pipeline as _pipeline
from archipelago.inference import state as st
from archipelago.inference.synthesis_pipeline import (
    _stage1_guardrails,
    _stage2_vector_search,
    _stage3_graph_traversal,
    _stage4_build_payload,
    _stage5_ollama_synthesis,
    run_archipelago_inference,
    _acquire_ollama,
    _release_ollama,
    _ollama_client,
)

_PIPELINE_COMPAT_LOCK = threading.RLock()
_DEFAULT_STAGES = {
    "_stage1_guardrails": _stage1_guardrails,
    "_stage2_vector_search": _stage2_vector_search,
    "_stage3_graph_traversal": _stage3_graph_traversal,
    "_stage4_build_payload": _stage4_build_payload,
    "_stage5_ollama_synthesis": _stage5_ollama_synthesis,
}


def run_archipelago_inference(query: str, history: list[Any] | None = None) -> dict[str, Any]:
    """Run the pipeline while preserving the historical monkeypatchable API."""
    with _PIPELINE_COMPAT_LOCK:
        names = tuple(_DEFAULT_STAGES)
        previous = {name: getattr(_pipeline, name) for name in names}
        try:
            for name in names:
                exported = globals()[name]
                if exported is not _DEFAULT_STAGES[name]:
                    setattr(_pipeline, name, exported)
            return _pipeline.run_archipelago_inference(query, history=history)
        finally:
            for name, implementation in previous.items():
                setattr(_pipeline, name, implementation)

logger = logging.getLogger(__name__)

__all__ = [
    "_stage1_guardrails",
    "_stage2_vector_search",
    "_stage3_graph_traversal",
    "_stage4_build_payload",
    "_stage5_ollama_synthesis",
    "run_archipelago_inference",
]
