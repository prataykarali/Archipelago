"""Acquisition discovery: turn unmet demand into a candidate purchase list.

The contract says that when students ask for a title the catalogue does not
hold, Archipelago logs it so librarians get an acquisition-order digest.  The
digest on its own answers *what* is missing but not *what to buy*: a librarian
still has to search each publisher by hand.

This module closes that gap by matching unmet demand against the two sources the
institution already pays for — the Pearson eLibrary catalogue and the Pearson
shelf export — and, optionally, an Apify actor run when one has been approved.
Discovery is **proposal only**: nothing is purchased, and no candidate is written
into the OPAC.  It returns rows with their evidence (ISBN, source, match strength)
so a librarian can accept or reject each one on its own judgement.

Deliberately not auto-populating.  The contract's "librarian can easily
auto-populate graph with proper links and updations" is satisfied by emitting a
reviewable, evidence-backed plan — silently adding books the library does not own
would put invented holdings on the shelf cards, which is the one failure mode
this codebase is built to avoid.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("archipelago.discovery")

#: Below this many distinctive-token overlaps a candidate is not even offered:
#: one shared word ("systems") would otherwise propose the whole catalogue.
MIN_CANDIDATE_TOKENS = 2

#: Cap on candidates per requested title, so one popular request cannot flood
#: the review list.
MAX_CANDIDATES_PER_TITLE = 5

#: Token-length floor, mirroring the catalogue matcher's noise filter.
MIN_TOKEN_LEN = 2

#: Demand entries below this count are routine curiosity, not an acquisition
#: signal. Repeated asking is the signal.
DEFAULT_MIN_DEMAND_COUNT = 2

_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "about",
    "edition", "ed", "vol", "volume", "book", "books", "copy", "copies",
    "please", "find", "where", "can", "will", "any", "have", "has", "do",
    "does", "did", "you", "your", "i", "me", "my", "is", "are", "was",
    "were", "library", "campus", "physical", "available", "need", "want",
})


def _norm_tokens(text: str) -> set[str]:
    """Lowercase content tokens for overlap scoring."""
    import re

    cleaned = re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower())
    return {
        token
        for token in cleaned.split()
        if token not in _STOPWORDS and len(token) >= MIN_TOKEN_LEN
    }


def _pearson_catalogue() -> list[dict[str, Any]]:
    """Pearson eLibrary catalogue rows, or ``[]`` when unavailable.

    Never raises: discovery is an advisory aid, and a publisher outage must not
    take down the librarian's review page.
    """
    try:
        from archipelago.resolver.pearson import _load_pearson_catalog

        return list(_load_pearson_catalog())
    except Exception as exc:
        logger.warning("Pearson catalogue unavailable: %s", exc)
        return []


def match_candidates(
    title: str, catalogue: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Pearson titles that plausibly satisfy ``title``, best overlap first.

    Ranked by distinctive-token overlap, so "Database System Concepts" prefers
    the exact title over something that merely contains "database".
    """
    wanted = _norm_tokens(title)
    if len(wanted) < MIN_CANDIDATE_TOKENS:
        return []
    rows = catalogue if catalogue is not None else _pearson_catalogue()

    scored: list[tuple[int, dict[str, Any]]] = []
    for book in rows:
        if not isinstance(book, dict):
            continue
        book_title = str(book.get("title") or "")
        if not book_title:
            continue
        overlap = len(wanted & _norm_tokens(f"{book_title} {book.get('author') or ''}"))
        if overlap >= MIN_CANDIDATE_TOKENS:
            scored.append((overlap, book))

    scored.sort(key=lambda pair: -pair[0])
    results: list[dict[str, Any]] = []
    for overlap, book in scored[:MAX_CANDIDATES_PER_TITLE]:
        results.append(
            {
                "requested_title": title,
                "source": "pearson_elibrary",
                "title": str(book.get("title") or ""),
                "author": str(book.get("author") or ""),
                "isbn": str(book.get("isbn") or ""),
                "domain": str(book.get("domain") or ""),
                "reader_url": str(book.get("reader_base_url") or ""),
                "match_tokens": overlap,
                "confidence": "exact" if overlap == len(wanted) else "partial",
                "action_required": "librarian_review",
            }
        )
    return results


