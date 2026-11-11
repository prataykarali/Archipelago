"""Tracked-topic scheduling for official scholarly source refreshes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
import uuid

from archipelago.scholarly.pipeline.postgres_store_constants import (
    ACTIVE_REFRESH_HOURS,
    ACTIVE_TOPIC_DAYS,
    INACTIVE_REFRESH_HOURS,
    MAX_REFRESH_HOURS,
    MIN_REFRESH_HOURS,
    PIPELINE_VERSION,
    STALE_JOB_HOURS,
)


class PostgresResearchTopicsMixin:
    """Add topic refresh operations to a PostgreSQL-backed store."""

    def _connect(self) -> Any:
        """Return a PostgreSQL connection supplied by the concrete store."""
        raise NotImplementedError

    def requeue_stale_jobs(self) -> int:
        """Recover jobs abandoned by a worker crash after a bounded lease."""
        with self._connect() as conn:
            result = conn.execute(
                """UPDATE research_intelligence.jobs
                   SET status = 'queued', stage = 'QUEUED', updated_at = now()
                   WHERE status = 'running'
                     AND updated_at < now() - make_interval(hours => %s)""",
                (STALE_JOB_HOURS,),
            )
        return int(result.rowcount)

    def track_topic(self, *, user_id: str, role: str, topic: str) -> dict[str, Any]:
        """Track a staff topic for later automatic metadata refresh."""
        normalized = " ".join(topic.casefold().split())
        with self._connect() as conn:
            row = conn.execute(
                """INSERT INTO research_intelligence.tracked_topics
                   (topic_id, user_id, role, topic, normalized_topic)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (user_id, normalized_topic) DO UPDATE SET
                     last_searched_at = now(), updated_at = now()
                   RETURNING topic_id, topic, pinned, refresh_hours, next_refresh_at""",
                (uuid.uuid4(), user_id, role, topic, normalized),
            ).fetchone()
        return dict(row)

    def set_topic_refresh(self, topic_id: str, hours: int, pinned: bool) -> bool:
        """Change a tracked topic's schedule after manager authorization."""
        if not MIN_REFRESH_HOURS <= hours <= MAX_REFRESH_HOURS:
            raise ValueError("Refresh interval outside allowed range")
        with self._connect() as conn:
            result = conn.execute(
                """UPDATE research_intelligence.tracked_topics
                   SET refresh_hours = %s, pinned = %s,
                       next_refresh_at = now() + make_interval(hours => %s),
                       updated_at = now()
                   WHERE topic_id = %s""",
                (hours, pinned, hours, topic_id),
            )
        return bool(result.rowcount > 0)

    def enqueue_due_topics(self) -> int:
        """Queue due topics with daily active and weekly inactive defaults."""
        with self._connect() as conn:
            topics = conn.execute(
                """SELECT topic_id, user_id, role, topic, pinned, refresh_hours,
                          last_searched_at,
                          next_refresh_at
                   FROM research_intelligence.tracked_topics
                   WHERE next_refresh_at <= now()
                   FOR UPDATE SKIP LOCKED"""
            ).fetchall()
            for topic in topics:
                active = datetime.now(UTC) - topic["last_searched_at"] < timedelta(
                    days=ACTIVE_TOPIC_DAYS
                )
                hours = (
                    topic["refresh_hours"]
                    if topic["pinned"] and topic["refresh_hours"]
                    else ACTIVE_REFRESH_HOURS
                    if active
                    else INACTIVE_REFRESH_HOURS
                )
                key = f"tracked:{topic['topic_id']}:{topic['next_refresh_at'].isoformat()}"
                conn.execute(
                    """INSERT INTO research_intelligence.jobs
                       (job_id, user_id, role, topic, idempotency_key,
                        pipeline_version, status, stage)
                       VALUES (%s, %s, %s, %s, %s, %s, 'queued', 'QUEUED')
                       ON CONFLICT (user_id, idempotency_key) DO NOTHING""",
                    (
                        uuid.uuid4(),
                        topic["user_id"],
                        topic["role"],
                        topic["topic"],
                        key,
                        PIPELINE_VERSION,
                    ),
                )
                conn.execute(
                    """UPDATE research_intelligence.tracked_topics
                       SET next_refresh_at = now() + make_interval(hours => %s),
                           updated_at = now()
                       WHERE topic_id = %s""",
                    (hours, topic["topic_id"]),
                )
        return len(topics)
