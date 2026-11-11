"""SQLite state for catalog observations, reviews, consent, and audit history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

MAX_PENDING_JOBS = 100
MAX_RETRIES = 3
RETRY_BASE_SECONDS = 60
CLASS_GRANT_HOURS = 24
DEFER_MINUTES = 60
AGING_POINTS_PER_DAY = 24
STALE_JOB_HOURS = 2


def now() -> str:
    """Return a sortable UTC timestamp."""
    return datetime.now(UTC).isoformat()


class AcademicStore:
    """Persist reconciliation state without replacing the canonical catalog."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS providers (
                    name TEXT PRIMARY KEY, last_attempt TEXT, last_success TEXT,
                    status TEXT NOT NULL DEFAULT 'never_checked', error TEXT
                );
                CREATE TABLE IF NOT EXISTS records (
                    record_key TEXT PRIMARY KEY, provider TEXT NOT NULL,
                    source_id TEXT NOT NULL, identity_key TEXT NOT NULL,
                    revision TEXT NOT NULL, status TEXT NOT NULL,
                    title TEXT NOT NULL, isbn TEXT, edition TEXT,
                    verified_at TEXT NOT NULL, availability_status TEXT NOT NULL,
                    payload TEXT NOT NULL, UNIQUE(provider, source_id)
                );
                CREATE TABLE IF NOT EXISTS record_versions (
                    record_key TEXT NOT NULL, revision TEXT NOT NULL,
                    observed_at TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(record_key, revision)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL,
                    record_key TEXT NOT NULL, status TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0, mode TEXT NOT NULL DEFAULT 'gpu',
                    rights TEXT NOT NULL, content_path TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, next_attempt_at TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0, progress TEXT NOT NULL DEFAULT '{}',
                    error TEXT, staging_path TEXT, baseline_version TEXT,
                    published_version TEXT, publication_backup TEXT
                );
                CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(status, next_attempt_at, priority);
                CREATE TABLE IF NOT EXISTS grants (
                    grant_id TEXT PRIMARY KEY, scope TEXT NOT NULL, job_id TEXT,
                    expires_at TEXT NOT NULL, revoked_at TEXT, actor TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                    actor TEXT NOT NULL, action TEXT NOT NULL, subject TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_matches (
                    record_key TEXT NOT NULL, provider TEXT NOT NULL,
                    source_id TEXT NOT NULL, source_url TEXT NOT NULL,
                    match_status TEXT NOT NULL, observed_at TEXT NOT NULL,
                    PRIMARY KEY(record_key, provider, source_id)
                );
                CREATE TABLE IF NOT EXISTS human_reviews (
                    job_id TEXT PRIMARY KEY, decision TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL, reviewer_name TEXT NOT NULL,
                    reviewer_role TEXT NOT NULL, review_digest TEXT NOT NULL,
                    at TEXT NOT NULL, note TEXT NOT NULL,
                    concept_count INTEGER NOT NULL, edge_count INTEGER NOT NULL
                );
            """)

    def review_decision(self, job_id: str) -> dict[str, Any] | None:
        """Read an attributable decision for one exact staging candidate."""
        with self._connect() as db:
            row = db.execute("SELECT * FROM human_reviews WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def record_review(self, job_id: str, decision: dict[str, Any]) -> None:
        """Replace a review only while the staging candidate remains pending."""
        with self._connect() as db:
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
        self.audit(
            decision["reviewer_id"], "human_review_" + decision["decision"], job_id, decision
        )

    def audit(self, actor: str, action: str, subject: str, detail: dict[str, Any]) -> None:
        """Append a structured audit event."""
        with self._connect() as db:
            db.execute(
                "INSERT INTO audit(at,actor,action,subject,detail) VALUES(?,?,?,?,?)",
                (now(), actor, action, subject, json.dumps(detail, sort_keys=True)),
            )

    def provider_result(self, name: str, *, error: str | None = None) -> None:
        """Record a provider check without withdrawing absent records."""
        from .store_views import provider_result

        provider_result(self, name, error=error)

    def observe(self, record: dict[str, str], payload: dict[str, Any]) -> str:
        """Version a validated provider record and return its change status."""
        key = f"{record['provider']}:{record['source_id']}"
        with self._connect() as db:
            old = db.execute(
                "SELECT revision,status FROM records WHERE record_key=?", (key,)
            ).fetchone()
            status = (
                "new"
                if old is None
                else "unchanged"
                if old["revision"] == record["revision"]
                else "changed"
            )
            db.execute(
                "INSERT INTO records(record_key,provider,source_id,identity_key,revision,status,title,isbn,edition,verified_at,availability_status,payload) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(record_key) DO UPDATE SET "
                "identity_key=excluded.identity_key,revision=excluded.revision,status=excluded.status,"
                "title=excluded.title,isbn=excluded.isbn,edition=excluded.edition,"
                "verified_at=excluded.verified_at,availability_status=excluded.availability_status,payload=excluded.payload",
                (
                    key,
                    record["provider"],
                    record["source_id"],
                    record["identity_key"],
                    record["revision"],
                    status,
                    record["title"],
                    record.get("isbn"),
                    record.get("edition"),
                    now(),
                    record["availability_status"],
                    json.dumps(payload, sort_keys=True),
                ),
            )
            db.execute(
                "INSERT OR IGNORE INTO record_versions(record_key,revision,observed_at,payload) VALUES(?,?,?,?)",
                (key, record["revision"], now(), json.dumps(payload, sort_keys=True)),
            )
        if status != "unchanged":
            self.audit("scheduler", "record_" + status, key, {"revision": record["revision"]})
        return status

    def withdraw(self, record_key: str, *, verified: bool, actor: str) -> bool:
        """Mark a record withdrawn only after an explicit authoritative check."""
        from .store_views import withdraw

        return withdraw(self, record_key, verified=verified, actor=actor)

    def enqueue(
        self,
        *,
        record_key: str,
        rights: str,
        content_path: str,
        content_sha256: str,
        priority: int = 0,
        mode: str = "gpu",
    ) -> str:
        """Create one bounded, idempotent candidate for permitted local content."""
        if rights != "open_permitted" or mode not in {"gpu", "cpu"}:
            raise ValueError("Content rights or execution mode not approved")
        key = f"{record_key}:{content_sha256}:{mode}"
        with self._connect() as db:
            record = db.execute(
                "SELECT status FROM records WHERE record_key=?", (record_key,)
            ).fetchone()
            if record is None or record["status"] == "withdrawn":
                raise ValueError("Candidate has no active reconciled catalog record")
            existing = db.execute(
                "SELECT job_id FROM jobs WHERE idempotency_key=?", (key,)
            ).fetchone()
            if existing:
                return str(existing["job_id"])
            count = db.execute(
                "SELECT count(*) FROM jobs WHERE status IN ('queued','awaiting_approval','approved','running','review_ready')"
            ).fetchone()[0]
            if count >= MAX_PENDING_JOBS:
                raise OverflowError("Academic ingestion queue is full")
            job_id = str(uuid4())
            db.execute(
                "INSERT INTO jobs(job_id,idempotency_key,record_key,status,priority,mode,rights,content_path,content_sha256,created_at,updated_at) "
                "VALUES(?,?,?,'awaiting_approval',?,?,?,?,?,?,?)",
                (
                    job_id,
                    key,
                    record_key,
                    priority,
                    mode,
                    rights,
                    content_path,
                    content_sha256,
                    now(),
                    now(),
                ),
            )
        self.audit("scheduler", "job_enqueued", job_id, {"record_key": record_key, "mode": mode})
        return job_id

    def job(self, job_id: str) -> dict[str, Any] | None:
        """Read one durable job."""
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def update_job(
        self,
        job_id: str,
        status: str,
        *,
        error: str | None = None,
        progress: dict[str, Any] | None = None,
        staging_path: str | None = None,
        baseline_version: str | None = None,
        published_version: str | None = None,
        publication_backup: str | None = None,
    ) -> None:
        """Persist a job transition and its audit record."""
        with self._connect() as db:
            changed = db.execute(
                "UPDATE jobs SET status=?,updated_at=?,error=?,progress=?,"
                "staging_path=COALESCE(?,staging_path),baseline_version=COALESCE(?,baseline_version),"
                "published_version=COALESCE(?,published_version),publication_backup=COALESCE(?,publication_backup) "
                "WHERE job_id=? AND (status!='cancelled' OR ? NOT IN ('running','review_ready'))",
                (
                    status,
                    now(),
                    error,
                    json.dumps(progress or {}),
                    staging_path,
                    baseline_version,
                    published_version,
                    publication_backup,
                    job_id,
                    status,
                ),
            ).rowcount
        if changed == 0:
            raise RuntimeError("Job was cancelled or disappeared during transition")
        self.audit("worker", "job_" + status, job_id, {"error": error})

    def cancel(self, job_id: str, actor: str) -> bool:
        """Cancel a waiting job or flag a running job for cooperative abort."""
        with self._connect() as db:
            changed = db.execute(
                "UPDATE jobs SET status='cancelled',updated_at=? WHERE job_id=? "
                "AND status IN ('awaiting_approval','approved','queued','claimed','running','review_ready','cpu_requested')",
                (now(), job_id),
            ).rowcount
        if changed:
            self.audit(actor, "job_cancelled", job_id, {})
        return bool(changed)

    def dashboard(self) -> dict[str, Any]:
        """Return durable source, job, grant, and audit status."""
        from .store_views import dashboard

        return dashboard(self)

    def match_rows(self) -> list[dict[str, Any]]:
        """List source-backed records eligible for external matching."""
        from .store_views import match_rows

        return match_rows(self)

    def save_match(
        self, record_key: str, provider: str, source_id: str, source_url: str, status: str
    ) -> None:
        """Retain one metadata-only external match."""
        from .store_views import save_match

        save_match(self, record_key, provider, source_id, source_url, status)

    def next_job(self) -> dict[str, Any] | None:
        """Claim the oldest highest-priority pending job, one worker at a time."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            running = db.execute(
                "SELECT count(*) FROM jobs WHERE status IN ('claimed','running')"
            ).fetchone()[0]
            if running:
                return None
            row = db.execute(
                "SELECT * FROM jobs WHERE status IN ('awaiting_approval','approved','cpu_requested') "
                "AND (next_attempt_at IS NULL OR next_attempt_at<=?) "
                "ORDER BY (priority + CAST((julianday(?) - julianday(created_at)) * ? AS INTEGER)) DESC,created_at ASC LIMIT 1",
                (now(), now(), AGING_POINTS_PER_DAY),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE jobs SET status='claimed',updated_at=? WHERE job_id=?",
                (now(), row["job_id"]),
            )
            return dict(row)

    def defer(self, job_id: str, *, reason: str, actor: str = "worker") -> None:
        """Delay one job so the local operator receives no repeated popup burst."""
        next_at = (datetime.now(UTC) + timedelta(minutes=DEFER_MINUTES)).isoformat()
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status='awaiting_approval',next_attempt_at=?,updated_at=?,error=? WHERE job_id=?",
                (next_at, now(), reason, job_id),
            )
        self.audit(actor, "job_deferred", job_id, {"reason": reason, "next_attempt_at": next_at})

    def grant(self, *, scope: str, actor: str, job_id: str | None = None) -> str:
        """Record explicit, revocable permission for one job or a bounded class."""
        if scope not in {"job", "trusted_academic_open_content"}:
            raise ValueError("Invalid GPU permission scope")
        if scope == "job" and not job_id:
            raise ValueError("Job scope requires a job ID")
        grant_id = str(uuid4())
        expiry = (datetime.now(UTC) + timedelta(hours=CLASS_GRANT_HOURS)).isoformat()
        with self._connect() as db:
            db.execute(
                "INSERT INTO grants(grant_id,scope,job_id,expires_at,actor,created_at) VALUES(?,?,?,?,?,?)",
                (grant_id, scope, job_id, expiry, actor, now()),
            )
        self.audit(
            actor,
            "gpu_grant_created",
            grant_id,
            {"scope": scope, "job_id": job_id, "expires_at": expiry},
        )
        return grant_id

    def revoke(self, grant_id: str, actor: str) -> bool:
        """Revoke a GPU grant immediately."""
        with self._connect() as db:
            changed = db.execute(
                "UPDATE grants SET revoked_at=? WHERE grant_id=? AND revoked_at IS NULL",
                (now(), grant_id),
            ).rowcount
        if changed:
            self.audit(actor, "gpu_grant_revoked", grant_id, {})
        return bool(changed)

    def has_grant(self, job_id: str) -> bool:
        """Check the current job or trusted open-content class permission."""
        with self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM grants WHERE revoked_at IS NULL AND expires_at>? "
                "AND ((scope='job' AND job_id=?) OR scope='trusted_academic_open_content') LIMIT 1",
                (now(), job_id),
            ).fetchone()
        return row is not None

    def retry(self, job_id: str, error: str) -> str:
        """Apply bounded exponential backoff; exhaust into a review queue."""
        with self._connect() as db:
            row = db.execute("SELECT attempts FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            attempts = int(row["attempts"]) + 1
            status = "dead_letter" if attempts >= MAX_RETRIES else "awaiting_approval"
            next_at = (
                datetime.now(UTC) + timedelta(seconds=RETRY_BASE_SECONDS * (2 ** (attempts - 1)))
            ).isoformat()
            db.execute(
                "UPDATE jobs SET attempts=?,status=?,next_attempt_at=?,updated_at=?,error=? WHERE job_id=?",
                (attempts, status, next_at, now(), error[:500], job_id),
            )
        self.audit(
            "worker",
            "job_retry" if status != "dead_letter" else "job_dead_letter",
            job_id,
            {"attempts": attempts, "error": error[:500]},
        )
        return status

    def set_mode(self, job_id: str, mode: str) -> None:
        """Persist the local operator's CPU selection for restart safety."""
        if mode != "cpu":
            raise ValueError("Only CPU fallback is set through this transition")
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET mode='cpu',status='cpu_requested',updated_at=? WHERE job_id=?",
                (now(), job_id),
            )
        self.audit("local_operator", "job_cpu_requested", job_id, {})

    def recover_stale(self) -> int:
        """Return interrupted claims to the bounded retry path after restart."""
        cutoff = (datetime.now(UTC) - timedelta(hours=STALE_JOB_HOURS)).isoformat()
        with self._connect() as db:
            rows = [
                str(row[0])
                for row in db.execute(
                    "SELECT job_id FROM jobs WHERE status IN ('claimed','running') AND updated_at<?",
                    (cutoff,),
                )
            ]
        for job_id in rows:
            self.retry(job_id, "Worker stopped before checkpoint completion")
        return len(rows)
