"""Backwards-compatibility shim — chat routes moved to routes/chat/ package."""

from archipelago.inference.routes.chat import (  # noqa: F401
    api_adaptive_step,
    api_chat,
    api_chat_telemetry,
    api_diagnostic_mcqs,
    api_verify_mcq,
    init_concepts_data,
)
