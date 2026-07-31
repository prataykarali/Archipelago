from __future__ import annotations

from typing import Any


def select_target_evidence(
    concept: dict[str, Any],
    query: str,
) -> list[dict[str, Any]]:
    """Select the best matching subset of evidence sources for the target concept.

    Args:
        concept: Concept dictionary.
        query: The user query string.

    Returns:
        List of selected source dictionaries.
    """
    q = query.lower()
    sources = concept.get("sources", [])
    out = []
    for s in sources:
        doc = s.get("doc_id", "").lower()
        txt = s.get("text_passage", "").lower()
        if "lora" in q:
            if "lora" in doc or "lora" in txt:
                out.append(s)
        else:
            out.append(s)
    return out
