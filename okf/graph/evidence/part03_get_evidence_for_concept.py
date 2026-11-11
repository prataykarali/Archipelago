"""Auto-split from monolith — blocks are verbatim."""

from __future__ import annotations

import logging
from typing import Any

from okf.graph.common import (
    _kuzu_escape,
)
from okf.query_rows import query_rows
from okf.util import create_concept_id

from . import _deps as _rt

logger = logging.getLogger(__name__)


def get_evidence_for_concept(
    conn: Any = None, concept_name: str | None = None
) -> list[dict[str, Any]]:
    """Module-level wrapper for GraphDB.get_evidence_for_concept.

    Can be called as:
      get_evidence_for_concept(conn, concept_name)
      get_evidence_for_concept(concept_name)  # uses default DB
    """
    actual_conn = _rt._get_conn(conn)
    if isinstance(conn, str) and not _rt._is_connection(conn):
        concept_name = conn
    concept_id = create_concept_id(concept_name or "")
    safe_name = _kuzu_escape((concept_name or "").lower())
    evidence: list[dict[str, Any]] = []
    try:
        for row in query_rows(
            actual_conn,
            f"""
            MATCH (doc:Document)-[:HAS_CHUNK]->(chk:Chunk)
                  -[:MENTIONS]->(c:Concept)
            WHERE c.id = '{concept_id}' OR lower(c.name) = '{safe_name}'
            {_rt._EVIDENCE_RETURN}
            ORDER BY doc.id, chk.page_number
        """,
        ):
            evidence.append(_rt._row_to_evidence(row))
    except Exception:
        logger.exception("Could not load concept evidence for %s", concept_name)
    return evidence


def get_evidence_for_edge(
    conn: Any = None, source: str | None = None, target: str | None = None
) -> dict[str, Any] | None:
    """Module-level wrapper for GraphDB.get_evidence_for_edge.

    Can be called as:
      get_evidence_for_edge(conn, source, target)
      get_evidence_for_edge(source, target)  # uses default DB
    """
    if isinstance(conn, str) and not _rt._is_connection(conn):
        target = source
        source = conn
        conn = None
    actual_conn = _rt._get_conn(conn)

    source_id = create_concept_id(source or "")
    target_id = create_concept_id(target or "")

    evidence: dict[str, Any] | None = None

    # 1. Edge provenance: REQUIRES stores 'doc_id:chunk_id' in r.source.
    prov = ""
    for a, b in ((source_id, target_id), (target_id, source_id)):
        try:
            rows = query_rows(
                actual_conn,
                f"""
                MATCH (a:Concept {{id: '{a}'}})
                      -[r:REQUIRES]->(b:Concept {{id: '{b}'}})
                RETURN r.source
            """,
            )
            first = next(rows, None)
            if first is not None:
                prov = str(first[0] or "")
                break
        except Exception:
            logger.debug("Could not load edge provenance", exc_info=True)
    if prov and ":" in prov:
        doc_id, chunk_id = prov.rsplit(":", 1)
        if doc_id and chunk_id:
            safe_cid = _kuzu_escape(f"{doc_id}_{chunk_id}")
            try:
                rows = query_rows(
                    actual_conn,
                    f"""
                    MATCH (doc:Document)-[:HAS_CHUNK]->
                          (chk:Chunk {{id: '{safe_cid}'}})
                    {_rt._EVIDENCE_RETURN}
                """,
                )
                first = next(rows, None)
                if first is not None:
                    evidence = _rt._row_to_evidence(first)
            except Exception:
                logger.debug("Could not load chunk evidence", exc_info=True)

    # 2. Fall back to a chunk mentioning BOTH concepts.
    if evidence is None:
        try:
            rows = query_rows(
                actual_conn,
                f"""
                MATCH (doc:Document)-[:HAS_CHUNK]->(chk:Chunk),
                      (chk)-[:MENTIONS]->(a:Concept {{id: '{source_id}'}}),
                      (chk)-[:MENTIONS]->(b:Concept {{id: '{target_id}'}})
                {_rt._EVIDENCE_RETURN}
                LIMIT 1
            """,
            )
            first = next(rows, None)
            if first is not None:
                evidence = _rt._row_to_evidence(first)
        except Exception:
            logger.debug("Could not load shared concept evidence", exc_info=True)

    # 3. Last resort: any chunk mentioning the source concept.
    if evidence is None:
        for_source = get_evidence_for_concept(actual_conn, source)
        if for_source:
            evidence = for_source[0]

    if evidence is None:
        return None
    evidence["source"] = source
    evidence["target"] = target
    return evidence
