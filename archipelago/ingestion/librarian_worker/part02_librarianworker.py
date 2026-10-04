"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import json
from pathlib import Path
import queue
import threading
import time
from typing import Any, Optional
import uuid

from archipelago.graph.engine import KuzuGraphEngine
from archipelago.graph.graph_fusion import GraphFusionEngine
from archipelago.ingestion.lib_qwen_extractor import (
    LibQwenConceptExtractor,
    canonical_concept_id,
    canonicalize_concept_name,
    is_negative_sample,
)

from . import _deps as _rt  # noqa: F401


class LibrarianWorker(threading.Thread):
    """Asynchronous background worker processing librarian document uploads."""

    def __init__(self):
        super().__init__(name="LibrarianWorker", daemon=True)
        self.queue: queue.Queue[str] = queue.Queue()
        self.jobs: dict[str, _rt.LibrarianJob] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        _rt.JOBS_DIR.mkdir(parents=True, exist_ok=True)
        _rt.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_persisted_jobs()

    def _load_persisted_jobs(self) -> None:
        """Load recent jobs from disk cache."""
        for jfile in _rt.JOBS_DIR.glob("*.json"):
            try:
                data = json.loads(jfile.read_text(encoding="utf-8"))
                job = _rt.LibrarianJob(**data)
                self.jobs[job.job_id] = job
            except Exception:
                pass

    def _save_job(self, job: _rt.LibrarianJob) -> None:
        """Persist job metadata to disk."""
        with self._lock:
            self.jobs[job.job_id] = job
        jfile = _rt.JOBS_DIR / f"{job.job_id}.json"
        try:
            jfile.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
        except Exception as e:
            _rt.logger.warning("Could not persist job %s: %s", job.job_id, e)

    def enqueue(self, job: _rt.LibrarianJob) -> str:
        self._save_job(job)
        self.queue.put(job.job_id)
        return job.job_id

    def get_job(self, job_id: str) -> Optional[_rt.LibrarianJob]:
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
                _rt.logger.error("Job %s failed with unhandled exception: %s", job_id, exc, exc_info=True)
                job.status = "failed"
                job.stage = "FAILED"
                job.error = str(exc)
                job.completed_at = time.time()
                self._save_job(job)
            finally:
                self.queue.task_done()

    def _process_job(self, job: _rt.LibrarianJob) -> None:
        job.status = "processing"
        job.stage = "LOCAL_VALIDATION"
        self._save_job(job)

        local_file = Path(job.file_path)
        if not local_file.is_file():
            raise FileNotFoundError(f"Uploaded file not found: {local_file}")

        # Full documents are never published merely because ingestion was requested.
        # Use a separately reviewed rights manifest and the graph-only export tool
        # for publication. Local ingestion remains usable without HF credentials.
        job.hf_remote_path = ""

        # ── Stage 2: Slicing with High-Yield Structural Filtering ──────────────
        job.stage = "STRUCTURAL_SLICING"
        self._save_job(job)

        from archipelago.ingestion.pdf_io import ingest_document

        try:
            raw_chunks = ingest_document(str(local_file), max_pages=30)
        except Exception as slice_err:
            raise RuntimeError("Document extraction/OCR failed; no graph was published.") from slice_err

        # Filter out negative boilerplate samples
        valid_chunks = []
        for chk in raw_chunks:
            passage = chk.get("text_passage") or chk.get("text") or ""
            if not is_negative_sample(passage):
                valid_chunks.append(chk)

        if not valid_chunks:
            raise ValueError("No eligible readable chunks were extracted; ingestion did not complete.")
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

        if not all_concepts:
            raise RuntimeError("Extraction returned no validated concepts. Verify the ingestion model before publishing.")
        resolved_concepts = extractor.second_pass_relation_resolver(all_concepts)
        job.concepts_extracted = len(resolved_concepts)

        # ── Stage 5: Kahn DAG Cycle Gate ──────────────────────────────────────
        job.stage = "KAHN_DAG_GATE"
        self._save_job(job)

        # Initialize staging DB from production DB if not already present
        _rt.ensure_staging_db()

        fusion = GraphFusionEngine(db_path=_rt.STAGING_DB_PATH)
        staging_engine = KuzuGraphEngine(db_path=_rt.STAGING_DB_PATH, read_only=False)

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
            _rt.logger.debug("Error reading staging graph topology: %s", e)

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
        # No remote URL exists until a separate, approved publication succeeds.
        remote_url = job.hf_remote_path or ""
        try:
            conn.execute(
                f"MERGE (d:Document {{id: '{doc_id}'}}) "
                f"ON CREATE SET d.title = '{safe_title}', d.doc_hash = '{doc_hash}', "
                f"d.page_count = {max(len(valid_chunks), 1)}, d.edition = '1', d.pdf_url = '{remote_url}'"
            )
            staged_docs.append({"id": doc_id, "title": job.title, "author": job.author, "pdf_url": remote_url})
        except Exception as exc:
            _rt.logger.warning("Could not merge staging Document %s: %s", doc_id, exc)

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
                _rt.logger.debug("Staging chunk insert notice: %s", exc)

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
                _rt.logger.debug("Staging concept merge notice (%s): %s", cid, exc)

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
                _rt.logger.debug("Staging REQUIRES edge notice (%s -> %s): %s", u, v, exc)

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
            auto_link_resources(str(_rt.STAGING_DB_PATH))
        except Exception as link_err:
            _rt.logger.debug("Staging catalog auto-link notice: %s", link_err)

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
        _rt.logger.info("Job %s successfully staged! Entities: %d concepts, %d edges.",
                    job.job_id, len(staged_concepts_list), len(staged_edges_list))

        if getattr(job, "auto_publish", False):
            _rt.logger.info("Job %s has auto_publish enabled; automatically publishing staging to production...", job.job_id)
            try:
                _rt.publish_staging()
                job.status = "complete"
                job.stage = "COMPLETE"
            except Exception as pub_err:
                _rt.logger.error("Auto-publish failed for job %s: %s", job.job_id, pub_err)
                job.error = f"Auto-publish failed: {pub_err}"
            self._save_job(job)
