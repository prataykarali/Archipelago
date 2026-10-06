"""Entrypoint: run the ingestion worker in the foreground.

The Docker appliance needs a long-running process that (a) starts the queue
worker, (b) installs log redaction, and (c) shuts down cleanly on SIGTERM so an
atomic graph swap in flight is never killed mid-rename.

Kept as a real module rather than an inline ``python -c`` so it can be linted,
tested, and pointed at by the compose healthcheck.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import signal
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# How often the idle loop wakes to check the shutdown flag. Short enough that
# SIGTERM is honoured promptly, long enough not to spin a core.
SHUTDOWN_POLL_SEC = 1.0
GRAPH_EXPORT_ENV = "ARCHIPELAGO_GRAPH_JSON"


def ensure_shared_graph_export() -> None:
    """Link the legacy graph export path to the shared Docker volume."""
    configured = os.environ.get(GRAPH_EXPORT_ENV, "").strip()
    if not configured:
        return
    target = Path(configured).resolve()
    legacy = REPO_ROOT / "okf_graph.json"
    if target == legacy:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if legacy.is_symlink() and legacy.resolve() == target:
        return
    if legacy.exists() or legacy.is_symlink():
        raise RuntimeError("Graph export path exists and is not the shared volume link")
    legacy.symlink_to(target)


def configure_logging() -> None:
    """Root logging plus credential redaction on every handler."""
    from archipelago.middleware.log_redaction import install_log_redaction

    logging.basicConfig(
        level=os.environ.get("ARCHIPELAGO_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    install_log_redaction()


def main() -> int:
    """Start the worker and block until asked to stop."""
    configure_logging()
    ensure_shared_graph_export()
    logger = logging.getLogger("archipelago.ingestion.worker")

    from ingestion_jobs import JobStore
    from ingestion_worker import GraphLock, IngestionWorker

    jobs_dir = os.environ.get("ARCHIPELAGO_JOBS_DIR", "jobs")
    store = JobStore(jobs_dir)
    worker = IngestionWorker(store, graph_lock=GraphLock())
    worker.start()
    logger.info("Ingestion worker started; jobs=%s", jobs_dir)

    stopping = False

    def request_stop(signum: int, _frame: object) -> None:
        nonlocal stopping
        logger.info("Signal %s received; finishing current job", signum)
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    try:
        while not stopping:
            time.sleep(SHUTDOWN_POLL_SEC)
    finally:
        worker.stop()
        logger.info("Ingestion worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
