"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional
from archipelago.graph.engine import KuzuGraphEngine
from . import _deps as _rt  # noqa: F401


def _copy_db(src: Path, dest: Path) -> None:
    """Copy a Kùzu database that may be either a single file (0.11+) or a directory."""
    if dest.exists():
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)


def clone_production_to_staging(*, force: bool = False) -> Path:
    """Clone production okf_graph.db onto the staging path. ``force`` replaces any existing staging copy."""
    if not _rt.PROD_DB_PATH.exists():
        raise FileNotFoundError(f"Production database missing: {_rt.PROD_DB_PATH}")
    if force or not _rt.STAGING_DB_PATH.exists():
        _rt.logger.info("Cloning production database %s -> %s for staging...", _rt.PROD_DB_PATH, _rt.STAGING_DB_PATH)
        _copy_db(_rt.PROD_DB_PATH, _rt.STAGING_DB_PATH)
    return _rt.STAGING_DB_PATH


def ensure_staging_db() -> Path:
    """Ensure okf_graph_staging.db exists as a faithful snapshot of production okf_graph.db."""
    if _rt.STAGING_DB_PATH.exists():
        return _rt.STAGING_DB_PATH
    if _rt.PROD_DB_PATH.exists():
        return clone_production_to_staging(force=True)
    return _rt.STAGING_DB_PATH


def count_concepts(db_path: Path | str) -> int:
    """Return Concept node count for a Kùzu database path."""
    try:
        engine = KuzuGraphEngine(db_path=db_path, read_only=True)
        try:
            n = engine.conn.execute("MATCH (c:Concept) RETURN count(c);").get_as_df().iloc[0, 0]
            return int(n)
        finally:
            engine.close()
    except Exception as exc:
        _rt.logger.warning("count_concepts kuzu failed on %s (%s); falling back to JSON stats", db_path, exc)
        if _rt.DATA_FILE.exists():
            data = json.loads(_rt.DATA_FILE.read_text(encoding="utf-8"))
            return int((data.get("stats") or {}).get("total_concepts") or len(
                (data.get("visualization") or {}).get("nodes") or []
            ))
        raise


