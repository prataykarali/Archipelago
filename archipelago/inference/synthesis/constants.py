"""Auto-split from synthesis.py — do not edit blocks by hand."""

from __future__ import annotations

from archipelago.inference.judge_reply import JUDGE_SYSTEM_PROMPT
from archipelago.inference.llm_gateway import (
    LLM_UNAVAILABLE_MSG,
)

OLLAMA_UNAVAILABLE_MSG = LLM_UNAVAILABLE_MSG


_STREAM_SYSTEM_PROMPT = JUDGE_SYSTEM_PROMPT


def stream_system_prompt() -> str:
    """Return the canonical judge architecture used by streaming replies."""
    return _STREAM_SYSTEM_PROMPT
