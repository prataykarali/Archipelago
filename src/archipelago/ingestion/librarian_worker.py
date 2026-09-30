"""
Librarian Ingestion Worker & Staging DB Management Engine.

Provides asynchronous ingestion pipeline for librarian uploads:
1. Streams document to Hugging Face Hub (Prataykarali/Library_books).
2. Structural slicing with high-yield filtering (dropping front matter, TOC, bibliographies).
3. Grammar-constrained OKF concept extraction via fine-tuned lib-qwen on GPU.
4. Entity resolution & Kahn DAG Cycle Gate verification.
5. Populates okf_graph_staging.db.
6. Vector embedding precomputation before connection-safe atomic swap to okf_graph.db.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import kuzu

from archipelago.graph.engine import KuzuGraphEngine
from archipelago.graph.graph_fusion import GraphFusionEngine
from archipelago.ingestion.lib_qwen_extractor import (
    LibQwenConceptExtractor,
    canonical_concept_id,
    canonicalize_concept_name,
    is_negative_sample,
)
from archipelago.storage.hf_remote import HFStorageClient

logger = logging.getLogger("archipelago.ingestion.librarian_worker")

def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "okf_graph.json").exists() or (parent / "pyproject.toml").exists():
            return parent
    return here.parents[2]


BASE_DIR = _repo_root()
STAGING_DB_PATH = BASE_DIR / "okf_graph_staging.db"
PROD_DB_PATH = BASE_DIR / "okf_graph.db"
DATA_FILE = BASE_DIR / "okf_graph.json"
INFERENCE_RELOAD_URL = os.environ.get(
    "ARCHIPELAGO_INFERENCE_RELOAD_URL",
    "http://127.0.0.1:5151/api/internal/reload-graph",
)
JOBS_DIR = BASE_DIR / "jobs" / "librarian"
UPLOADS_DIR = BASE_DIR / "data" / "uploads"


@dataclass
class LibrarianJob:
    job_id: str
    title: str
    author: str
    isbn: str
    domain: str
    filename: str
    file_path: str
    status: str = "queued"
    stage: str = "QUEUED"
    chunks_processed: int = 0
    concepts_extracted: int = 0
    dag_status: str = "pending"
    error: Optional[str] = None
    hf_remote_path: Optional[str] = None
    staged_entities: dict[str, Any] = field(default_factory=lambda: {
        "documents": [],
        "chunks": [],
        "concepts": [],
        "edges": [],
    })
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    auto_publish: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LibrarianWorker(threading.Thread):
    """Asynchronous background worker processing librarian document uploads."""

    def __init__(self):
        super().__init__(name="LibrarianWorker", daemon=True)
        self.queue: queue.Queue[str] = queue.Queue()
        self.jobs: dict[str, LibrarianJob] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_persisted_jobs()

    def _load_persisted_jobs(self) -> None:
        """Load recent jobs from disk cache."""
        for jfile in JOBS_DIR.glob("*.json"):
            try:
                data = json.loads(jfile.read_text(encoding="utf-8"))
                job = LibrarianJob(**data)
                self.jobs[job.job_id] = job
            except Exception:
                pass

    def _save_job(self, job: LibrarianJob) -> None:
        """Persist job metadata to disk."""
        with self._lock:
            self.jobs[job.job_id] = job
        jfile = JOBS_DIR / f"{job.job_id}.json"
        try:
            jfile.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Could not persist job %s: %s", job.job_id, e)

    def enqueue(self, job: LibrarianJob) -> str:
        self._save_job(job)
        self.queue.put(job.job_id)
        return job.job_id

    def get_job(self, job_id: str) -> Optional[LibrarianJob]:
        with self._lock:
            return self.jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [j.to_dict() for j in self.jobs.values()]

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_id = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue

            job = self.get_job(job_id)
            if not job or job.status == "cancelled":
                self.queue.task_done()
                continue

            try:
                self._process_job(job)
            except Exception as exc:
                logger.error("Job %s failed with unhandled exception: %s", job_id, exc, exc_info=True)
                job.status = "failed"
                job.stage = "FAILED"
                job.error = str(exc)
                job.completed_at = time.time()
                self._save_job(job)
            finally:
                self.queue.task_done()

    def _process_job(self, job: LibrarianJob) -> None:
        job.status = "processing"
        job.stage = "HF_UPLOAD"
        self._save_job(job)

        local_file = Path(job.file_path)
        if not local_file.is_file():
            raise FileNotFoundError(f"Uploaded file not found: {local_file}")

        # ── Stage 1: Push to Hugging Face Remote Storage ───────────────────────
        hf_client = HFStorageClient()
        safe_name = re.sub(r"[^\w\.-]", "_", local_file.name)
        remote_rel_path = f"books/librarian_uploads/{safe_name}"
        try:
            logger.info("Uploading %s to HF dataset %s...", local_file, hf_client.repo_id)
            hf_res = hf_client.upload_file(
                local_path=local_file,
                remote_path=remote_rel_path,
                commit_message=f"Librarian upload: {job.title} ({job.isbn})",
            )
            job.hf_remote_path = remote_rel_path
            logger.info("HF remote push finished: %s", hf_res.get("mode"))
        except Exception as hf_err:
            logger.warning("HF upload warning (will continue locally): %s", hf_err)
            job.hf_remote_path = remote_rel_path

        # ── Stage 2: Slicing with High-Yield Structural Filtering ──────────────
        job.stage = "STRUCTURAL_SLICING"
        self._save_job(job)

        from archipelago.ingestion.pdf_io import ingest_document

        try:
            raw_chunks = ingest_document(str(local_file), max_pages=30)
        except Exception as slice_err:
            logger.warning("Universal chunker failed, falling back to basic text slice: %s", slice_err)
            raw_chunks = []

        # Filter out negative boilerplate samples
        valid_chunks = []
        for chk in raw_chunks:
            passage = chk.get("text_passage") or chk.get("text") or ""
            if not is_negative_sample(passage):
                valid_chunks.append(chk)

        job.chunks_processed = len(valid_chunks)
        self._save_job(job)

        # ── Stage 3: Grammar-Constrained OKF Extraction ────────────────────────
        job.stage = "SLM_EXTRACTION"
        self._save_job(job)

        extractor = LibQwenConceptExtractor(model_name="lib-qwen:latest")
        all_concepts = []

        for chk in valid_chunks[:15]:  # Process high-yield pedagogical sections
            text = chk.get("text_passage") or chk.get("text") or ""
            page = int(chk.get("page_number", 1))
            extracted = extractor.extract_from_chunk(
                text=text,
                book_title=job.title,
                page_number=page,
                domain=job.domain,
            )
            for c in extracted:
                c["chunk_id"] = chk.get("chunk_id") or f"chk_p{page}_{len(all_concepts)}"
                c["page_number"] = page
                all_concepts.append(c)

        # ── Stage 4: Canonical Resolution & Self-Loop Elimination ─────────────
        job.stage = "CANONICAL_RESOLVE"
        self._save_job(job)

        resolved_concepts = extractor.second_pass_relation_resolver(all_concepts)
        job.concepts_extracted = len(resolved_concepts)

        # ── Stage 5: Kahn DAG Cycle Gate ──────────────────────────────────────
        job.stage = "KAHN_DAG_GATE"
        self._save_job(job)

        # Initialize staging DB from production DB if not already present
        ensure_staging_db()

        fusion = GraphFusionEngine(db_path=STAGING_DB_PATH)
        staging_engine = KuzuGraphEngine(db_path=STAGING_DB_PATH, read_only=False)

        candidate_nodes = set()
        candidate_edges = set()
        for c in resolved_concepts:
            cid = c["id"]
            candidate_nodes.add(cid)
            for p in c.get("prerequisites", []):
                pid = p["id"] if isinstance(p, dict) else str(p)
                candidate_edges.add((cid, pid))
                candidate_nodes.add(pid)
            for u in c.get("unlocks", []):
                uid = u["id"] if isinstance(u, dict) else canonical_concept_id(canonicalize_concept_name(str(u)))
                if uid != cid:
                    candidate_edges.add((cid, uid))
                    candidate_nodes.add(uid)

        existing_nodes = set()
        existing_edges = set()
        try:
            res_n = staging_engine.conn.execute("MATCH (c:Concept) RETURN c.id")
            while res_n.has_next():
                existing_nodes.add(res_n.get_next()[0])
            res_e = staging_engine.conn.execute("MATCH (a:Concept)-[:REQUIRES]->(b:Concept) RETURN a.id, b.id")
            while res_e.has_next():
                row = res_e.get_next()
                existing_edges.add((row[0], row[1]))
        except Exception as e:
            logger.debug("Error reading staging graph topology: %s", e)

        is_dag, rejected_edges = fusion.validate_dag_kahn(
            existing_nodes=existing_nodes,
            existing_edges=existing_edges,
            new_nodes=candidate_nodes,
            new_edges=candidate_edges,
        )

        job.dag_status = "verified_acyclic" if is_dag else f"cycle_rejected ({len(rejected_edges)} rejected)"
        accepted_edges = candidate_edges - set(rejected_edges)

        # ── Stage 6: Staging DB Merge ──────────────────────────────────────────
        job.stage = "STAGING_MERGE"
        self._save_job(job)

        doc_id = f"upload_{job.job_id[:8]}"
        doc_hash = str(uuid.uuid5(uuid.NAMESPACE_DNS, job.title + job.filename))
        staged_docs = []
        staged_chunks = []
        staged_concepts_list = []
        staged_edges_list = []

        conn = staging_engine.conn

        # 1. Merge Document
        safe_title = job.title.replace("'", "''")
        safe_author = job.author.replace("'", "''")
        remote_url = job.hf_remote_path or f"books/librarian_uploads/{safe_name}"
        try:
            conn.execute(
                f"MERGE (d:Document {{id: '{doc_id}'}}) "
                f"ON CREATE SET d.title = '{safe_title}', d.doc_hash = '{doc_hash}', "
                f"d.page_count = {max(len(valid_chunks), 1)}, d.edition = '1', d.pdf_url = '{remote_url}'"
            )
            staged_docs.append({"id": doc_id, "title": job.title, "author": job.author, "pdf_url": remote_url})
        except Exception as exc:
            logger.warning("Could not merge staging Document %s: %s", doc_id, exc)

        # 2. Merge Chunks and HAS_CHUNK
        for chk in valid_chunks[:15]:
            p_num = int(chk.get("page_number", 1))
            sec_title = (chk.get("section_title") or f"Section p.{p_num}").replace("'", "''")
            passage = (chk.get("text_passage") or chk.get("text") or "")[:400].replace("'", "''")
            chunk_key = f"{doc_id}_p{p_num}_{len(staged_chunks)}"

            try:
                conn.execute(
                    f"MERGE (c:Chunk {{id: '{chunk_key}'}}) "
                    f"ON CREATE SET c.chunk_id = '{chunk_key}', c.page_number = {p_num}, "
                    f"c.section_title = '{sec_title}', c.text_passage = '{passage}'"
                )
                conn.execute(
                    f"MATCH (d:Document {{id: '{doc_id}'}}), (c:Chunk {{id: '{chunk_key}'}}) "
                    f"MERGE (d)-[:HAS_CHUNK]->(c)"
                )
                staged_chunks.append({"id": chunk_key, "page_number": p_num, "section_title": sec_title})
            except Exception as exc:
                logger.debug("Staging chunk insert notice: %s", exc)

        # 3. Merge Concepts and MENTIONS
        for c in resolved_concepts:
            cid = c["id"]
            cname = c["name"].replace("'", "''")
            ctype = c.get("concept_type", "definition")
            diff = c.get("difficulty", "intermediate")
            summ = (c.get("summary") or c.get("definition") or "").replace("'", "''")[:500]
            tags_str = ",".join(c.get("tags", [])).replace("'", "''")

            try:
                try:
                    conn.execute(
                        f"MERGE (con:Concept {{id: '{cid}'}}) "
                        f"ON CREATE SET con.name = '{cname}', con.concept_type = '{ctype}', "
                        f"con.difficulty = '{diff}', con.summary = '{summ}', con.tags = '{tags_str}'"
                    )
                except Exception:
                    conn.execute(
                        f"MERGE (con:Concept {{id: '{cid}'}}) "
                        f"ON CREATE SET con.name = '{cname}', con.concept_type = '{ctype}', "
                        f"con.difficulty = '{diff}', con.summary = '{summ}'"
                    )
                staged_concepts_list.append({
                    "id": cid,
                    "name": c["name"],
                    "concept_type": ctype,
                    "difficulty": diff,
                    "summary": c.get("summary", ""),
                })

                # Link Chunk -> Concept via MENTIONS using source page
                concept_page = c.get("page_number", 1)
                matched_chunk_id = None
                for sc in staged_chunks:
                    if sc.get("page_number") == concept_page:
                        matched_chunk_id = sc["id"]
                        break
                if not matched_chunk_id and staged_chunks:
                    matched_chunk_id = staged_chunks[0]["id"]
                if matched_chunk_id:
                    conn.execute(
                        f"MATCH (chk:Chunk {{id: '{matched_chunk_id}'}}), (con:Concept {{id: '{cid}'}}) "
                        f"MERGE (chk)-[:MENTIONS]->(con)"
                    )
            except Exception as exc:
                logger.debug("Staging concept merge notice (%s): %s", cid, exc)

        # 4. Merge Relationships (REQUIRES / UNLOCKS / RELATED)
        for u, v in accepted_edges:
            try:
                conn.execute(
                    f"MATCH (a:Concept), (b:Concept) "
                    f"WHERE a.id = '{u}' AND b.id = '{v}' "
                    f"MERGE (a)-[r:REQUIRES {{relation_type: 'prerequisite', source: 'librarian_upload'}}]->(b)"
                )
                staged_edges_list.append({"from_id": u, "to_id": v, "relation": "REQUIRES"})
            except Exception as exc:
                logger.debug("Staging REQUIRES edge notice (%s -> %s): %s", u, v, exc)

        for c in resolved_concepts:
            cid = c["id"]
            for u_item in c.get("unlocks", []):
                u_id = u_item["id"] if isinstance(u_item, dict) else canonical_concept_id(canonicalize_concept_name(str(u_item)))
                if u_id != cid:
                    try:
                        conn.execute(
                            f"MATCH (a:Concept), (b:Concept) "
                            f"WHERE a.id = '{cid}' AND b.id = '{u_id}' "
                            f"MERGE (a)-[r:UNLOCKS {{relation_type: 'unlocks', source: 'librarian_upload'}}]->(b)"
                        )
                        staged_edges_list.append({"from_id": cid, "to_id": u_id, "relation": "UNLOCKS"})
                    except Exception:
                        pass

        # 4b. Merge RELATED edges from related_to field
        for c in resolved_concepts:
            cid = c["id"]
            for rel_item in c.get("related_to", []):
                if isinstance(rel_item, dict):
                    rel_target = rel_item.get("concept") or rel_item.get("name") or ""
                    rel_type = (rel_item.get("relation") or "uses").lower().strip()
                else:
                    rel_target = str(rel_item)
                    rel_type = "uses"
                if not rel_target:
                    continue
                rel_id = canonical_concept_id(canonicalize_concept_name(rel_target))
                if rel_id == cid:
                    continue
                try:
                    conn.execute(
                        f"MATCH (a:Concept), (b:Concept) "
                        f"WHERE a.id = '{cid}' AND b.id = '{rel_id}' "
                        f"MERGE (a)-[r:RELATED {{relation_type: '{rel_type}', source: 'librarian_upload'}}]->(b)"
                    )
                    staged_edges_list.append({"from_id": cid, "to_id": rel_id, "relation": "RELATED", "relation_type": rel_type})
                except Exception:
                    pass

        # 5. Link physical Resource to Document via PROVIDES_TEXT
        try:
            from catalog_bridge import auto_link_resources
            auto_link_resources(str(STAGING_DB_PATH))
        except Exception as link_err:
            logger.debug("Staging catalog auto-link notice: %s", link_err)

        staging_engine.close()

        # Update Job Record with Staged Entities
        job.staged_entities = {
            "documents": staged_docs,
            "chunks": staged_chunks,
            "concepts": staged_concepts_list,
            "edges": staged_edges_list,
        }
        job.stage = "STAGED"
        job.status = "staged"
        job.completed_at = time.time()
        self._save_job(job)
        logger.info("Job %s successfully staged! Entities: %d concepts, %d edges.",
                    job.job_id, len(staged_concepts_list), len(staged_edges_list))

        if getattr(job, "auto_publish", False):
            logger.info("Job %s has auto_publish enabled; automatically publishing staging to production...", job.job_id)
            try:
                publish_staging()
                job.status = "complete"
                job.stage = "COMPLETE"
            except Exception as pub_err:
                logger.error("Auto-publish failed for job %s: %s", job.job_id, pub_err)
                job.error = f"Auto-publish failed: {pub_err}"
            self._save_job(job)


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
    if not PROD_DB_PATH.exists():
        raise FileNotFoundError(f"Production database missing: {PROD_DB_PATH}")
    if force or not STAGING_DB_PATH.exists():
        logger.info("Cloning production database %s -> %s for staging...", PROD_DB_PATH, STAGING_DB_PATH)
        _copy_db(PROD_DB_PATH, STAGING_DB_PATH)
    return STAGING_DB_PATH


def ensure_staging_db() -> Path:
    """Ensure okf_graph_staging.db exists as a faithful snapshot of production okf_graph.db."""
    if STAGING_DB_PATH.exists():
        return STAGING_DB_PATH
    if PROD_DB_PATH.exists():
        return clone_production_to_staging(force=True)
    return STAGING_DB_PATH


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
        logger.warning("count_concepts kuzu failed on %s (%s); falling back to JSON stats", db_path, exc)
        if DATA_FILE.exists():
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            return int((data.get("stats") or {}).get("total_concepts") or len(
                (data.get("visualization") or {}).get("nodes") or []
            ))
        raise


def export_graph_json(db_path: Path | str, data_file: Path | str = DATA_FILE) -> dict[str, Any]:
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
    logger.info("Exported %s (%d nodes, %d edges) from %s", data_file, len(nodes), len(edges), db_path)
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
            logger.info("Inference POST %s -> %s", url, body)
            try:
                return json.loads(body)
            except Exception:
                return {"raw": body}
    except Exception as exc:
        logger.warning("Could not notify inference server (%s): %s", url, exc)
        return None


def notify_inference_close() -> dict[str, Any] | None:
    """Drop the live inference Kùzu handle so os.replace is not EBUSY."""
    url = INFERENCE_RELOAD_URL.replace("/reload-graph", "/close-graph")
    return _post_inference(url, timeout=30)


def notify_inference_reload(*, embeddings_only: bool = False) -> dict[str, Any] | None:
    """Ask the live inference process to rebuild embeddings / reopen Kùzu."""
    url = INFERENCE_RELOAD_URL
    if embeddings_only:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}embeddings_only=1"
    return _post_inference(url)


def sync_embeddings_from_db(db_path: Path | str) -> None:
    """Write JSON from ``db_path`` then rebuild the arctic-embed concept cache.

    Prefers the live inference process (already has the embedder loaded) so the
    ingest worker does not double-load Snowflake weights onto the 4 GB GPU.
    """
    export_graph_json(db_path, DATA_FILE)
    notified = notify_inference_reload(embeddings_only=True)
    if notified:
        return
    os.environ.setdefault("ARCHIPELAGO_FORCE_CPU_EMBED", "1")
    from archipelago.inference.embeddings import build_concept_embeddings
    build_concept_embeddings()


# Module Singleton Worker
_librarian_worker = LibrarianWorker()
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
    upload_path = UPLOADS_DIR / safe_name
    upload_path.write_bytes(file_bytes)

    job = LibrarianJob(
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
    if not STAGING_DB_PATH.exists():
        return {
            "staging_available": False,
            "documents": [],
            "chunks": [],
            "concepts": [],
            "proposed_edges": [],
            "stats": {"total_concepts": 0, "total_edges": 0},
        }

    engine = KuzuGraphEngine(db_path=STAGING_DB_PATH, read_only=True)
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
        logger.warning("Error reading staging review: %s", exc)
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


def publish_staging(
    approved_edges: Optional[list[dict[str, str]]] = None,
    rejected_edges: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """
    Publish curated staging database to production:
    1. Applies any librarian edge rejections in staging DB.
    2. Synchronizes vector embeddings for all concepts (Pitfall 2 fix).
    3. Executes connection-safe atomic swap: KuzuGraphEngine.atomic_swap(STAGING_DB_PATH, PROD_DB_PATH).
    4. Syncs JSON export & triggers inference server reload.
    """
    if not STAGING_DB_PATH.exists():
        raise FileNotFoundError(f"Staging database {STAGING_DB_PATH} not found.")

    # 1. Apply librarian edge rejections if provided
    if rejected_edges:
        staging_engine = KuzuGraphEngine(db_path=STAGING_DB_PATH, read_only=False)
        try:
            for rej in rejected_edges:
                u = rej.get("from_id")
                v = rej.get("to_id")
                if u and v:
                    staging_engine.conn.execute(
                        f"MATCH (a:Concept {{id: '{u}'}})-[r:REQUIRES]->(b:Concept {{id: '{v}'}}) DELETE r"
                    )
        except Exception as exc:
            logger.warning("Error applying rejected edges in staging: %s", exc)
        finally:
            staging_engine.close()

    # 2. Export staging graph → JSON, then rebuild embeddings BEFORE swap
    #    so the 0.75 firewall already knows newly approved concepts.
    logger.info("Exporting staging concepts and synchronizing arctic-embed cache before swap...")
    try:
        sync_embeddings_from_db(STAGING_DB_PATH)
    except Exception as embed_err:
        logger.warning("Embedding synchronization notice: %s", embed_err)

    # 3. Connection-safe Atomic Swap (Pitfall 1 Fix)
    # Drop the other-process inference handle first; in-process handles are
    # closed inside KuzuGraphEngine.atomic_swap.
    notify_inference_close()
    logger.info("Executing zero-downtime atomic swap %s -> %s...", STAGING_DB_PATH, PROD_DB_PATH)
    KuzuGraphEngine.atomic_swap(STAGING_DB_PATH, PROD_DB_PATH)

    # 4. Re-open the live inference Kùzu handle onto the swapped file
    reload_info = notify_inference_reload(embeddings_only=False)

    return {
        "success": True,
        "message": "Zero-downtime atomic database swap completed successfully.",
        "prod_db_path": str(PROD_DB_PATH),
        "inference_reload": reload_info,
    }
