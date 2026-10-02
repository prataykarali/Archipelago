"""Withdrawal-aware source selection.

Kept separate from :mod:`engine.graph` so the lifecycle rule has one home: a
source document that the ledger marks ``withdrawn`` is never chosen for a
citation, and — importantly — a concept is not dropped from the graph merely
because its *best* source disappeared. If another live document mentions the
same concept, that passage is cited instead.

That distinction is the point of "the graph forgets it": the institution stops
citing and offering a withdrawn title, without destroying knowledge that other
sources independently support.
"""
from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

import sibling_path  # noqa: F401 - repo root on sys.path for a standalone deploy

logger = logging.getLogger(__name__)

# Used when the provider is unknown; kept in sync with the lifecycle module's
# provider-neutral wording.
NEUTRAL_NOTICE = (
    "This title is no longer in the library's records and cannot be cited or opened."
)


def withdrawn_documents(states: dict[str, Any] | None = None) -> set[str]:
    """Set of ``doc_id`` values whose documents are retired.

    Falls back to an empty set when the lifecycle ledger cannot be loaded, so a
    missing or unreadable ledger degrades to the previous behaviour (sources
    stay citable) instead of silently emptying the library.
    """
    try:
        from archipelago.resolver.source_lifecycle import load_ledger
    except ImportError:
        logger.debug("source_lifecycle unavailable; withdrawal checks disabled")
        return set()

    states = states if states is not None else load_ledger()
    docs: set[str] = set()
    for state in states.values():
        if state.status == "withdrawn":
            tombstone = state.tombstone or {}
            doc_id = str(tombstone.get("doc_id") or "").strip()
            if doc_id:
                docs.add(doc_id)
            # Fall back to the source id itself: some catalogues key documents
            # by ISBN or Pearson book id rather than a pdfs/ path.
            if state.source_id:
                docs.add(state.source_id)
    return docs


def is_citable_source(source: dict[str, Any] | None, retired: set[str]) -> bool:
    """True when a source passage may be cited."""
    if not source:
        return False
    doc_id = str(source.get("doc_id") or "").strip()
    if not doc_id:
        # No provenance at all: not traceable, so not citable.
        return False
    return doc_id not in retired


def best_live_source(
    sources: Iterable[dict[str, Any]],
    score_fn,
    retired: set[str] | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    """Highest-scoring source that is still citable.

    Returns:
        ``(source, all_withdrawn)``. ``source`` is ``None`` when nothing is
        citable; ``all_withdrawn`` is True only when every candidate was
        retired, which is what lets the caller say "not in records anymore"
        instead of quietly falling back to an unrelated passage.
    """
    retired = retired if retired is not None else withdrawn_documents()
    candidates = [s for s in sources if isinstance(s, dict)]
    if not candidates:
        return None, False

    best = None
    best_score = -1
    for source in candidates:
        if not is_citable_source(source, retired):
            continue
        score = score_fn(source)
        if score > best_score:
            best, best_score = source, score
    return best, best is None


def partition_sources(
    sources: Iterable[dict[str, Any]], retired: set[str] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split sources into ``(citable, withdrawn)``."""
    retired = retired if retired is not None else withdrawn_documents()
    citable: list[dict[str, Any]] = []
    gone: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        (citable if is_citable_source(source, retired) else gone).append(source)
    return citable, gone


def withdrawal_notice_for_doc(doc_id: str) -> str:
    """Reply copy naming the provider that retired ``doc_id``, when known.

    Falls back to the provider-neutral wording if the document is not in the
    ledger (e.g. the caller already knows it has no citable source).
    """
    try:
        from archipelago.resolver.source_lifecycle import load_ledger, withdrawal_notice
    except ImportError:
        logger.debug("source_lifecycle unavailable; using neutral notice")
        return NEUTRAL_NOTICE

    target = (doc_id or "").strip()
    for state in load_ledger().values():
        if state.status != "withdrawn":
            continue
        tombstone = state.tombstone or {}
        if target and target in {
            str(tombstone.get("doc_id") or "").strip(),
            state.source_id,
        }:
            return withdrawal_notice(state)
    return NEUTRAL_NOTICE


__all__ = [
    "NEUTRAL_NOTICE",
    "best_live_source",
    "is_citable_source",
    "partition_sources",
    "withdrawal_notice_for_doc",
    "withdrawn_documents",
]
