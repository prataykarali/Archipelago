"""Auto-split from monolith — blocks are verbatim."""

from __future__ import annotations

import re

from . import _deps as _rt  # noqa: F401
from .catalog_data import LIBRARY_CATALOG_KNOWLEDGE as LIBRARY_CATALOG_KNOWLEDGE


def _populate_pearson_knowledge() -> None:
    """Ingest all 40 Pearson bookshelf titles into LIBRARY_CATALOG_KNOWLEDGE."""
    import json
    from pathlib import Path

    try:
        repo_root = Path(__file__).resolve().parents[2]
        cat_file = repo_root / "data" / "catalogs" / "pearson_bookshelf.json"
        if not cat_file.is_file():
            return
        with cat_file.open(encoding="utf-8") as f:
            books = json.load(f).get("books", [])
        for b in books:
            book_id = b.get("id", "")
            slug = b.get("slug") or book_id
            title = b.get("title", "")
            author = b.get("author", "Pearson Education")
            isbn = b.get("isbn", "")
            domain = b.get("domain", "Computer Science & Engineering")
            reader_url = (
                b.get("reader_base_url")
                or f"https://ebooks.elibrary.in.pearson.com/wr/index.html#book/{book_id}"
            )

            aliases = [title.lower(), book_id.lower()]
            if slug:
                aliases.append(slug.lower())
                aliases.append(slug.lower().replace("_", " "))
            if isbn:
                aliases.append(isbn)
            if author:
                aliases.append(author.lower())

            title_clean = re.sub(r"[,/:\d+eE]+", " ", title).strip().lower()
            aliases.append(title_clean)

            entry = {
                "title": title,
                "aliases": list(set(aliases)),
                "authors": author,
                "year": "2024",
                "domain": domain,
                "format": f"Pearson eLibrary {'Reflowable' if b.get('book_type') == 'reflowable' else 'PDF'} Textbook (ISBN: {isbn})",
                "shelf_location": f"PEARSON-ELIB-{(slug or 'BOOK').upper()[:16]}",
                "total_copies": 10,
                "available_copies": 8,
                "pdf_path": reader_url,
                "reader_url": reader_url,
                "is_pearson": True,
                "book_id": book_id,
                "subscription_id": b.get("subscription_id", ""),
                "isbn": isbn,
                "summary": f"Authoritative Pearson eLibrary textbook: '{title}' by {author}. Comprehensive academic textbook within {domain} for engineering and computing curricula.",
                "key_sections": [
                    "1. Foundational Principles & Theoretical Background",
                    "2. Core Architectural & Algorithmic Methods",
                    "3. Practical Systems & Case Studies",
                    "4. Modern Design Considerations & Applications",
                    "5. Review Questions, Exercises & Advanced Topics",
                ],
                "prerequisites": [
                    "Foundations of Computing",
                    "Discrete Mathematics",
                    "Systems Basics",
                ],
                "unlocks": ["Advanced Specialized Electives", "Research & Industry Implementation"],
            }
            LIBRARY_CATALOG_KNOWLEDGE[slug] = entry
            if slug != book_id:
                LIBRARY_CATALOG_KNOWLEDGE[book_id] = entry
            doc_key = f"doc_{re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')}"
            LIBRARY_CATALOG_KNOWLEDGE[doc_key] = entry
    except Exception as exc:
        print(f"Notice: Pearson knowledge bootstrap skipped: {exc}")


_populate_pearson_knowledge()


JOURNAL_REGISTRY = [
    {
        "title": "Journal of Human Resource Management",
        "publisher": "Academy Publications",
        "accession": "J297, J621",
        "volume_years": "Vol. 14 - 28 (2010-2024)",
        "total_copies": 2,
        "available_copies": 2,
        "status": "Available in Periodical Section",
    },
    {
        "title": "Academy of Management Journal",
        "publisher": "Academy of Management",
        "accession": "J280, J342, J415, J512, J590, J675",
        "volume_years": "Vol. 45 - 67 (2002-2024)",
        "total_copies": 6,
        "available_copies": 6,
        "status": "Available in Periodical Section",
    },
    {
        "title": "Applied Artificial Intelligence Journal",
        "publisher": "Taylor & Francis",
        "accession": "J501, J502, J503",
        "volume_years": "Vol. 32 - 38 (2018-2024)",
        "total_copies": 3,
        "available_copies": 3,
        "status": "Available in AI Research Archive",
    },
    {
        "title": "IEEE Transactions on Neural Networks and Learning Systems",
        "publisher": "IEEE Computational Intelligence Society",
        "accession": "IEEE-TNN-01..04",
        "volume_years": "Vol. 26 - 35 (2015-2024)",
        "total_copies": 4,
        "available_copies": 4,
        "status": "Available in Digital & Print Archive",
    },
    {
        "title": "ACM Transactions on Database Systems (TODS)",
        "publisher": "ACM Press",
        "accession": "ACM-TODS-01, ACM-TODS-02",
        "volume_years": "Vol. 40 - 49 (2015-2024)",
        "total_copies": 2,
        "available_copies": 2,
        "status": "Available in Reference Stacks",
    },
]


def clean_topic_query(query: str) -> str:
    q = re.sub(
        r"\b(suggest|recommend|top|best|\d+|books?|papers?|readings?|textbooks?|for|the|topic|about|on|of|me|show|find|list|a|an|some|regarding)\b",
        " ",
        query,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", q).strip(" :\"'?.")


def clean_book_query(query: str) -> str:
    q = re.sub(
        r"\b(tell|me|about|this|the|book|paper|what|is|are|details|of|in|show|table|contents|journal|inventory|holdings|copies)\b",
        " ",
        query,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", q).strip(" :\"'?.")


def parse_chapter_lookup_query(query: str) -> tuple[str, str]:
    query_lower = query.lower()
    splitters = [
        "discusses",
        "discussed",
        "discuss",
        "mentioning",
        "mentions",
        "mentioned",
        "mention",
        "containing",
        "contains",
        "contained",
        "contain",
        "covering",
        "covers",
        "covered",
        "cover",
        "is in",
        "about",
        "has",
    ]
    for splitter in splitters:
        if splitter in query_lower:
            idx = query_lower.find(splitter)
            book_part = query[:idx]
            concept_part = query[idx + len(splitter) :]
            book = re.sub(
                r"\b(which|chapter|section|of|book|paper|where|in)\b", "", book_part, flags=re.I
            ).strip(" :\"'?.")
            concept = concept_part.strip(" :\"'?.")
            return book, concept
    return query, query
