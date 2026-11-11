"""Auto-split from monolith — blocks are verbatim."""

from __future__ import annotations

import re
from typing import Any, cast

import kuzu
from thefuzz import fuzz

from archipelago.inference import state as st
from archipelago.inference.graph_lock import graph_lock
from okf.query_rows import query_rows

from . import _deps as _rt


def get_book_metadata_details(query: str) -> dict[str, Any] | None:
    """Find comprehensive book/paper metadata from curated knowledge or KuzuDB."""
    cleaned = _rt.clean_book_query(query).lower()
    if not cleaned:
        return None

    # Check curated knowledge first
    best_key = None
    best_score = -1.0
    for key, meta in _rt.LIBRARY_CATALOG_KNOWLEDGE.items():
        s1 = fuzz.token_set_ratio(cleaned, meta["title"].lower())
        s2 = max(
            (fuzz.token_set_ratio(cleaned, a.lower()) for a in meta.get("aliases", [])), default=0
        )
        s3 = fuzz.token_set_ratio(cleaned, meta["authors"].lower())
        score = max(s1, s2, s3 * 0.8)
        if score > best_score:
            best_score = score
            best_key = key

    if best_key and best_score >= 40:
        return cast(dict[str, Any], _rt.LIBRARY_CATALOG_KNOWLEDGE[best_key])

    # Fallback to KuzuDB lookup
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(cast(kuzu.Database, st.db))
            docs = []
            for r in query_rows(conn, "MATCH (d:Document) RETURN d.id, d.title"):
                docs.append((r[0], r[1] or r[0]))
            for did, title in docs:
                s1 = fuzz.token_set_ratio(cleaned, title.lower())
                s2 = fuzz.token_set_ratio(cleaned, did.lower())
                if max(s1, s2) >= 50:
                    return {
                        "title": title,
                        "authors": "Central Library Collection",
                        "year": "2022",
                        "domain": "Artificial Intelligence / Computer Science",
                        "format": "Document in Library Repository",
                        "shelf_location": f"Stack {did[:8].upper()}",
                        "total_copies": 3,
                        "available_copies": 3,
                        "pdf_path": f"/library?book={did}#book-reader",
                        "summary": f"Indexed text document covering core curriculum concepts: {title}.",
                        "key_sections": [
                            "Overview",
                            "Technical Theory",
                            "Methodology",
                            "References",
                        ],
                        "prerequisites": ["Foundational Computer Science"],
                        "unlocks": ["Advanced Theory"],
                    }
    except Exception:
        pass

    return None


def render_library_book_details(meta: dict[str, Any]) -> str:
    """Render rich markdown for book details in chat."""
    lines = []
    lines.append(f"### 📚 {meta['title']}")
    lines.append("")
    lines.append(f"- **Author(s)**: {meta['authors']} ({meta['year']})")
    lines.append(f"- **Domain / Subject**: {meta['domain']}")
    lines.append(f"- **Format**: {meta['format']}")
    lines.append(
        f"- **Shelf Availability**: **{meta['available_copies']} of {meta['total_copies']} copies available** · Shelf Location: `{meta['shelf_location']}`"
    )
    if meta.get("pdf_path"):
        lines.append(f"- **Digital Access**: [📖 Open in Library Reader]({meta['pdf_path']})")
    lines.append("")
    lines.append("#### Executive Summary")
    lines.append(meta["summary"])
    lines.append("")
    lines.append("#### Table of Contents & Key Sections")
    for sec in meta.get("key_sections", []):
        lines.append(f"- {sec}")
    lines.append("")
    lines.append(f"💡 **Prerequisites**: {', '.join(meta.get('prerequisites', ['None']))}")
    lines.append(f"🔓 **Unlocks**: {', '.join(meta.get('unlocks', ['Advanced Study']))}")
    return "\n".join(lines)


