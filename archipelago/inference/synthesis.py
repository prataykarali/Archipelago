"""Answer rendering, Ollama wording, and free chat facade for Archipelago."""
from __future__ import annotations

import re
import time
from typing import Any
import ollama
from archipelago.inference import state as st
from archipelago.inference.math_text import fix_math_expressions

OLLAMA_UNAVAILABLE_MSG = (
    "The library is currently library closed — the librarian is waking up and will be "
    "with you shortly. Please hold while I stoke the intellectual furnaces..."
)

_ollama_cache: dict[str, Any] = {"available": None, "timestamp": 0}
_CACHE_TTL = 5.0

def is_ollama_available() -> bool:
    now = time.monotonic()
    if _ollama_cache["available"] is not None and (now - _ollama_cache["timestamp"]) < _CACHE_TTL:
        return bool(_ollama_cache["available"])
    try:
        client = ollama.Client(host="http://localhost:11434")
        client.chat(model=st.DEFAULT_OLLAMA_MODEL, messages=[{"role": "user", "content": "hi"}], options={"num_predict": 5})
        _ollama_cache["available"] = True
    except Exception:
        _ollama_cache["available"] = False
    _ollama_cache["timestamp"] = now
    return bool(_ollama_cache["available"])

def _strip_latex(text: str) -> str:
    return fix_math_expressions(text or "")

_CASES_BLOCK_RE = re.compile(r"begincases\b.*?(?:endcases\b|$)", re.IGNORECASE | re.DOTALL)
_SUBSCRIPT_LINE_RE = re.compile(r"^.*(?:[a-z](?:[,_][a-z])?\s*,\s*){8,}[a-z]\s*=.*$", re.IGNORECASE | re.MULTILINE)

def _scrub_slm_artifacts(text: str) -> str:
    if not text:
        return text
    text = _CASES_BLOCK_RE.sub("", text)
    text = _SUBSCRIPT_LINE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

from archipelago.inference.synthesis_cleaner import (
    enforce_sterile_prose,
    enforce_four_tier,
)
from archipelago.inference.synthesis_library import (
    prettify_doc_title,
    render_library_books,
    render_library_chapters,
    render_library_chapter_lookup,
    render_journal_status,
    render_catalog_holdings,
    render_library_catalog,
    render_physical_resources,
    render_catalog_resources,
    render_resource_availability,
    render_library_info,
    render_catalog_stats,
    closed_library_reply,
)
from archipelago.inference.synthesis_chat import (
    not_indexed_reply,
    general_chat_reply,
    identity_reply,
    onboarding_reply,
)
from archipelago.inference.synthesis_notes import (
    build_graph_notes,
    format_natural_fallback,
)
from archipelago.inference.synthesis_pipeline import (
    run_archipelago_inference,
)

__all__ = [
    "is_ollama_available",
    "_strip_latex",
    "_scrub_slm_artifacts",
    "enforce_sterile_prose",
    "enforce_four_tier",
    "prettify_doc_title",
    "render_library_books",
    "render_library_chapters",
    "render_library_chapter_lookup",
    "render_journal_status",
    "render_catalog_holdings",
    "render_library_catalog",
    "render_physical_resources",
    "render_catalog_resources",
    "render_resource_availability",
    "render_library_info",
    "render_catalog_stats",
    "closed_library_reply",
    "not_indexed_reply",
    "general_chat_reply",
    "identity_reply",
    "onboarding_reply",
    "build_graph_notes",
    "format_natural_fallback",
    "run_archipelago_inference",
    "synthesize_with_ollama_streaming",
]


def synthesize_with_ollama_streaming(
    notes: str,
    *,
    evidence_ids: set[str] | None = None,
    user_query: str = "",
    citation_payloads: list[dict[str, Any]] | None = None,
    sterile: bool = False,
    fallback_text: str = "",
    history: list[dict[str, Any]] | None = None,
    yield_stream: bool = False,
) -> Any:
    """Stream tokens from the local Ollama SLM for optional synthesis.

    Yields individual token strings when yield_stream=True.
    """
    system_prompt = (
        "You are Archipelago, an academic AI/ML library assistant. "
        "Write concise study advice (2-3 sentences max). "
        "No greetings, no source list, no doc_id/chunk ids, no Style/LAYOUT tokens."
    )
    messages = [{"role": "system", "content": system_prompt}]
    for h in (history or [])[-4:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": f"{notes}\n\n{user_query}".strip()})

    try:
        client = ollama.Client(host="http://localhost:11434")
        response = client.chat(
            model=st.DEFAULT_OLLAMA_MODEL,
            messages=messages,
            stream=True,
            think=False,
            keep_alive="30m",
            options={"temperature": 0.1, "top_p": 0.9, "num_predict": 180, "num_ctx": 2048},
        )
        for chunk in response:
            msg = chunk.get("message") if isinstance(chunk, dict) else getattr(chunk, "message", None)
            token = (msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")) or ""
            if token:
                yield token
    except Exception:
        if fallback_text:
            yield fallback_text
