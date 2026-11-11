"""Append physical holdings only when a Koha export verifies the title."""

from __future__ import annotations

import re
from typing import Any

from archipelago.inference.corpus_inventory import (
    books_from_catalog_meta,
    books_from_citations,
    inventory_for_books,
)
from archipelago.inference.demo_query_books import (
    enrich_reply_with_books,
)
from archipelago.inference.evidence_contract import catalog_search_url

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
    """Return only rows confirmed by the institutional holdings snapshot."""
    if books:
        return [row for row in inventory_for_books(list(books)) if row.get("koha_record_verified")]
    from_cites = books_from_citations(citations)
    if from_cites:
        return [row for row in from_cites if row.get("koha_record_verified")]
    from_meta = books_from_catalog_meta(meta)
    if from_meta:
        return [row for row in from_meta if row.get("koha_record_verified")]
    return []


def inventory_suffix(
    query: str,
    citations: list[dict[str, Any]] | None = None,
    books: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Markdown suffix for verified imported holdings only.

    Empty when the body already contains a holdings table.
    """
    if not re.search(
        r"\b(book|books|library|catalog|catalogue|holdings|copies|available|shelf|inventory)\b",
        query,
        re.I,
    ):
        return ""
    rows = resolve_reply_books(query, citations=citations, books=books, meta=meta)
    if not rows:
        title = str((meta or {}).get("title") or "").strip()
        if title:
            return (
                f"\n\nNot verified in the catalog. [Search the OPAC]({catalog_search_url(title)})."
            )
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
