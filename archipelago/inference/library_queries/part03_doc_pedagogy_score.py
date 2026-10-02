"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from typing import Any
from . import _deps as _rt  # noqa: F401


def _doc_pedagogy_score(doc: dict[str, Any], prefer_papers: bool = False) -> float:
    """Score a document for pedagogical recommendation based on user intent and mentions."""
    mentions = float(doc.get("mentions") or doc.get("mention_count") or 1)
    cat = (doc.get("source_category") or doc.get("category") or "").lower()
    doc_id = str(doc.get("id") or "").lower()
    is_book = "book" in cat or "textbook" in cat or "textbooks" in doc_id
    is_paper = "paper" in cat or "papers" in doc_id

    score = mentions
    if prefer_papers:
        if is_paper:
            score += 100.0
        elif is_book:
            score -= 20.0
    else:
        if is_book:
            score += 100.0
        elif is_paper:
            score -= 20.0
    return score
