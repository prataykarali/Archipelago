"""Shared helpers for chat route handlers."""

from __future__ import annotations

from typing import Any

from archipelago.inference.reply_inventory import attach_inventory


def with_holdings(
    query: str,
    text: str,
    citations: list[dict[str, Any]] | None = None,
    books: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Append inventory table + exact-page links to a finished reply."""
    return attach_inventory(
        query,
        text,
        citations=citations,
        books=books,
        meta=meta,
    )
