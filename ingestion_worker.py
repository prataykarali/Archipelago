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
from okf.pipeline import run_pipeline_staged, PipelineAborted
from ingestion_jobs import JobStatus, JobStore


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


# Module-level singleton lock
graph_lock = GraphLock()


# ---------------------------------------------------------------------------
# IngestionWorker
# ---------------------------------------------------------------------------

class IngestionWorker(threading.Thread):
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

    def _process_job(self, job_id: str):
        job = self.job_store.get_job(job_id)
        if not job:
            return

        if self.job_store.is_cancelled(job_id):
            self.job_store.update_status(job_id, JobStatus.CANCELLED)
            return

        job_dir = self.job_store.job_dir(job_id)
        # Resolve quarantined upload (PDF, MD, or TXT)
        upload_pdf = None
        for candidate in (
            job_dir / "upload.pdf",
            job_dir / "upload.md",
            job_dir / "upload.txt",
            job_dir / "upload.markdown",
        ):
            if candidate.is_file():
                upload_pdf = candidate
                break
        if upload_pdf is None:
            # Fallback: any upload.* file
            for p in sorted(job_dir.glob("upload.*")):
                if p.is_file() and p.suffix.lower() in (".pdf", ".md", ".txt", ".markdown"):
                    upload_pdf = p
                    break
        if upload_pdf is None:
            self.job_store.update_status(
                job_id, JobStatus.FAILED, error="No upload.pdf/.md/.txt found in job dir"
            )
            return
        temp_db_path = str(job_dir / "temp_graph.db")

        # 1. Update status to PARSING
        self.job_store.update_status(job_id, JobStatus.PARSING)

        def on_progress(stage, pct, detail):
            self.job_store.update_status(
                job_id,
                JobStatus(stage),
                progress={stage: {"pct": pct, "detail": detail}}
            )

        def check_cancelled():
            return self.job_store.is_cancelled(job_id)

        try:
            from okf.graph.merge_document import (
                assert_merge_safe,
                doc_ids_in_results,
                load_okf_results,
                upsert_upload_inventory_meta,
                write_okf_results_atomic,
            )
            from okf.pipeline import compute_doc_id

            results_path = BASE_DIR / "okf_results.json"
            prior_results = load_okf_results(results_path)
            prior_doc_ids = doc_ids_in_results(prior_results)

            # Optional librarian metadata (title, shelf, license, …)
            upload_meta: Dict[str, Any] = {}
            meta_path = job_dir / "meta.json"
            if meta_path.is_file():
                try:
                    upload_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    upload_meta = {}

            license_mode = str(
                upload_meta.get("license_mode") or "full"
            ).strip().lower() or "full"
            if license_mode not in ("full", "toc_only", "metadata_only"):
                license_mode = "full"
            upload_meta["license_mode"] = license_mode

            # metadata_only: shelf row only — no OKF extract / graph swap.
            if license_mode == "metadata_only":
                on_progress(
                    "GRAPH_VALIDATION",
                    100,
                    {"message": "metadata_only — inventory upsert, no graph extract"},
                )
                pdf_dest_dir = BASE_DIR / "pdfs"
                pdf_dest_dir.mkdir(parents=True, exist_ok=True)
                src_name = job.source_filename or upload_pdf.name
                low = src_name.lower()
                meta_kind = str(upload_meta.get("kind") or "").lower()
                if low.endswith((".md", ".markdown", ".txt")):
                    sub = pdf_dest_dir / "web_syllabi"
                elif meta_kind in ("textbook", "book", "ebook") or "textbook" in low:
                    sub = pdf_dest_dir / "textbooks"
                else:
                    sub = pdf_dest_dir / "papers"
                sub.mkdir(parents=True, exist_ok=True)
                dest_pdf_path = sub / Path(src_name).name
                shutil.copy2(str(upload_pdf), str(dest_pdf_path))
                dest_rel_full = f"{sub.name}/{Path(src_name).name}"
                upsert_upload_inventory_meta(
                    upload_meta, dest_rel_full, graph_ready=False,
                )
                try:
                    from archipelago.inference.inventory_ssot import (
                        clear_all_inventory_caches,
                    )
                    clear_all_inventory_caches()
                except Exception as cache_err:
                    print(f"Warning: inventory cache clear failed: {cache_err}")
                self.job_store.update_status(
                    job_id,
                    JobStatus.COMPLETE,
                    result={
                        "nodes": 0,
                        "edges": 0,
                        "new_node_ids": [],
                        "merged_concepts": [],
                        "source_pages": [],
                        "merge": {
                            "mode": "metadata_only",
                            "license_mode": license_mode,
                            "graph_ready": False,
                        },
                        "pdf_relpath": dest_rel_full,
                        "inventory_id": (
                            f"librarian_upload_"
                            + "".join(
                                ch if ch.isalnum() else "_"
                                for ch in str(
                                    upload_meta.get("title") or dest_rel_full
                                ).lower()
                            ).strip("_")[:64]
                        ),
                    },
                    graph_version=0,
                )
                return

            # toc_only / full: staged OKF extract. Cap pages for commercial TOC.
            import okf.config as _okf_cfg
            _prev_max_pages = _okf_cfg.MAX_PAGES_PER_DOC
            if license_mode == "toc_only":
                # Structure/front-matter only — never full commercial body.
                _TOC_ONLY_MAX_PAGES = 24
                _okf_cfg.MAX_PAGES_PER_DOC = _TOC_ONLY_MAX_PAGES

            try:
                # Staged pipeline merges this upload into existing okf_results and
                # builds a FULL multi-doc graph in the quarantine temp DB.
                okf_results, temp_db, graph_export = run_pipeline_staged(
                    source_path=str(upload_pdf),
                    temp_db_path=temp_db_path,
                    on_progress=on_progress,
                    check_cancelled=check_cancelled
                )
            finally:
                _okf_cfg.MAX_PAGES_PER_DOC = _prev_max_pages

            # Resolve doc_id the same way the pipeline tags chunks.
            uploading_doc_id = compute_doc_id(str(upload_pdf))
            # After copy into pdfs/, final id may be papers/<name>; use
            # results-derived id when present.
            merged_ids = doc_ids_in_results(okf_results)
            for candidate in merged_ids:
                base = candidate.replace("\\", "/").rsplit("/", 1)[-1]
                upload_base = Path(job.source_filename or upload_pdf.name).name
                if base == upload_base or candidate == uploading_doc_id:
                    uploading_doc_id = candidate
                    break

            assert_merge_safe(prior_doc_ids, merged_ids, uploading_doc_id)

            # Persist merged results BEFORE swapping the live DB so a crash
            # mid-swap still leaves a recoverable multi-doc corpus.
            write_okf_results_atomic(results_path, okf_results)

            # Export temp nodes/edges visualization JSONs inside quarantine
            temp_nodes_path = job_dir / "temp_nodes.json"
            temp_edges_path = job_dir / "temp_edges.json"
            export_vis_json(temp_db, str(temp_nodes_path), str(temp_edges_path))

            # Explicitly delete temp_db to release Kuzu locks before copying
            del temp_db

            on_progress(
                "GRAPH_VALIDATION",
                100,
                {
                    "message": "Merging into live graph (full rebuild from merged results)",
                    "prior_docs": len(prior_doc_ids),
                    "merged_docs": len(merged_ids),
                    "uploading_doc_id": uploading_doc_id,
                },
            )

            # 2. COMPLETE — atomic swap of the *merged multi-doc* temp graph
            with self.graph_lock.write_lock():
                backup_path = self.live_db_path + ".bak"
                has_backup = False

                if os.path.exists(self.live_db_path):
                    if os.path.exists(backup_path):
                        if os.path.isdir(backup_path):
                            shutil.rmtree(backup_path, ignore_errors=True)
                        else:
                            os.remove(backup_path)
                    os.rename(self.live_db_path, backup_path)
                    has_backup = True

                try:
                    if os.path.isdir(temp_db_path):
                        shutil.copytree(temp_db_path, self.live_db_path)
                    else:
                        shutil.copy2(temp_db_path, self.live_db_path)
                except Exception as swap_err:
                    if os.path.exists(self.live_db_path):
                        if os.path.isdir(self.live_db_path):
                            shutil.rmtree(self.live_db_path, ignore_errors=True)
                        else:
                            os.remove(self.live_db_path)
                    if has_backup:
                        os.rename(backup_path, self.live_db_path)
                    raise swap_err

                if has_backup and os.path.exists(backup_path):
                    if os.path.isdir(backup_path):
                        shutil.rmtree(backup_path, ignore_errors=True)
                    else:
                        os.remove(backup_path)

                try:
                    import inference_server
                    inference_server.reload_db()
                except ImportError:
                    pass
                except Exception as reload_err:
                    print(f"Warning: inference_server.reload_db failed after swap: {reload_err}")

                try:
                    import okf.graph_db as _gdb
                    _gdb._DEFAULT_GRAPH_DB = None
                except ImportError:
                    pass

                from okf.exports import write_all_artifacts
                import kuzu
                new_db = kuzu.Database(self.live_db_path)
                write_all_artifacts(graph_export, okf_results, new_db,
                                    base_dir=BASE_DIR)

                # Link Resource ↔ Document when catalog schema is present.
                try:
                    from catalog_bridge import auto_link_resources
                    link_stats = auto_link_resources(self.live_db_path)
                    on_progress(
                        "GRAPH_VALIDATION",
                        100,
                        {"message": "auto_link_resources", "stats": link_stats},
                    )
                except Exception as link_err:
                    print(f"Warning: catalog auto_link failed: {link_err}")

                try:
                    import inference_server
                    inference_server.build_concept_embeddings()
                except (ImportError, AttributeError):
                    pass

            # 3. FINALIZE (after releasing write lock)
            pdf_dest_dir = BASE_DIR / "pdfs"
            pdf_dest_dir.mkdir(parents=True, exist_ok=True)
            src_name = job.source_filename or upload_pdf.name
            low = src_name.lower()
            meta_kind = str(upload_meta.get("kind") or "").lower()
            if low.endswith((".md", ".markdown", ".txt")):
                sub = pdf_dest_dir / "web_syllabi"
            elif meta_kind in ("textbook", "book", "ebook") or "textbook" in low:
                sub = pdf_dest_dir / "textbooks"
            else:
                sub = pdf_dest_dir / "papers"
            sub.mkdir(parents=True, exist_ok=True)
            dest_pdf_path = sub / Path(src_name).name
            shutil.copy2(str(upload_pdf), str(dest_pdf_path))
            try:
                dest_rel = str(dest_pdf_path.relative_to(pdf_dest_dir)).replace("\\", "/")
            except ValueError:
                dest_rel = dest_pdf_path.name
            # Prefer path under pdfs/ for inventory + future re-ingest
            dest_rel_full = f"{sub.name}/{Path(src_name).name}" if sub.name in (
                "papers", "textbooks", "web_syllabi",
            ) else dest_rel

            # graph_ready=1 only after successful merge + swap above.
            upsert_upload_inventory_meta(
                upload_meta or {"title": Path(src_name).stem, "kind": meta_kind or "paper"},
                dest_rel_full,
                graph_ready=True,
            )
            try:
                from archipelago.inference.inventory_ssot import clear_all_inventory_caches
                clear_all_inventory_caches()
            except Exception as cache_err:
                print(f"Warning: inventory cache clear failed: {cache_err}")

            max_v = 0
            jobs_list = self.job_store.list_jobs()
            for j_sum in jobs_list:
                j_rec = self.job_store.get_job(j_sum["job_id"])
                if j_rec and j_rec.status == JobStatus.COMPLETE and j_rec.graph_version:
                    max_v = max(max_v, j_rec.graph_version)
            next_version = max_v + 1

            new_node_ids = []
            merged_concepts = []
            source_pages = set()
            doc_id = uploading_doc_id or job.source_filename
            for cid, cinfo in graph_export.get("concepts", {}).items():
                is_from_doc = False
                for src in cinfo.get("sources", []):
                    src_doc = str(src.get("doc_id") or "")
                    if src_doc == doc_id or src_doc.endswith("/" + str(Path(doc_id).name)):
                        is_from_doc = True
                        if src.get("page_number"):
                            source_pages.add(int(src["page_number"]))
                if is_from_doc:
                    new_node_ids.append(cid)
                    merged_concepts.append(cinfo.get("name"))

            inv_slug = "".join(
                ch if ch.isalnum() else "_"
                for ch in str(
                    (upload_meta or {}).get("title") or Path(src_name).stem
                ).lower()
            ).strip("_")[:64] or "upload"
            res_meta = {
                "nodes": graph_export.get("stats", {}).get("total_concepts", 0),
                "edges": graph_export.get("stats", {}).get("total_edges", 0),
                "new_node_ids": new_node_ids,
                "merged_concepts": merged_concepts,
                "source_pages": sorted(list(source_pages)),
                "merge": {
                    "mode": "full_rebuild_from_merged_okf_results",
                    "license_mode": license_mode,
                    "prior_doc_count": len(prior_doc_ids),
                    "merged_doc_count": len(merged_ids),
                    "uploading_doc_id": doc_id,
                    "prior_docs_retained": sorted(prior_doc_ids & merged_ids),
                    "graph_ready": True,
                },
                "pdf_relpath": dest_rel_full,
                "inventory_id": f"librarian_upload_{inv_slug}",
            }
            self.job_store.update_status(
                job_id,
                JobStatus.COMPLETE,
                result=res_meta,
                graph_version=next_version
            )

        except PipelineAborted:
            self.job_store.update_status(job_id, JobStatus.CANCELLED)
        except Exception as e:
            self.job_store.update_status(job_id, JobStatus.FAILED, error=str(e))
        finally:
            # Clean up temp_graph.db from quarantine directory, but keep upload.pdf and job.json
            if os.path.exists(temp_db_path):
                shutil.rmtree(temp_db_path, ignore_errors=True)


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
