"""Shared helpers for chat route handlers."""

from __future__ import annotations

from archipelago.inference.reply_inventory import attach_inventory


def with_holdings(query, text, citations=None, books=None, meta=None):
    """Append inventory table + exact-page links to a finished reply."""
    return attach_inventory(
        query,
        text,
        citations=citations,
        books=books,
        meta=meta,
    )
