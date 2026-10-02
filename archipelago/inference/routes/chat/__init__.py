"""Chat route package — split from the former routes_chat.py monolith.

Importing this package registers all /api/chat* routes on st.app.
"""

from archipelago.inference.routes.chat.part01_api_chat import api_chat
from archipelago.inference.routes.chat.part06_mcq_endpoints import (
    api_adaptive_step,
    api_chat_telemetry,
    api_diagnostic_mcqs,
    api_verify_mcq,
)
from archipelago.inference.routes.chat.part07_init import init_concepts_data

__all__ = [
    "api_adaptive_step",
    "api_chat",
    "api_chat_telemetry",
    "api_diagnostic_mcqs",
    "api_verify_mcq",
    "init_concepts_data",
]
