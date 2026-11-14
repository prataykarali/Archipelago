"""Run the local GPU research worker against the durable hosted queue."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
from threading import Event, Thread
import time
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import requests

from archipelago.academic_automation.gpu import gpu_snapshot
from archipelago.ingestion.gpu_lease import (
    GPUJobTypeRejected,
    GPUWorkerBusy,
    shared_gpu_lease,
    unload_ollama_model,
    validate_gpu_job_type,
)
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
MIN_FREE_VRAM_MIB = 1024
BYTES_PER_GIB = 1024**3
OLLAMA_TAGS_ENDPOINT = "http://127.0.0.1:11434/api/tags"
IST_TZ = ZoneInfo("Asia/Kolkata")
MAX_AUTO_PROMPTS_PER_DAY = 2
MIN_PROMPT_INTERVAL_SECONDS = 28800
DEFAULT_NOTIFICATION_LEDGER = Path.home() / ".cache" / "archipelago" / "ingestion_notifications.json"
LOGGER = logging.getLogger(__name__)


def _ledger_path() -> Path:
    override = os.getenv("ARCHIPELAGO_NOTIFICATION_LEDGER", "").strip()
    return Path(override) if override else DEFAULT_NOTIFICATION_LEDGER


class NotificationLedger:
    """Persistent ledger limiting automatic ingestion consent popups."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _ledger_path()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "daily_counts": {},
                "last_prompt_at": 0.0,
                "suppressed_jobs": {},
                "prompted_jobs": {},
            }
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("daily_counts", {})
                data.setdefault("last_prompt_at", 0.0)
                data.setdefault("suppressed_jobs", {})
                data.setdefault("prompted_jobs", {})
                return data
        except (OSError, ValueError):
            LOGGER.warning("Notification ledger unreadable; resetting %s", self.path)
        return {
            "daily_counts": {},
            "last_prompt_at": 0.0,
            "suppressed_jobs": {},
            "prompted_jobs": {},
        }

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def can_prompt(
        self,
        job_id: str,
        *,
        now: float | None = None,
        manual_review: bool = False,
    ) -> tuple[bool, str]:
        """Return whether an automatic consent dialog may be shown for ``job_id``."""
        if manual_review:
            return True, "manual_review"
        ts = time.time() if now is None else now
        data = self._load()
        if job_id in data["suppressed_jobs"]:
            return False, "job_suppressed"
        if job_id in data["prompted_jobs"]:
            return False, "already_prompted_in_polling"
        today_ist = datetime.fromtimestamp(ts, tz=IST_TZ).strftime("%Y-%m-%d")
        if int(data["daily_counts"].get(today_ist, 0)) >= MAX_AUTO_PROMPTS_PER_DAY:
            return False, "daily_prompt_cap_reached"
        last_prompt_at = float(data.get("last_prompt_at") or 0.0)
        if last_prompt_at > 0 and (ts - last_prompt_at) < MIN_PROMPT_INTERVAL_SECONDS:
            return False, "prompt_cooldown_active"
        return True, "ok"

    def record_prompt(
        self,
        job_id: str,
        *,
        approved: bool,
        now: float | None = None,
        manual_review: bool = False,
    ) -> None:
        """Persist a shown prompt and suppress declined/deferred jobs."""
        ts = time.time() if now is None else now
        data = self._load()
        data["prompted_jobs"][job_id] = ts
        if not manual_review:
            today_ist = datetime.fromtimestamp(ts, tz=IST_TZ).strftime("%Y-%m-%d")
            data["daily_counts"][today_ist] = int(data["daily_counts"].get(today_ist, 0)) + 1
            data["last_prompt_at"] = ts
        if not approved:
            data["suppressed_jobs"][job_id] = {"reason": "declined_or_deferred", "at": ts}
        self._save(data)


def _available_ram_gib() -> float:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024 / BYTES_PER_GIB
    except (OSError, ValueError, IndexError):
        LOGGER.warning("Could not read available system memory")
    return 0.0