def export_graph_json(db_path: Path | str, data_file: Path | str = _rt.DATA_FILE) -> dict[str, Any]:
    """Serialize concepts/edges from ``db_path`` into okf_graph.json (label + name)."""
    db_path = Path(db_path)
    data_file = Path(data_file)
    engine = KuzuGraphEngine(db_path=db_path, read_only=True)
    try:
        nodes: list[dict[str, Any]] = []
        try:
            res_nodes = engine.conn.execute(
                "MATCH (c:Concept) RETURN c.id, c.name, c.concept_type, c.difficulty, c.summary, c.tags"
            )
            while res_nodes.has_next():
                row = res_nodes.get_next()
                name = row[1] or row[0]
                tags_raw = row[5] or ""
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
                nodes.append({
                    "id": row[0],
                    "label": name,
                    "name": name,
                    "concept_type": row[2],
                    "difficulty": row[3],
                    "summary": row[4],
                    "tags": tags,
                })
        except Exception:
            res_nodes = engine.conn.execute(
                "MATCH (c:Concept) RETURN c.id, c.name, c.concept_type, c.difficulty, c.summary"
            )
            while res_nodes.has_next():
                row = res_nodes.get_next()
                name = row[1] or row[0]
                nodes.append({
                    "id": row[0],
                    "label": name,
                    "name": name,
                    "concept_type": row[2],
                    "difficulty": row[3],
                    "summary": row[4],
                })

        # Query chunk citations/sources via MENTIONS
        sources_by_concept = {}
        try:
            res_src = engine.conn.execute(
                "MATCH (d:Document)-[:HAS_CHUNK]->(chk:Chunk)-[:MENTIONS]->(c:Concept) "
                "RETURN c.id, d.id, chk.chunk_id, chk.page_number, chk.section_title, chk.text_passage"
            )
            while res_src.has_next():
                row = res_src.get_next()
                cid = row[0]
                if cid not in sources_by_concept:
                    sources_by_concept[cid] = []
                sources_by_concept[cid].append({
                    "doc_id": row[1],
                    "chunk_id": row[2],
                    "page_number": row[3],
                    "section_title": row[4] or "",
                    "text_passage": row[5] or "",
                })
        except Exception:
            pass

        for n in nodes:
            if n["id"] in sources_by_concept:
                n["sources"] = sources_by_concept[n["id"]]

        edges: list[dict[str, Any]] = []
        for rel_table in ["REQUIRES", "UNLOCKS", "RELATED"]:
            try:
                res_edges = engine.conn.execute(
                    f"MATCH (a:Concept)-[r:{rel_table}]->(b:Concept) RETURN a.id, b.id, r.relation_type, r.source"
                )
                while res_edges.has_next():
                    row = res_edges.get_next()
                    edges.append({
                        "from_id": row[0],
                        "to_id": row[1],
                        "relation": row[2] or rel_table.lower(),
                        "edge_type": rel_table,
                        "source": row[3] or "",
                    })
            except Exception:
                pass
    finally:
        engine.close()

    graph_data: dict[str, Any] = {}
    if data_file.exists():
        try:
            graph_data = json.loads(data_file.read_text(encoding="utf-8"))
        except Exception:
            graph_data = {}

    graph_data["stats"] = {"total_concepts": len(nodes), "total_edges": len(edges)}
    graph_data["visualization"] = {"nodes": nodes}
    graph_data["edges"] = edges
    data_file.write_text(json.dumps(graph_data, indent=2), encoding="utf-8")
    _rt.logger.info("Exported %s (%d nodes, %d edges) from %s", data_file, len(nodes), len(edges), db_path)
    return graph_data


def _post_inference(url: str, timeout: int = 90) -> dict[str, Any] | None:
    import urllib.request

    req = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            _rt.logger.info("Inference POST %s -> %s", url, body)
            try:
                return json.loads(body)
            except Exception:
                return {"raw": body}
    except Exception as exc:
        _rt.logger.warning("Could not notify inference server (%s): %s", url, exc)
        return None


def notify_inference_close() -> dict[str, Any] | None:
    """Drop the live inference Kùzu handle so os.replace is not EBUSY."""
    url = _rt.INFERENCE_RELOAD_URL.replace("/reload-graph", "/close-graph")
    return _post_inference(url, timeout=30)


def notify_inference_reload(*, embeddings_only: bool = False) -> dict[str, Any] | None:
    """Ask the live inference process to rebuild embeddings / reopen Kùzu."""
    url = _rt.INFERENCE_RELOAD_URL
    if embeddings_only:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}embeddings_only=1"
    return _post_inference(url)


def sync_embeddings_from_db(db_path: Path | str) -> None:
    """Write JSON from ``db_path`` then rebuild the arctic-embed concept cache.

    Prefers the live inference process (already has the embedder loaded) so the
    ingest worker does not double-load Snowflake weights onto the 4 GB GPU.
    """
    export_graph_json(db_path, _rt.DATA_FILE)
    notified = notify_inference_reload(embeddings_only=True)
    if notified:
        return
    os.environ.setdefault("ARCHIPELAGO_FORCE_CPU_EMBED", "1")
    from archipelago.inference.embeddings import build_concept_embeddings
    build_concept_embeddings()


_librarian_worker = _rt.LibrarianWorker()


_librarian_worker.start()


