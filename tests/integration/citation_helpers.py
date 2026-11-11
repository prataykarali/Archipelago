"""Graph contract helpers for citation correctness integration tests."""

from __future__ import annotations

import inspect
import json

import pytest

DOC_ID = "flow_matching_notes.pdf"
DOC_TITLE = "Flow Matching Lecture Notes"


# ── adaptive call helpers (signatures land with ENGINEER-1/2 work) ──────────


def _import_graph_db():
    try:
        import okf.graph_db as graph_db
    except Exception as exc:
        pytest.fail(f"okf.graph_db failed to import: {exc}")
    return graph_db


def _require(module, name):
    fn = getattr(module, name, None)
    if not callable(fn):
        pytest.fail(
            f"{module.__name__}.{name} is not implemented yet "
            f"(required by the Session 3 citation contract)"
        )
    return fn


def _call_adaptive(fn, conn, /, *args, **kwargs):
    """Call fn with kwargs filtered to its signature, passing conn if wanted.

    The contract fixes the field names but not whether functions take an
    explicit connection first argument (the existing okf.graph_db style) or
    manage one internally.
    """
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        params = None

    accepted = kwargs
    wants_conn = False
    if params is not None:
        has_var_kw = any(p.kind == p.VAR_KEYWORD for p in params.values())
        if not has_var_kw:
            accepted = {k: v for k, v in kwargs.items() if k in params}
        first = next(iter(params), "")
        wants_conn = first in ("conn", "connection", "db", "database")

    if wants_conn:
        return fn(conn, *args, **accepted)
    try:
        return fn(*args, **accepted)
    except TypeError:
        return fn(conn, *args, **accepted)


def _ensure_schema(graph_db, conn):
    """Prefer a schema helper from graph_db; otherwise create contract schema."""
    for name in ("create_schema", "ensure_schema", "init_schema", "setup_schema", "_create_schema"):
        fn = getattr(graph_db, name, None)
        if callable(fn):
            try:
                fn(conn)
                return
            except TypeError:
                pass

    statements = [
        """CREATE NODE TABLE Document (
               id STRING PRIMARY KEY,
               doc_hash STRING,
               page_count INT64,
               title STRING,
               edition STRING,
               page_label_map STRING
           )""",
        """CREATE NODE TABLE Chunk (
               id STRING PRIMARY KEY,
               chunk_id STRING,
               page_number INT64,
               section_title STRING,
               text_passage STRING,
               text_offset_start INT64,
               text_offset_end INT64,
               block_x DOUBLE,
               block_y DOUBLE,
               block_w DOUBLE,
               block_h DOUBLE
           )""",
        """CREATE NODE TABLE Concept (
               id STRING PRIMARY KEY,
               name STRING,
               concept_type STRING,
               difficulty STRING,
               summary STRING
           )""",
        "CREATE REL TABLE HAS_CHUNK (FROM Document TO Chunk)",
        "CREATE REL TABLE MENTIONS (FROM Chunk TO Concept)",
        "CREATE REL TABLE REQUIRES (FROM Concept TO Concept, relation_type STRING, source STRING)",
        "CREATE REL TABLE UNLOCKS (FROM Concept TO Concept, relation_type STRING, source STRING)",
        "CREATE REL TABLE RELATED (FROM Concept TO Concept, relation_type STRING, source STRING)",
    ]
    for stmt in statements:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # table already created by a graph_db-side helper


def _add_document(graph_db, conn, doc_id, page_count, page_label_map):
    add_document = _require(graph_db, "add_document")
    return _call_adaptive(
        add_document,
        conn,
        doc_id=doc_id,
        doc_hash=f"hash_{doc_id}",
        page_count=page_count,
        title=DOC_TITLE,
        edition="1st",
        page_label_map=json.dumps(page_label_map) if page_label_map else None,
    )


def _add_chunk(graph_db, conn, chunk):
    add_chunk = _require(graph_db, "add_chunk")
    result = _call_adaptive(
        add_chunk,
        conn,
        doc_id=chunk["doc_id"],
        chunk_id=chunk["chunk_id"],
        page_number=chunk["page_number"],
        section_title=chunk["section_title"],
        text=chunk["text"],
        text_passage=chunk["text"],
        text_offset_start=chunk["text_offset_start"],
        text_offset_end=chunk["text_offset_end"],
        block_x=chunk["block_x"],
        block_y=chunk["block_y"],
        block_w=chunk["block_w"],
        block_h=chunk["block_h"],
    )
    if isinstance(result, str) and result:
        return result
    return f"{chunk['doc_id']}_{chunk['chunk_id']}"


