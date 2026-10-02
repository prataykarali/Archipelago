"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from okf.graph.common import (
    _DEFAULT_DB_PATH, _kuzu_escape, _kuzu_literal, _SCHEMA_DDL,
    _create_schema, _migrate_schema, logger, BASE_DIR,
)
from okf.util import create_concept_id
from . import _deps as _rt  # noqa: F401


def get_evidence_for_concept(conn=None, concept_name: str = None) -> list:
    """Module-level wrapper for GraphDB.get_evidence_for_concept.
    
    Can be called as:
      get_evidence_for_concept(conn, concept_name)
      get_evidence_for_concept(concept_name)  # uses default DB
    """
    actual_conn = _rt._get_conn(conn)
    if conn is not None and not _rt._is_connection(conn):
        concept_name = conn
    concept_id = create_concept_id(concept_name or "")
    safe_name = _kuzu_escape((concept_name or "").lower())
    evidence = []
    try:
        res = actual_conn.execute(f"""
            MATCH (doc:Document)-[:HAS_CHUNK]->(chk:Chunk)
                  -[:MENTIONS]->(c:Concept)
            WHERE c.id = '{concept_id}' OR lower(c.name) = '{safe_name}'
            {_rt._EVIDENCE_RETURN}
            ORDER BY doc.id, chk.page_number
        """)
        while res.has_next():
            evidence.append(_rt._row_to_evidence(res.get_next()))
    except Exception:
        pass
    return evidence


def get_evidence_for_edge(conn=None, source: str = None, target: str = None):
    """Module-level wrapper for GraphDB.get_evidence_for_edge.
    
    Can be called as:
      get_evidence_for_edge(conn, source, target)
      get_evidence_for_edge(source, target)  # uses default DB
    """
    if conn is not None and not _rt._is_connection(conn):
        target = source
        source = conn
        conn = None
    actual_conn = _rt._get_conn(conn)
    
    source_id = create_concept_id(source or "")
    target_id = create_concept_id(target or "")

    evidence = None

    # 1. Edge provenance: REQUIRES stores 'doc_id:chunk_id' in r.source.
    prov = ""
    for a, b in ((source_id, target_id), (target_id, source_id)):
        try:
            res = actual_conn.execute(f"""
                MATCH (a:Concept {{id: '{a}'}})
                      -[r:REQUIRES]->(b:Concept {{id: '{b}'}})
                RETURN r.source
            """)
            if res.has_next():
                prov = str(res.get_next()[0] or "")
                break
        except Exception:
            pass
    if prov and ":" in prov:
        doc_id, chunk_id = prov.rsplit(":", 1)
        if doc_id and chunk_id:
            safe_cid = _kuzu_escape(f"{doc_id}_{chunk_id}")
            try:
                res = actual_conn.execute(f"""
                    MATCH (doc:Document)-[:HAS_CHUNK]->
                          (chk:Chunk {{id: '{safe_cid}'}})
                    {_rt._EVIDENCE_RETURN}
                """)
                if res.has_next():
                    evidence = _rt._row_to_evidence(res.get_next())
            except Exception:
                pass

    # 2. Fall back to a chunk mentioning BOTH concepts.
    if evidence is None:
        try:
            res = actual_conn.execute(f"""
                MATCH (doc:Document)-[:HAS_CHUNK]->(chk:Chunk),
                      (chk)-[:MENTIONS]->(a:Concept {{id: '{source_id}'}}),
                      (chk)-[:MENTIONS]->(b:Concept {{id: '{target_id}'}})
                {_rt._EVIDENCE_RETURN}
                LIMIT 1
            """)
            if res.has_next():
                evidence = _rt._row_to_evidence(res.get_next())
        except Exception:
            pass

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
