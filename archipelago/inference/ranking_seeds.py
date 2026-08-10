from __future__ import annotations

from typing import Any


def detect_subject_key(query: str) -> str | None:
    """Identify subject from stack + graph."""
    from archipelago.inference.stack_domains import detect_stack_subject_key
    return detect_stack_subject_key(query)


SEED_BOOKS: list[dict[str, Any]] = [
    {
        "title": "Database System Concepts",
        "authors": "Silberschatz, Korth, Sudarshan",
        "subject_key": "dbms",
        "kind": "textbook",
        "doc_id_hint": "textbooks/db_concepts.pdf",
    },
    {
        "title": "Modern Operating Systems",
        "authors": "Andrew S. Tanenbaum",
        "subject_key": "operating_systems",
        "kind": "textbook",
        "doc_id_hint": "textbooks/modern_operating_systems.pdf",
    },
    {
        "title": "Operating Systems: Three Easy Pieces",
        "authors": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
        "subject_key": "operating_systems",
        "kind": "textbook",
        "doc_id_hint": "ostep_three_easy_pieces/00_Preface.pdf",
    },
    {
        "title": "Introduction to Algorithms",
        "authors": "Cormen, Leiserson, Rivest, Stein",
        "subject_key": "data_structures",
        "kind": "textbook",
        "doc_id_hint": "textbooks/clrs.pdf",
    },
    {
        "title": "Data Structures and Algorithms in Python",
        "authors": "Goodrich, Tamassia, Goldwasser",
        "subject_key": "data_structures",
        "kind": "textbook",
        "doc_id_hint": "textbooks/dsa_python.pdf",
    },
    {
        "title": "Mathematics for Machine Learning",
        "authors": "Deisenroth, Faisal, Ong",
        "subject_key": "aiml",
        "kind": "textbook",
        "doc_id_hint": "textbooks/Deisenroth_Math_For_ML.pdf",
    },
    {
        "title": "Neural Networks and Learning Machines",
        "authors": "Simon Haykin",
        "subject_key": "aiml",
        "kind": "textbook",
        "doc_id_hint": None,
        "source": "pearson_elibrary",
        "isbn": "9781282645820",
        "rank_reason": "Classic NN textbook; Pearson institutional e-book",
    },
    {
        "title": "Artificial Intelligence: A Modern Approach, 4/e",
        "authors": "Stuart J. Russell, Peter Norvig",
        "subject_key": "aiml",
        "kind": "textbook",
        "doc_id_hint": None,
        "source": "pearson_elibrary",
        "isbn": "9789356063488",
        "rank_reason": "Canonical AI survey; top author authority",
    },
    {
        "title": "Operating Systems: Internals and Design Principles, Global Edition",
        "authors": "William Stallings",
        "subject_key": "operating_systems",
        "kind": "textbook",
        "doc_id_hint": None,
        "source": "pearson_elibrary",
        "isbn": "9781292214306",
        "rank_reason": "Systems design depth; pairs with OSTEP",
    },
    {
        "title": "Speech and Language Processing 2/e",
        "authors": "Jurafsky, Martin",
        "subject_key": "aiml",
        "kind": "textbook",
        "doc_id_hint": None,
        "source": "pearson_elibrary",
        "isbn": "9789353948078",
        "rank_reason": "Standard NLP reference (Pearson edition)",
    },
    {
        "title": "Computer Vision",
        "authors": "Forsyth, Ponce",
        "subject_key": "aiml",
        "kind": "textbook",
        "doc_id_hint": None,
        "source": "pearson_elibrary",
        "isbn": "9781292014081",
        "rank_reason": "Core vision text; Pearson institutional e-book",
    },
    {
        "title": "Data Structures Using C, 1e",
        "authors": "Tenenbaum, Langsam, Augenstein",
        "subject_key": "data_structures",
        "kind": "textbook",
        "doc_id_hint": None,
        "source": "pearson_elibrary",
        "isbn": "9789353948849",
        "rank_reason": "Classic DSA with C; Pearson e-book",
    },
    {
        "title": "Software Engineering",
        "authors": "Ian Sommerville",
        "subject_key": "aiml",
        "kind": "textbook",
        "doc_id_hint": None,
        "source": "pearson_elibrary",
        "isbn": "9789352861569",
        "rank_reason": "Widely adopted SE survey; Pearson e-book",
    },
    {
        "title": "Computer Organization and Architecture",
        "authors": "William Stallings",
        "subject_key": "operating_systems",
        "kind": "textbook",
        "doc_id_hint": None,
        "source": "pearson_elibrary",
        "isbn": "9789356062931",
        "rank_reason": "Hardware/org foundation; author authority",
    },
]

