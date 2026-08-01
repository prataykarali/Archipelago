from __future__ import annotations

from typing import Any


GROUNDED_PREAMBLE: str = "Based on the retrieved knowledge graph evidence:"


def build_grounded_answer(
    query: str,
    context: str,
    payloads: list[dict[str, Any]],
) -> str:
    """Build a grounded answer from context and citation payloads.

    Args:
        query: The original user query.
        context: Retrieved context text.
        payloads: Citation payload list.

    Returns:
        A formatted grounded answer string.
    """
    return f"{GROUNDED_PREAMBLE}\n\n{context}"


def build_benchmark_grounded_answer(
    query: str,
    payloads: list[dict[str, Any]],
) -> str:
    """Build a benchmark-style grounded answer from payloads only.

    Args:
        query: The user query string.
        payloads: Citation payload list.

    Returns:
        A formatted answer string for evaluation benchmarks.
    """
    if not payloads:
        return f"{GROUNDED_PREAMBLE}\n\nNo sources found for: {query}"
    parts = [f"{GROUNDED_PREAMBLE}"]
    for i, p in enumerate(payloads, start=1):
        topic = p.get("topic", "")
        text = p.get("text", "")
        parts.append(f"[S{i}] {topic}: {text}")
    return "\n".join(parts)


def clean_weird_symbols(text: str) -> str:
    """Remove unusual unicode and formatting symbols from model output.

    Args:
        text: Raw text possibly containing odd symbols.

    Returns:
        Cleaned text with unusual symbols removed.
    """
    import re

    text = re.sub(r"[\u00ad\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_false_out_of_scope_refusal(text: str) -> bool:
    """Detect if the response is a false out-of-scope refusal.

    Args:
        text: Response text to check.

    Returns:
        True if the text appears to be a reply refusal.
    """
    return "out of scope" in text.lower() and "sorry" in text.lower()


def looks_garbled_or_template_leaky(text: str) -> bool:
    """Check if the text has template leaks or is garbled.

    Args:
        text: Text to inspect.

    Returns:
        True if leaky or garbled.
    """
    return "{" in text or "}" in text or ("[S" in text and "]" not in text)


def true_out_of_scope_message() -> str:
    """Return the true out of scope refusal message.

    Returns:
        OUT_OF_SCOPE_MESSAGE string.
    """
    from archipelago.inference.scope_gate import OUT_OF_SCOPE_MESSAGE

    return OUT_OF_SCOPE_MESSAGE



