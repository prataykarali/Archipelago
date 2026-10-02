"""Librarian manual graph API — conn-first concept and edge upserts.

Split out of ``okf/graph/ingest.py`` so every module stays under 400 lines.
Behaviour is unchanged; ``okf.graph.ingest`` re-exports these names.
"""
from __future__ import annotations

import logging

from okf.cleanup import is_valid_concept_name
from okf.graph.common import _kuzu_escape, logger
from okf.graph.export import enforce_dag
from okf.util import create_concept_id

# ── Module-level helpers for librarian manual API (conn-first) ──────────────

_RELATION_TO_TABLE = {
    "requires": ("REQUIRES", "requires"),
    "enables": ("UNLOCKS", "enables"),
    "uses": ("RELATED", "uses"),
    "extends": ("RELATED", "extends"),
    "part_of": ("RELATED", "part_of"),
    "contrasts_with": ("RELATED", "contrasts_with"),
    "evaluated_by": ("RELATED", "evaluated_by"),
}


def ensure_concept(
    conn,
    concept_id: str,
    name: str,
    concept_type: str = "definition",
    difficulty: str = "intermediate",
    summary: str = "",
    tags=None,
) -> str:
    """Upsert a Concept node. Used by librarian manual API and tests.

    Signature: ``ensure_concept(conn, concept_id, name, ...)``.
    Returns the concept id.
    """
    if not concept_id:
        concept_id = create_concept_id(name)
    safe_id = _kuzu_escape(concept_id)
    safe_name = _kuzu_escape(name or concept_id)
    safe_type = _kuzu_escape(concept_type or "definition")
    safe_diff = _kuzu_escape(difficulty or "intermediate")
    safe_summary = _kuzu_escape((summary or "")[:500])
    try:
        conn.execute(
            f"""
            MERGE (c:Concept {{id: '{safe_id}'}})
            ON CREATE SET c.name = '{safe_name}',
                          c.concept_type = '{safe_type}',
                          c.difficulty = '{safe_diff}',
                          c.summary = '{safe_summary}'
            ON MATCH SET c.name = '{safe_name}',
                         c.concept_type = '{safe_type}',
                         c.difficulty = '{safe_diff}',
                         c.summary = '{safe_summary}'
            """
        )
    except Exception as e:
        logger.warning("ensure_concept failed for %s: %s", concept_id, e)
        raise
    return concept_id


def create_edge(conn, from_id: str, to_id: str, relation: str, source: str = "manual:librarian") -> bool:
    """Create a structural edge between two concepts.

    ``relation`` is a librarian-facing name (requires/enables/uses/…).
    Maps to REQUIRES / UNLOCKS / RELATED tables.
    """
    if not from_id or not to_id or from_id == to_id:
        return False
    key = (relation or "").strip().lower()
    mapping = _RELATION_TO_TABLE.get(key)
    if not mapping:
        # Allow direct table names
        if key.upper() in ("REQUIRES", "UNLOCKS", "RELATED"):
            rel_table, rel_type = key.upper(), key.lower()
        else:
            raise ValueError(f"Unknown relation: {relation}")
    else:
        rel_table, rel_type = mapping

    if rel_table == "REQUIRES":
        # from requires to  => to is prereq of from; learn-order: to -> from
        enforce_dag(conn, to_id, from_id)
    elif rel_table == "UNLOCKS":
        enforce_dag(conn, from_id, to_id)

    safe_from = _kuzu_escape(from_id)
    safe_to = _kuzu_escape(to_id)
    safe_source = _kuzu_escape(source or "manual")
    safe_rel = _kuzu_escape(rel_type)
    try:
        conn.execute(
            f"""
            MATCH (a:Concept {{id: '{safe_from}'}}),
                  (b:Concept {{id: '{safe_to}'}})
            MERGE (a)-[r:{rel_table}]->(b)
            ON CREATE SET r.relation_type = '{safe_rel}', r.source = '{safe_source}'
            """
        )
        return True
    except Exception as e:
        logger.warning("create_edge failed %s %s->%s: %s", rel_table, from_id, to_id, e)
        raise