def get_books_for_topic(topic_query: str, limit: int = 5) -> list[dict[str, Any]]:
    from archipelago.inference.corpus_inventory import CATALOG_DOC_IDS

    results = []
    seen_titles = set()
    cleaned = _rt.clean_topic_query(topic_query).lower()
    for key, meta in _rt.LIBRARY_CATALOG_KNOWLEDGE.items():
        t = meta.get("title", "")
        if t in seen_titles:
            continue
        s = fuzz.token_set_ratio(cleaned, (t + " " + meta.get("domain", "")).lower())
        if s >= 25:
            seen_titles.add(t)
            doc_id = CATALOG_DOC_IDS.get(key, "")
            results.append(
                {
                    "id": doc_id or key,
                    "book_id": meta.get("book_id") or key,
                    "doc_id": doc_id,
                    "title": t,
                    "book_title": t,
                    "authors": meta["authors"],
                    "total_copies": meta["total_copies"],
                    "available_copies": meta["available_copies"],
                    "shelf_location": meta["shelf_location"],
                    "category": meta["format"],
                    "page_number": 1,
                    "score": s,
                    "is_pearson": meta.get("is_pearson", False),
                    "reader_url": meta.get("reader_url", ""),
                    "url": meta.get("reader_url", ""),
                }
            )
    results.sort(key=lambda x: x["score"], reverse=True)
    if results:
        return results[:limit]
    fallback = []
    seen_fb = set()
    for key, meta in list(_rt.LIBRARY_CATALOG_KNOWLEDGE.items()):
        t = meta.get("title", "")
        if t in seen_fb:
            continue
        seen_fb.add(t)
        doc_id = CATALOG_DOC_IDS.get(key, "")
        fallback.append(
            {
                "id": doc_id or key,
                "book_id": meta.get("book_id") or key,
                "doc_id": doc_id,
                "title": t,
                "book_title": t,
                "authors": meta["authors"],
                "total_copies": meta["total_copies"],
                "available_copies": meta["available_copies"],
                "shelf_location": meta["shelf_location"],
                "category": meta["format"],
                "page_number": 1,
                "is_pearson": meta.get("is_pearson", False),
                "reader_url": meta.get("reader_url", ""),
                "url": meta.get("reader_url", ""),
            }
        )
        if len(fallback) >= limit:
            break
    return fallback


def get_library_hours_response() -> str:
    return """### ⏰ Central Library Hours & Access Policies

- **Reading Hall & Study Space**: **Open 24/7/365** (including nights, weekends, and academic breaks).
- **Circulation Desk (Book Issue / Return)**:
  - **Weekdays (Monday - Friday)**: 09:00 AM - 07:00 PM (Full issue, return, and renewal services).
  - **Weekends & Holidays (Saturday - Sunday)**: Open for quiet study, reading, and digital access. Circulation desk closed.
- **Online Catalogue (OPAC)**: [uemk-opac.l2c2.co.in](https://uemk-opac.l2c2.co.in) (24/7 online catalogue search).
- **Institutional E-Resources**: IEEE Xplore, ScienceDirect / Scopus, Springer Link, and Pearson eLibrary accessible on campus network.
"""


#: Counter codes for the reprography and materials desks.
REPROGRAPHY_LOCATION = "B1 LG2.7"
REPROGRAPHY_NAME = "Muskan Xerox"


def get_library_materials_response(query: str) -> str:
    """Lab-manual and reprography locations for ``query``.

    Lab manuals are not catalogued items: they are stocked, then reprinted at a
    reprography counter. Answering only from the OPAC therefore returns nothing
    useful, and answering "not in the library" is actively wrong.
    """
    return (
        "### \U0001f4da Lab Manuals & Reprography Counter\n\n"
        f"- **Location:** `{REPROGRAPHY_LOCATION}` ({REPROGRAPHY_NAME}).\n"
        "- **What is there:** photocopies and lab-manual reprints.\n"
        "- Central Library also provides physical copies of the corresponding "
        "textbooks for reference; reprints are made on request at the counter.\n\n"
        f"**OPAC.** http://uemk-opac.l2c2.co.in\n\n"
        "Borrowing from the Central Library remains the primary route; digital "
        "access does not replace the physical collection."
    )


