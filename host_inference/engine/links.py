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

HF_LINK_LABEL = "**Hugging Face page.**"
PEARSON_LINK_LABEL = "**Pearson page.**"


def source_links(record: dict, book: dict | None, page: int = 1) -> str:
    """Return the newline-joined link lines for one citation record.

    ``record`` is a ``LibraryGraph.cite_record`` result; ``book`` is the matched
    Pearson shelf record (``None`` when no physical/e-book copy matches).
    """
    page_n = int(record["page_number"]) if record.get("page_number") else None
    lines: list[str] = []
    if record.get("url"):
        name = (record.get("doc_id") or "paper").split("/")[-1]
        title = record.get("doc_title") or record.get("title") or name
        source_url = record["url"]
        if page_n and name.lower().endswith(".pdf") and source_url.startswith("/read?"):
            source_url = f"/papers/{quote(name, safe='')}#page={page_n}"
        page_label = f" — page {page_n}" if page_n else ""
        lines.append(f"[{title}{page_label}]({source_url})")
    if not book:
        return "\n".join(lines)
    page_count = int(book.get("page_count") or 0)
    if page_count and page_n and page_n > page_count:
        return "\n".join(lines)
    href = f"/open/{book.get('id')}"
    if page_n:
        href += f"?page={page_n}"
    btitle = book.get("title") or "Pearson Textbook"
    page_label = f" — page {page_n}" if page_n else ""
    lines.append(f"[{btitle}{page_label}]({href})")
    return "\n".join(lines)
