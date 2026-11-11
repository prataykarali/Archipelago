"""Run the local GPU research worker against the durable hosted queue."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
from threading import Event, Thread
from typing import Any

from dotenv import load_dotenv
import requests

from archipelago.ingestion.gpu_lease import GPUWorkerBusy, shared_gpu_lease
from archipelago.scholarly.acquisition.indra_parser import indra_available
from archipelago.scholarly.bridge.processor import process_job
from archipelago.scholarly.bridge.supabase_store import ResearchQueueStore
from archipelago.scholarly.extraction.abstract_fields import ingestion_model_name

POLL_SECONDS = 15
HEARTBEAT_SECONDS = 20
MAX_ERROR_CHARS = 240
APPROVAL_TIMEOUT_SECONDS = 300
APPROVAL_GRACE_SECONDS = 5
MODEL_CHECK_TIMEOUT_SECONDS = 5
MIN_AVAILABLE_RAM_GIB = 3
MIN_FREE_DISK_GIB = 5
BYTES_PER_GIB = 1024**3
OLLAMA_TAGS_ENDPOINT = "http://127.0.0.1:11434/api/tags"
LOGGER = logging.getLogger(__name__)


def _model_ready() -> bool:
    """Avoid claiming hosted work when the configured local model is absent."""
    try:
        response = requests.get(OLLAMA_TAGS_ENDPOINT, timeout=MODEL_CHECK_TIMEOUT_SECONDS)
        response.raise_for_status()
        models = response.json().get("models", [])
        return any(item.get("name") == ingestion_model_name() for item in models)
    except (requests.RequestException, ValueError, AttributeError):
        return False


def _approve_gpu_request(topic: str) -> bool:
    """Ask the workstation owner before any local research processing starts."""
    if not os.getenv("DISPLAY") and not os.getenv("WAYLAND_DISPLAY"):
        LOGGER.error("Research approval unavailable: no desktop display")
        return False
    try:
        ocr_ready = indra_available()
        ram_gib = 0.0
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("MemAvailable:"):
                    ram_gib = int(line.split()[1]) * 1024 / BYTES_PER_GIB
                    break
        except (OSError, ValueError, IndexError):
            LOGGER.warning("Could not read available system memory")
        disk_gib = shutil.disk_usage(Path.cwd()).free / BYTES_PER_GIB
        ram_status = "✓" if ram_gib >= MIN_AVAILABLE_RAM_GIB else "✕"
        disk_status = "✓" if disk_gib >= MIN_FREE_DISK_GIB else "✕"
        ocr_status = "✓" if ocr_ready else "✕"
        result = subprocess.run(
            [
                "zenity",
                "--question",
                "--title=Archipelago research request",
                f"--text=Approve local research ingestion?\n\n{topic[:200]}\n\n{ram_status} Free RAM: {ram_gib:.1f} GiB (need {MIN_AVAILABLE_RAM_GIB})\n{disk_status} Free disk: {disk_gib:.1f} GiB (need {MIN_FREE_DISK_GIB})\n{ocr_status} Indra OCR installed\n✓ Local SLM ready\n✓ PDFs only when access is verified\n✓ Up to 30 permitted PDFs per job; other papers use metadata and abstracts\n\nThe job will publish OKF observations to the configured Hugging Face dataset when credentials are available.",
                "--ok-label=✓ Approve ingestion",
                "--cancel-label=✕ Decline",
                f"--timeout={APPROVAL_TIMEOUT_SECONDS}",
            ],
            check=False,
            timeout=APPROVAL_TIMEOUT_SECONDS + APPROVAL_GRACE_SECONDS,
        )
        return (
            result.returncode == 0
            and ocr_ready
            and ram_gib >= MIN_AVAILABLE_RAM_GIB
            and disk_gib >= MIN_FREE_DISK_GIB
        )
    except (OSError, subprocess.TimeoutExpired):
        LOGGER.exception("Desktop research approval unavailable")
        return False


def _pulse(store: ResearchQueueStore, worker_id: str, job_id: str, stop: Event) -> None:
    """Refresh the lease while discovery or GPU extraction is in progress."""
    while not stop.wait(HEARTBEAT_SECONDS):
        try:
            ocr_state = "ocr_ready" if indra_available() else "ocr_unavailable"
            store.heartbeat(worker_id, f"processing:{ingestion_model_name()}:{ocr_state}", 0)
            store.update_job(job_id)
        except (requests.RequestException, RuntimeError):
            LOGGER.exception("Research worker heartbeat failed")


def run_once(store: ResearchQueueStore, worker_id: str) -> dict[str, Any] | None:
    """Claim and process at most one queued research request."""
    store.recover_stale_jobs()
    if not os.getenv("DISPLAY") and not os.getenv("WAYLAND_DISPLAY"):
        store.heartbeat(worker_id, "desktop_approval_unavailable", 0)
        return None
    if not _model_ready():
        store.heartbeat(worker_id, f"model_unavailable:{ingestion_model_name()}", 0)
        return None
    ocr_state = "ocr_ready" if indra_available() else "ocr_unavailable"
    store.heartbeat(worker_id, f"ready:{ingestion_model_name()}:{ocr_state}", 0)
    job = store.claim_next(worker_id)
    if job is None:
        return None
    job_id = str(job["job_id"])
    stop = Event()
    pulse = Thread(target=_pulse, args=(store, worker_id, job_id, stop), daemon=True)
    pulse.start()
    try:
        store.update_job(job_id, stage="AWAITING_LOCAL_APPROVAL")
        store.heartbeat(worker_id, f"awaiting_local_approval:{ocr_state}", 0)
        if not _approve_gpu_request(str(job["topic"])):
            store.update_job(
                job_id,
                status="failed",
                stage="LOCAL_APPROVAL_DECLINED",
                error="Local workstation owner declined or did not approve GPU ingestion.",
                completed_at=datetime.now(UTC).isoformat(),
            )
            return {"job_id": job_id, "status": "failed"}
        try:
            with shared_gpu_lease():
                result = process_job(store, job, worker_id)
        except GPUWorkerBusy:
            store.update_job(job_id, status="queued", stage="GPU_BUSY", worker_id=None)
            return {"job_id": job_id, "status": "queued"}
        store.heartbeat(
            worker_id,
            f"{result.get('model_status', 'ready')}:{ingestion_model_name()}:{ocr_state}",
            1,
        )
        return result
    except (requests.RequestException, RuntimeError, OSError, ValueError, KeyError) as exc:
        LOGGER.exception("Research job failed: %s", job_id)
        store.update_job(
            job_id,
            status="failed",
            stage="FAILED",
            error=f"{type(exc).__name__}: {str(exc)[:MAX_ERROR_CHARS]}",
            completed_at=datetime.now(UTC).isoformat(),
        )
        return {"job_id": job_id, "status": "failed"}
    finally:
        stop.set()
        pulse.join(timeout=HEARTBEAT_SECONDS)


def main() -> None:
    """Load local credentials and maintain the queue until stopped."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process one available job and exit")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    load_dotenv(root / ".env", override=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # HTTP client INFO logs include temporary signed upload URLs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    store = ResearchQueueStore()
    worker_id = f"{socket.gethostname()}-research-gpu"
    while True:
        try:
            result = run_once(store, worker_id)
            if result is not None:
                LOGGER.info("Research job %s: %s", result["job_id"], result["status"])
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research queue connection failed")
        if args.once:
            break
        Event().wait(POLL_SECONDS)


if __name__ == "__main__":
    main()
