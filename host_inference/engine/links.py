"""Build the exact-source link lines appended to a grounded reply.

Two link families, in priority order:

* **Hugging Face page.** — the dataset PDF at the cited page.
* **Pearson page.** — the institutional e-book reader URL at the cited page,
  built by ``remote_cache.pearson_page_url``.

The link line is re-appended verbatim after LLM polishing, so it must always
point at a real, exact page — never a generic homepage or ``/chat``.
"""

from __future__ import annotations

from urllib.parse import quote

from .access_profile import (
    d14_canonical_oa_url,
    is_d14_approved_oa,
    is_d14_excluded_commercial,
    is_open_access_profile,
    is_pearson_url,
)
from .corpus_titles import OPEN_CORPUS_TITLES
from .provenance import (
    EVIDENCE_STATE_METADATA_ONLY,
    EVIDENCE_STATE_UNAVAILABLE,
    classify_evidence_state,
    format_canonical_title,
    resolve_page_provenance,
)

HF_LINK_LABEL = "**Hugging Face page.**"
PEARSON_LINK_LABEL = "**Pearson page.**"

PAPER_TITLE_MAP: dict[str, str] = dict(OPEN_CORPUS_TITLES)


def human_paper_title(raw_title: str, doc_id: str = "") -> str:
    """Resolve a human-readable paper title from a PDF filename or raw title."""
    return format_canonical_title(doc_id, raw_title)


def source_links(record: dict, book: dict | None, page: int = 1) -> str:
    """Return the newline-joined link lines for one citation record.

    ``record`` is a ``LibraryGraph.cite_record`` result; ``book`` is the matched
    Pearson shelf record (``None`` when no physical/e-book copy matches).
    """
    del page  # Explicit page_number on ``record`` is the sole source of truth.
    open_only = is_open_access_profile()
    if is_d14_excluded_commercial(record):
        return ""
    ev_state = str(record.get("evidence_state") or "").strip() or classify_evidence_state(
        record, open_access_only=open_only
    )
    if ev_state in {EVIDENCE_STATE_UNAVAILABLE, EVIDENCE_STATE_METADATA_ONLY}:
        return ""

    raw_page_n = int(record["page_number"]) if record.get("page_number") else None
    doc_ref = str(record.get("doc_id") or "paper")
    prov = resolve_page_provenance(doc_ref, raw_page_n, record.get("printed_page"))
    page_n = prov["pdf_page"] if prov["page_in_bounds"] else None
    page_verified = bool(record.get("page_verified", bool(page_n))) and bool(page_n)
    lines: list[str] = []
    source_url = str(record.get("url") or "").strip()
    if not source_url and is_d14_approved_oa(record):
        source_url = d14_canonical_oa_url(record)
    if (
        source_url
        and not source_url.startswith("/chat")
        and record.get("reader_resolvable", True)
    ):
        name = doc_ref.split("/")[-1]
        raw_title = record.get("doc_title") or record.get("title") or name
        title = human_paper_title(str(raw_title), doc_ref)
        if is_pearson_url(source_url):
            if not open_only:
                lines.append(f"[{title} (Pearson institutional access)]({source_url})")
        else:
            if page_n and name.lower().endswith(".pdf") and source_url.startswith("/read?"):
                source_url = f"/papers/{quote(name, safe='')}#page={page_n}"
            page_label = f" — {prov['page_display']}" if (page_n and prov["page_display"]) else ""
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
    page_label = (
        f" — page {page_n}" if (page_n and page_verified and book_type == "pdf") else ""
    )
    lines.append(f"[{btitle}{page_label}]({href})")
    return "\n".join(lines)
