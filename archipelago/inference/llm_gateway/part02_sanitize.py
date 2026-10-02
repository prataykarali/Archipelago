"""Prompt redaction and provider message-format conversion.

Untrusted corpus text is never forwarded verbatim to an external LLM.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

_INTERNAL_ROUTE_RE = r"/(?:api/page-view|read|open|papers|pdfs)\S*"
_ARCHIPELAGO_BOOKS_RE = r"archipelago-books-\S+"
_URL_SCHEMES = (r"https?://\S+", r"ftp://\S+")
_MARKDOWN_LINK_RE = r"\[([^\]]+)\]\([^)]+\)"
_FILE_SUFFIX_RE = r"[\w./-]+\.(?:pdf|json|db|ods)"
_OKF_INTERNALS_RE = r"\bOKF\b|\bOKFGraph\b|\bokf_graph\b|\bkuzu\b|\bcypher\b|subscriptionId"
_UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def sanitize_for_external_llm(text: str) -> str:
    """Strictly redact links, URLs, and OKF references before sending to external LLMs."""
    if not text:
        return ""
    # Strip markdown links [label](url) -> label
    clean = re.sub(_MARKDOWN_LINK_RE, r"\1", str(text))
    # Strip full URLs
    for scheme in _URL_SCHEMES:
        clean = re.sub(scheme, "", clean)
    # Strip internal routes and file paths
    clean = re.sub(_INTERNAL_ROUTE_RE, "", clean)
    clean = re.sub(_FILE_SUFFIX_RE, "", clean, flags=re.IGNORECASE)
    clean = re.sub(_ARCHIPELAGO_BOOKS_RE, "", clean, flags=re.IGNORECASE)
    # Strip OKF and database internals
    clean = re.sub(_OKF_INTERNALS_RE, "", clean, flags=re.IGNORECASE)
    # Strip UUIDs
    clean = re.sub(_UUID_RE, "", clean, flags=re.IGNORECASE)
    # Collapse excess whitespace
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def _convert_messages_for_gemini(messages: List[Dict]) -> Tuple[Optional[str], List[Dict]]:
    """Convert standard messages to Gemini format with leak sanitization."""
    system_instruction = None
    formatted_history = []

    for msg in messages:
        role = msg.get("role")
        content = sanitize_for_external_llm(str(msg.get("content", "")))

        if role == "system":
            system_instruction = content
        elif role == "user":
            formatted_history.append({"role": "user", "parts": [content]})
        elif role in ("assistant", "model"):
            formatted_history.append({"role": "model", "parts": [content]})

    return system_instruction, formatted_history


def _clean_messages_for_openai(messages: List[Dict]) -> List[Dict]:
    """Ensure valid roles and sanitized string content for the OpenAI-compatible API."""
    clean = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "model":
            role = "assistant"
        sanitized = sanitize_for_external_llm(str(msg.get("content", "")))
        clean.append({"role": role, "content": sanitized})
    return clean
