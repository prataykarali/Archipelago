"""Source lifecycle: track whether a catalogued source is still available.

A graph that keeps answering from a withdrawn document is worse than one that
says nothing: it states as fact something the institution no longer holds. When
Pearson or Hugging Face removes a title (subscription lapse, repo deletion,
revoked licence), the library must **forget** it — stop citing it, and answer
that it is not in records anymore — while keeping the provenance trail so the
history of *why* it disappeared is auditable.

Three states, deliberately explicit:

``verified``
    The source was reachable at ``last_verified``. Citable.
``withdrawn``
    The source is gone upstream. **Not** citable. Answers must say so rather
    than cite it. ``tombstone`` records what we knew when it was withdrawn.
``unknown``
    Never checked, or the check itself failed (network, credentials). Stays
    citable — an unreachable check is not evidence of withdrawal.

The distinction between ``withdrawn`` and ``unknown`` is the whole point: only
an authoritative negative ("404 Gone", "no longer in the repo listing") retires
a source. A timeout, a DNS failure, or a missing credential must not silently
delete a book from the record.

Storage is a single JSON ledger under ``data/`` so the state survives restarts
and can be diffed/committed like any other artifact.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Literal

from okf.config import BASE_DIR

logger = logging.getLogger(__name__)

Status = Literal["verified", "withdrawn", "unknown"]

LEDGER_RELPATH = Path("data") / "source_lifecycle.json"
LEDGER_VERSION = 1

# Root override for both this ledger and the proposal queue. The hosted
# inference service may mount institutional state away from the repo root (the
# library appliance keeps its data with the corpus, not with the code), and
# tests need an isolated root.
STATE_DIR_ENV = "ARCHIPELAGO_STATE_DIR"


def _base_dir() -> Path:
    """Resolve the state root: env override when set, otherwise the repo root."""
    override = os.environ.get(STATE_DIR_ENV, "").strip()
    return Path(override) if override else Path(BASE_DIR)

# The reply shown in place of an answer we can no longer ground. Wording is
# deliberately factual: the source left the record, it is not "lost", and we do
# not speculate about why.
NOT_IN_RECORDS = (
    "This title is no longer in the library's records. "
    "It was withdrawn from {source}, so it cannot be cited or opened from here."
)
NOT_IN_RECORDS_NO_SOURCE = (
    "This title is no longer in the library's records and cannot be cited or opened."
)

# Provider verdicts that DO retire a source. Anything not listed here is
# treated as inconclusive and leaves the source citable.
WITHDRAWAL_VERDICTS = frozenset({"gone", "withdrawn", "not_found", "deleted", "404"})
# Verdict codes that confirm the source is present and reachable.
VERIFIED_VERDICTS = frozenset({"verified", "ok", "available", "found", "200"})
# Verdict codes that mean "the check failed", not "the source is gone".
INCONCLUSIVE_VERDICTS = frozenset(
    {"error", "timeout", "network_error", "auth_required", "forbidden", "unknown", ""}
)

_lock = threading.Lock()


def _now() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(UTC).isoformat()


@dataclass
class SourceState:
    """Availability of one catalogued source."""

    source_id: str
    status: Status = "unknown"
    provider: str = ""
    last_verified: str = ""
    last_checked: str = ""
    # Verbatim upstream signal, kept for the audit trail (e.g. "HTTP 410 Gone").
    verdict: str = ""
    message: str = ""
    # What we knew while the source was still live: title, isbn, doc_id.
    # Retained so the librarian can see what was withdrawn, and so re-acquiring
    # the title can restore it without a re-ingest.
    tombstone: dict[str, Any] = field(default_factory=dict)

    @property
    def citable(self) -> bool:
        """Only ``verified``/``unknown`` sources may be cited."""
        return self.status != "withdrawn"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SourceState:
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in raw.items() if k in known})


def ledger_path(base_dir: Path | str | None = None) -> Path:
    """Absolute path of the lifecycle ledger."""
    root = Path(base_dir if base_dir is not None else _base_dir())
    return root / LEDGER_RELPATH


def load_ledger(base_dir: Path | str | None = None) -> dict[str, SourceState]:
    """Read the ledger. A missing or corrupt file is an empty library."""
    path = ledger_path(base_dir)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable source ledger at %s: %s", path, exc)
        return {}
    entries = raw.get("sources", {}) if isinstance(raw, dict) else {}
    if not isinstance(entries, dict):
        return {}
    states: dict[str, SourceState] = {}
    for source_id, payload in entries.items():
        if isinstance(payload, dict):
            try:
                states[str(source_id)] = SourceState.from_dict(payload)
            except TypeError as exc:
                logger.warning("Skipping malformed ledger row %r: %s", source_id, exc)
    return states


def save_ledger(states: dict[str, SourceState], base_dir: Path | str | None = None) -> Path:
    """Write the ledger atomically."""
    path = ledger_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": LEDGER_VERSION,
        "updated_at": _now(),
        "sources": {sid: state.to_dict() for sid, state in sorted(states.items())},
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def classify_verdict(verdict: str | None) -> Status:
    """Map a provider verdict code onto a lifecycle status.

    Only authoritative negatives retire a source. Everything else — including
    an authentication failure — stays ``unknown`` so a transient problem never
    removes a book from the record.
    """
    code = (verdict or "").strip().lower()
    if code in WITHDRAWAL_VERDICTS:
        return "withdrawn"
    if code in VERIFIED_VERDICTS:
        return "verified"
    return "unknown"


def record_check(
    source_id: str,
    verdict: str | None,
    provider: str = "",
    message: str = "",
    metadata: dict[str, Any] | None = None,
    states: dict[str, SourceState] | None = None,
    base_dir: Path | str | None = None,
) -> SourceState:
    """Apply one provider check to the ledger and return the new state.

    Args:
        source_id: Stable identifier (ISBN, Pearson book id, HF path…).
        verdict: Provider verdict code. Only an authoritative negative
            (``gone``/``not_found``/``404``) marks the source withdrawn.
        provider: ``"pearson"``, ``"huggingface"``, …
        message: Human-readable upstream signal, stored verbatim.
        metadata: Title/isbn/doc_id, snapshotted into the tombstone.
        states: Existing states to update in place; loaded from disk when None.
        base_dir: Ledger root override.
    """
    if not source_id:
        raise ValueError("source_id is required")

    with _lock:
        current = states if states is not None else load_ledger(base_dir)
        state = current.get(source_id) or SourceState(source_id=source_id, provider=provider)

        new_status = classify_verdict(verdict)
        state.provider = provider or state.provider
        state.verdict = (verdict or "").strip()
        state.message = message or ""
        state.last_checked = _now()

        if new_status == "verified":
            state.status = "verified"
            state.last_verified = state.last_checked
            state.tombstone = {}
        elif new_status == "withdrawn":
            if state.status != "withdrawn":
                # Snapshot what we knew while the source was live, so the
                # librarian can see exactly what was retired.
                state.tombstone = {
                    "title": (metadata or {}).get("title", ""),
                    "isbn": (metadata or {}).get("isbn", ""),
                    "doc_id": (metadata or {}).get("doc_id", ""),
                    "withdrawn_at": state.last_checked,
                    "last_verified": state.last_verified,
                    "reason": message or state.verdict,
                }
            state.status = "withdrawn"
        else:
            # Inconclusive: keep whatever we already knew. A failed check must
            # not promote a withdrawn source back to citable, nor retire a
            # healthy one.
            if state.status not in ("verified", "withdrawn"):
                state.status = "unknown"

        current[source_id] = state
        if states is None:
            save_ledger(current, base_dir)
    return state


def get_state(source_id: str, states: dict[str, SourceState] | None = None) -> SourceState:
    """Current state for one source, or an ``unknown`` placeholder."""
    current = states if states is not None else load_ledger()
    return current.get(source_id) or SourceState(source_id=source_id)


def withdrawn_ids(states: dict[str, SourceState] | None = None) -> set[str]:
    """Ids of every retired source."""
    current = states if states is not None else load_ledger()
    return {sid for sid, state in current.items() if state.status == "withdrawn"}


def filter_citable(
    items: Iterable[dict[str, Any]],
    id_key: str,
    states: dict[str, SourceState] | None = None,
) -> list[dict[str, Any]]:
    """Drop withdrawn sources from a result list.

    Used on every retrieval path so a retired book cannot reach a citation.
    """
    current = states if states is not None else load_ledger()
    retired = {sid for sid, state in current.items() if not state.citable}
    return [item for item in items if str(item.get(id_key, "")) not in retired]


def withdrawal_notice(state: SourceState) -> str:
    """Reply copy for a withdrawn source, naming its provider when known."""
    if state.provider:
        return NOT_IN_RECORDS.format(source=state.provider)
    return NOT_IN_RECORDS_NO_SOURCE


def reconcile(
    live_ids: Iterable[str],
    checked: dict[str, tuple[str, str, str]],
    base_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Reconcile provider check results against the catalogue.

    Args:
        live_ids: Ids the institution believes it holds.
        checked: ``{source_id: (verdict, provider, message)}`` from a provider
            sweep. Only ids present here are re-evaluated; an id missing from
            ``checked`` keeps its current state (absence of a check is not
            evidence of withdrawal).
        base_dir: Ledger root override.

    Returns:
        Counts of newly withdrawn, still-verified, and unchanged sources.
    """
    states = load_ledger(base_dir)
    live = set(live_ids)
    newly_withdrawn: list[str] = []
    verified: list[str] = []

    for source_id, (verdict, provider, message) in checked.items():
        before = states.get(source_id)
        state = record_check(
            source_id,
            verdict,
            provider=provider,
            message=message,
            metadata={"title": source_id},
            states=states,
            base_dir=base_dir,
        )
        if state.status == "withdrawn" and (before is None or before.status != "withdrawn"):
            newly_withdrawn.append(source_id)
        elif state.status == "verified":
            verified.append(source_id)

    save_ledger(states, base_dir)
    return {
        "live": len(live),
        "checked": len(checked),
        "withdrawn_total": len(withdrawn_ids(states)),
        "newly_withdrawn": newly_withdrawn,
        "verified": verified,
    }


__all__ = [
    "NOT_IN_RECORDS",
    "NOT_IN_RECORDS_NO_SOURCE",
    "SourceState",
    "classify_verdict",
    "filter_citable",
    "get_state",
    "ledger_path",
    "load_ledger",
    "reconcile",
    "record_check",
    "save_ledger",
    "withdrawal_notice",
    "withdrawn_ids",
]
