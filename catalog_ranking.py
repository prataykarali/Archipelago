"""Catalog ranking module for sorting documents by academic metrics."""
from __future__ import annotations

from typing import Any
from evaluate_pdf_catalog import evaluate_pdf_catalog


def rank_documents(
    topic: str | None = None, parameter: str = "composite", top_k: int = 5
) -> list[dict[str, Any]]:
    """Rank catalog documents by composite score, authority, or review score."""
    catalog = evaluate_pdf_catalog()

    if topic:
        q = topic.strip().lower()
        filtered = []
        for doc in catalog:
            doc_topics = [t.lower() for t in doc.get("topics", [])]
            doc_title = doc.get("title", "").lower()
            if q in doc_topics or any(q in t for t in doc_topics) or q in doc_title:
                filtered.append(doc)
        docs = filtered
    else:
        docs = list(catalog)

    if not docs:
        return []

    param_key_map = {
        "composite": "composite_score",
        "authors": "author_authority",
        "reviews": "review_score",
    }
    sort_key = param_key_map.get(parameter, "composite_score")
    docs.sort(key=lambda d: d.get(sort_key, 0.0), reverse=True)

    return docs[:top_k]


def format_ranking_response(
    topic: str | None = None, parameter: str = "composite", top_k: int = 5
) -> str:
    """Format ranked documents into Markdown output."""
    results = rank_documents(topic=topic, parameter=parameter, top_k=top_k)

    if not results:
        topic_str = f" for topic '{topic}'" if topic else ""
        return f"No catalog documents matched{topic_str}."

    lines = [f"### Top-Ranked Books & Papers (by {parameter}):\n"]
    param_label_map = {
        "composite": "Composite Score",
        "authors": "Author Authority",
        "reviews": "Review Score",
    }
    label = param_label_map.get(parameter, "Score")
    param_key_map = {
        "composite": "composite_score",
        "authors": "author_authority",
        "reviews": "review_score",
    }
    key = param_key_map.get(parameter, "composite_score")
    for i, doc in enumerate(results, start=1):
        lines.append(
            f"{i}. **{doc.get('title')}** by *{doc.get('authors')}* ({label}: {doc.get(key, 0.0)})"
        )

    return "\n".join(lines)
