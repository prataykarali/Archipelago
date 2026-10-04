"""Short-lived diagnostic sessions shared by hosted WSGI workers.

SQLite holds only a bounded learning neighborhood, never student profiles.
Opaque owner hashes and session identifiers are not sent to inference providers.
"""
from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import secrets
import sqlite3
import time

SESSION_TTL_SECONDS = 3600
MAX_SESSIONS = 1000
DB_TIMEOUT_SECONDS = 10


class QuizStore:
    """Atomic session updates prevent forged answers and concurrent replay."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS quiz_session "
                "(id TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL, data TEXT NOT NULL)"
            )
        path.chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=DB_TIMEOUT_SECONDS)

    def create(self, owner: str, state: dict) -> str:
        """Persist a new one-hour session; evict oldest sessions if the cap is reached."""
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM quiz_session WHERE expires < ?", (now,))
            count = connection.execute("SELECT COUNT(1) FROM quiz_session").fetchone()[0]
            if count >= MAX_SESSIONS:
                connection.execute(
                    "DELETE FROM quiz_session WHERE id IN "
                    "(SELECT id FROM quiz_session ORDER BY expires LIMIT ?)",
                    (count - MAX_SESSIONS + 1,),
                )
            connection.execute(
                "INSERT INTO quiz_session VALUES (?, ?, ?, ?)",
                (session_id, owner, now + SESSION_TTL_SECONDS, json.dumps(state)),
            )
        return session_id

    def advance(self, session_id: str, owner: str, update: Callable[[dict], dict]) -> dict:
        """Apply one verified update; reject another owner's, expired or unknown session."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT data FROM quiz_session WHERE id = ? AND owner = ? AND expires > ?",
                (session_id, owner, time.time()),
            ).fetchone()
            if row is None:
                raise LookupError("Diagnostic session unavailable. Start a new diagnostic.")
            state = json.loads(row[0])
            result = update(state)
            connection.execute(
                "UPDATE quiz_session SET data = ? WHERE id = ?",
                (json.dumps(state), session_id),
            )
        return result
