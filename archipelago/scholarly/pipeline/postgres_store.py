"""Canonical PostgreSQL storage for resumable research jobs."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any
import uuid

from archipelago.scholarly.contracts.okf_models import PaperRecord
from archipelago.scholarly.discovery.live_sources import SourceResponse
from archipelago.scholarly.pipeline.postgres_projection import PostgresResearchProjectionMixin
from archipelago.scholarly.pipeline.postgres_store_constants import (
    PIPELINE_VERSION,
)
from archipelago.scholarly.pipeline.postgres_topics import PostgresResearchTopicsMixin

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DATABASE_ENV = "ARCHIPELAGO_RESEARCH_DATABASE_URL"


class StoreUnavailable(RuntimeError):
    """Research PostgreSQL is not configured or reachable."""


class IdentityConflict(RuntimeError):
    """Two established identifiers point to different canonical papers."""


class PostgresResearchStore(PostgresResearchTopicsMixin, PostgresResearchProjectionMixin):
    """Keep research state in a private PostgreSQL schema."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn: str = dsn if dsn is not None else os.getenv(DATABASE_ENV, "")
        if not self.dsn:
            raise StoreUnavailable(f"{DATABASE_ENV} is not configured")

    def _connect(self) -> Any:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise StoreUnavailable("PostgreSQL driver is unavailable") from exc
        try:
            return psycopg.connect(self.dsn, row_factory=dict_row)
        except psycopg.OperationalError as exc:
            raise StoreUnavailable("PostgreSQL driver or connection unavailable") from exc

    def initialize_schema(self) -> None:
        """Install the private schema explicitly during environment setup."""
        with self._connect() as conn:
            conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

    def create_job(
        self,
        *,
        user_id: str,
        role: str,
        topic: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Create one queued job per user and idempotency key."""
        job_id = uuid.uuid4()
        with self._connect() as conn:
            row = conn.execute(
                """INSERT INTO research_intelligence.jobs
                   (job_id, user_id, role, topic, idempotency_key, pipeline_version, status, stage)
                   VALUES (%s, %s, %s, %s, %s, %s, 'queued', 'QUEUED')
                   ON CONFLICT (user_id, idempotency_key)
                   DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
                   RETURNING job_id, user_id, role, topic, status, stage, pipeline_version,
                             counts, shortlist, created_at, updated_at""",
                (job_id, user_id, role, topic, idempotency_key, PIPELINE_VERSION),
            ).fetchone()
        return dict(row)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Fetch one job; callers must enforce owner or manager authorization."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT job_id, user_id, role, topic, pipeline_version, status,
                          stage, counts, shortlist, error, created_at, updated_at
                   FROM research_intelligence.jobs WHERE job_id = %s""",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None

    def claim_next(self) -> dict[str, Any] | None:
        """Claim one queued job atomically for a worker."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT job_id, topic, user_id, role FROM research_intelligence.jobs
                   WHERE status = 'queued' ORDER BY created_at
                   FOR UPDATE SKIP LOCKED LIMIT 1"""
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE research_intelligence.jobs
                       SET status = 'running', stage = 'SOURCE_DISCOVERY', updated_at = now()
                       WHERE job_id = %s""",
                    (row["job_id"],),
                )
        return dict(row) if row else None

    def resume_job(self, job_id: str) -> None:
        """Put an interrupted or failed job back on the queue."""
        with self._connect() as conn:
            conn.execute(
                """UPDATE research_intelligence.jobs
                   SET status = 'queued', updated_at = now()
                   WHERE job_id = %s AND status IN ('running', 'partial', 'failed')""",
                (job_id,),
            )

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        stage: str,
        counts: dict[str, int] | None = None,
        shortlist: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        """Persist a stage checkpoint without erasing earlier counts/results."""
        from psycopg.types.json import Jsonb

        with self._connect() as conn:
            conn.execute(
                """UPDATE research_intelligence.jobs
                   SET status = %s, stage = %s,
                       counts = COALESCE(%s, counts),
                       shortlist = COALESCE(%s, shortlist),
                       error = %s, updated_at = now()
                   WHERE job_id = %s""",
                (
                    status,
                    stage,
                    Jsonb(counts) if counts is not None else None,
                    Jsonb(shortlist) if shortlist is not None else None,
                    error,
                    job_id,
                ),
            )

    def save_source(self, job_id: str, response: SourceResponse) -> None:
        """Store actual raw bytes and their response hash privately."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO research_intelligence.source_snapshots
                   (job_id, source, requested_at, status, response_sha256, response_body,
                    request_id, http_status, record_count, error)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (job_id, source) DO UPDATE SET
                     requested_at = EXCLUDED.requested_at, status = EXCLUDED.status,
                     response_sha256 = EXCLUDED.response_sha256,
                     response_body = EXCLUDED.response_body,
                     request_id = EXCLUDED.request_id, http_status = EXCLUDED.http_status,
                     record_count = EXCLUDED.record_count, error = EXCLUDED.error""",
                (
                    job_id,
                    response.source,
                    response.requested_at,
                    response.status,
                    response.raw_sha256,
                    response.raw_body,
                    response.request_id,
                    response.http_status,
                    len(response.records),
                    response.error,
                ),
            )

    def source_summaries(self, job_id: str) -> list[dict[str, Any]]:
        """Read source provenance without returning raw response bodies."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT source, requested_at, status, response_sha256,
                          request_id, http_status, record_count, error
                   FROM research_intelligence.source_snapshots WHERE job_id = %s
                   ORDER BY source""",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def source_payload(self, job_id: str, source: str) -> dict[str, Any] | None:
        """Load a previous successful response for idempotent job resume."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT source, requested_at, status, response_sha256,
                          response_body, request_id, http_status
                   FROM research_intelligence.source_snapshots
                   WHERE job_id = %s AND source = %s""",
                (job_id, source),
            ).fetchone()
        return dict(row) if row else None

    def save_paper(self, job_id: str, item: dict[str, Any]) -> None:
        """Upsert canonical metadata and the job-specific validation state."""
        from psycopg.types.json import Jsonb

        paper = item["paper"]
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO research_intelligence.papers (paper_id, paper)
                   VALUES (%s, %s)
                   ON CONFLICT (paper_id) DO UPDATE
                   SET paper = (research_intelligence.papers.paper || EXCLUDED.paper)
                     || jsonb_build_object(
                          'identifiers',
                          COALESCE(research_intelligence.papers.paper->'identifiers', '{}'::jsonb)
                          || COALESCE(EXCLUDED.paper->'identifiers', '{}'::jsonb)
                        ),
                       updated_at = now()""",
                (
                    paper.paper_id,
                    Jsonb(paper.model_dump(mode="json", exclude_none=True, exclude_defaults=True)),
                ),
            )
            for kind, value in self._identifier_pairs(paper):
                conn.execute(
                    """INSERT INTO research_intelligence.paper_identifiers
                       (kind, value, paper_id) VALUES (%s, %s, %s)
                       ON CONFLICT (kind, value) DO NOTHING""",
                    (kind, value, paper.paper_id),
                )
                owner = conn.execute(
                    """SELECT paper_id FROM research_intelligence.paper_identifiers
                       WHERE kind = %s AND value = %s""",
                    (kind, value),
                ).fetchone()
                if str(owner["paper_id"]) != paper.paper_id:
                    raise IdentityConflict("Identifier was claimed by another paper")
            conn.execute(
                """INSERT INTO research_intelligence.job_papers
                   (job_id, paper_id, pipeline_state, access_state, identity_review, merge_history)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (job_id, paper_id) DO UPDATE SET
                     pipeline_state = EXCLUDED.pipeline_state,
                     access_state = EXCLUDED.access_state,
                     identity_review = EXCLUDED.identity_review,
                     merge_history = EXCLUDED.merge_history""",
                (
                    job_id,
                    paper.paper_id,
                    item.get("pipeline_state", "METADATA_VALIDATED"),
                    item.get("access_state", "METADATA_ONLY"),
                    Jsonb(item.get("identity_review", [])),
                    Jsonb(item.get("merge_history", [])),
                ),
            )

    def resolve_identity(self, paper: PaperRecord) -> str:
        """Reuse a PostgreSQL paper ID for known exact identifiers."""
        with self._connect() as conn:
            found: set[str] = set()
            for kind, value in self._identifier_pairs(paper):
                row = conn.execute(
                    """SELECT paper_id FROM research_intelligence.paper_identifiers
                       WHERE kind = %s AND value = %s""",
                    (kind, value),
                ).fetchone()
                if row:
                    found.add(str(row["paper_id"]))
            if len(found) > 1:
                raise IdentityConflict("Exact identifiers map to different papers")
            if found:
                owner = next(iter(found))
                existing = conn.execute(
                    """SELECT paper->'identifiers' AS identifiers
                       FROM research_intelligence.papers WHERE paper_id = %s""",
                    (owner,),
                ).fetchone()
                known = existing["identifiers"] or {} if existing else {}
                for kind, value in self._identifier_pairs(paper):
                    prior = known.get(kind)
                    normalized_prior = str(prior).lower().strip() if prior else ""
                    if kind == "arxiv_id":
                        normalized_prior = re.sub(r"v\d+$", "", normalized_prior)
                    if prior and normalized_prior != value:
                        raise IdentityConflict("New source conflicts with established identifier")
        return next(iter(found), paper.paper_id)

    @staticmethod
    def _identifier_pairs(paper: PaperRecord) -> list[tuple[str, str]]:
        ids = paper.identifiers
        return [
            (
                kind,
                re.sub(r"v\d+$", "", str(value).lower().strip())
                if kind == "arxiv_id"
                else str(value).lower().strip(),
            )
            for kind, value in (
                ("doi", ids.doi),
                ("arxiv_id", ids.arxiv_id),
                ("openalex_id", ids.openalex_id),
                ("semantic_scholar_id", ids.semantic_scholar_id),
            )
            if value
        ]

    def save_features(self, job_id: str, paper_id: str, features: list[Any]) -> None:
        """Upsert typed feature observations and derivation inputs."""
        from psycopg.types.json import Jsonb

        with self._connect() as conn:
            for observation in features:
                conn.execute(
                    """INSERT INTO research_intelligence.feature_observations
                       (job_id, paper_id, feature_name, observation) VALUES (%s, %s, %s, %s)
                       ON CONFLICT (job_id, paper_id, feature_name) DO UPDATE
                       SET observation = EXCLUDED.observation""",
                    (
                        job_id,
                        paper_id,
                        observation.feature_name,
                        Jsonb(observation.model_dump(mode="json")),
                    ),
                )

    def get_features(self, job_id: str, paper_id: str) -> list[dict[str, Any]]:
        """Read observations for an authorized job and paper."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT observation FROM research_intelligence.feature_observations
                   WHERE job_id = %s AND paper_id = %s ORDER BY feature_name""",
                (job_id, paper_id),
            ).fetchall()
        return [row["observation"] for row in rows]

    def job_has_paper(self, job_id: str, paper_id: str) -> bool:
        """Check that a paper belongs to the authorized job."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT 1 FROM research_intelligence.job_papers
                   WHERE job_id = %s AND paper_id = %s""",
                (job_id, paper_id),
            ).fetchone()
        return row is not None

    def audit(
        self,
        *,
        user_id: str | None,
        role: str | None,
        action: str,
        result: str,
        job_id: str | None = None,
        topic: str | None = None,
    ) -> None:
        """Store an immutable privileged-action audit row."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO research_intelligence.audit
                   (user_id, role, action, research_job_id, topic, result)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, role, action, job_id, topic, result),
            )

    def enqueue_projection(self, job_id: str) -> None:
        """Queue a rebuild after canonical records are committed."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO research_intelligence.projection_events (event_key)
                   VALUES (%s) ON CONFLICT (event_key) DO NOTHING""",
                (f"research-job:{job_id}",),
            )
