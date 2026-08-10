"""5-Stage local inference pipeline for Archipelago.

Re-exports pipeline execution functions from synthesis_pipeline while maintaining
backwards compatibility and maintaining module size <= 500 lines.
"""
from __future__ import annotations

import logging
from typing import Any

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

logger = logging.getLogger(__name__)

__all__ = [
    "_stage1_guardrails",
    "_stage2_vector_search",
    "_stage3_graph_traversal",
    "_stage4_build_payload",
    "_stage5_ollama_synthesis",
    "run_archipelago_inference",
]
