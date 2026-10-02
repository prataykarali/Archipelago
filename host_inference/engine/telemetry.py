"""Demand telemetry: what the library does not hold, and how often it is asked for.

When a student asks for a title the catalogue does not index, that is an
acquisition signal. Accumulating them produces an acquisition-order digest the
librarian can act on, instead of a stream of identical "not indexed" replies
that individually look like nothing.

Records are keyed on the normalised title, so the same unanswered request counts
once however often it is asked — a frequency signal, not a hit counter.

Never raises and never blocks the chat path: telemetry must not be able to fail
a student's question.
"""
from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import re
import threading
from typing import Any

logger = logging.getLogger(__name__)

#: Shared with the source-lifecycle ledger so institutional state has one root.
STATE_DIR_ENV = "ARCHIPELAGO_STATE_DIR"

DIGEST_RELPATH = Path("data") / "demand_digest.json"
DIGEST_VERSION = 1
# Cap the digest so a long-lived deployment cannot grow it without bound.
MAX_TRACKED_TITLES = 5000

_lock = threading.Lock()
_cache: dict[str, Any] | None = None


def _now() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(UTC).isoformat()


def _norm(title: str) -> str:
    """Normalise a title into a stable demand key."""
    return " ".join(re.sub(r"[^a-z0-9\s]+", " ", (title or "").lower()).split())


def digest_path(base_dir: Path | str | None = None) -> Path:
    """Absolute path of the demand digest.

    Honours the same state-root override as the lifecycle ledger, so a hosted
    deployment can keep institutional state on a mounted volume. Without an
    override the digest lands beside the engine package rather than in the
    process CWD, which is not writable on AntDeploy.
    """
    if base_dir is not None:
        return Path(base_dir) / DIGEST_RELPATH
    override = os.environ.get(STATE_DIR_ENV, "").strip()
    if override:
        return Path(override) / DIGEST_RELPATH
    return Path(__file__).resolve().parents[2] / DIGEST_RELPATH


def load_digest(base_dir: Path | str | None = None) -> dict[str, Any]:
    """Read the digest. Missing or corrupt means no demand recorded yet."""
    path = digest_path(base_dir)
    if not path.is_file():
        return {"version": DIGEST_VERSION, "titles": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable demand digest %s: %s", path, exc)
        return {"version": DIGEST_VERSION, "titles": {}}
    titles = raw.get("titles") if isinstance(raw, dict) else None
    return {"version": DIGEST_VERSION, "titles": titles if isinstance(titles, dict) else {}}


def _save(digest: dict[str, Any], base_dir: Path | str | None = None) -> None:
    path = digest_path(base_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(digest, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("Could not persist demand digest %s: %s", path, exc)


def log_demand(
    title: str,
    subject: str = "",
    query: str = "",
    base_dir: Path | str | None = None,
) -> bool:
    """Record one unmet request. Returns True when it was persisted.

    Idempotent per normalised title: repeated asks increment ``count`` and
    refresh ``last_seen`` but do not create duplicate rows.
    """
    key = _norm(title)
    if not key:
        return False
    try:
        with _lock:
            digest = load_digest(base_dir)
            titles = digest["titles"]
            now = _now()
            entry = titles.get(key)
            if isinstance(entry, dict):
                entry["count"] = int(entry.get("count") or 0) + 1
                entry["last_seen"] = now
                if query:
                    entry.setdefault("examples", [])
                    if len(entry["examples"]) < 3 and query not in entry["examples"]:
                        entry["examples"].append(query)
            else:
                if len(titles) >= MAX_TRACKED_TITLES:
                    return False
                titles[key] = {
                    "title": title.strip(),
                    "subject": subject.strip(),
                    "count": 1,
                    "first_seen": now,
                    "last_seen": now,
                    "examples": [query] if query else [],
                }
            digest["updated_at"] = now
            _save(digest, base_dir)
        return True
    except Exception as exc:
        logger.warning("Demand logging failed for %r: %s", title, exc)
        return False


def unmet_titles(
    min_count: int = 1, base_dir: Path | str | None = None
) -> list[dict[str, Any]]:
    """Unmet requests, most-requested first — the acquisition-order digest."""
    titles = load_digest(base_dir)["titles"]
    rows = [row for row in titles.values() if isinstance(row, dict)]
    rows = [row for row in rows if int(row.get("count") or 0) >= min_count]
    rows.sort(key=lambda row: (-int(row.get("count") or 0), str(row.get("last_seen") or "")))
    return rows


def render_digest(min_count: int = 2, base_dir: Path | str | None = None) -> str:
    """Markdown digest of the most-requested-but-unheld titles."""
    rows = unmet_titles(min_count, base_dir)
    if not rows:
        return "No unmet demand recorded yet."

    lines = [
        "**Acquisition demand digest** — titles asked for that the catalogue does not hold.",
        "",
        "| Requested | Times asked | First seen |",
        "|---|---:|---|",
    ]
    for row in rows[:50]:
        lines.append(
            f"| {row.get('title', '')} | {int(row.get('count') or 0)} | "
            f"{str(row.get('first_seen', ''))[:10]} |"
        )
    if len(rows) > 50:
        lines.append(f"| … and {len(rows) - 50} more | | |")
    return "\n".join(lines)


def clear(base_dir: Path | str | None = None) -> bool:
    """Empty the digest. Returns True when a digest was removed."""
    path = digest_path(base_dir)
    global _cache
    _cache = None
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError as exc:
        logger.warning("Could not clear demand digest %s: %s", path, exc)
    return False


__all__ = [
    "DIGEST_RELPATH",
    "clear",
    "digest_path",
    "load_digest",
    "log_demand",
    "render_digest",
    "unmet_titles",
]
