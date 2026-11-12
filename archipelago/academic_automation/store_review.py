"""Persist human review decisions and revocable GPU consent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .store import now

if TYPE_CHECKING:
    from .store import AcademicStore

CLASS_GRANT_HOURS = 24


def review_decision(store: AcademicStore, job_id: str) -> dict[str, Any] | None:
    """Read an attributable decision for one exact staging candidate."""
    with store._connect() as db:
        row = db.execute("SELECT * FROM human_reviews WHERE job_id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def record_review(store: AcademicStore, job_id: str, decision: dict[str, Any]) -> None:
    """Replace a review only while the staging candidate remains pending."""
    with store._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None or row["status"] != "review_ready":
            raise ValueError("Job is not awaiting human review")
        db.execute(
            "INSERT INTO human_reviews(job_id,decision,reviewer_id,reviewer_name,"
            "reviewer_role,review_digest,at,note,concept_count,edge_count) "
            "VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET "
            "decision=excluded.decision,reviewer_id=excluded.reviewer_id,"
            "reviewer_name=excluded.reviewer_name,reviewer_role=excluded.reviewer_role,"
            "review_digest=excluded.review_digest,at=excluded.at,note=excluded.note,"
            "concept_count=excluded.concept_count,edge_count=excluded.edge_count",
            (
                job_id,
                *(
                    decision[key]
                    for key in (
                        "decision",
                        "reviewer_id",
                        "reviewer_name",
                        "reviewer_role",
                        "review_digest",
                        "at",
                        "note",
                        "concept_count",
                        "edge_count",
                    )
                ),
            ),
        )
    store.audit(decision["reviewer_id"], "human_review_" + decision["decision"], job_id, decision)


def grant(store: AcademicStore, *, scope: str, actor: str, job_id: str | None = None) -> str:
    """Record explicit, revocable permission for one job or a bounded class."""
    if scope not in {"job", "trusted_academic_open_content"}:
        raise ValueError("Invalid GPU permission scope")
    if scope == "job" and not job_id:
        raise ValueError("Job scope requires a job ID")
    grant_id = str(uuid4())
    expiry = (datetime.now(UTC) + timedelta(hours=CLASS_GRANT_HOURS)).isoformat()
    with store._connect() as db:
        db.execute(
            "INSERT INTO grants(grant_id,scope,job_id,expires_at,actor,created_at) VALUES(?,?,?,?,?,?)",
            (grant_id, scope, job_id, expiry, actor, now()),
        )
    store.audit(
        actor,
        "gpu_grant_created",
        grant_id,
        {"scope": scope, "job_id": job_id, "expires_at": expiry},
    )
    return grant_id


def revoke(store: AcademicStore, grant_id: str, actor: str) -> bool:
    """Revoke a GPU grant immediately."""
    with store._connect() as db:
        changed = db.execute(
            "UPDATE grants SET revoked_at=? WHERE grant_id=? AND revoked_at IS NULL",
            (now(), grant_id),
        ).rowcount
    if changed:
        store.audit(actor, "gpu_grant_revoked", grant_id, {})
    return bool(changed)


def has_grant(store: AcademicStore, job_id: str) -> bool:
    """Check current job or trusted open-content class permission."""
    with store._connect() as db:
        row = db.execute(
            "SELECT 1 FROM grants WHERE revoked_at IS NULL AND expires_at>? "
            "AND ((scope='job' AND job_id=?) OR scope='trusted_academic_open_content') LIMIT 1",
            (now(), job_id),
        ).fetchone()
    return row is not None
