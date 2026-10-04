"""Opt-in browser-owned mastery memory, never answers, identities or external context."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time

RETENTION_SECONDS = 30 * 86400
MAX_OWNERS = 1000
MAX_NODES = 100
MAX_JSON_BYTES = 128 * 1024
FIELDS = (
    "node_id",
    "mastery_state",
    "confidence",
    "reported_confidence",
    "last_verified",
    "verification_count",
)


class LearningMemory:
    """Bounded SQLite mastery storage with explicit consent and owner deletion."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS learning_memory "
                "(owner TEXT PRIMARY KEY, expires REAL NOT NULL, preference TEXT, mastery TEXT NOT NULL)"
            )
        path.chmod(0o600)

    def connect(self) -> sqlite3.Connection:
        """Open a worker-safe connection."""
        return sqlite3.connect(self.path, timeout=10)

    def load(self, owner: str) -> dict:
        """Return only this consenting owner's unexpired records."""
        with self.connect() as db:
            db.execute("DELETE FROM learning_memory WHERE expires <= ?", (time.time(),))
            row = db.execute(
                "SELECT preference,mastery FROM learning_memory WHERE owner = ?",
                (owner,),
            ).fetchone()
        return {"preference": row[0], "mastery": json.loads(row[1])} if row else {}

    def enable(self, owner: str) -> None:
        """Persist consent without fabricating any assessment evidence."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM learning_memory WHERE expires <= ?", (time.time(),))
            db.execute(
                "INSERT OR IGNORE INTO learning_memory VALUES (?, ?, ?, ?)",
                (owner, time.time() + RETENTION_SECONDS, "conceptual", "{}"),
            )
            db.execute(
                "DELETE FROM learning_memory WHERE owner IN "
                "(SELECT owner FROM learning_memory ORDER BY expires DESC LIMIT -1 OFFSET ?)",
                (MAX_OWNERS,),
            )

    def save(self, owner: str, state: dict) -> None:
        """Update consented mastery atomically; deletion cannot be undone by a stale session."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT mastery FROM learning_memory WHERE owner = ? AND expires > ?",
                (owner, time.time()),
            ).fetchone()
            if row is None:
                return
            merged = json.loads(row[0])
            for cid, record in state.get("mastery", {}).items():
                if isinstance(record, dict):
                    merged[cid] = {field: record[field] for field in FIELDS if field in record}
            # Keep the most recently verified bounded concepts, not full history.
            merged = dict(
                sorted(
                    merged.items(),
                    key=lambda pair: pair[1].get("last_verified", 0),
                    reverse=True,
                )[:MAX_NODES]
            )
            payload = json.dumps(merged)
            if len(payload.encode()) > MAX_JSON_BYTES:
                raise ValueError("Learning memory exceeds its storage limit.")
            db.execute(
                "UPDATE learning_memory SET expires=?,preference=?,mastery=? WHERE owner=?",
                (time.time() + RETENTION_SECONDS, state["preference"], payload, owner),
            )

    def delete(self, owner: str) -> None:
        """Remove consent and every saved mastery record for this owner."""
        with self.connect() as db:
            db.execute("DELETE FROM learning_memory WHERE owner = ?", (owner,))

    def aggregate(self, minimum: int = 5) -> list[dict]:
        """Release anonymous gap counts only after an opted-in minimum cohort."""
        counts: dict[str, int] = {}
        with self.connect() as db:
            rows = db.execute(
                "SELECT mastery FROM learning_memory WHERE expires > ?",
                (time.time(),),
            ).fetchall()
        for row in rows:
            for cid, record in json.loads(row[0]).items():
                if record.get("mastery_state") in {"review_gap", "missing"}:
                    counts[cid] = counts.get(cid, 0) + 1
        return [
            {"concept_id": cid, "gap_count": count}
            for cid, count in sorted(counts.items())
            if count >= minimum
        ]
