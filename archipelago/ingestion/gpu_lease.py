"""Cross-process local lease shared by academic and research GPU workers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import fcntl
import logging
from pathlib import Path

import requests  # type: ignore[import-untyped]

GPU_LOCK_PATH = Path.home() / ".cache" / "archipelago" / "gpu-worker.lock"
OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
UNLOAD_TIMEOUT_SECONDS = 5.0
LOGGER = logging.getLogger(__name__)

ALLOWED_GPU_JOB_TYPES = frozenset(
    {
        "academic_pdf_ingestion",
        "opac_linked_document_ingestion",
        "academic_concept_extraction",
        "academic_ocr_processing",
    }
)

DISALLOWED_GPU_JOB_TYPES = frozenset(
    {
        "chat",
        "research_chat",
        "scholarly_search",
        "research_monitoring",
        "excel_generation",
        "ui_rendering",
        "experimental_research",
    }
)


class GPUWorkerBusy(RuntimeError):
    """Another Archipelago worker holds the GPU lease."""


class GPUJobTypeRejected(ValueError):
    """The requested job_type is not permitted to acquire the local GPU."""


def validate_gpu_job_type(job_type: str | None) -> str:
    """Enforce the server-side GPU job_type allowlist."""
    normalized = (job_type or "").strip()
    if normalized not in ALLOWED_GPU_JOB_TYPES:
        raise GPUJobTypeRejected(
            f"GPU lease rejected for job_type={normalized!r}; "
            f"allowed={sorted(ALLOWED_GPU_JOB_TYPES)}"
        )
    return normalized


def unload_ollama_model(
    model: str,
    *,
    endpoint: str = OLLAMA_GENERATE_URL,
    timeout: float = UNLOAD_TIMEOUT_SECONDS,
) -> bool:
    """Unload an idle Archipelago-owned Ollama model via keep_alive=0."""
    target = (model or "").strip()
    if not target:
        return False
    try:
        response = requests.post(
            endpoint,
            json={"model": target, "keep_alive": 0, "prompt": "", "stream": False},
            timeout=timeout,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        LOGGER.warning("Unable to unload Ollama model %s: %s", target, exc)
        return False


@contextmanager
def shared_gpu_lease(
    lock_path: Path = GPU_LOCK_PATH,
    *,
    job_type: str = "academic_pdf_ingestion",
) -> Iterator[None]:
    """Allow only one allowlisted Archipelago heavy model job across local processes."""
    validate_gpu_job_type(job_type)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise GPUWorkerBusy("Another Archipelago GPU job is active") from exc
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