def _add_concept(conn, concept_id, name, summary):
    safe_name = name.replace("'", "\\'")
    safe_summary = summary.replace("'", "\\'")
    conn.execute(f"""
        MERGE (c:Concept {{id: '{concept_id}'}})
        ON CREATE SET c.name = '{safe_name}',
                      c.concept_type = 'definition',
                      c.difficulty = 'intermediate',
                      c.summary = '{safe_summary}'
    """)


def _link_mention(conn, chunk_db_id, concept_id):
    safe_chunk = chunk_db_id.replace("'", "\\'")
    conn.execute(f"""
        MATCH (ch:Chunk {{id: '{safe_chunk}'}}), (c:Concept {{id: '{concept_id}'}})
        MERGE (ch)-[:MENTIONS]->(c)
    """)


def _link_requires(conn, from_id, to_id, source):
    conn.execute(f"""
        MATCH (a:Concept {{id: '{from_id}'}}), (b:Concept {{id: '{to_id}'}})
        MERGE (a)-[r:REQUIRES]->(b)
        ON CREATE SET r.relation_type = 'requires', r.source = '{source}'
    """)


def _get_evidence_for_concept(graph_db, conn, concept_name):
    fn = _require(graph_db, "get_evidence_for_concept")
    evidence = _call_adaptive(fn, conn, concept_name)
    assert isinstance(evidence, list), (
        f"get_evidence_for_concept must return a list of dicts, got {type(evidence)}"
    )
    return evidence


def _walk_citation_records(obj, out):
    """Collect dicts that look like emitted citation/evidence records."""
    if isinstance(obj, dict):
        keys = set(obj.keys())
        if "doc_id" in keys and ("chunk_id" in keys or "page_number" in keys):
            out.append(obj)
        for value in obj.values():
            _walk_citation_records(value, out)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _walk_citation_records(item, out)


def _resolve_chunk(conn, doc_id, chunk_id):
    """Fetch the real chunk row (doc, chunk_id, page, text) or None."""
    safe_doc = str(doc_id).replace("'", "\\'")
    safe_chunk = str(chunk_id).replace("'", "\\'")
    res = conn.execute(f"""
        MATCH (d:Document {{id: '{safe_doc}'}})-[:HAS_CHUNK]->(ch:Chunk)
        WHERE ch.chunk_id = '{safe_chunk}' OR ch.id = '{safe_chunk}'
        RETURN ch.chunk_id, ch.page_number, ch.text_passage, ch.section_title
    """)
    if res.has_next():
        row = res.get_next()
        return {
            "chunk_id": row[0],
            "page_number": int(row[1]) if row[1] is not None else None,
            "text": row[2],
            "section_title": row[3],
        }
    return None


# ── fixtures ─────────────────────────────────────────────────────────────────

CHUNKS = [
    {
        "doc_id": DOC_ID,
        "chunk_id": "chunk_p5",
        "page_number": 5,
        "section_title": "1. Background",
        "text": "Ordinary differential equations describe continuous change and underpin flow-based models.",
        "text_offset_start": 0,
        "text_offset_end": 93,
        "block_x": 72.0,
        "block_y": 100.0,
        "block_w": 450.0,
        "block_h": 60.0,
    },
    {
        "doc_id": DOC_ID,
        "chunk_id": "chunk_p6",
        "page_number": 6,
        "section_title": "2. Flow Matching",
        "text": "Flow matching trains a vector field by regressing onto conditional probability paths.",
        "text_offset_start": 93,
        "text_offset_end": 179,
        "block_x": 72.0,
        "block_y": 150.0,
        "block_w": 450.0,
        "block_h": 48.0,
    },
    {
        "doc_id": DOC_ID,
        "chunk_id": "chunk_p7",
        "page_number": 7,
        "section_title": "3. Applications",
        "text": "Diffusion transformers apply flow objectives at scale for image generation.",
        "text_offset_start": 179,
        "text_offset_end": 255,
        "block_x": 72.0,
        "block_y": 90.0,
        "block_w": 450.0,
        "block_h": 52.0,
    },
]

CONCEPTS = {
    "ordinary_differential_equations": {
        "name": "Ordinary Differential Equations",
        "summary": "Equations describing continuous change.",
        "chunk": "chunk_p5",
    },
    "flow_matching": {
        "name": "Flow Matching",
        "summary": "Training vector fields via conditional probability paths.",
        "chunk": "chunk_p6",
    },
    "diffusion_transformers": {
        "name": "Diffusion Transformers",
        "summary": "Scaled generative models using flow objectives.",
        "chunk": "chunk_p7",
    },
}
