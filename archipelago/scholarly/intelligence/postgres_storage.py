"""Durable, owner-scoped S5 storage for the hosted research service."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from typing import TYPE_CHECKING, Any
import uuid

import requests

from .storage import DEFAULT_CADENCE_HOURS, validate_cadence

if TYPE_CHECKING:
    import psycopg

MAX_LIST_ROWS = 30
RETRY_BASE_MINUTES = 5
RETRY_MAX_EXPONENT = 4
RETRY_MAX_MINUTES = 60
CONNECT_TIMEOUT_SECONDS = 10


def _rpc_credentials() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    return (url, key) if url and key else None


class PostgresResearchStore:
    """Use the private research schema through direct Postgres or service-role RPC."""

    def __init__(self, dsn: str | None = None) -> None:
        env_dsn = os.getenv("ARCHIPELAGO_RESEARCH_DATABASE_URL", "").strip()
        self._explicit_dsn = dsn is not None
        self.dsn = (dsn or env_dsn).strip()
        self._creds = _rpc_credentials()
        if not self.dsn and not self._creds:
            raise RuntimeError("research_storage_not_configured")

    def _use_rpc(self) -> bool:
        if self._explicit_dsn:
            return False
        return bool(
            self._creds
            and (
                not self.dsn
                or "[YOUR-PASSWORD]" in self.dsn
                or self.dsn == "[SENSITIVE]"
                or not self.dsn.startswith(("postgres://", "postgresql://"))
            )
        )

    def _rpc(self, op: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        creds = self._creds or _rpc_credentials()
        if not creds:
            raise RuntimeError("research_storage_not_configured")
        url, key = creds
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        response = requests.post(
            f"{url}/rest/v1/rpc/s5_research_rpc",
            json={"p_op": op, "p_args": args or {}},
            headers=headers,
            timeout=CONNECT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("invalid_s5_rpc_response")
        return data

    def _connect(self) -> psycopg.Connection[Any]:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(
            self.dsn, row_factory=dict_row, connect_timeout=CONNECT_TIMEOUT_SECONDS
        )

    def check_ready(self) -> bool:
        """Verify the private research schema is reachable from this deployment."""
        if self._use_rpc():
            return bool(self._rpc("check_ready").get("ready"))
        try:
            with self._connect() as db, db.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('research_intelligence.s5_runs') IS NOT NULL AS runs, "
                    "to_regclass('research_intelligence.s5_monitors') IS NOT NULL AS monitors, "
                    "to_regclass('research_intelligence.s5_monitor_history') IS NOT NULL AS history, "
                    "to_regclass('research_intelligence.s5_events') IS NOT NULL AS events"
                )
                row = cursor.fetchone()
                cursor.execute(
                    "SELECT consecutive_failures, last_success_at "
                    "FROM research_intelligence.s5_monitors LIMIT 0"
                )
            return bool(row and all(row.values()))
        except Exception:
            if self._creds and not self._explicit_dsn:
                return bool(self._rpc("check_ready").get("ready"))
            raise

    def save_run(self, owner: str, payload: dict[str, Any]) -> str:
        """Write a versioned snapshot in one committed transaction."""
        run_id, topic = str(uuid.uuid4()), payload["options"]["topic"]
        if self._use_rpc():
            args = {"id": run_id, "owner_id": owner, "schema_version": payload["schema"], "topic": topic, "payload": payload}
            self._rpc("save_run", args)
            return run_id
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO research_intelligence.s5_runs "
                "(id, owner_id, schema_version, topic, payload) VALUES (%s, %s, %s, %s, %s)",
                (run_id, owner, payload["schema"], topic, json.dumps(payload)),
            )
        return run_id

    def get_run(self, run_id: str, owner: str, manager: bool = False) -> dict[str, Any] | None:
        """Return only a snapshot belonging to the authenticated caller."""
        del manager
        if self._use_rpc():
            res = self._rpc("get_run", {"id": run_id, "owner_id": owner})
            return res.get("payload") if res.get("found") else None
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "SELECT payload FROM research_intelligence.s5_runs WHERE id = %s AND owner_id = %s",
                (run_id, owner),
            )
            row = cursor.fetchone()
        return row["payload"] if row else None

    def list_runs(self, owner: str) -> list[dict[str, Any]]:
        """Page the caller's most recent research snapshots."""
        if self._use_rpc():
            return list(self._rpc("list_runs", {"owner_id": owner}).get("runs") or [])
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "SELECT id, created_at, topic FROM research_intelligence.s5_runs "
                "WHERE owner_id = %s ORDER BY created_at DESC LIMIT %s",
                (owner, MAX_LIST_ROWS),
            )
            rows = cursor.fetchall()
        return [
            {"run_id": str(r["id"]), "created_at": r["created_at"].isoformat(), "topic": r["topic"]}
            for r in rows
        ]

    def save_monitor(
        self, owner: str, options: dict[str, Any], cadence_hours: int = DEFAULT_CADENCE_HOURS
    ) -> str:
        """Save a disabled monitor; activation requires an explicit request."""
        monitor_id, cadence = str(uuid.uuid4()), validate_cadence(cadence_hours)
        if self._use_rpc():
            self._rpc("save_monitor", {"id": monitor_id, "owner_id": owner, "options": options, "cadence_hours": cadence})
            return monitor_id
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO research_intelligence.s5_monitors (id, owner_id, options, cadence_hours) "
                "VALUES (%s, %s, %s, %s)",
                (monitor_id, owner, json.dumps(options), cadence),
            )
        return monitor_id

    def list_monitors(self, owner: str) -> list[dict[str, Any]]:
        """List only monitors owned by the caller."""
        if self._use_rpc():
            return list(self._rpc("list_monitors", {"owner_id": owner}).get("monitors") or [])
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "SELECT id, options, enabled, cadence_hours, next_run_at, last_run_id, "
                "last_error, last_success_at, consecutive_failures "
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
                "last_success_at": row["last_success_at"].isoformat() if row["last_success_at"] else None,
                "consecutive_failures": row["consecutive_failures"],
            }
            for row in rows
        ]

    def set_monitor_enabled(self, monitor_id: str, owner: str, enabled: bool) -> bool:
        """Activate only the caller's monitor and set its first due time."""
        if self._use_rpc():
            return bool(self._rpc("set_monitor_enabled", {"id": monitor_id, "owner_id": owner, "enabled": enabled}).get("ok"))
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "UPDATE research_intelligence.s5_monitors SET enabled = %s, "
                "next_run_at = CASE WHEN %s THEN now() ELSE NULL END, "
                "lease_until = NULL, updated_at = now() WHERE id = %s AND owner_id = %s",
                (enabled, enabled, monitor_id, owner),
            )
            return bool(cursor.rowcount == 1)

    def set_monitor_cadence(self, monitor_id: str, owner: str, cadence_hours: int) -> bool:
        """Update an owned monitor's interval without triggering a refresh."""
        cadence = validate_cadence(cadence_hours)
        if self._use_rpc():
            return bool(self._rpc("set_monitor_cadence", {"id": monitor_id, "owner_id": owner, "cadence_hours": cadence}).get("ok"))
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "UPDATE research_intelligence.s5_monitors SET cadence_hours = %s, "
                "next_run_at = CASE WHEN enabled THEN now() + %s * interval '1 hour' ELSE NULL END, "
                "updated_at = now() WHERE id = %s AND owner_id = %s",
                (cadence, cadence, monitor_id, owner),
            )
            return bool(cursor.rowcount == 1)

    def delete_monitor(self, monitor_id: str, owner: str) -> bool:
        """Remove an owned monitor and its cascading execution history and updates."""
        if self._use_rpc():
            return bool(self._rpc("delete_monitor", {"id": monitor_id, "owner_id": owner}).get("ok"))
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "DELETE FROM research_intelligence.s5_monitors WHERE id = %s AND owner_id = %s",
                (monitor_id, owner),
            )
            return bool(cursor.rowcount == 1)

    def make_monitor_due(self, monitor_id: str, owner: str) -> bool:
        """Queue an explicit owner-triggered refresh for immediate claiming."""
        if self._use_rpc():
            return bool(self._rpc("make_monitor_due", {"id": monitor_id, "owner_id": owner}).get("ok"))
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "UPDATE research_intelligence.s5_monitors SET next_run_at = now() "
                "WHERE id = %s AND owner_id = %s AND enabled",
                (monitor_id, owner),
            )
            return bool(cursor.rowcount == 1)

    def claim_monitor(self, monitor_id: str, now: str, lease_until: str) -> dict[str, Any] | None:
        """Atomically lease one due monitor across scheduler instances."""
        if self._use_rpc():
            claimed = self._rpc("claim_monitor", {"id": monitor_id, "now": now, "lease_until": lease_until}).get("claimed")
            return claimed if isinstance(claimed, dict) else None
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "UPDATE research_intelligence.s5_monitors SET lease_until = %s, "
                "lease_started_at = now() "
                "WHERE id = %s AND enabled AND next_run_at <= GREATEST(%s::timestamptz, now()) "
                "AND (lease_until IS NULL OR lease_until < %s) "
                "RETURNING id, owner_id, options, last_run_id",
                (lease_until, monitor_id, now, now),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "owner": str(row["owner_id"]),
            "options": json.dumps(row["options"]),
            "last_run": str(row["last_run_id"]) if row["last_run_id"] else None,
        }

    def due_monitor_ids(self, limit: int = MAX_LIST_ROWS) -> list[str]:
        """Find due monitors for the dedicated S5 scheduler."""
        if self._use_rpc():
            ids = self._rpc("due_monitor_ids", {"limit": min(limit, MAX_LIST_ROWS)}).get("ids") or []
            return [str(item) for item in ids]
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
        history_id = str(uuid.uuid4())
        if self._use_rpc():
            self._rpc("finish_monitor", {"id": monitor_id, "history_id": history_id, "run_id": run_id, "error": error})
            return
        now = datetime.now(UTC)
        status = "failed" if error else "updated" if run_id else "unchanged"
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "UPDATE research_intelligence.s5_monitors SET "
                "last_run_id = COALESCE(%s, last_run_id), last_error = %s, "
                "consecutive_failures = CASE WHEN %s::text IS NULL THEN 0 ELSE consecutive_failures + 1 END, "
                "last_success_at = CASE WHEN %s::text IS NULL THEN now() ELSE last_success_at END, "
                "lease_until = NULL, next_run_at = CASE WHEN NOT enabled THEN NULL "
                "WHEN %s::text IS NULL THEN now() + cadence_hours * interval '1 hour' "
                "ELSE now() + LEAST(%s, %s * power(2, LEAST(consecutive_failures, %s))) "
                "* interval '1 minute' END, updated_at = now() WHERE id = %s "
                "RETURNING owner_id, lease_started_at",
                (
                    run_id,
                    error,
                    error,
                    error,
                    error,
                    RETRY_MAX_MINUTES,
                    RETRY_BASE_MINUTES,
                    RETRY_MAX_EXPONENT,
                    monitor_id,
                ),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "INSERT INTO research_intelligence.s5_monitor_history "
                    "(id, monitor_id, owner_id, run_id, status, error_code, started_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (history_id, monitor_id, row["owner_id"], run_id, status, error, row["lease_started_at"] or now),
                )

    def list_history(self, monitor_id: str, owner: str) -> list[dict[str, Any]]:
        """Return execution history after checking monitor ownership."""
        if self._use_rpc():
            return list(self._rpc("list_history", {"monitor_id": monitor_id, "owner_id": owner}).get("history") or [])
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
                "id": str(r["id"]),
                "run_id": str(r["run_id"]) if r["run_id"] else None,
                "status": r["status"],
                "error": r["error_code"],
                "finished_at": r["finished_at"].isoformat(),
            }
            for r in rows
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
        event_id = str(uuid.uuid4())
        if self._use_rpc():
            args = {"id": event_id, "owner_id": owner, "monitor_id": monitor_id, "run_id": run_id, "kind": kind, "subject_id": subject_id, "payload": payload}
            self._rpc("add_event", args)
            return
        with self._connect() as db, db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO research_intelligence.s5_events "
                "(id, owner_id, monitor_id, run_id, kind, subject_id, payload) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (monitor_id, kind, subject_id, run_id) DO NOTHING",
                (event_id, owner, monitor_id, run_id, kind, subject_id, json.dumps(payload)),
            )

    def list_events(self, owner: str) -> list[dict[str, Any]]:
        """Return the caller's recent research updates."""
        if self._use_rpc():
            return list(self._rpc("list_events", {"owner_id": owner}).get("events") or [])
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
                "id": str(r["id"]),
                "monitor_id": str(r["monitor_id"]),
                "run_id": str(r["run_id"]) if r["run_id"] else None,
                "kind": r["kind"],
                "subject_id": r["subject_id"],
                "payload": r["payload"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
