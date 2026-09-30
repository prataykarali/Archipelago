"""Append a fake holdings table + exact-page links to every chat reply."""
from __future__ import annotations

from typing import Any

from archipelago.inference.corpus_inventory import (
    books_from_catalog_meta,
    books_from_citations,
    default_core_inventory,
    inventory_for_books,
)
from archipelago.inference.demo_query_books import (
    books_for_query,
    enrich_reply_with_books,
)

_HOLDINGS_MARKERS = (
    "Koha catalogue matches",
    "### Library holdings",
)


def resolve_reply_books(
    query: str,
    citations: list[dict[str, Any]] | None = None,
    books: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Pick the best book rows for this reply: explicit, cites, demo, or core shelf."""
    if books:
        return inventory_for_books(list(books))
    from_cites = books_from_citations(citations)
    if from_cites:
        return from_cites
    from_meta = books_from_catalog_meta(meta)
    if from_meta:
        return from_meta
    demo = books_for_query(query)
    if demo:
        return inventory_for_books(demo)
    return default_core_inventory()


def inventory_suffix(
    query: str,
    citations: list[dict[str, Any]] | None = None,
    books: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Markdown suffix: inline page chips + fake inventory table.

    Empty when the body already contains a holdings table.
    """
    rows = resolve_reply_books(query, citations=citations, books=books, meta=meta)
    if not rows:
        return ""
    # enrich_reply_with_books prepends to an empty body → suffix only.
    extra = enrich_reply_with_books(query, "", books=rows)
    return extra if extra.strip() else ""


def attach_inventory(
    query: str,
    reply: str,
    citations: list[dict[str, Any]] | None = None,
    books: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Return reply with holdings table and exact-page links appended."""
    body = (reply or "").rstrip()
    if any(marker in body for marker in _HOLDINGS_MARKERS):
        return body
    extra = inventory_suffix(query, citations=citations, books=books, meta=meta)
    if not extra:
        return body
    return body + extra
