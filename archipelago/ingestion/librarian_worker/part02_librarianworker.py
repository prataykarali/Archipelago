"""Auto-split from monolith — blocks are verbatim."""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any

from . import _deps as _rt
from .part03_process_job import LibrarianProcessMixin


class LibrarianWorker(threading.Thread, LibrarianProcessMixin):
    """Asynchronous background worker processing librarian document uploads."""

    def __init__(self) -> None:
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
        return str(job.job_id)

    def get_job(self, job_id: str) -> _rt.LibrarianJob | None:
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
                _rt.logger.error(
                    "Job %s failed with unhandled exception: %s", job_id, exc, exc_info=True
                )
                job.status = "failed"
                job.stage = "FAILED"
                job.error = str(exc)
                job.completed_at = time.time()
                self._save_job(job)
            finally:
                self.queue.task_done()
