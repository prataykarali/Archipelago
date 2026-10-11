"""Build the exact-source link lines appended to a grounded reply.

Two link families, in priority order:

* **Hugging Face page.** — the dataset PDF at the cited page.
* **Pearson page.** — the institutional e-book reader URL at the cited page,
  built by ``remote_cache.pearson_page_url``.

The link line is re-appended verbatim after LLM polishing, so it must always
point at a real, exact page — never a generic homepage.
"""

from __future__ import annotations

HF_LINK_LABEL = "**Hugging Face page.**"
PEARSON_LINK_LABEL = "**Pearson page.**"


def source_links(record: dict, book: dict | None, page: int = 1) -> str:
    """Return the newline-joined link lines for one citation record.

    ``record`` is a ``LibraryGraph.cite_record`` result; ``book`` is the matched
    Pearson shelf record (``None`` when no physical/e-book copy matches).
    """
    page_n = int(record.get("page_number") or page or 1)
    lines: list[str] = []
    if record.get("url"):
        name = (record.get("doc_id") or "paper").split("/")[-1]
        title = (
            record.get("doc_title")
            or record.get("title")
            or name.replace("_", " ").replace(".pdf", "")
        )
        lines.append(f"[{title} — page {page_n}]({record['url']})")
    if not book:
        return "\n".join(lines)
    page_count = int(book.get("page_count") or 0)
    if page_count and page_n > page_count:
        return "\n".join(lines)
    href = f"/open/{book.get('id')}?page={page_n}"
    btitle = book.get("title") or "Pearson Textbook"
    lines.append(f"[{btitle} — page {page_n}]({href})")
    return "\n".join(lines)
