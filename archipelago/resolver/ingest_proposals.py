"""New-source detection: tell the librarian about books the graph does not hold.

When a provider sweep (Pearson eLibrary, Hugging Face) surfaces a title that is
in the institution's entitlement but absent from the graph, ingestion should
*ask* rather than silently pulling down a textbook. Two reasons:

1. Ingesting a commercial PDF is a licensing decision, not a technical one.
   The existing worker already distinguishes ``toc_only`` from ``full`` for
   exactly this reason.
2. The librarian knows whether the physical copy has been received.

So this module produces a **proposal queue**: one entry per unseen title, with
everything needed to decide, and a stable fingerprint so re-running the sweep
does not re-ask about the same book.

Proposals are advisory. Nothing here downloads, ingests, or mutates the graph.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import logging
from pathlib import Path
import threading
from typing import Any, Literal

from archipelago.resolver.source_lifecycle import _base_dir

logger = logging.getLogger(__name__)

QUEUE_RELPATH = Path("data") / "ingest_proposals.json"
QUEUE_VERSION = 1

Decision = Literal["pending", "approved", "declined", "ingested"]

# Default licence posture for a proposal. ``toc_only`` means structure and
# front matter only — safe for a commercial title the library has access to
# but whose full text we should not copy. A librarian can approve a full ingest
# explicitly.
DEFAULT_LICENSE_MODE = "toc_only"

_lock = threading.Lock()


def _now() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(UTC).isoformat()


@dataclass
class IngestProposal:
    """One book/paper the institution may hold but the graph does not."""

    # Derived from (provider, title, isbn) in __post_init__ when left blank.
    fingerprint: str = ""
    title: str = ""
    provider: str = ""
    isbn: str = ""
    external_id: str = ""
    author: str = ""
    url: str = ""
    license_mode: str = DEFAULT_LICENSE_MODE
    decision: Decision = "pending"
    reason: str = ""
    first_seen: str = ""
    decided_at: str = ""
    # Free-form provenance so a decision can be justified later.
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.fingerprint:
            self.fingerprint = fingerprint_for(self.provider, self.title, self.isbn)
        if not self.first_seen:
            self.first_seen = _now()

    @property
    def actionable(self) -> bool:
        """Only a pending proposal needs a librarian decision."""
        return self.decision == "pending"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IngestProposal:
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in raw.items() if k in known})


def fingerprint_for(provider: str, title: str, isbn: str = "") -> str:
    """Stable id for a title, so the same book is never asked about twice.

    ISBN when available (authoritative), otherwise provider + normalised title.
    """
    if isbn:
        return f"isbn:{isbn.strip().lower()}"
    norm = " ".join((title or "").lower().split())
    digest = hashlib.sha256(f"{provider.lower()}|{norm}".encode()).hexdigest()[:16]
    return f"title:{digest}"


def queue_path(base_dir: Path | str | None = None) -> Path:
    """Absolute path of the proposal queue file."""
    root = Path(base_dir if base_dir is not None else _base_dir())
    return root / QUEUE_RELPATH


def load_queue(base_dir: Path | str | None = None) -> dict[str, IngestProposal]:
    """Read the queue. Missing or corrupt means "nothing proposed yet"."""
    path = queue_path(base_dir)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable proposal queue at %s: %s", path, exc)
        return {}
    entries = raw.get("proposals", {}) if isinstance(raw, dict) else {}
    if not isinstance(entries, dict):
        return {}
    out: dict[str, IngestProposal] = {}
    for key, payload in entries.items():
        if isinstance(payload, dict):
            try:
                out[str(key)] = IngestProposal.from_dict(payload)
            except TypeError as exc:
                logger.warning("Skipping malformed proposal %r: %s", key, exc)
    return out


def save_queue(queue: dict[str, IngestProposal], base_dir: Path | str | None = None) -> Path:
    """Write the queue atomically."""
    path = queue_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": QUEUE_VERSION,
        "updated_at": _now(),
        "proposals": {k: v.to_dict() for k, v in sorted(queue.items())},
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def discover_from_provider_bookshelf(
    bookshelf_path: Path | str,
    held_ids: Iterable[str],
    provider: str = "pearson",
    base_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Propose books from a Pearson eLibrary bookshelf export.

    The bookshelf is a catalogue of what the institution is *entitled to*, so
    every title in it that the graph lacks is a legitimate question for the
    librarian. Entries without a title are skipped.
    """
    path = Path(bookshelf_path)
    if not path.is_file():
        logger.info("Bookshelf export not found at %s; nothing to propose", path)
        return {"proposed": [], "already_held": 0, "skipped": 0, "pending_total": 0}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable bookshelf export at %s: %s", path, exc)
        return {"proposed": [], "already_held": 0, "skipped": 0, "pending_total": 0}

    books = payload.get("books", []) if isinstance(payload, dict) else []
    discovered = []
    for book in books:
        if not isinstance(book, dict):
            continue
        discovered.append(
            {
                "title": book.get("title", ""),
                "isbn": book.get("isbn", ""),
                "author": book.get("author", ""),
                "url": book.get("reader_base_url") or book.get("cover_url") or "",
                "external_id": book.get("id", ""),
                "page_count": book.get("page_count", 0),
                "provider": provider,
                "reason": "In institutional eLibrary entitlement, absent from the graph",
            }
        )
    return detect_new_sources(discovered, held_ids, base_dir=base_dir)


