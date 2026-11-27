"""Build the exact-source link lines appended to a grounded reply.

Two link families, in priority order:

* **Hugging Face page.** — the dataset PDF at the cited page.
* **Pearson page.** — the institutional e-book reader URL at the cited page,
  built by ``remote_cache.pearson_page_url``.

The link line is re-appended verbatim after LLM polishing, so it must always
point at a real, exact page — never a generic homepage.
"""

from __future__ import annotations

from urllib.parse import quote

from .access_profile import is_open_access_profile, is_pearson_url
from .corpus_titles import OPEN_CORPUS_TITLES, clean_bibliographic_title

HF_LINK_LABEL = "**Hugging Face page.**"
PEARSON_LINK_LABEL = "**Pearson page.**"

PAPER_TITLE_MAP: dict[str, str] = dict(OPEN_CORPUS_TITLES)


def human_paper_title(raw_title: str, doc_id: str = "") -> str:
    """Resolve a human-readable paper title from a PDF filename or raw title."""
    return clean_bibliographic_title(doc_id, raw_title)


def source_links(record: dict, book: dict | None, page: int = 1) -> str:
    """Return the newline-joined link lines for one citation record.

    ``record`` is a ``LibraryGraph.cite_record`` result; ``book`` is the matched
    Pearson shelf record (``None`` when no physical/e-book copy matches).
    """
    open_only = is_open_access_profile()
    page_n = int(record["page_number"]) if record.get("page_number") else None
    page_verified = bool(record.get("page_verified", bool(page_n)))
    lines: list[str] = []
    if record.get("url") and record.get("reader_resolvable", True):
        name = (record.get("doc_id") or "paper").split("/")[-1]
        raw_title = record.get("doc_title") or record.get("title") or name
        title = human_paper_title(str(raw_title), name)
        source_url = record["url"]
        if is_pearson_url(source_url):
            if not open_only:
                lines.append(f"[{title} (Pearson institutional access)]({source_url})")
        else:
            if page_n and name.lower().endswith(".pdf") and source_url.startswith("/read?"):
                source_url = f"/papers/{quote(name, safe='')}#page={page_n}"
            page_label = f" — p. {page_n}" if page_n else ""
            lines.append(f"[{title}{page_label}]({source_url})")
    if open_only or not book:
        return "\n".join(lines)
    if record.get("is_pearson") and record.get("book_id") == book.get("id"):
        return "\n".join(lines)
    page_count = int(book.get("page_count") or 0)
    if page_count and page_n and page_n > page_count:
        return "\n".join(lines)
    href = f"/open/{book.get('id')}"
    book_type = str(book.get("book_type") or "pdf").strip().lower()
    if page_n and page_verified and book_type == "pdf":
        href += f"?page={page_n}"
    btitle = book.get("title") or "Pearson Textbook"
    page_label = f" — page {page_n}" if (page_n and page_verified and book_type == "pdf") else ""
    lines.append(f"[{btitle}{page_label}]({href})")
    return "\n".join(lines)