SEED_PAPERS: list[dict[str, Any]] = [
    {
        "title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "authors": "Edward J. Hu et al.",
        "subject_key": "aiml",
        "kind": "paper",
        "venue": "arXiv 2021",
        "doc_id_hint": "papers/Hu2021_LoRA.pdf",
    },
    {
        "title": "Attention Is All You Need",
        "authors": "Vaswani et al.",
        "subject_key": "aiml",
        "kind": "paper",
        "venue": "NeurIPS 2017",
        "doc_id_hint": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    },
    {
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "authors": "Devlin et al.",
        "subject_key": "aiml",
        "kind": "paper",
        "venue": "NAACL 2019",
        "doc_id_hint": "papers/Devlin2018_BERT.pdf",
    },
    {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "authors": "Lewis et al.",
        "subject_key": "aiml",
        "kind": "paper",
        "venue": "NeurIPS 2020",
        "doc_id_hint": "papers/Lewis2020_RAG.pdf",
    },
    {
        "title": "Language Models are Few-Shot Learners",
        "authors": "Brown et al.",
        "subject_key": "aiml",
        "kind": "paper",
        "venue": "NeurIPS 2020",
        "doc_id_hint": "papers/Brown2020_GPT3.pdf",
    },
]

# Scores are normalized, librarian-reviewed metadata.  They deliberately live
# with the source/provenance rather than being inferred by the reply model.
_BOOK_SIGNAL_BY_TITLE: dict[str, dict[str, Any]] = {
    "database system concepts": {"author_authority": 0.94, "review_score": 0.91, "recency_score": 0.76, "source": "publisher_and_librarian_review"},
    "modern operating systems": {"author_authority": 0.96, "review_score": 0.90, "recency_score": 0.82, "source": "publisher_and_librarian_review"},
    "operating systems: three easy pieces": {"author_authority": 0.91, "review_score": 0.93, "recency_score": 0.88, "source": "open_textbook_and_librarian_review"},
    "introduction to algorithms": {"author_authority": 0.98, "review_score": 0.95, "recency_score": 0.80, "source": "publisher_and_librarian_review"},
    "data structures and algorithms in python": {"author_authority": 0.88, "review_score": 0.87, "recency_score": 0.84, "source": "publisher_and_librarian_review"},
    "mathematics for machine learning": {"author_authority": 0.96, "review_score": 0.98, "recency_score": 0.95, "source": "open_textbook_and_librarian_review"},
    "neural networks and learning machines": {"author_authority": 0.93, "review_score": 0.88, "recency_score": 0.72, "source": "pearson_and_librarian_review"},
    "artificial intelligence: a modern approach, 4/e": {"author_authority": 0.99, "review_score": 0.96, "recency_score": 0.91, "source": "pearson_and_librarian_review"},
    "operating systems: internals and design principles, global edition": {"author_authority": 0.92, "review_score": 0.86, "recency_score": 0.85, "source": "pearson_and_librarian_review"},
    "speech and language processing 2/e": {"author_authority": 0.98, "review_score": 0.94, "recency_score": 0.74, "source": "pearson_and_librarian_review"},
    "computer vision": {"author_authority": 0.89, "review_score": 0.84, "recency_score": 0.70, "source": "pearson_and_librarian_review"},
    "data structures using c, 1e": {"author_authority": 0.86, "review_score": 0.80, "recency_score": 0.62, "source": "pearson_and_librarian_review"},
    "software engineering": {"author_authority": 0.94, "review_score": 0.90, "recency_score": 0.86, "source": "pearson_and_librarian_review"},
    "computer organization and architecture": {"author_authority": 0.92, "review_score": 0.87, "recency_score": 0.79, "source": "pearson_and_librarian_review"},
}

_PAPER_SIGNAL_BY_TITLE: dict[str, dict[str, Any]] = {
    "lora: low-rank adaptation of large language models": {"author_authority": 0.93, "review_score": 0.91, "citation_impact": 0.94, "recency_score": 0.88, "source": "arxiv_and_scholarly_index_review"},
    "attention is all you need": {"author_authority": 0.99, "review_score": 0.98, "citation_impact": 1.0, "recency_score": 0.78, "source": "neurips_and_scholarly_index_review"},
    "bert: pre-training of deep bidirectional transformers": {"author_authority": 0.97, "review_score": 0.96, "citation_impact": 0.99, "recency_score": 0.83, "source": "naacl_and_scholarly_index_review"},
    "retrieval-augmented generation for knowledge-intensive nlp tasks": {"author_authority": 0.94, "review_score": 0.93, "citation_impact": 0.92, "recency_score": 0.90, "source": "neurips_and_scholarly_index_review"},
    "language models are few-shot learners": {"author_authority": 0.98, "review_score": 0.94, "citation_impact": 0.97, "recency_score": 0.89, "source": "neurips_and_scholarly_index_review"},
}

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
    "aiml": frozenset({
        "aiml", "rag", "finetuning", "deep_learning", "gnn", "mathematics", "syllabi",
    }),
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
        if subject == "gnn" and any(
            tok in title_lower for tok in ("graph", "gcn", "gat")
        ):
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
