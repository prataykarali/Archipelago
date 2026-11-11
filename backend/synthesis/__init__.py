"""Synthesis orchestration and multi-model LLM gateway for Archipelago."""
from __future__ import annotations

from archipelago.inference.llm_gateway import (
    configure_gateway,
    gateway_chat,
    gateway_chat_stream,
    is_llm_available,
)
from archipelago.inference.synthesis import (
    build_graph_notes,
    enforce_sterile_prose,
    format_natural_fallback,
    stream_synthesis_with_ollama,
    synthesize_with_ollama_streaming,
)
from archipelago.inference.synthesis_cleaner import cleanse_synthesis_stream

__all__ = [
    "build_graph_notes",
    "cleanse_synthesis_stream",
    "configure_gateway",
    "enforce_sterile_prose",
    "format_natural_fallback",
    "gateway_chat",
    "gateway_chat_stream",
    "is_llm_available",
    "stream_synthesis_with_ollama",
    "synthesize_with_ollama_streaming",
]
