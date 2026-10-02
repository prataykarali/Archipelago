"""Auto-split from synthesis.py — do not edit blocks by hand."""
from __future__ import annotations

import os
import re


DOC_TITLE_MAP = {
    "Deisenroth_Math_For_ML.pdf": "Mathematics for Machine Learning (Deisenroth et al.)",
    "Vaswani2017_Attention_Is_All_You_Need.pdf": "Attention Is All You Need (Vaswani et al., 2017)",
    "Hu2021_LoRA.pdf": "LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)",
    "Lewis2020_RAG.pdf": "Retrieval-Augmented Generation (Lewis et al., 2020)",
    "Devlin2018_BERT.pdf": "BERT (Devlin et al., 2018)",
    "Edge2024_GraphRAG.pdf": "From Local to Global: GraphRAG (Edge et al., 2024)",
    "AI_ML_Archipelago_Corpus_Seed.md": "AI/ML Corpus Seed Syllabus",
}


def prettify_doc_title(doc_id_or_title: str) -> str:
    """Map a raw doc id/path like 'textbooks/Deisenroth_Math_For_ML.pdf' to a human title."""
    raw = (doc_id_or_title or "").strip()
    if not raw:
        return raw
    if raw in DOC_TITLE_MAP:
        return DOC_TITLE_MAP[raw]
    basename = os.path.basename(raw)
    if basename in DOC_TITLE_MAP:
        return DOC_TITLE_MAP[basename]
    # Only rewrite path-like ids; leave already-human titles untouched.
    if re.search(r"\.(pdf|md|txt|epub)$", raw, re.IGNORECASE) or raw.startswith(("/", "./", "../", "textbooks/", "papers/", "ostep_")):
        name = re.sub(r"\.(pdf|md|txt|epub)$", "", basename, flags=re.IGNORECASE)
        return name.replace("_", " ").strip() or raw
    if " " not in raw and "_" in raw:
        return raw.replace("_", " ").strip()
    return raw


def render_library_books(topic: str, books: list[dict]) -> str:
    """Format suggested books for a topic in Markdown."""
    lines = [f"Recommended reading for: **{topic}**\n"]
    if not books:
        lines.append("No books found matching this topic in the database.")
        return "\n".join(lines)

    for index, book in enumerate(books, 1):
        title = prettify_doc_title(book.get("title") or book.get("id") or "")
        doc_id = book.get("id") or book.get("shelf_location") or "library_shelf"
        mentions = book.get("mentions") or 0
        matched = ", ".join(book.get("matched") or [])
        cat = book.get("source_category") or book.get("category") or ""
        cat_label = {
            "textbook": "textbook",
            "paper": "paper",
            "web_syllabus": "syllabus",
            "markdown": "notes",
        }.get(cat, cat or "source")

        reader_url = book.get("reader_url") or book.get("url") or ""
        if not reader_url:
            try:
                from archipelago.resolver.pearson import resolve as pearson_resolve
                reader_url = pearson_resolve(doc_id) or (pearson_resolve(title) if title else "")
            except Exception:
                pass
        if not reader_url and doc_id:
            reader_url = f"/api/page-view?doc_id={doc_id}&page=1#page=1"

        link_str = f" — [📖 Open in Reader]({reader_url})" if reader_url else ""
        lines.append(f"{index}. **{title}** _{cat_label}_ (`{doc_id}`){link_str}")
        if matched:
            lines.append(f"   - Matched concepts: {matched} ({mentions} mentions)\n")
        else:
            lines.append(f"   - Mentions: {mentions}\n")
    lines.append(
        "\n_Textbooks are preferred for book-style questions; ask for “papers on …” "
        "if you want research articles._"
    )
    return "\n".join(lines)


def render_library_chapters(book_title: str, chapters: list[dict]) -> str:
    """Format chapters list for a book in Markdown.

    Books ingested at section granularity can have hundreds of headings; above
    40 entries we show only top-level chapters (numbered like "1 Title") and
    frontmatter, with a note about the omitted sections.
    """
    pretty_title = prettify_doc_title(book_title)
    lines = [f"Chapters and sections in **{pretty_title}**:\n"]
    if not chapters:
        lines.append("No chapters or sections are indexed for this book.")
        return "\n".join(lines)

    total = len(chapters)
    shown = chapters
    if total > 40:
        top_level = [
            ch for ch in chapters
            if _TOP_LEVEL_CHAPTER_RE.match((ch.get("section_title") or "").strip())
            or _FRONTMATTER_RE.match((ch.get("section_title") or "").strip())
        ]
        if top_level:
            shown = top_level
            lines[0] = (
                f"Chapters and sections in **{pretty_title}** "
                f"(showing {len(top_level)} top-level chapters of {total} sections):\n"
            )
        else:
            shown = chapters[:40]
            lines[0] = (
                f"Chapters and sections in **{pretty_title}** "
                f"(showing first 40 of {total} sections):\n"
            )

    for index, ch in enumerate(shown, 1):
        sect = ch["section_title"]
        page = ch["page_number"]
        lines.append(f"   {index}. **{sect}** — starting at page {page}")
    return "\n".join(lines)


def render_library_chapter_lookup(book_title: str, concept_name: str, chapters: list[dict]) -> str:
    """Format sections in a book discussing a concept in Markdown."""
    pretty_title = prettify_doc_title(book_title)
    lines = [f"Sections in **{pretty_title}** discussing **{concept_name}**:\n"]
    if not chapters:
        lines.append(f"No sections discussing '{concept_name}' were found in this book.")
        return "\n".join(lines)

    for index, ch in enumerate(chapters, 1):
        sect = ch["section_title"]
        page = ch["page_number"]
        lines.append(f"   {index}. **{sect}** — Page {page}")
    return "\n".join(lines)


_FRONTMATTER_RE = re.compile(
    r"^(foreword|preface|acknowledg|introduction|contents|notation|abstract|"
    r"references|bibliography|index|appendix|glossary|conclusion)",
    re.IGNORECASE,
)


_TOP_LEVEL_CHAPTER_RE = re.compile(r"^(chapter\s+)?\d+\s+\S", re.IGNORECASE)
