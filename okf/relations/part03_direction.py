"""Infer prerequisite edge direction from evidence order and difficulty."""

from __future__ import annotations

from typing import Any


def infer_prerequisite_direction(
    concept_a: str | dict[str, Any],
    concept_b: str | dict[str, Any],
    chunks: list[dict[str, Any]],
) -> tuple[str, str]:
    """Infer prerequisite direction between concept_a and concept_b.

    Uses order of appearance in chunks (first occurrence or co-occurrence position).
    Falls back to difficulty ranks (foundational < intermediate < advanced < expert).
    """
    diff_rank = {"foundational": 1, "intermediate": 2, "advanced": 3, "expert": 4}

    diff_a = "intermediate"
    diff_b = "intermediate"

    if isinstance(concept_a, dict):
        diff_a = concept_a.get("difficulty", "intermediate")
        name_a = concept_a.get("concept_name") or concept_a.get("name") or ""
    else:
        name_a = str(concept_a)

    if isinstance(concept_b, dict):
        diff_b = concept_b.get("difficulty", "intermediate")
        name_b = concept_b.get("concept_name") or concept_b.get("name") or ""
    else:
        name_b = str(concept_b)

    a_lower = name_a.strip().lower()
    b_lower = name_b.strip().lower()

    co_occur_score = 0
    first_chunk_a = None
    first_chunk_b = None

    for idx, chunk in enumerate(chunks):
        text = (chunk.get("text") or chunk.get("text_passage") or "").lower()
        has_a = a_lower in text
        has_b = b_lower in text

        if has_a and first_chunk_a is None:
            first_chunk_a = idx
        if has_b and first_chunk_b is None:
            first_chunk_b = idx

        if has_a and has_b:
            try:
                idx_a = text.index(a_lower)
                idx_b = text.index(b_lower)
                if idx_a < idx_b:
                    co_occur_score += 1
                elif idx_b < idx_a:
                    co_occur_score -= 1
            except ValueError:
                pass

    if co_occur_score > 0:
        return (name_a, name_b)
    elif co_occur_score < 0:
        return (name_b, name_a)

    if first_chunk_a is not None and first_chunk_b is not None and first_chunk_a != first_chunk_b:
        if first_chunk_a < first_chunk_b:
            return (name_a, name_b)
        else:
            return (name_b, name_a)

    # Fallback to difficulty rank
    rank_a = diff_rank.get(str(diff_a).lower(), 2)
    rank_b = diff_rank.get(str(diff_b).lower(), 2)

    if rank_a < rank_b:
        return (name_a, name_b)
    elif rank_b < rank_a:
        return (name_b, name_a)

    # Final fallback: alphabetical
    if name_a < name_b:
        return (name_a, name_b)
    else:
        return (name_b, name_a)
