from __future__ import annotations

from typing import Any

from archipelago.inference.ranking_seed_data import (
    _BOOK_SIGNAL_BY_TITLE as _BOOK_SIGNAL_BY_TITLE,
)
from archipelago.inference.ranking_seed_data import (
    _PAPER_SIGNAL_BY_TITLE as _PAPER_SIGNAL_BY_TITLE,
)
from archipelago.inference.ranking_seed_data import (
    SEED_BOOKS as SEED_BOOKS,
)
from archipelago.inference.ranking_seed_data import (
    SEED_PAPERS as SEED_PAPERS,
)


def detect_subject_key(query: str) -> str | None:
    """Identify subject from stack + graph."""
    from archipelago.inference.stack_domains import detect_stack_subject_key

    return detect_stack_subject_key(query)


_TOPIC_WEIGHT = 0.35
_AUTHOR_WEIGHT = 0.20
_REVIEW_WEIGHT = 0.20
_RECENCY_WEIGHT = 0.10
_AVAILABILITY_WEIGHT = 0.15
_PAPER_IMPACT_WEIGHT = 0.15
_PAPER_RECENCY_WEIGHT = 0.05
_MAX_RECOMMENDATIONS = 4

# Fine-grained domain keys still match the broader AIML seed bucket so
# "papers on RAG" does not empty the librarian shortlist.
_SUBJECT_FAMILIES: dict[str, frozenset[str]] = {
    "aiml": frozenset(
        {
            "aiml",
            "rag",
            "finetuning",
            "deep_learning",
            "gnn",
            "mathematics",
            "syllabi",
        }
    ),
    "rag": frozenset({"rag", "aiml"}),
    "finetuning": frozenset({"finetuning", "aiml"}),
    "deep_learning": frozenset({"deep_learning", "aiml"}),
    "gnn": frozenset({"gnn", "aiml"}),
    "mathematics": frozenset({"mathematics", "aiml"}),
    "syllabi": frozenset({"syllabi", "aiml"}),
    "dbms": frozenset({"dbms"}),
    "operating_systems": frozenset({"operating_systems"}),
    "data_structures": frozenset({"data_structures"}),
}


def subjects_compatible(detected: str | None, entry_key: str | None) -> bool:
    """True when a detected query subject may rank a seed/inventory subject_key."""
    if not detected:
        return True
    if not entry_key:
        return False
    if detected == entry_key:
        return True
    family = _SUBJECT_FAMILIES.get(detected, frozenset({detected}))
    if entry_key in family:
        return True
    # Also allow entry's family to claim the detected key (aiml seed ↔ rag query).
    entry_family = _SUBJECT_FAMILIES.get(entry_key, frozenset({entry_key}))
    return detected in entry_family


def _enrich_seed_entries(entries: list[dict[str, Any]], signals: dict[str, dict[str, Any]]) -> None:
    """Attach reviewed ranking evidence to every curated seed entry."""
    for entry in entries:
        title_key = str(entry["title"]).lower()
        signal = signals.get(title_key, {})
        entry.update(signal)
        entry.setdefault("author_authority", 0.0)
        entry.setdefault("review_score", 0.0)
        entry.setdefault("citation_impact", 0.0)
        entry.setdefault("recency_score", 0.0)
        entry.setdefault("rank_reason", "Curated library recommendation")


_enrich_seed_entries(SEED_BOOKS, _BOOK_SIGNAL_BY_TITLE)
_enrich_seed_entries(SEED_PAPERS, _PAPER_SIGNAL_BY_TITLE)


def seed_local_doc_id(entry: dict[str, Any] | None) -> str | None:
    """Resolve local path relative to PDF_DIR for a given book/paper entry."""
    if not entry:
        return None
    hint = entry.get("doc_id_hint")
    if not hint:
        return None
    from archipelago.inference.state import PDF_DIR

    pdf_path = PDF_DIR / hint
    if pdf_path.is_file():
        return hint
    return None


