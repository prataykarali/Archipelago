"""Owner-scoped SQLite snapshots and opt-in monitoring definitions."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
import uuid

DEFAULT_PATH = Path("data/research_intelligence.sqlite3")


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
                "SELECT id, created_at, payload FROM runs WHERE owner = ? ORDER BY created_at DESC LIMIT 30",
                (owner,),
            ).fetchall()
        return [
            {
                "run_id": row["id"],
                "created_at": row["created_at"],
                "topic": json.loads(row["payload"])["options"]["topic"],
            }
            for row in rows
        ]

    def save_monitor(self, owner: str, options: dict[str, Any]) -> str:
        """Save a disabled topic; activation requires an explicit action."""
        monitor_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute(
                "INSERT INTO monitors (id, owner, options) VALUES (?, ?, ?)",
                (monitor_id, owner, json.dumps(options)),
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
            }
            for row in rows
        ]

    def set_monitor_enabled(self, monitor_id: str, owner: str, enabled: bool) -> bool:
        """Change activation only after the caller's role is checked by the route."""
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE monitors SET enabled = ? WHERE id = ? AND owner = ?",
                (int(enabled), monitor_id, owner),
            )
        return cursor.rowcount == 1

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
            db.execute(
                "UPDATE monitors SET last_run = COALESCE(?, last_run), last_error = ?, lease_until = NULL WHERE id = ?",
                (run_id, error, monitor_id),
            )