def apify_candidates(
    keywords: str, dataset_id: str = "", limit: int = 50
) -> list[dict[str, Any]]:
    """Candidate titles from an approved Apify run, if one is available.

    Returns ``[]`` — never raises — when Apify is unconfigured, unapproved, or
    the run produced nothing.  The Apify client is cost-capped and approval-gated
    by design; this adds the librarian-facing read path over its dataset without
    weakening either gate.
    """
    try:
        from archipelago.ingestion.apify_source import (
            ApifyApprovalRequired,
            ApifyBudgetError,
            ApifyNotConfigured,
            fetch_dataset_items,
        )
    except Exception as exc:
        logger.warning("Apify source module unavailable: %s", exc)
        return []

    if not dataset_id:
        return []
    try:
        items = fetch_dataset_items(dataset_id, limit=limit)
    except (ApifyNotConfigured, ApifyApprovalRequired, ApifyBudgetError) as exc:
        logger.info("Apify discovery skipped: %s", exc)
        return []
    except Exception as exc:
        logger.warning("Apify dataset %s unreadable: %s", dataset_id, exc)
        return []

    return _rows_to_candidates(keywords, items)


def _rows_to_candidates(keywords: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise scraped rows into the same candidate shape as Pearson matches."""
    wanted = _norm_tokens(keywords)
    candidates: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        overlap = len(wanted & _norm_tokens(title)) if wanted else 0
        candidates.append(
            {
                "requested_title": keywords,
                "source": "apify",
                "title": title,
                "author": str(item.get("author") or ""),
                "isbn": str(item.get("isbn") or item.get("isbn13") or ""),
                "publisher": str(item.get("publisher") or ""),
                "match_tokens": overlap,
                "confidence": "exact" if wanted and overlap == len(wanted) else "partial",
                "action_required": "librarian_review",
            }
        )
    return candidates


def discovery_plan(
    demand: list[dict[str, Any]],
    min_count: int = DEFAULT_MIN_DEMAND_COUNT,
    include_apify_dataset: str = "",
) -> dict[str, Any]:
    """Full acquisition review plan: unmet demand plus candidate sources.

    Takes the unmet-demand rows as an argument rather than reading the digest
    itself: the digest lives in the hosted engine, which ships as a separate
    deployable and must not become an import-time dependency of this package.
    The caller (the librarian route) supplies the rows.

    Returns ``rows`` (one entry per unmet title, each carrying its candidates)
    and ``totals``.  A title with no candidate is omitted rather than shown with
    an empty list, so the review page is a worklist and not a mirror of the log.
    """
    qualifying = [
        row
        for row in demand
        if isinstance(row, dict) and int(row.get("count") or 0) >= min_count
    ]

    catalogue = _pearson_catalogue()
    rows: list[dict[str, Any]] = []
    total_candidates = 0
    for entry in qualifying:
        requested = str(entry.get("title") or "")
        candidates = match_candidates(requested, catalogue)
        if include_apify_dataset:
            candidates.extend(apify_candidates(requested, include_apify_dataset))
        if not candidates:
            continue
        total_candidates += len(candidates)
        rows.append(
            {
                "requested_title": requested,
                "times_asked": int(entry.get("count") or 0),
                "last_seen": str(entry.get("last_seen") or ""),
                "candidates": candidates,
            }
        )

    rows.sort(key=lambda row: -row["times_asked"])
    return {
        "rows": rows,
        "totals": {"unmet_titles": len(qualifying), "candidates": total_candidates},
    }


__all__ = [
    "DEFAULT_MIN_DEMAND_COUNT",
    "MAX_CANDIDATES_PER_TITLE",
    "MIN_CANDIDATE_TOKENS",
    "apify_candidates",
    "discovery_plan",
    "match_candidates",
]