def detect_new_sources(
    discovered: Iterable[dict[str, Any]],
    held_ids: Iterable[str],
    base_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Propose every discovered title the library does not already hold.

    Args:
        discovered: Provider payloads with at least ``title``; ``provider``,
            ``isbn``, ``author``, ``url`` are used when present.
        held_ids: Identifiers the graph/library already has — ISBNs, titles, or
            the graph's own ``doc_id``s. Compared against the fingerprint inputs.
        base_dir: Queue root override.

    Returns:
        ``{"proposed": [...], "already_held": n, "skipped": n}``. Existing
        proposals keep their recorded decision, so a declined book is not
        re-asked on every sweep.
    """
    with _lock:
        queue = load_queue(base_dir)
        held = {str(item).strip().lower() for item in held_ids if str(item).strip()}

        proposed: list[dict[str, Any]] = []
        already_held = 0
        skipped = 0

        for item in discovered:
            if not isinstance(item, dict):
                skipped += 1
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                skipped += 1
                continue

            isbn = str(item.get("isbn") or "").strip()
            provider = str(item.get("provider") or "").strip()
            key = fingerprint_for(provider, title, isbn)

            # Already indexed under any of its identifiers?
            if isbn and isbn.lower() in held:
                already_held += 1
                continue
            if title.lower() in held:
                already_held += 1
                continue

            existing = queue.get(key)
            if existing is not None:
                # Refresh mutable metadata but keep the recorded decision.
                existing.url = str(item.get("url") or existing.url)
                existing.metadata = {
                    **existing.metadata,
                    **{k: v for k, v in item.items() if k not in ("title",)},
                }
                continue

            proposal = IngestProposal(
                fingerprint=key,
                title=title,
                provider=provider,
                isbn=isbn,
                external_id=str(item.get("id") or item.get("external_id") or ""),
                author=str(item.get("author") or ""),
                url=str(item.get("url") or ""),
                reason=str(item.get("reason") or "Detected by provider sweep"),
                metadata={k: v for k, v in item.items() if k != "title"},
            )
            queue[key] = proposal
            proposed.append(proposal.to_dict())

        if proposed:
            save_queue(queue, base_dir)
            logger.info("Proposed %d new source(s) for librarian review", len(proposed))
        return {
            "proposed": proposed,
            "already_held": already_held,
            "skipped": skipped,
            "pending_total": sum(1 for p in queue.values() if p.actionable),
        }


def pending_proposals(base_dir: Path | str | None = None) -> list[IngestProposal]:
    """Proposals still awaiting a decision."""
    return [p for p in load_queue(base_dir).values() if p.actionable]


def decide(
    fingerprint: str,
    decision: Decision,
    note: str = "",
    license_mode: str | None = None,
    base_dir: Path | str | None = None,
) -> IngestProposal:
    """Record a librarian's decision on one proposal.

    Raises:
        KeyError: no such proposal.
        ValueError: unknown decision value.
    """
    if decision not in ("pending", "approved", "declined", "ingested"):
        raise ValueError(f"unknown decision: {decision!r}")
    with _lock:
        queue = load_queue(base_dir)
        proposal = queue.get(fingerprint)
        if proposal is None:
            raise KeyError(f"no proposal with fingerprint {fingerprint!r}")
        proposal.decision = decision
        proposal.decided_at = _now()
        if note:
            proposal.reason = note
        if license_mode:
            proposal.license_mode = license_mode
        save_queue(queue, base_dir)
        return proposal


def approved_for_ingest(base_dir: Path | str | None = None) -> list[IngestProposal]:
    """Approved proposals the ingestion worker should act on."""
    return [p for p in load_queue(base_dir).values() if p.decision == "approved"]


__all__ = [
    "DEFAULT_LICENSE_MODE",
    "IngestProposal",
    "approved_for_ingest",
    "decide",
    "detect_new_sources",
    "discover_from_provider_bookshelf",
    "fingerprint_for",
    "load_queue",
    "pending_proposals",
    "queue_path",
    "save_queue",
]
