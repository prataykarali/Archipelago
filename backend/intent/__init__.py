"""Intent identification and safety gating for Archipelago."""
from __future__ import annotations

import re
from typing import Any

from archipelago.inference.intent_gate import classify_intent, intent_to_block_reason
from archipelago.inference.scope_gate import is_aiml_in_scope, parse_scope_answer
from firewall import Stage1Firewall

GREETING_PATTERN = re.compile(
    r"^(h(i|ey|ello|owdy)|good\s*(morning|afternoon|evening|day)|"
    r"yo\b|sup\b|what'?s?\s*up|who are you|help|what can you do|"
    r"thanks?|thank\s*you|bye|goodbye|see ya)[\s?!.]*$",
    re.I,
)

GREETING_RESPONSE = (
    "Hello! I'm **Archipelago**, your AI librarian and academic tutor. "
    "I can explain concepts from the indexed CS/AI/ML corpus, show "
    "prerequisite graphs, find textbook pages, check library hours, "
    "look up e-resource credentials, and build personalized learning "
    "roadmaps.\n\n"
    "Try asking about **LoRA**, **RAG**, **BERT**, **Attention**, "
    "**3NF**, or any indexed topic!"
)

def is_greeting(query: str) -> bool:
    """Return True if query is a conversational greeting/identity inquiry."""
    return bool(GREETING_PATTERN.match((query or "").strip()))

__all__ = [
    "GREETING_PATTERN",
    "GREETING_RESPONSE",
    "Stage1Firewall",
    "classify_intent",
    "intent_to_block_reason",
    "is_aiml_in_scope",
    "is_greeting",
    "parse_scope_answer",
]
