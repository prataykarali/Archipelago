"""Reviewed evidence and rebuildable research projection records."""

from __future__ import annotations

from typing import Any


class PostgresResearchProjectionMixin:
    """Add projection and evidence-review operations to the canonical store."""

    def _connect(self) -> Any:
        """Return a PostgreSQL connection supplied by the concrete store."""
        raise NotImplementedError

    def save_evidence(
        self,
        paper_id: str,
        artifact_sha256: str,
        evidence: dict[str, Any],
        verification_state: str,
    ) -> None:
        """Persist provenance-bound extraction without asserting review success."""
        from psycopg.types.json import Jsonb

        with self._connect() as conn:
            conn.execute(
                """INSERT INTO research_intelligence.paper_evidence
                   (paper_id, artifact_sha256, evidence, verification_state)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (paper_id, artifact_sha256) DO UPDATE
                   SET evidence = EXCLUDED.evidence,
                       verification_state = EXCLUDED.verification_state""",
                (paper_id, artifact_sha256, Jsonb(evidence), verification_state),
            )

    def get_evidence(self, paper_id: str) -> list[dict[str, Any]]:
        """Read evidence records for an authorized paper."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT artifact_sha256, evidence, verification_state
                   FROM research_intelligence.paper_evidence WHERE paper_id = %s""",
                (paper_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def review_evidence(
        self, job_id: str, paper_id: str, artifact_sha256: str, *, approve: bool
    ) -> bool:
        """Publish only a provenance-checked extraction after staff adjudication."""
        state = "validated" if approve else "rejected"
        with self._connect() as conn:
            row = conn.execute(
                """UPDATE research_intelligence.paper_evidence
                   SET verification_state = %s
                   WHERE paper_id = %s AND artifact_sha256 = %s
                     AND verification_state = 'provenance_checked'
                     AND EXISTS (SELECT 1 FROM research_intelligence.job_papers
                                 WHERE job_id = %s AND paper_id = %s)
                   RETURNING paper_id""",
                (state, paper_id, artifact_sha256, job_id, paper_id),
            ).fetchone()
            if row is None:
                return False
            if approve:
                conn.execute(
                    """UPDATE research_intelligence.job_papers
                       SET pipeline_state = 'EVIDENCE_VALIDATED'
                       WHERE job_id = %s AND paper_id = %s""",
                    (job_id, paper_id),
                )
                count = conn.execute(
                    """SELECT count(DISTINCT jp.paper_id) AS total
                       FROM research_intelligence.job_papers jp
                       JOIN research_intelligence.paper_evidence pe
                         ON pe.paper_id = jp.paper_id
                       WHERE jp.job_id = %s AND pe.verification_state = 'validated'""",
                    (job_id,),
                ).fetchone()["total"]
                conn.execute(
                    """UPDATE research_intelligence.jobs
                       SET counts = jsonb_set(counts, '{evidence_validated}', to_jsonb(%s::int)),
                           updated_at = now()
                       WHERE job_id = %s""",
                    (count, job_id),
                )
            conn.execute(
                """INSERT INTO research_intelligence.projection_events (event_key)
                   VALUES (%s) ON CONFLICT (event_key) DO NOTHING""",
                (f"evidence-review:{paper_id}:{artifact_sha256}:{state}",),
            )
        return True

    def pending_projection_events(self) -> list[str]:
        """List outstanding generation requests."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT event_key FROM research_intelligence.projection_events
                   WHERE processed_at IS NULL ORDER BY created_at"""
            ).fetchall()
        return [str(row["event_key"]) for row in rows]

    def complete_projection_events(self, event_keys: list[str], output_path: str) -> None:
        """Acknowledge only events represented in a successful generation."""
        with self._connect() as conn:
            for event_key in event_keys:
                conn.execute(
                    """UPDATE research_intelligence.projection_events
                       SET processed_at = now(), output_path = %s, error = NULL
                       WHERE event_key = %s AND processed_at IS NULL""",
                    (output_path, event_key),
                )

    def projection_records(self) -> list[dict[str, Any]]:
        """Read only validated canonical records for a rebuildable projection."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT DISTINCT p.paper_id, p.paper
                   FROM research_intelligence.papers p
                   JOIN research_intelligence.job_papers jp ON jp.paper_id = p.paper_id
                   WHERE jp.pipeline_state IN
                     ('METADATA_VALIDATED', 'FULLTEXT_PARSED', 'EVIDENCE_VALIDATED')"""
            ).fetchall()
        return [dict(row) for row in rows]

    def projection_evidence(self) -> list[dict[str, Any]]:
        """Read evidence only when provenance verification passed."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT paper_id, artifact_sha256, evidence
                   FROM research_intelligence.paper_evidence
                   WHERE verification_state = 'validated'"""
            ).fetchall()
        return [dict(row) for row in rows]
