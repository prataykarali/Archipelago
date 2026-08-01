from __future__ import annotations

from typing import Any


def detect_subject_key(query: str) -> str | None:
    """Identify which curriculum subject domain matches the search query terms."""
    q = query.lower()
    if "dbms" in q or "database" in q or "sql" in q:
        return "dbms"
    if "os" in q or "operating system" in q or "scheduler" in q:
        return "operating_systems"
    if "dsa" in q or "data structure" in q or "algorithm" in q or "heap" in q or "tree" in q:
        return "data_structures"
    if "aiml" in q or "machine learning" in q or "transformer" in q or "deep learning" in q:
        return "aiml"
    return None


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
) -> list[dict[str, Any]]:
    """Rank seed textbooks/papers based on subject match and availability bonus."""
    all_entries = SEED_BOOKS + SEED_PAPERS
    results = []
    for entry in all_entries:
        if kind and entry.get("kind") != kind:
            continue

        score = float("0.5")

        subject = detect_subject_key(query)
        if subject and entry.get("subject_key") == subject:
            score += float("0.3")

        title_lower = entry["title"].lower()
        if availability_by_title and title_lower in availability_by_title:
            score += availability_by_title[title_lower] * float("0.2")

        new_entry = dict(entry)
        new_entry["score"] = score
        results.append(new_entry)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def format_seed_ranking(entries: list[dict[str, Any]]) -> str:
    """Format the ranked list into a curated Markdown recommendation block."""
    if not entries:
        return "No librarian-approved seed titles found."
    from archipelago.inference.state import PDF_DIR

    lines = ["### Curated reading list"]
    for entry in entries:
        title = entry.get("title", "Unknown Title")
        authors = entry.get("authors", "Unknown Authors")
        kind = entry.get("kind", "entry")
        doc_id = entry.get("doc_id_hint", "")
        # Decide if openable
        if doc_id and (PDF_DIR / doc_id).is_file():
            openable = "openable here"
        else:
            openable = "not openable here"
        lines.append(f"- **{title}** by {authors} ({kind}, {openable})")
    return "\n".join(lines)
