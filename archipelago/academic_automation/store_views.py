"""Read views and provider observations for the academic ledger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .store import now

if TYPE_CHECKING:
    from .store import AcademicStore


def provider_result(store: AcademicStore, name: str, *, error: str | None = None) -> None:
    """Record a check without treating an outage as a withdrawal."""
    timestamp = now()
    with store._connect() as db:
        db.execute(
            "INSERT INTO providers(name,last_attempt,last_success,status,error) VALUES(?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET last_attempt=excluded.last_attempt, "
            "last_success=CASE WHEN excluded.error IS NULL THEN excluded.last_success "
            "ELSE providers.last_success END,status=excluded.status,error=excluded.error",
            (
                name,
                timestamp,
                timestamp if error is None else None,
                "available" if error is None else "unavailable",
                error,
            ),
        )
    store.audit(
        "scheduler",
        "provider_check",
        name,
        {"status": "ok" if error is None else "error", "error": error},
    )


def dashboard(store: AcademicStore) -> dict[str, Any]:
    """Return status and recent work without claiming unrun synchronization."""
    with store._connect() as db:
        providers = [dict(row) for row in db.execute("SELECT * FROM providers ORDER BY name")]
        jobs = [
            dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 50")
        ]
        counts = {
            row[0]: row[1]
            for row in db.execute("SELECT status,count(*) FROM records GROUP BY status")
        }
        discovery_counts = {
            row[0]: row[1]
            for row in db.execute(
                "SELECT action,count(*) FROM audit WHERE action IN ('record_new','record_changed') GROUP BY action"
            )
        }
        audits = [
            dict(row) for row in db.execute("SELECT * FROM audit ORDER BY event_id DESC LIMIT 30")
        ]
        grants = [
            dict(row)
            for row in db.execute(
                "SELECT grant_id,scope,job_id,expires_at,revoked_at,actor,created_at FROM grants ORDER BY created_at DESC LIMIT 30"
            )
        ]
        match_count = db.execute("SELECT count(*) FROM source_matches").fetchone()[0]
    return {
        "providers": providers,
        "jobs": jobs,
        "record_counts": counts,
        "discovery_counts": discovery_counts,
        "grants": grants,
        "audit": audits,
        "external_matches": match_count,
    }


def match_rows(store: AcademicStore) -> list[dict[str, Any]]:
    """List source-backed bibliographic records for permitted matching."""
    with store._connect() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT record_key,title,isbn,edition FROM records WHERE status!='withdrawn'"
            )
        ]


def save_match(
    store: AcademicStore,
    record_key: str,
    provider: str,
    source_id: str,
    source_url: str,
    status: str,
) -> None:
    """Retain a source link as metadata only until content rights are proven."""
    with store._connect() as db:
        db.execute(
            "INSERT INTO source_matches(record_key,provider,source_id,source_url,match_status,observed_at) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(record_key,provider,source_id) DO UPDATE SET "
            "source_url=excluded.source_url,match_status=excluded.match_status,observed_at=excluded.observed_at",
            (record_key, provider, source_id, source_url, status, now()),
        )


def withdraw(store: AcademicStore, record_key: str, *, verified: bool, actor: str) -> bool:
    """Withdraw only after an explicit authoritative check."""
    if not verified:
        return False
    with store._connect() as db:
        changed = db.execute(
            "UPDATE records SET status='withdrawn',availability_status='requires_verification',verified_at=? "
            "WHERE record_key=?",
            (now(), record_key),
        ).rowcount
    if changed:
        store.audit(actor, "record_withdrawn", record_key, {"verified": True})
    return bool(changed)