def start_upload_job(
    file_bytes: bytes,
    filename: str,
    title: str,
    author: str = "",
    isbn: str = "",
    domain: str = "Computer Science",
    auto_publish: bool = False,
) -> str:
    """Entrypoint: save upload and enqueue asynchronous librarian ingestion."""
    job_id = uuid.uuid4().hex[:12]
    safe_name = f"{job_id}_{re.sub(r'[^\w\.-]', '_', filename)}"
    upload_path = _rt.UPLOADS_DIR / safe_name
    upload_path.write_bytes(file_bytes)

    job = _rt.LibrarianJob(
        job_id=job_id,
        title=title or filename.rsplit(".", 1)[0],
        author=author or "Unknown Author",
        isbn=isbn or "N/A",
        domain=domain or "General Engineering",
        filename=filename,
        file_path=str(upload_path),
        status="queued",
        stage="QUEUED",
        auto_publish=auto_publish,
    )
    return _librarian_worker.enqueue(job)


def get_job_status(job_id: str) -> Optional[dict[str, Any]]:
    """Query progress and stage of a librarian ingestion job."""
    job = _librarian_worker.get_job(job_id)
    return job.to_dict() if job else None


def get_staging_review(job_id: Optional[str] = None) -> dict[str, Any]:
    """
    Retrieve newly staged entities and proposed edges awaiting librarian review.
    """
    ensure_staging_db()
    if not _rt.STAGING_DB_PATH.exists():
        return {
            "staging_available": False,
            "documents": [],
            "chunks": [],
            "concepts": [],
            "proposed_edges": [],
            "stats": {"total_concepts": 0, "total_edges": 0},
        }

    engine = KuzuGraphEngine(db_path=_rt.STAGING_DB_PATH, read_only=True)
    concepts = []
    edges = []
    documents = []

    try:
        # Check concepts with source librarian_upload or recent
        res_c = engine.conn.execute(
            "MATCH (c:Concept) RETURN c.id, c.name, c.concept_type, c.difficulty, c.summary LIMIT 200;"
        )
        while res_c.has_next():
            row = res_c.get_next()
            concepts.append({
                "id": row[0],
                "name": row[1],
                "concept_type": row[2],
                "difficulty": row[3],
                "summary": row[4],
            })

        for _rel_table in ["REQUIRES", "UNLOCKS", "RELATED"]:
            try:
                res_e = engine.conn.execute(
                    f"MATCH (a:Concept)-[r:{_rel_table}]->(b:Concept) "
                    f"RETURN a.id, b.id, a.name, b.name, r.relation_type, r.source LIMIT 200;"
                )
                while res_e.has_next():
                    row = res_e.get_next()
                    edges.append({
                        "from_id": row[0],
                        "to_id": row[1],
                        "from_name": row[2],
                        "to_name": row[3],
                        "relation": row[4] or _rel_table.lower(),
                        "edge_type": _rel_table,
                        "source": row[5] or "librarian_upload",
                    })
            except Exception:
                pass

        res_d = engine.conn.execute("MATCH (d:Document) RETURN d.id, d.title, d.pdf_url LIMIT 50;")
        while res_d.has_next():
            row = res_d.get_next()
            documents.append({"id": row[0], "title": row[1], "pdf_url": row[2]})

    except Exception as exc:
        _rt.logger.warning("Error reading staging review: %s", exc)
    finally:
        engine.close()

    # If specific job requested, filter staged entities by job
    if job_id:
        job = _librarian_worker.get_job(job_id)
        if job and job.staged_entities:
            return {
                "staging_available": True,
                "job_id": job_id,
                "status": job.status,
                "documents": job.staged_entities.get("documents", []),
                "chunks": job.staged_entities.get("chunks", []),
                "concepts": job.staged_entities.get("concepts", []),
                "proposed_edges": job.staged_entities.get("edges", []),
                "stats": {
                    "total_concepts": len(job.staged_entities.get("concepts", [])),
                    "total_edges": len(job.staged_entities.get("edges", [])),
                },
            }

    return {
        "staging_available": True,
        "documents": documents,
        "concepts": concepts,
        "proposed_edges": edges,
        "stats": {"total_concepts": len(concepts), "total_edges": len(edges)},
    }
