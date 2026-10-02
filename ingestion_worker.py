"""
ingestion_worker.py — Background worker thread and GraphLock reader-writer lock
for safe live ingestion.
"""

import json
import os
import shutil
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from okf.config import BASE_DIR
from okf.exports import export_vis_json

# NOTE: `run_pipeline_staged` / `PipelineAborted` are deliberately NOT imported
# here. The job-processing code moved to `ingestion_worker_job_mixin`, which
# imports them itself; re-importing them into this module left the documented
# test patch targets (`patch("ingestion_worker.run_pipeline_staged")`) pointing
# at a name the worker never calls, so mocked pipeline runs silently executed
# the real one.
from ingestion_jobs import JobStatus, JobStore

from ingestion_worker_job_mixin import JobProcessingMixin


# ---------------------------------------------------------------------------
# GraphLock (Reader-Writer Lock)
# ---------------------------------------------------------------------------

class GraphLock:
    """
    A readers-writer lock to allow concurrent reads of the graph database while
    ensuring exclusive access for writes (database swaps and embedding updates).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._readers = 0
        self._writers_waiting = 0
        self._writer_active = False

    @contextmanager
    def read_lock(self):
        with self._cond:
            while self._writer_active or self._writers_waiting > 0:
                self._cond.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._cond:
                self._readers -= 1
                if self._readers == 0:
                    self._cond.notify_all()

    @contextmanager
    def write_lock(self):
        with self._cond:
            self._writers_waiting += 1
            while self._writer_active or self._readers > 0:
                self._cond.wait()
            self._writers_waiting -= 1
            self._writer_active = True
        try:
            yield
        finally:
            with self._cond:
                self._writer_active = False
                self._cond.notify_all()


# Share one process lock between inference readers and the ingestion swap.
from archipelago.inference.graph_lock import graph_lock


# ---------------------------------------------------------------------------
# IngestionWorker
# ---------------------------------------------------------------------------

class IngestionWorker(threading.Thread, JobProcessingMixin):
    """
    A single-threaded background worker that processes ingestion jobs sequentially.
    """

    def __init__(self, job_store: JobStore, live_db_path: str = None, graph_lock: GraphLock = None):
        super().__init__(name="IngestionWorker", daemon=True)
        self.job_store = job_store
        self.live_db_path = live_db_path or str(BASE_DIR / "okf_graph.db")
        self.graph_lock = graph_lock or globals().get("graph_lock")
        self.queue = []
        self._stop_event = threading.Event()
        self._cond = threading.Condition()

    def enqueue(self, job_id: str):
        with self._cond:
            self.queue.append(job_id)
            self._cond.notify()

    def stop(self):
        self._stop_event.set()
        with self._cond:
            self._cond.notify()

    def _process_index_job(self, job_id: str, payload: dict) -> None:
        """Create schema-valid document/chunk/concept provenance for a submitted TOC."""
        import kuzu
        from ingestion_jobs import JobStatus
        from okf.graph.common import _create_schema, _kuzu_escape, _migrate_schema
        from okf.graph.ingest import ensure_concept
        from okf.util import create_concept_id

        doc_id = str(payload.get("doc_id") or "").strip()
        title = str(payload.get("title") or doc_id).strip()
        chapters = payload.get("chapters") or []
        if not doc_id or not isinstance(chapters, list) or not chapters:
            self.job_store.update_status(job_id, JobStatus.FAILED, error="doc_id and at least one chapter are required")
            return

        db = None
        conn = None
        try:
            from archipelago.graph.engine import KuzuGraphEngine
            from archipelago.graph.engine import _close_colocated_kuzu_handles

            with (self.graph_lock or graph_lock).write_lock():
                KuzuGraphEngine.close_all_for_path(self.live_db_path)
                _close_colocated_kuzu_handles()
                db = kuzu.Database(self.live_db_path)
                conn = kuzu.Connection(db)
                _create_schema(conn)
                _migrate_schema(conn)
                safe_doc_id = _kuzu_escape(doc_id)
                safe_title = _kuzu_escape(title)
                conn.execute(
                    f"MERGE (d:Document {{id: '{safe_doc_id}'}}) "
                    f"ON CREATE SET d.title = '{safe_title}' "
                    f"ON MATCH SET d.title = '{safe_title}'"
                )
                for index, chapter in enumerate(chapters, start=1):
                    chapter_title = str(
                        chapter.get("title", f"Chapter {index}") if isinstance(chapter, dict) else chapter
                    ).strip()[:300]
                    if not chapter_title:
                        continue
                    page_number = index
                    if isinstance(chapter, dict):
                        try:
                            page_number = max(1, int(chapter.get("page", chapter.get("page_number", index))))
                        except (TypeError, ValueError):
                            page_number = index
                    concept_id = create_concept_id(chapter_title)
                    ensure_concept(
                        conn,
                        concept_id,
                        chapter_title,
                        concept_type="topic",
                        difficulty="intermediate",
                        summary=f"Chapter topic from {title}",
                    )
                    chunk_id = f"{doc_id}_toc_{index}"
                    safe_chunk_id = _kuzu_escape(chunk_id)
                    safe_section = _kuzu_escape(chapter_title)
                    conn.execute(
                        f"MERGE (ch:Chunk {{id: '{safe_chunk_id}'}}) "
                        f"ON CREATE SET ch.chunk_id = '{safe_chunk_id}', ch.page_number = {page_number}, "
                        f"ch.section_title = '{safe_section}', ch.text_passage = '{safe_section}'"
                    )
                    conn.execute(
                        f"MATCH (d:Document {{id: '{safe_doc_id}'}}), (ch:Chunk {{id: '{safe_chunk_id}'}}) "
                        "MERGE (d)-[:HAS_CHUNK]->(ch)"
                    )
                    conn.execute(
                        f"MATCH (ch:Chunk {{id: '{safe_chunk_id}'}}), (c:Concept {{id: '{_kuzu_escape(concept_id)}'}}) "
                        "MERGE (ch)-[:MENTIONS]->(c)"
                    )

            from okf.graph.export import export_graph
            from okf.exports import build_graph_rag_index, build_visual_graph, write_all_artifacts

            graph_export = export_graph(conn)
            graph_export["visualization"] = build_visual_graph([], graph_export)
            graph_export["graph_rag_index"] = build_graph_rag_index([], graph_export)
            write_all_artifacts(graph_export, [], db, base_dir=BASE_DIR)

            if conn is not None:
                conn.close()
                conn = None
            if db is not None:
                db.close()
                db = None

            try:
                from archipelago.inference.state import reload_db
                reload_db()
            except Exception as reload_error:
                self.job_store.update_status(
                    job_id,
                    JobStatus.COMPLETE,
                    result={"doc_id": doc_id, "chapters": len(chapters), "mode": "toc_only", "reload_warning": str(reload_error)},
                )
                return
            self.job_store.update_status(
                job_id,
                JobStatus.COMPLETE,
                result={"doc_id": doc_id, "chapters": len(chapters), "mode": "toc_only"},
            )
        except Exception as exc:
            self.job_store.update_status(job_id, JobStatus.FAILED, error=str(exc))
            raise
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    def run(self):
        while not self._stop_event.is_set():
            job_id = None
            with self._cond:
                while not self.queue and not self._stop_event.is_set():
                    self._cond.wait()
                if self._stop_event.is_set():
                    break
                if self.queue:
                    job_id = self.queue.pop(0)

            if job_id:
                self._process_job(job_id)



# Module-level singletons
job_store = JobStore(BASE_DIR / "jobs")
worker = IngestionWorker(job_store)


def get_worker() -> IngestionWorker:
    """Get the active IngestionWorker thread, starting it if not alive."""
    global worker
    if not worker.is_alive():
        if getattr(worker, "_started", None) and worker._started.is_set():
            worker = IngestionWorker(job_store)
        worker.start()
    return worker
