"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import re
from typing import Any
from thefuzz import fuzz
from archipelago.inference.graph_lock import graph_lock
from archipelago.inference import state as st
import kuzu
from . import _deps as _rt  # noqa: F401


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
        s2 = max((fuzz.token_set_ratio(cleaned, a.lower()) for a in meta.get("aliases", [])), default=0)
        s3 = fuzz.token_set_ratio(cleaned, meta["authors"].lower())
        score = max(s1, s2, s3 * 0.8)
        if score > best_score:
            best_score = score
            best_key = key

    if best_key and best_score >= 40:
        return _rt.LIBRARY_CATALOG_KNOWLEDGE[best_key]

    # Fallback to KuzuDB lookup
    try:
        with graph_lock.read_lock():
            conn = kuzu.Connection(st.db)
            res = conn.execute("MATCH (d:Document) RETURN d.id, d.title")
            docs = []
            while res.has_next():
                r = res.get_next()
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
                        "key_sections": ["Overview", "Technical Theory", "Methodology", "References"],
                        "prerequisites": ["Foundational Computer Science"],
                        "unlocks": ["Advanced Theory"]
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
    lines.append(f"- **Shelf Availability**: **{meta['available_copies']} of {meta['total_copies']} copies available** · Shelf Location: `{meta['shelf_location']}`")
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


def get_books_for_topic(topic_query: str, limit: int = 5) -> list[dict]:
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
            results.append({
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
            })
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
        fallback.append({
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
        })
        if len(fallback) >= limit:
            break
    return fallback


def get_library_hours_response() -> str:
    return """### ⏰ Central Library Hours & Access Policies

- **Reading Hall & Study Space**: **Open 24 × 7 × 365** (including nights, weekends, and academic breaks).
- **Circulation Desk (Book Issue / Return)**:
  - **Weekdays (Monday – Friday)**: 09:00 AM – 07:00 PM (Full issue, return, and renewal services).
  - **Weekends & Holidays (Saturday – Sunday)**: Open for quiet study, reading, and digital access. Circulation desk closed.
- **Online Catalogue (OPAC)**: [uemk-opac.l2c2.co.in](https://uemk-opac.l2c2.co.in) (24/7 online catalogue search).
- **Institutional E-Resources**: IEEE Xplore, ScienceDirect / Scopus, Springer Link, and Pearson eLibrary accessible on campus network.
"""


def get_library_holdings_response(query: str) -> str:
    ql = (query or "").lower()

    # Check if specifically asking about journals
    if "journal" in ql:
        lines = ["### 📰 Central Library Journal Registry & Periodical Holdings\n"]
        lines.append("| Journal Title | Publisher | Accession / Shelving | Volumes | Copies Available |")
        lines.append("|---|---|---|---|---|")
        for j in _rt.JOURNAL_REGISTRY:
            lines.append(f"| **{j['title']}** | {j['publisher']} | `{j['accession']}` | {j['volume_years']} | **{j['available_copies']}/{j['total_copies']} Available** |")
        lines.append("\n📍 *All journals are available in the Periodicals Section & AI Research Archive.*")
        return "\n".join(lines)

    # General Holdings & Inventory Summary
    return """### 📊 Central Library Holdings & Inventory

- **Total Holdings Records**: **109 Records**
- **Total Physical Copies**: **904 Copies**
- **Currently Available Now**: **901 Copies**

#### Core Book Inventory:
1. **Attention Is All You Need** (Vaswani et al.) · **3/4 Available** · Shelf: `AIML-NLP-02`
2. **Deep Learning** (Goodfellow, Bengio, Courville) · **5/5 Available** · Shelf: `DL-01`
3. **Operating Systems: Three Easy Pieces** (Arpaci-Dusseau) · **4/7 Available** · Shelf: `OS-01`
4. **Database System Concepts** (Silberschatz et al.) · **4/4 Available** · Shelf: `DBMS-01`
5. **Mathematics for Machine Learning** (Deisenroth et al.) · **5/5 Available** · Shelf: `AIML-MATH-01`
6. **LoRA: Low-Rank Adaptation of LLMs** (Hu et al.) · **2/3 Available** · Shelf: `AIML-PEFT-01`
7. **BERT: Pre-training Deep Bidirectional Transformers** (Devlin et al.) · **4/5 Available** · Shelf: `AIML-NLP-01`

#### Core Journal Registry:
1. **Journal of Human Resource Management** · **2/2 Available** · Accession: `J297, J621`
2. **Academy of Management Journal** · **6/6 Available** · Accession: `J280..J675`
3. **Applied Artificial Intelligence Journal** · **3/3 Available** · Accession: `J501..J503`
4. **IEEE Transactions on Neural Networks** · **4/4 Available** · Shelf: `IEEE-TNN-01`
5. **ACM Transactions on Database Systems (TODS)** · **2/2 Available** · Shelf: `ACM-TODS-01`

📍 *Visit [/library](/library) to interact with 3D rotatable & opening books and browse all 109 catalog items.*
"""


def render_library_books(topic: str, books: list[dict]) -> str:
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
    lines.append("\n📍 *Ask 'tell me about this book: <title>' for full chapter outlines and digital reader access.*")
    return "\n".join(lines)


def render_library_chapters(book_title: str, chapters: list[dict]) -> str:
    lines = [f"### 📑 Table of Contents for '{book_title}'\n"]
    if not chapters:
        lines.append("No chapter breakdown recorded in the current index.")
        return "\n".join(lines)
    for ch in chapters:
        title = ch.get("section_title", "Section")
        pg = ch.get("page_number", 0)
        lines.append(f"- **{title}** (Page {pg})")
    return "\n".join(lines)


def render_library_chapter_lookup(book_title: str, concept: str, chapters: list[dict]) -> str:
    lines = [f"### 🔍 Chapters in '{book_title}' discussing '{concept}'\n"]
    if not chapters:
        lines.append(f"No chapters specifically indexing '{concept}' were found.")
        return "\n".join(lines)
    for ch in chapters:
        title = ch.get("section_title", "Section")
        pg = ch.get("page_number", 0)
        lines.append(f"- **{title}** (Page {pg})")
    return "\n".join(lines)


def get_chapters_of_book(book_query: str) -> tuple[str, list[dict]] | None:
    meta = get_book_metadata_details(book_query)
    if meta:
        chapters = [{"section_title": s, "page_number": idx + 1} for idx, s in enumerate(meta.get("key_sections", []))]
        return meta["title"], chapters
    return None


def get_chapters_containing_concept(query: str) -> tuple[str, str, list[dict]] | None:
    book_part, concept_part = _rt.parse_chapter_lookup_query(query)
    meta = get_book_metadata_details(book_part)
    if meta:
        chapters = [{"section_title": s, "page_number": idx + 1} for idx, s in enumerate(meta.get("key_sections", []))]
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
            return j
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
