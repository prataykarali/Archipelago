"""Owner-scoped SQLite snapshots and opt-in monitoring definitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
from typing import TYPE_CHECKING, Any
import uuid

if TYPE_CHECKING:
    from .postgres_storage import PostgresResearchStore

DEFAULT_PATH = Path("data/research_intelligence.sqlite3")
MAX_LIST_ROWS = 30
DEFAULT_CADENCE_HOURS = 24
MIN_CADENCE_HOURS = 1
MAX_CADENCE_HOURS = 720
RETRY_BASE_MINUTES = 5
RETRY_MAX_EXPONENT = 4
RETRY_MAX_MINUTES = 60


def validate_cadence(value: object) -> int:
    """Accept only bounded whole-hour refresh intervals."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not MIN_CADENCE_HOURS <= value <= MAX_CADENCE_HOURS
    ):
        raise ValueError("invalid_cadence_hours")
    return value


class ResearchStore:
    """Keep scholarly runs outside the academic graph and staging ledger."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.getenv("ARCHIPELAGO_RESEARCH_DB", DEFAULT_PATH))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, owner TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS monitors (id TEXT PRIMARY KEY, owner TEXT NOT NULL, options TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0, last_run TEXT, last_error TEXT, lease_until TEXT)"
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(monitors)")}
            if "cadence_hours" not in columns:
                db.execute(
                    f"ALTER TABLE monitors ADD COLUMN cadence_hours INTEGER NOT NULL DEFAULT {DEFAULT_CADENCE_HOURS}"
                )
            if "next_run_at" not in columns:
                db.execute("ALTER TABLE monitors ADD COLUMN next_run_at TEXT")
            if "consecutive_failures" not in columns:
                db.execute(
                    "ALTER TABLE monitors ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0"
                )
            if "last_success_at" not in columns:
                db.execute("ALTER TABLE monitors ADD COLUMN last_success_at TEXT")
            db.execute(
                "CREATE TABLE IF NOT EXISTS monitor_history "
                "(id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, owner TEXT NOT NULL, "
                "run_id TEXT, status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS monitor_events "
                "(id TEXT PRIMARY KEY, owner TEXT NOT NULL, monitor_id TEXT NOT NULL, "
                "run_id TEXT, kind TEXT NOT NULL, subject_id TEXT NOT NULL, "
                "payload TEXT NOT NULL, created_at TEXT NOT NULL, "
                "UNIQUE(monitor_id, run_id, kind, subject_id))"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def save_run(self, owner: str, payload: dict[str, Any]) -> str:
        """Persist one reproducible result snapshot."""
        run_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?)",
                (run_id, owner, datetime.now(UTC).isoformat(), json.dumps(payload)),
            )
        return run_id

    def get_run(self, run_id: str, owner: str, manager: bool = False) -> dict[str, Any] | None:
        """Read a run only for its owner or an authorized manager."""
        with self._connect() as db:
            row = db.execute("SELECT owner, payload FROM runs WHERE id = ?", (run_id,)).fetchone()
        return json.loads(row["payload"]) if row and (manager or row["owner"] == owner) else None

    def list_runs(self, owner: str) -> list[dict[str, Any]]:
        """List recent run manifests without exposing other users' queries."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, created_at, payload FROM runs WHERE owner = ? ORDER BY created_at DESC LIMIT ?",
                (owner, MAX_LIST_ROWS),
            ).fetchall()
        return [
            {
                "run_id": row["id"],
                "created_at": row["created_at"],
                "topic": json.loads(row["payload"])["options"]["topic"],
            }
            for row in rows
        ]

    def save_monitor(
        self, owner: str, options: dict[str, Any], cadence_hours: int = DEFAULT_CADENCE_HOURS
    ) -> str:
        """Save a disabled topic; activation requires an explicit action."""
        monitor_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute(
                "INSERT INTO monitors (id, owner, options, cadence_hours) VALUES (?, ?, ?, ?)",
                (monitor_id, owner, json.dumps(options), validate_cadence(cadence_hours)),
            )
        return monitor_id

    def list_monitors(self, owner: str) -> list[dict[str, Any]]:
        """Return the owner's monitoring configuration and last status."""
        with self._connect() as db:
            rows = db.execute("SELECT * FROM monitors WHERE owner = ?", (owner,)).fetchall()
        return [
            {
                "id": row["id"],
                "options": json.loads(row["options"]),
                "enabled": bool(row["enabled"]),
                "last_run": row["last_run"],
                "last_error": row["last_error"],
                "cadence_hours": row["cadence_hours"],
                "next_run_at": row["next_run_at"],
                "last_success_at": row["last_success_at"],
                "consecutive_failures": row["consecutive_failures"],
            }
            for row in rows
        ]

    def set_monitor_enabled(self, monitor_id: str, owner: str, enabled: bool) -> bool:
        """Change activation only after the caller's role is checked by the route."""
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE monitors SET enabled = ?, next_run_at = ?, lease_until = NULL "
                "WHERE id = ? AND owner = ?",
                (
                    int(enabled),
                    datetime.now(UTC).isoformat() if enabled else None,
                    monitor_id,
                    owner,
                ),
            )
        return cursor.rowcount == 1

    def set_monitor_cadence(self, monitor_id: str, owner: str, cadence_hours: int) -> bool:
        """Change an owned monitor interval without a forced collection."""
        cadence = validate_cadence(cadence_hours)
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE monitors SET cadence_hours = ?, next_run_at = CASE WHEN enabled = 1 "
                "THEN ? ELSE NULL END "
                "WHERE id = ? AND owner = ?",
                (
                    cadence,
                    (datetime.now(UTC) + timedelta(hours=cadence)).isoformat(),
                    monitor_id,
                    owner,
                ),
            )
        return cursor.rowcount == 1

    def delete_monitor(self, monitor_id: str, owner: str) -> bool:
        """Delete an owned monitor and its local history and notifications."""
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM monitors WHERE id = ? AND owner = ?", (monitor_id, owner)
            )
            if cursor.rowcount == 1:
                db.execute("DELETE FROM monitor_history WHERE monitor_id = ?", (monitor_id,))
                db.execute("DELETE FROM monitor_events WHERE monitor_id = ?", (monitor_id,))
        return cursor.rowcount == 1

    def make_monitor_due(self, monitor_id: str, owner: str) -> bool:
        """Permit an immediate refresh only for an enabled owned monitor."""
        with self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM monitors WHERE id = ? AND owner = ? AND enabled = 1",
                (monitor_id, owner),
            ).fetchone()
        return row is not None

    def claim_monitor(self, monitor_id: str, now: str, lease_until: str) -> dict[str, Any] | None:
        """Claim one enabled job with a recoverable lease."""
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE monitors SET lease_until = ? WHERE id = ? AND enabled = 1 AND (lease_until IS NULL OR lease_until < ?)",
                (lease_until, monitor_id, now),
            )
            if cursor.rowcount != 1:
                return None
            row = db.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,)).fetchone()
        return dict(row) if row else None

    def finish_monitor(self, monitor_id: str, run_id: str | None, error: str | None) -> None:
        """Release the lease and retain run/error history."""
        with self._connect() as db:
            row = db.execute(
                "SELECT owner, enabled, cadence_hours, consecutive_failures FROM monitors WHERE id = ?",
                (monitor_id,),
            ).fetchone()
            if row is None:
                return
            now = datetime.now(UTC)
            failures = row["consecutive_failures"] + 1 if error else 0
            delay = (
                timedelta(
                    minutes=min(
                        RETRY_MAX_MINUTES,
                        RETRY_BASE_MINUTES
                        * 2 ** min(row["consecutive_failures"], RETRY_MAX_EXPONENT),
                    )
                )
                if error
                else timedelta(hours=row["cadence_hours"])
            )
            next_run = (now + delay).isoformat() if row["enabled"] else None
            db.execute(
                "UPDATE monitors SET last_run = COALESCE(?, last_run), last_error = ?, "
                "lease_until = NULL, next_run_at = ?, consecutive_failures = ?, "
                "last_success_at = CASE WHEN ? IS NULL THEN ? ELSE last_success_at END "
                "WHERE id = ?",
                (run_id, error, next_run, failures, error, now.isoformat(), monitor_id),
            )
            db.execute(
                "INSERT INTO monitor_history VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    monitor_id,
                    row["owner"],
                    run_id,
                    "failed" if error else "updated" if run_id else "unchanged",
                    error,
                    now.isoformat(),
                ),
            )

    def list_history(self, monitor_id: str, owner: str) -> list[dict[str, Any]]:
        """Read recent runs for one owned monitor."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, run_id, status, error, created_at FROM monitor_history "
                "WHERE monitor_id = ? AND owner = ? ORDER BY created_at DESC LIMIT ?",
                (monitor_id, owner, MAX_LIST_ROWS),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_event(
        self,
        owner: str,
        monitor_id: str,
        run_id: str | None,
        kind: str,
        subject_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Persist one owner-scoped in-app update."""
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO monitor_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    owner,
                    monitor_id,
                    run_id,
                    kind,
                    subject_id,
                    json.dumps(payload),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def list_events(self, owner: str) -> list[dict[str, Any]]:
        """List the owner's recent monitor updates."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, monitor_id, run_id, kind, subject_id, payload, created_at "
                "FROM monitor_events WHERE owner = ? ORDER BY created_at DESC LIMIT ?",
                (owner, MAX_LIST_ROWS),
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]


def hosted_store() -> ResearchStore | PostgresResearchStore:
    """Select durable Postgres on Vercel; never write hosted data to /tmp."""
    if os.getenv("ARCHIPELAGO_RESEARCH_DATABASE_URL"):
        from .postgres_storage import PostgresResearchStore

        return PostgresResearchStore()
    if os.getenv("VERCEL"):
        raise RuntimeError("research_storage_not_configured")
    return ResearchStore()
