"""Durable, owner-scoped S5 storage for the hosted research service."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from typing import Any
import uuid

import psycopg
from psycopg.rows import dict_row

MAX_LIST_ROWS = 30


class PostgresResearchStore:
    """Use the private research schema through a server-only Postgres connection."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.environ["ARCHIPELAGO_RESEARCH_DATABASE_URL"]

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=10)

    def save_run(self, owner: str, payload: dict[str, Any]) -> str:
        """Write a versioned snapshot in one committed transaction."""
        run_id = str(uuid.uuid4())
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO research_intelligence.s5_runs "
                "(id, owner_id, schema_version, topic, payload) VALUES (%s, %s, %s, %s, %s)",
                (
                    run_id,
                    owner,
                    payload["schema"],
                    payload["options"]["topic"],
                    json.dumps(payload),
                ),
            )
        return run_id

    def get_run(self, run_id: str, owner: str, manager: bool = False) -> dict[str, Any] | None:
        """Return only a snapshot belonging to the authenticated caller."""
        del manager  # Research snapshots are private, including from other managers.
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "SELECT payload FROM research_intelligence.s5_runs WHERE id = %s AND owner_id = %s",
                (run_id, owner),
            )
            row = cursor.fetchone()
        return row["payload"] if row else None

    def list_runs(self, owner: str) -> list[dict[str, Any]]:
        """Page the caller's most recent research snapshots."""
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "SELECT id, created_at, topic FROM research_intelligence.s5_runs "
                "WHERE owner_id = %s ORDER BY created_at DESC LIMIT %s",
                (owner, MAX_LIST_ROWS),
            )
            rows = cursor.fetchall()
        return [
            {
                "run_id": str(row["id"]),
                "created_at": row["created_at"].isoformat(),
                "topic": row["topic"],
            }
            for row in rows
        ]

    def save_monitor(self, owner: str, options: dict[str, Any]) -> str:
        """Save a disabled monitor; activation requires an explicit request."""
        monitor_id = str(uuid.uuid4())
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO research_intelligence.s5_monitors (id, owner_id, options) "
                "VALUES (%s, %s, %s)",
                (monitor_id, owner, json.dumps(options)),
            )
        return monitor_id

    def list_monitors(self, owner: str) -> list[dict[str, Any]]:
        """List only monitors owned by the caller."""
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "SELECT id, options, enabled, cadence_hours, next_run_at, last_run_id, last_error "
                "FROM research_intelligence.s5_monitors WHERE owner_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (owner, MAX_LIST_ROWS),
            )
            rows = cursor.fetchall()
        return [
            {
                "id": str(row["id"]),
                "options": row["options"],
                "enabled": row["enabled"],
                "cadence_hours": row["cadence_hours"],
                "next_run_at": row["next_run_at"].isoformat() if row["next_run_at"] else None,
                "last_run": str(row["last_run_id"]) if row["last_run_id"] else None,
                "last_error": row["last_error"],
            }
            for row in rows
        ]

    def set_monitor_enabled(self, monitor_id: str, owner: str, enabled: bool) -> bool:
        """Activate only the caller's monitor and set its first due time."""
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "UPDATE research_intelligence.s5_monitors SET enabled = %s, "
                "next_run_at = CASE WHEN %s THEN now() ELSE NULL END, "
                "lease_until = NULL, updated_at = now() "
                "WHERE id = %s AND owner_id = %s",
                (enabled, enabled, monitor_id, owner),
            )
            return cursor.rowcount == 1

    def make_monitor_due(self, monitor_id: str, owner: str) -> bool:
        """Queue an explicit owner-triggered refresh for immediate claiming."""
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "UPDATE research_intelligence.s5_monitors SET next_run_at = now() "
                "WHERE id = %s AND owner_id = %s AND enabled",
                (monitor_id, owner),
            )
            return cursor.rowcount == 1

    def claim_monitor(self, monitor_id: str, now: str, lease_until: str) -> dict[str, Any] | None:
        """Atomically lease one due monitor across scheduler instances."""
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "UPDATE research_intelligence.s5_monitors SET lease_until = %s "
                "WHERE id = %s AND enabled AND next_run_at <= %s "
                "AND (lease_until IS NULL OR lease_until < %s) "
                "RETURNING id, owner_id, options, last_run_id",
                (lease_until, monitor_id, now, now),
            )
            row = cursor.fetchone()
        return (
            {
                "id": str(row["id"]),
                "owner": str(row["owner_id"]),
                "options": json.dumps(row["options"]),
                "last_run": str(row["last_run_id"]) if row["last_run_id"] else None,
            }
            if row
            else None
        )

    def due_monitor_ids(self, limit: int = MAX_LIST_ROWS) -> list[str]:
        """Find due monitors for the dedicated S5 scheduler."""
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM research_intelligence.s5_monitors "
                "WHERE enabled AND next_run_at <= now() "
                "AND (lease_until IS NULL OR lease_until < now()) "
                "ORDER BY next_run_at LIMIT %s",
                (min(limit, MAX_LIST_ROWS),),
            )
            rows = cursor.fetchall()
        return [str(row["id"]) for row in rows]

    def finish_monitor(self, monitor_id: str, run_id: str | None, error: str | None) -> None:
        """Record outcome and move the next check beyond this lease."""
        now = datetime.now(UTC)
        status = "failed" if error else "updated" if run_id else "unchanged"
        history_id = str(uuid.uuid4())
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "UPDATE research_intelligence.s5_monitors SET "
                "last_run_id = COALESCE(%s, last_run_id), last_error = %s, "
                "lease_until = NULL, next_run_at = now() + cadence_hours * interval '1 hour', "
                "updated_at = now() WHERE id = %s "
                "RETURNING owner_id, cadence_hours",
                (run_id, error, monitor_id),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "INSERT INTO research_intelligence.s5_monitor_history "
                    "(id, monitor_id, owner_id, run_id, status, error_code, started_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (history_id, monitor_id, row["owner_id"], run_id, status, error, now),
                )

    def list_history(self, monitor_id: str, owner: str) -> list[dict[str, Any]]:
        """Return execution history after checking monitor ownership."""
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "SELECT h.id, h.run_id, h.status, h.error_code, h.finished_at "
                "FROM research_intelligence.s5_monitor_history h "
                "JOIN research_intelligence.s5_monitors m ON m.id = h.monitor_id "
                "WHERE h.monitor_id = %s AND m.owner_id = %s "
                "ORDER BY h.finished_at DESC LIMIT %s",
                (monitor_id, owner, MAX_LIST_ROWS),
            )
            rows = cursor.fetchall()
        return [
            {
                "id": str(row["id"]),
                "run_id": str(row["run_id"]) if row["run_id"] else None,
                "status": row["status"],
                "error": row["error_code"],
                "finished_at": row["finished_at"].isoformat(),
            }
            for row in rows
        ]

    def add_event(
        self,
        owner: str,
        monitor_id: str,
        run_id: str | None,
        kind: str,
        subject_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Insert one idempotent in-app notification."""
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO research_intelligence.s5_events "
                "(id, owner_id, monitor_id, run_id, kind, subject_id, payload) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (monitor_id, kind, subject_id, run_id) DO NOTHING",
                (
                    str(uuid.uuid4()),
                    owner,
                    monitor_id,
                    run_id,
                    kind,
                    subject_id,
                    json.dumps(payload),
                ),
            )

    def list_events(self, owner: str) -> list[dict[str, Any]]:
        """Return the caller's recent research updates."""
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "SELECT id, monitor_id, run_id, kind, subject_id, payload, created_at "
                "FROM research_intelligence.s5_events WHERE owner_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (owner, MAX_LIST_ROWS),
            )
            rows = cursor.fetchall()
        return [
            {
                "id": str(row["id"]),
                "monitor_id": str(row["monitor_id"]),
                "run_id": str(row["run_id"]) if row["run_id"] else None,
                "kind": row["kind"],
                "subject_id": row["subject_id"],
                "payload": row["payload"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