def rank_seed_entries(
    query: str,
    kind: str | None = None,
    availability_by_title: dict[str, float] | None = None,
    limit: int = _MAX_RECOMMENDATIONS,
) -> list[dict[str, Any]]:
    """Rank curated books/papers before response synthesis.

    Ranking uses reviewed metadata and live catalog availability when supplied;
    a reply model receives only this already sorted shortlist.
    """
    all_entries = SEED_BOOKS + SEED_PAPERS
    subject = detect_subject_key(query)
    results: list[dict[str, Any]] = []
    for entry in all_entries:
        if kind and entry.get("kind") != kind:
            continue
        entry_subject = str(entry.get("subject_key") or "")
        if subject and not subjects_compatible(subject, entry_subject):
            continue

        title_lower = entry["title"].lower()
        availability = 0.0
        if availability_by_title:
            availability = max(0.0, min(1.0, float(availability_by_title.get(title_lower, 0.0))))
        if subject and entry_subject == subject:
            topic_match = 1.0
        elif subject and subjects_compatible(subject, entry_subject):
            topic_match = 0.85
        else:
            topic_match = 0.0
        # Title/token boost for fine-grained domains (RAG query → Lewis paper).
        q_low = (query or "").lower()
        if subject == "rag" and "retrieval" in title_lower:
            topic_match = max(topic_match, 1.0)
        if subject == "finetuning" and any(
            tok in title_lower for tok in ("lora", "qlora", "adapter", "fine")
        ):
            topic_match = max(topic_match, 1.0)
        if subject == "gnn" and any(tok in title_lower for tok in ("graph", "gcn", "gat")):
            topic_match = max(topic_match, 1.0)
        if "rag" in q_low and "retrieval" in title_lower:
            topic_match = max(topic_match, 1.0)
        score = (
            topic_match * _TOPIC_WEIGHT
            + float(entry["author_authority"]) * _AUTHOR_WEIGHT
            + float(entry["review_score"]) * _REVIEW_WEIGHT
            + float(entry["recency_score"]) * _RECENCY_WEIGHT
            + availability * _AVAILABILITY_WEIGHT
        )
        if entry.get("kind") == "paper":
            score += float(entry["citation_impact"]) * _PAPER_IMPACT_WEIGHT
            score -= float(entry["recency_score"]) * _RECENCY_WEIGHT
            score += float(entry["recency_score"]) * _PAPER_RECENCY_WEIGHT

        new_entry = dict(entry)
        new_entry["score"] = score
        new_entry["availability"] = availability
        new_entry["ranking_signals"] = {
            "topic_match": topic_match,
            "author_authority": float(entry["author_authority"]),
            "review_score": float(entry["review_score"]),
            "citation_impact": float(entry["citation_impact"]),
            "recency_score": float(entry["recency_score"]),
            "availability": availability,
            "provenance": str(entry.get("source") or "librarian_review"),
        }
        results.append(new_entry)

    results.sort(key=lambda item: (-float(item["score"]), str(item["title"]).lower()))
    return results[: min(_MAX_RECOMMENDATIONS, max(1, limit))]


def format_seed_ranking(entries: list[dict[str, Any]], topic: str = "") -> str:
    """Format the ranked list into a curated Markdown recommendation block."""
    if not entries:
        return "No librarian-approved seed titles found."
    from archipelago.inference.state import PDF_DIR

    title = f"### Curated reading list for {topic}" if topic else "### Curated reading list"
    lines = [title]
    for entry in entries:
        entry_title = entry.get("title", "Unknown Title")
        authors = entry.get("authors", "Unknown Authors")
        kind = entry.get("kind", "entry")
        doc_id = entry.get("doc_id_hint", "")
        if doc_id and (PDF_DIR / doc_id).is_file():
            access = f"[Open page](/api/page-view?doc_id={doc_id}&page=1)"
        else:
            access = "metadata only"
        signals = entry.get("ranking_signals") or {}
        reason = entry.get("rank_reason") or "Curated library recommendation"
        evidence = ", ".join(
            label
            for label, value in (
                ("author authority", signals.get("author_authority")),
                ("reviews", signals.get("review_score")),
                ("citation impact", signals.get("citation_impact")),
                ("availability", signals.get("availability")),
            )
            if value
        )
        lines.append(f"- **{entry_title}** by {authors} ({kind}; {access})")
        lines.append(f"  - Why ranked here: {reason}. Signals: {evidence or 'subject match'}.")
    return "\n".join(lines)