def _free_disk_gib() -> float:
    return shutil.disk_usage(Path.cwd()).free / BYTES_PER_GIB


def _has_verified_rights(job: dict[str, Any] | None) -> bool:
    if not job:
        return True
    if job.get("rights_verified") is False:
        return False
    rights = str(job.get("rights") or "").strip().lower()
    return rights not in {"all-rights-reserved", "unverified", "denied", "restricted"}


def _check_gpu_preflight() -> tuple[bool, str]:
    snap = gpu_snapshot()
    if not snap.get("available"):
        return False, str(snap.get("reason") or "gpu_unavailable")
    target_model = ingestion_model_name()
    active_models = {str(m) for m in (snap.get("active_models") or [])}
    if active_models - {target_model}:
        return False, "other_ollama_model_loaded"
    mem_total = int(snap.get("memory_total_mib") or 0)
    mem_used = int(snap.get("memory_used_mib") or 0)
    if mem_total > 0 and target_model not in active_models:
        free_vram = mem_total - mem_used
        if free_vram < MIN_FREE_VRAM_MIB:
            return False, f"insufficient_vram:{free_vram}MiB"
    return True, "ok"


def _preflight_check(job: dict[str, Any] | None = None) -> tuple[bool, str, str]:
    """Verify display, rights, RAM, disk, model, and GPU BEFORE showing zenity."""
    if not os.getenv("DISPLAY") and not os.getenv("WAYLAND_DISPLAY"):
        return False, "DEFERRED", "desktop_display_unavailable"
    if not _has_verified_rights(job):
        return False, "BLOCKED_RESOURCE", "unverified_rights"
    ram_gib = _available_ram_gib()
    if ram_gib < MIN_AVAILABLE_RAM_GIB:
        return False, "BLOCKED_RESOURCE", f"insufficient_ram:{ram_gib:.1f}GiB"
    disk_gib = _free_disk_gib()
    if disk_gib < MIN_FREE_DISK_GIB:
        return False, "BLOCKED_RESOURCE", f"insufficient_disk:{disk_gib:.1f}GiB"
    if not _model_ready():
        return False, "BLOCKED_RESOURCE", f"model_unavailable:{ingestion_model_name()}"
    gpu_ok, gpu_reason = _check_gpu_preflight()
    if not gpu_ok:
        return False, "BLOCKED_RESOURCE", gpu_reason
    return True, "READY", "ok"


def _model_ready() -> bool:
    """Avoid claiming hosted work when the configured local model is absent."""
    try:
        response = requests.get(OLLAMA_TAGS_ENDPOINT, timeout=MODEL_CHECK_TIMEOUT_SECONDS)
        response.raise_for_status()
        models = response.json().get("models", [])
        return any(item.get("name") == ingestion_model_name() for item in models)
    except (requests.RequestException, ValueError, AttributeError):
        return False


