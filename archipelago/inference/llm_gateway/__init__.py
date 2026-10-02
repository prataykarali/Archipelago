"""LLM gateway package — split from the former llm_gateway.py monolith.

xkiro (`qwen/qwen3.8-max:free`) remains the PRIMARY provider; Google Gemini is
the cloud failover. Nothing here changes provider precedence.
"""

from archipelago.inference.llm_gateway.part01_config import (
    DEFAULT_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_MODELS,
    GEMINI_PURPOSE_MAP,
    LLM_UNAVAILABLE_MSG,
    XKIRO_API_KEY,
    XKIRO_BASE_URL,
    XKIRO_DEFAULT_MODEL,
    configure_gateway,
    get_active_provider,
    is_llm_available,
)
from archipelago.inference.llm_gateway.part02_sanitize import (
    _clean_messages_for_openai,
    _convert_messages_for_gemini,
    sanitize_for_external_llm,
)
from archipelago.inference.llm_gateway.part03_chat import (
    _chat_gemini,
    _chat_xkiro,
    gateway_chat,
)
from archipelago.inference.llm_gateway.part04_stream import (
    _stream_gemini,
    _stream_xkiro,
    gateway_chat_stream,
)
from archipelago.inference.llm_gateway.part05_tools import gateway_chat_with_tools

__all__ = [
    "DEFAULT_PROVIDER",
    "GEMINI_API_KEY",
    "GEMINI_MODELS",
    "GEMINI_PURPOSE_MAP",
    "LLM_UNAVAILABLE_MSG",
    "XKIRO_API_KEY",
    "XKIRO_BASE_URL",
    "XKIRO_DEFAULT_MODEL",
    "configure_gateway",
    "gateway_chat",
    "gateway_chat_stream",
    "gateway_chat_with_tools",
    "get_active_provider",
    "is_llm_available",
    "sanitize_for_external_llm",
]
