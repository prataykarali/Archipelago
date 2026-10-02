"""Auto-split from synthesis.py — do not edit blocks by hand."""
from __future__ import annotations

from archipelago.inference.llm_gateway import gateway_chat, gateway_chat_stream, gateway_chat_with_tools, is_llm_available, LLM_UNAVAILABLE_MSG, configure_gateway
from archipelago.inference.judge_reply import JUDGE_SYSTEM_PROMPT


OLLAMA_UNAVAILABLE_MSG = LLM_UNAVAILABLE_MSG


_STREAM_SYSTEM_PROMPT = JUDGE_SYSTEM_PROMPT


def stream_system_prompt() -> str:
    """Return the canonical judge architecture used by streaming replies."""
    return _STREAM_SYSTEM_PROMPT