def _approve_gpu_request(topic: str, *, pending_count: int = 1) -> bool:
    """Ask the workstation owner before any local research processing starts."""
    if not os.getenv("DISPLAY") and not os.getenv("WAYLAND_DISPLAY"):
        LOGGER.error("Research approval unavailable: no desktop display")
        return False
    try:
        ocr_ready = indra_available()
        ram_gib = _available_ram_gib()
        disk_gib = _free_disk_gib()
        ram_status = "✓" if ram_gib >= MIN_AVAILABLE_RAM_GIB else "✕"
        disk_status = "✓" if disk_gib >= MIN_FREE_DISK_GIB else "✕"
        ocr_status = "✓" if ocr_ready else "✕"
        queue_line = (
            f"{pending_count} queued ingestion job(s) pending.\n"
            if pending_count > 1
            else ""
        )
        result = subprocess.run(
            [
                "zenity",
                "--question",
                "--title=Archipelago research request",
                f"--text=Approve local research ingestion?\n\n{queue_line}{topic[:200]}\n\n{ram_status} Free RAM: {ram_gib:.1f} GiB (need {MIN_AVAILABLE_RAM_GIB})\n{disk_status} Free disk: {disk_gib:.1f} GiB (need {MIN_FREE_DISK_GIB})\n{ocr_status} Indra OCR installed\n✓ Local SLM ready\n✓ PDFs only when access is verified\n✓ Up to 30 permitted PDFs per job; other papers use metadata and abstracts\n\nThe job will publish OKF observations to the configured Hugging Face dataset when credentials are available.",
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


def run_once(
    store: ResearchQueueStore,
    worker_id: str,
    *,
    manual_review: bool = False,
    ledger: NotificationLedger | None = None,
) -> dict[str, Any] | None:
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
    active_ledger = ledger or NotificationLedger()
    stop = Event()
    pulse = Thread(target=_pulse, args=(store, worker_id, job_id, stop), daemon=True)
    pulse.start()
    gpu_acquired = False
    try:
        raw_job_type = job.get("job_type")
        try:
            job_type = validate_gpu_job_type(
                raw_job_type if isinstance(raw_job_type, str) else None
            )
        except GPUJobTypeRejected as exc:
            store.update_job(
                job_id,
                status="failed",
                stage="GPU_POLICY_REJECTED",
                error=str(exc)[:MAX_ERROR_CHARS],
                completed_at=datetime.now(UTC).isoformat(),
            )
            return {"job_id": job_id, "status": "failed"}

        preflight_ok, preflight_stage, preflight_reason = _preflight_check(job)
        if not preflight_ok:
            store.update_job(
                job_id,
                status="queued",
                stage=preflight_stage,
                error=preflight_reason,
                worker_id=None,
            )
            return {
                "job_id": job_id,
                "status": "deferred",
                "stage": preflight_stage,
                "reason": preflight_reason,
            }

        can_prompt, prompt_reason = active_ledger.can_prompt(job_id, manual_review=manual_review)
        if not can_prompt:
            store.update_job(
                job_id,
                status="queued",
                stage="DEFERRED",
                error=prompt_reason,
                worker_id=None,
            )
            return {
                "job_id": job_id,
                "status": "deferred",
                "stage": "DEFERRED",
                "reason": prompt_reason,
            }

        store.update_job(job_id, stage="AWAITING_LOCAL_APPROVAL")
        store.heartbeat(worker_id, f"awaiting_local_approval:{ocr_state}", 0)
        pending_count = int(job.get("pending_count") or 1)
        approved = _approve_gpu_request(str(job["topic"]), pending_count=pending_count)
        active_ledger.record_prompt(job_id, approved=approved, manual_review=manual_review)
        if not approved:
            store.update_job(
                job_id,
                status="failed",
                stage="LOCAL_APPROVAL_DECLINED",
                error="Local workstation owner declined or did not approve GPU ingestion.",
                completed_at=datetime.now(UTC).isoformat(),
            )
            return {"job_id": job_id, "status": "failed"}

        try:
            with shared_gpu_lease(job_type=job_type):
                gpu_acquired = True
                result = process_job(store, job, worker_id)
        except GPUJobTypeRejected as exc:
            store.update_job(
                job_id,
                status="failed",
                stage="GPU_POLICY_REJECTED",
                error=str(exc)[:MAX_ERROR_CHARS],
                completed_at=datetime.now(UTC).isoformat(),
            )
            return {"job_id": job_id, "status": "failed"}
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
        if gpu_acquired:
            unload_ollama_model(ingestion_model_name())
        stop.set()
        pulse.join(timeout=HEARTBEAT_SECONDS)


def main() -> None:
    """Load local credentials and maintain the queue until stopped."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process one available job and exit")
    parser.add_argument(
        "--manual-review",
        action="store_true",
        help="Manual operator queue review (bypasses automatic prompt throttling)",
    )
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
            result = run_once(store, worker_id, manual_review=args.manual_review)
            if result is not None:
                LOGGER.info("Research job %s: %s", result["job_id"], result["status"])
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research queue connection failed")
        if args.once:
            break
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
