"""Stage librarian uploads and merge their extracted graph records."""

from __future__ import annotations

from pathlib import Path
import re
import time
from typing import Any
import uuid

from archipelago.graph.engine import KuzuGraphEngine
from archipelago.graph.graph_fusion import GraphFusionEngine
from archipelago.ingestion.lib_qwen_extractor import (
    LibQwenConceptExtractor,
    canonical_concept_id,
    canonicalize_concept_name,
    is_negative_sample,
)
from archipelago.storage.hf_remote import HFStorageClient
from okf.query_rows import query_rows

from . import _deps as _rt


class LibrarianProcessMixin:
    """Process one librarian job using the worker's persistence hook."""

    def _save_job(self, job: _rt.LibrarianJob) -> None:
        """Persist a job through the concrete worker."""
        raise NotImplementedError

    def _process_job(self, job: _rt.LibrarianJob) -> None:
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
            _rt.logger.info("Uploading %s to HF dataset %s...", local_file, hf_client.repo_id)
            hf_res = hf_client.upload_file(
                local_path=local_file,
                remote_path=remote_rel_path,
                commit_message=f"Librarian upload: {job.title} ({job.isbn})",
            )
            job.hf_remote_path = remote_rel_path
            _rt.logger.info("HF remote push finished: %s", hf_res.get("mode"))
        except Exception as hf_err:
            _rt.logger.warning("HF upload warning (will continue locally): %s", hf_err)
            job.hf_remote_path = remote_rel_path

        # ── Stage 2: Slicing with High-Yield Structural Filtering ──────────────
        job.stage = "STRUCTURAL_SLICING"
        self._save_job(job)

        from archipelago.ingestion.pdf_io import ingest_document

        try:
            raw_chunks = ingest_document(str(local_file), max_pages=30)
        except Exception as slice_err:
            _rt.logger.warning(
                "Universal chunker failed, falling back to basic text slice: %s", slice_err
            )
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

        extractor = LibQwenConceptExtractor()
        all_concepts: list[dict[str, Any]] = []

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
        _rt.ensure_staging_db()

        fusion = GraphFusionEngine(db_path=_rt.STAGING_DB_PATH)
        staging_engine = KuzuGraphEngine(db_path=_rt.STAGING_DB_PATH, read_only=False)
        conn = staging_engine.conn
        if conn is None:
            raise RuntimeError("Staging graph connection is unavailable")

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
                uid = (
                    u["id"]
                    if isinstance(u, dict)
                    else canonical_concept_id(canonicalize_concept_name(str(u)))
                )
                if uid != cid:
                    candidate_edges.add((cid, uid))
                    candidate_nodes.add(uid)

        existing_nodes = set()
        existing_edges = set()
        try:
            for row in query_rows(conn, "MATCH (c:Concept) RETURN c.id"):
                existing_nodes.add(row[0])
            for row in query_rows(
                conn, "MATCH (a:Concept)-[:REQUIRES]->(b:Concept) RETURN a.id, b.id"
            ):
                existing_edges.add((row[0], row[1]))
        except Exception as e:
            _rt.logger.debug("Error reading staging graph topology: %s", e)

        is_dag, rejected_edges = fusion.validate_dag_kahn(
            existing_nodes=existing_nodes,
            existing_edges=existing_edges,
            new_nodes=candidate_nodes,
            new_edges=candidate_edges,
        )

        job.dag_status = (
            "verified_acyclic" if is_dag else f"cycle_rejected ({len(rejected_edges)} rejected)"
        )
        accepted_edges = candidate_edges - set(rejected_edges)

        # ── Stage 6: Staging DB Merge ──────────────────────────────────────────
        job.stage = "STAGING_MERGE"
        self._save_job(job)

        doc_id = f"upload_{job.job_id[:8]}"
        doc_hash = str(uuid.uuid5(uuid.NAMESPACE_DNS, job.title + job.filename))
        staged_docs = []
        staged_chunks: list[dict[str, Any]] = []
        staged_concepts_list = []
        staged_edges_list = []

        # 1. Merge Document
        safe_title = job.title.replace("'", "''")
        job.author.replace("'", "''")
        remote_url = job.hf_remote_path or f"books/librarian_uploads/{safe_name}"
        try:
            conn.execute(
                f"MERGE (d:Document {{id: '{doc_id}'}}) "
                f"ON CREATE SET d.title = '{safe_title}', d.doc_hash = '{doc_hash}', "
                f"d.page_count = {max(len(valid_chunks), 1)}, d.edition = '1', d.pdf_url = '{remote_url}'"
            )
            staged_docs.append(
                {"id": doc_id, "title": job.title, "author": job.author, "pdf_url": remote_url}
            )
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
                staged_chunks.append(
                    {"id": chunk_key, "page_number": p_num, "section_title": sec_title}
                )
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
                staged_concepts_list.append(
                    {
                        "id": cid,
                        "name": c["name"],
                        "concept_type": ctype,
                        "difficulty": diff,
                        "summary": c.get("summary", ""),
                    }
                )

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
                u_id = (
                    u_item["id"]
                    if isinstance(u_item, dict)
                    else canonical_concept_id(canonicalize_concept_name(str(u_item)))
                )
                if u_id != cid:
                    try:
                        conn.execute(
                            f"MATCH (a:Concept), (b:Concept) "
                            f"WHERE a.id = '{cid}' AND b.id = '{u_id}' "
                            f"MERGE (a)-[r:UNLOCKS {{relation_type: 'unlocks', source: 'librarian_upload'}}]->(b)"
                        )
                        staged_edges_list.append(
                            {"from_id": cid, "to_id": u_id, "relation": "UNLOCKS"}
                        )
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
                    staged_edges_list.append(
                        {
                            "from_id": cid,
                            "to_id": rel_id,
                            "relation": "RELATED",
                            "relation_type": rel_type,
                        }
                    )
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
        _rt.logger.info(
            "Job %s successfully staged! Entities: %d concepts, %d edges.",
            job.job_id,
            len(staged_concepts_list),
            len(staged_edges_list),
        )

        if getattr(job, "auto_publish", False):
            _rt.logger.info(
                "Job %s has auto_publish enabled; automatically publishing staging to production...",
                job.job_id,
            )
            try:
                _rt.publish_staging()
                job.status = "complete"
                job.stage = "COMPLETE"
            except Exception as pub_err:
                _rt.logger.error("Auto-publish failed for job %s: %s", job.job_id, pub_err)
                job.error = f"Auto-publish failed: {pub_err}"
            self._save_job(job)
