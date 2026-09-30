"""Auto-Active Ingestion Watchdog Daemon for Archipelago.

Monitors data/catalogs/ and data/koha/ for new/modified files and
enqueues ingestion jobs via the IngestionWorker pipeline.
"""
from __future__ import annotations

import logging
import os
import time
import threading
from pathlib import Path
from typing import Dict, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from ingestion_jobs import JobStore
    from ingestion_worker import IngestionWorker

logger = logging.getLogger("archipelago.okf_watcher")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

WATCH_DIRS = [
    DATA_DIR / "catalogs",
    DATA_DIR / "koha",
]

WATCHED_EXTENSIONS = frozenset({".pdf", ".md", ".txt", ".ods"})
DEFAULT_POLL_INTERVAL = 30.0  # seconds


class OKFWatcher(threading.Thread):
    """Background watchdog monitoring catalog directories for modifications.

    When new or modified files are detected, enqueues ingestion jobs
    through the shared JobStore and IngestionWorker.
    """

    def __init__(
        self,
        job_store: "JobStore",
        worker: "IngestionWorker",
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ):
        super().__init__(daemon=True, name="OKFWatcher")
        self.job_store = job_store
        self.worker = worker
        self.poll_interval = poll_interval
        self.file_mtimes: Dict[Path, float] = {}
        self._stop_event = threading.Event()
        self._initial_scan()

    def _get_watchable_files(self) -> Set[Path]:
        """Scan watched directories for supported file types."""
        files: Set[Path] = set()
        for wdir in WATCH_DIRS:
            if not wdir.is_dir():
                continue
            try:
                for entry in wdir.rglob("*"):
                    if entry.is_file() and entry.suffix.lower() in WATCHED_EXTENSIONS:
                        files.add(entry)
            except Exception as exc:
                logger.debug("Error scanning %s: %s", wdir, exc)
        return files

    def _initial_scan(self) -> None:
        """Record initial file modification timestamps without triggering jobs."""
        for fpath in self._get_watchable_files():
            try:
                self.file_mtimes[fpath] = fpath.stat().st_mtime
            except OSError:
                pass

    def _enqueue_file(self, file_path: Path) -> None:
        """Create an ingestion job for a detected file and enqueue it."""
        try:
            filename = file_path.name
            rel_path = str(file_path.relative_to(BASE_DIR))
            logger.info("OKF Watcher: Detected change in %s — enqueuing ingestion job.", rel_path)

            job = self.job_store.create_job(
                source_filename=filename,
                doc_id=rel_path,
            )
            self.worker.enqueue(job.job_id)
            logger.info("OKF Watcher: Enqueued job %s for %s", job.job_id, filename)
        except Exception as exc:
            logger.error("OKF Watcher: Failed to enqueue job for %s: %s", file_path, exc)

    def run(self) -> None:
        """Main polling loop checking file modification times."""
        logger.info(
            "OKF Watcher started. Monitoring %s (poll interval: %.0fs)",
            [str(d) for d in WATCH_DIRS],
            self.poll_interval,
        )
        while not self._stop_event.is_set():
            try:
                current_files = self._get_watchable_files()
                for fpath in current_files:
                    try:
                        mtime = fpath.stat().st_mtime
                        last_mtime = self.file_mtimes.get(fpath)
                        if last_mtime is None:
                            self.file_mtimes[fpath] = mtime
                            self._enqueue_file(fpath)
                        elif mtime > last_mtime:
                            self.file_mtimes[fpath] = mtime
                            self._enqueue_file(fpath)
                    except OSError:
                        pass

                deleted = set(self.file_mtimes.keys()) - current_files
                for df in deleted:
                    del self.file_mtimes[df]

            except Exception as exc:
                logger.error("Error in OKF Watcher loop: %s", exc)

            self._stop_event.wait(self.poll_interval)

    def stop(self) -> None:
        """Stop the watcher daemon."""
        self._stop_event.set()


_WATCHER_INSTANCE: Optional[OKFWatcher] = None


def start_watcher(job_store: "JobStore", worker: "IngestionWorker", poll_interval: float = DEFAULT_POLL_INTERVAL) -> OKFWatcher:
    """Boot the OKF Watcher as a background daemon thread."""
    global _WATCHER_INSTANCE
    if _WATCHER_INSTANCE is None or not _WATCHER_INSTANCE.is_alive():
        _WATCHER_INSTANCE = OKFWatcher(job_store, worker, poll_interval)
        _WATCHER_INSTANCE.start()
        logger.info("OKF Watcher daemon booted successfully.")
    return _WATCHER_INSTANCE


def start_okf_watcher(job_store=None, worker=None, poll_interval: float = DEFAULT_POLL_INTERVAL) -> Optional[OKFWatcher]:
    """Convenience helper to boot watcher with default JobStore and IngestionWorker."""
    if job_store is None or worker is None:
        try:
            from archipelago.ingestion.ingestion_jobs import JobStore
            from archipelago.ingestion.ingestion_worker import IngestionWorker
            job_store = job_store or JobStore()
            worker = worker or IngestionWorker(job_store)
        except Exception as err:
            logger.debug("OKF Watcher dependencies not available: %s", err)
            return None
    return start_watcher(job_store, worker, poll_interval)

