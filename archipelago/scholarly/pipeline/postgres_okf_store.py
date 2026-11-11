"""Persistence for complete structured OKF paper outputs."""

from __future__ import annotations

from typing import Any


class PostgresOKFStoreMixin:
    """Attach versioned OKF JSON to an existing research job and paper."""

    def _connect(self) -> Any:
        """Return a PostgreSQL connection supplied by the concrete store."""
        raise NotImplementedError

    def save_okf_record(self, job_id: str, paper_id: str, record: dict[str, Any]) -> None:
        """Persist one complete paper object; initialize the additive table once."""
        from psycopg.types.json import Jsonb

        with self._connect() as conn:
            if not getattr(self, "_okf_schema_ready", False):
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS research_intelligence.okf_paper_records (
                           job_id uuid NOT NULL REFERENCES research_intelligence.jobs(job_id),
                           paper_id uuid NOT NULL REFERENCES research_intelligence.papers(paper_id),
                           okf_version text NOT NULL,
                           record jsonb NOT NULL,
                           updated_at timestamptz NOT NULL DEFAULT now(),
                           PRIMARY KEY (job_id, paper_id))"""
                )
                conn.execute(
                    "ALTER TABLE research_intelligence.okf_paper_records ENABLE ROW LEVEL SECURITY"
                )
            conn.execute(
                """INSERT INTO research_intelligence.okf_paper_records
                   (job_id, paper_id, okf_version, record) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (job_id, paper_id) DO UPDATE SET
                     okf_version = EXCLUDED.okf_version,
                     record = EXCLUDED.record,
                     updated_at = now()""",
                (job_id, paper_id, record["okf_version"], Jsonb(record)),
            )
        self._okf_schema_ready = True

    def get_okf_record(self, job_id: str, paper_id: str) -> dict[str, Any] | None:
        """Load the persisted OKF JSON for an authorized job and paper."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT record FROM research_intelligence.okf_paper_records
                   WHERE job_id = %s AND paper_id = %s""",
                (job_id, paper_id),
            ).fetchone()
        return row["record"] if row else None
