"""export.py — Kùzu graph submodule."""

from __future__ import annotations

import logging
from typing import Any

from okf.config import infer_source_category
from okf.query_rows import query_rows

logger = logging.getLogger(__name__)


def export_graph(conn: Any) -> dict[str, Any]:
    """Export the full graph structure to a dict, reconstructing concept sources from chunk relationships."""
    # Get concepts, documents, chunks, and their mentions
    rows = query_rows(
        conn,
        """
        MATCH (c:Concept)
        OPTIONAL MATCH (chk:Chunk)-[:MENTIONS]->(c)
        OPTIONAL MATCH (doc:Document)-[:HAS_CHUNK]->(chk)
        RETURN c.id, c.name, c.concept_type, c.difficulty, c.summary, doc.id, chk.chunk_id, chk.page_number, chk.section_title, chk.text_passage
        ORDER BY c.name
    """,
    )

    concepts: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = row[0]
        name = row[1]
        concept_type = row[2]
        difficulty = row[3]
        summary = row[4]

        doc_id = row[5]
        chunk_id = row[6]
        page_number = row[7]
        section_title = row[8]
        text_passage = row[9]

        if cid not in concepts:
            concepts[cid] = {
                "name": name,
                "concept_type": concept_type,
                "difficulty": difficulty,
                "summary": summary,
                "sources": [],
            }

        if doc_id:
            source_rec = {
                "doc_id": doc_id,
                "source_category": infer_source_category(doc_id),
                "chunk_id": chunk_id,
                "page_number": int(page_number) if page_number is not None else 0,
                "section_title": section_title,
                "text_passage": text_passage,
            }
            if source_rec not in concepts[cid]["sources"]:
                concepts[cid]["sources"].append(source_rec)

    # Get all edges
    edges: list[dict[str, Any]] = []
    for rel_table in ["REQUIRES", "UNLOCKS", "RELATED"]:
        try:
            for row in query_rows(
                conn,
                f"""
                MATCH (a:Concept)-[r:{rel_table}]->(b:Concept)
                RETURN a.id, a.name, r.relation_type, b.id, b.name, r.source
            """,
            ):
                edges.append(
                    {
                        "from_id": row[0],
                        "from_name": row[1],
                        "relation": row[2],
                        "to_id": row[3],
                        "to_name": row[4],
                        "source": row[5],
                        "edge_type": rel_table,
                    }
                )
        except Exception:
            logger.debug("Could not export %s edges", rel_table, exc_info=True)

    return {
        "concepts": concepts,
        "edges": edges,
        "stats": {
            "total_concepts": len(concepts),
            "total_edges": len(edges),
            "requires_edges": sum(1 for e in edges if e["edge_type"] == "REQUIRES"),
            "unlocks_edges": sum(1 for e in edges if e["edge_type"] == "UNLOCKS"),
            "related_edges": sum(1 for e in edges if e["edge_type"] == "RELATED"),
        },
    }


def enforce_dag(conn: Any, from_id: str, to_id: str) -> None:
    """Pre-check if adding a dependency edge from from_id to to_id creates a cycle.

    Raises ValueError if adding the edge creates a cycle.
    """
    if from_id == to_id:
        raise ValueError(f"Self-loop detected: {from_id} -> {to_id}")

    # 1. Fetch all REQUIRES and UNLOCKS edges
    adj: dict[str, set[str]] = {}

    # Fetch REQUIRES (a -REQUIRES-> b means b -> a dependency)
    try:
        for row in query_rows(conn, "MATCH (a:Concept)-[:REQUIRES]->(b:Concept) RETURN a.id, b.id"):
            u, v = row[1], row[0]
            adj.setdefault(u, set()).add(v)
    except Exception:
        logger.debug("Could not inspect REQUIRES edges for DAG check", exc_info=True)

    # Fetch UNLOCKS (a -UNLOCKS-> b means a -> b dependency)
    try:
        for row in query_rows(conn, "MATCH (a:Concept)-[:UNLOCKS]->(b:Concept) RETURN a.id, b.id"):
            u, v = row[0], row[1]
            adj.setdefault(u, set()).add(v)
    except Exception:
        logger.debug("Could not inspect UNLOCKS edges for DAG check", exc_info=True)

    # 2. Add the proposed edge: from_id -> to_id
    adj.setdefault(from_id, set()).add(to_id)

    # 3. Check if there is a cycle using BFS from to_id to find from_id
    visited = set()
    queue = [to_id]
    while queue:
        curr = queue.pop(0)
        if curr == from_id:
            raise ValueError(f"Adding dependency {from_id} -> {to_id} creates a cycle")
        if curr not in visited:
            visited.add(curr)
            for neighbor in adj.get(curr, []):
                if neighbor not in visited:
                    queue.append(neighbor)


def get_orphan_ratio(conn: Any) -> float:
    """Return the ratio of orphan concept nodes (nodes with no REQUIRES, UNLOCKS, or RELATED edges)."""
    total_row = next(query_rows(conn, "MATCH (c:Concept) RETURN count(c)"), None)
    total = int(total_row[0]) if total_row is not None else 0
    if total == 0:
        return 0.0
    orphan_row = next(
        query_rows(
            conn,
            "MATCH (c:Concept) WHERE NOT (c)-[:REQUIRES|UNLOCKS|RELATED]-(:Concept) RETURN count(c)",
        ),
        None,
    )
    orphans = int(orphan_row[0]) if orphan_row is not None else 0
    return float(orphans / total)


def get_edge_provenance(conn: Any, source_id: str, target_id: str) -> str:
    """Return the source provenance string of the edge between source_id and target_id."""
    for rel_table in ["REQUIRES", "UNLOCKS", "RELATED"]:
        try:
            row = next(
                query_rows(
                    conn,
                    f"""
                MATCH (a:Concept {{id: '{source_id}'}})-[r:{rel_table}]->(b:Concept {{id: '{target_id}'}})
                RETURN r.source
            """,
                ),
                None,
            )
            if row is not None:
                return str(row[0])
        except Exception:
            logger.debug("Could not read %s edge provenance", rel_table, exc_info=True)
    return ""
