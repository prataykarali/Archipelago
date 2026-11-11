"""Queries for identity, evidence, and feature report examples."""

from __future__ import annotations

from typing import Any

FEATURE_EXAMPLE_LIMIT = 3
EVIDENCE_EXAMPLE_LIMIT = 2
IDENTITY_EXAMPLE_LIMIT = 3


def _identity_examples(conn: Any, job_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT jp.paper_id, jp.merge_history, jp.identity_review, p.paper->'identifiers' AS ids,
                  p.paper->>'title' AS title
           FROM research_intelligence.job_papers jp
           JOIN research_intelligence.papers p ON p.paper_id = jp.paper_id
           WHERE jp.job_id = %s AND jsonb_array_length(jp.merge_history) > 0
           ORDER BY jsonb_array_length(jp.merge_history) DESC LIMIT %s""",
        (job_id, IDENTITY_EXAMPLE_LIMIT),
    ).fetchall()
    return [
        {
            "canonical_paper_id": str(row["paper_id"]),
            "title": row["title"],
            "identifiers": row["ids"],
            "source_records": len(row["merge_history"]) + 1,
            "dedup_decision": "MERGED",
            "merge_history": row["merge_history"],
            "identity_review": row["identity_review"],
        }
        for row in rows
    ]


def _evidence_examples(conn: Any, job_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT pe.paper_id, pe.artifact_sha256, pe.evidence, pe.verification_state
           FROM research_intelligence.paper_evidence pe
           JOIN research_intelligence.job_papers jp ON jp.paper_id = pe.paper_id
           WHERE jp.job_id = %s ORDER BY pe.verification_state, pe.paper_id""",
        (job_id,),
    ).fetchall()
    result = []
    for row in rows:
        extracted = row["evidence"]
        assertions = [
            *extracted.get("claims", []),
            *extracted.get("experiments", []),
            *extracted.get("results", []),
        ]
        if not assertions:
            continue
        assertion = assertions[0]
        pointers = {item["provenance_id"]: item for item in extracted.get("provenance", [])}
        result.append(
            {
                "paper_id": str(row["paper_id"]),
                "artifact_sha256": row["artifact_sha256"],
                "assertion": assertion,
                "evidence_pointers": [
                    pointers[identifier]
                    for identifier in assertion.get("provenance_ids", [])
                    if identifier in pointers
                ],
                "verification_state": row["verification_state"],
                "extractor_version": extracted.get("extractor_version"),
            }
        )
        if len(result) == EVIDENCE_EXAMPLE_LIMIT:
            break
    return result


def _feature_examples(
    conn: Any, job_id: str, shortlist: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for paper in shortlist[:FEATURE_EXAMPLE_LIMIT]:
        rows = conn.execute(
            """SELECT feature_name, observation
               FROM research_intelligence.feature_observations
               WHERE job_id = %s AND paper_id = %s ORDER BY feature_name""",
            (job_id, paper["paper_id"]),
        ).fetchall()
        result.append(
            {
                "paper_id": paper["paper_id"],
                "features": {row["feature_name"]: row["observation"] for row in rows},
            }
        )
    return result