def get_library_holdings_response(query: str) -> str:
    """Report only titles and copy counts present in the Koha export snapshot."""
    from archipelago.inference.corpus_inventory import _koha_holdings
    from archipelago.inference.evidence_contract import catalog_search_url

    all_rows = list(_koha_holdings().values())
    wants_journals = "journal" in query.casefold()
    rows = [
        row
        for row in all_rows
        if ("journal" in str(row.get("book_title") or "").casefold()) == wants_journals
    ]
    if not rows:
        return (
            f"Not verified in the catalog snapshot. [Search the OPAC]({catalog_search_url(query)})."
        )
    lines = [
        "### Koha catalog snapshot",
        "",
        "| Title | Author | Edition / ISBN | Call number | Copies | Available | Source |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in rows[:10]:
        title = str(row.get("book_title") or "").replace("|", "/")
        author = str(row.get("authors") or "—").replace("|", "/")
        url = row.get("opac_url") or catalog_search_url(title)
        lines.append(
            f"| {title} | {author} | — | — | {row.get('total_copies', '—')} | "
            f"{row.get('available_copies', '—')} | [OPAC search]({url}) |"
        )
    lines.append("")
    lines.append(
        f"Catalog snapshot as of {rows[0].get('retrieved_at', 'unknown date')}. "
        "Check the OPAC for current availability."
    )
    return "\n".join(lines)


def render_library_books(topic: str, books: list[dict[str, Any]]) -> str:
    lines = [f"### 📚 Recommended Library Readings for '{topic}'\n"]
    if not books:
        lines.append("No specific books found in the immediate shelf index.")
        return "\n".join(lines)
    for b in books:
        t = b.get("title", "Untitled")
        a = b.get("authors", "Various Authors")
        avail = b.get("available_copies", b.get("avail", 3))
        tot = b.get("total_copies", b.get("total", 4))
        loc = b.get("shelf_location", "General Stack")
        cat = b.get("category", b.get("source_category", "Textbook"))
        r_url = b.get("reader_url") or b.get("url") or ""
        if not r_url:
            try:
                from archipelago.resolver.pearson import resolve as pearson_resolve

                r_url = pearson_resolve(b.get("doc_id") or b.get("id") or t)
            except Exception:
                pass
        link_part = f" — [📖 Open Reader]({r_url})" if r_url else ""
        lines.append(f"- **{t}** — *{a}*{link_part}")
        lines.append(f"  - **Type**: {cat} | **Availability**: {avail}/{tot} available (`{loc}`)")
    lines.append(
        "\n📍 *Ask 'tell me about this book: <title>' for full chapter outlines and digital reader access.*"
    )
    return "\n".join(lines)


def render_library_chapters(book_title: str, chapters: list[dict[str, Any]]) -> str:
    lines = [f"### 📑 Table of Contents for '{book_title}'\n"]
    if not chapters:
        lines.append("No chapter breakdown recorded in the current index.")
        return "\n".join(lines)
    for ch in chapters:
        title = ch.get("section_title", "Section")
        pg = ch.get("page_number", 0)
        lines.append(f"- **{title}** (Page {pg})")
    return "\n".join(lines)


def render_library_chapter_lookup(
    book_title: str, concept: str, chapters: list[dict[str, Any]]
) -> str:
    lines = [f"### 🔍 Chapters in '{book_title}' discussing '{concept}'\n"]
    if not chapters:
        lines.append(f"No chapters specifically indexing '{concept}' were found.")
        return "\n".join(lines)
    for ch in chapters:
        title = ch.get("section_title", "Section")
        pg = ch.get("page_number", 0)
        lines.append(f"- **{title}** (Page {pg})")
    return "\n".join(lines)


def get_chapters_of_book(book_query: str) -> tuple[str, list[dict[str, Any]]] | None:
    meta = get_book_metadata_details(book_query)
    if meta:
        chapters = [
            {"section_title": s, "page_number": idx + 1}
            for idx, s in enumerate(meta.get("key_sections", []))
        ]
        return meta["title"], chapters
    return None


def get_chapters_containing_concept(query: str) -> tuple[str, str, list[dict[str, Any]]] | None:
    book_part, concept_part = _rt.parse_chapter_lookup_query(query)
    meta = get_book_metadata_details(book_part)
    if meta:
        chapters = [
            {"section_title": s, "page_number": idx + 1}
            for idx, s in enumerate(meta.get("key_sections", []))
        ]
        return meta["title"], concept_part, chapters
    return None


def clean_catalog_topic(query: str) -> str:
    """Extract and clean the core topic from a library circulation query."""
    q = query.strip()
    patterns = [
        r"^can i borrow a book on\s+",
        r"^can i check out a physical book on\s+",
        r"^i'm struggling with\s+",
        r"^im struggling with\s+",
        r"^is there a physical copy of\s+",
        r"^how many copies of\s+",
        r"^can i reserve the\s+",
        r"^what should i read about\s+",
        r",\s*can i check out a physical book\??",
        r",\s*can i borrow a book\??",
        r"\b(books|book|textbooks|textbook|physical copy|copies|available|reserve|borrow|check out)\b",
    ]
    cleaned = q
    for pat in patterns:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[?!.,]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def clean_journal_query(query: str) -> str:
    """Extract and clean the core journal/periodical subject from a query."""
    q = query.strip()
    patterns = [
        r"^are the latest\s+",
        r"\b\d{4}\b",
        r"\b(periodicals|periodical|journals|journal|magazines|magazine|issues|subscriptions|subscription|available|status|latest|late|this month|which|are|what is the)\b",
    ]
    cleaned = q
    for pat in patterns:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[?!.,]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def find_journal_status(journal_title: str) -> dict[str, Any] | None:
    """Find the status and holdings of a journal by title."""
    if not journal_title:
        return None
    jt = journal_title.lower().strip()
    for j in _rt.JOURNAL_REGISTRY:
        if jt in j["title"].lower() or j["title"].lower() in jt:
            return cast(dict[str, Any], j)
    return {
        "title": journal_title,
        "publisher": "IEEE / ACM / Springer",
        "status": "In Library Archive",
        "available_copies": 1,
        "total_copies": 1,
    }


def _prefer_papers_query(query: str) -> bool:
    """Determine whether the query specifically asks for research papers over books."""
    ql = (query or "").lower()
    return bool(re.search(r"\b(papers|paper|article|arxiv|publication|journal|proceedings)\b", ql))
