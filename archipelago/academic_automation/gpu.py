"""Shared local GPU lease and explicit desktop consent for academic jobs."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess

import requests  # type: ignore[import-untyped]

from archipelago.ingestion.gpu_lease import GPU_LOCK_PATH, GPUWorkerBusy, shared_gpu_lease

GPU_PROBE_TIMEOUT = 5
CONSENT_TIMEOUT = 300
OLLAMA_PS_URL = "http://127.0.0.1:11434/api/ps"


class GPUUnavailable(RuntimeError):
    """The local GPU cannot be used exclusively."""


def active_model_names() -> set[str]:
    """Read loaded Ollama models without starting another model."""
    try:
        response = requests.get(OLLAMA_PS_URL, timeout=GPU_PROBE_TIMEOUT)
        response.raise_for_status()
        return {
            str(row.get("name") or row.get("model") or "")
            for row in response.json().get("models", [])
            if isinstance(row, dict)
        }
    except (requests.RequestException, ValueError, AttributeError) as exc:
        raise GPUUnavailable("Ollama model occupancy is unavailable") from exc


def compute_processes() -> set[int]:
    """Read NVIDIA compute PIDs; fail closed if the device cannot be probed."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
            timeout=GPU_PROBE_TIMEOUT,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise GPUUnavailable("GPU process probe unavailable") from exc
    return {int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()}


def _is_ollama_process(pid: int) -> bool:
    """Allow the configured Ollama server while refusing unrelated GPU work."""
    try:
        command = (
            (Path("/proc") / str(pid) / "cmdline")
            .read_bytes()
            .replace(b"\x00", b" ")
            .decode(errors="replace")
        )
    except OSError:
        return False
    return "ollama" in command.casefold()


def assert_exclusive_occupancy(model: str) -> None:
    """Reject a second loaded model or unrelated compute process."""
    loaded = active_model_names()
    if loaded - {model}:
        raise GPUUnavailable("Another Ollama model is loaded on the GPU")
    busy = {pid for pid in compute_processes() if not _is_ollama_process(pid)}
    if busy:
        raise GPUUnavailable("Another process is using the GPU")


@contextmanager
def exclusive_gpu(model: str, *, lock_path: Path = GPU_LOCK_PATH) -> Iterator[None]:
    """Hold one cross-process lease and reject other loaded GPU models."""
    try:
        with shared_gpu_lease(lock_path):
            assert_exclusive_occupancy(model)
            yield
    except GPUWorkerBusy as exc:
        raise GPUUnavailable(str(exc)) from exc


def desktop_consent(title: str, *, model: str) -> str:
    """Ask the local operator once; return a fixed action, never implicit consent."""
    if not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
        return "defer"
    choices = ("approve_once", "approve_class", "cpu", "defer", "cancel")
    try:
        result = subprocess.run(
            [
                "zenity",
                "--list",
                "--title=Archipelago academic GPU request",
                f"--text=Academic OKF extraction for {title[:160]}\nModel: {model}\nChoose one action.",
                "--column=Action",
                *choices,
                f"--timeout={CONSENT_TIMEOUT}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=CONSENT_TIMEOUT + GPU_PROBE_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "defer"
    selection = result.stdout.strip()
    return selection if result.returncode == 0 and selection in choices else "defer"


def gpu_snapshot() -> dict[str, object]:
    """Expose only aggregate resource state, never process command lines."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=GPU_PROBE_TIMEOUT,
        )
        first = result.stdout.splitlines()[0].split(",")
        return {
            "available": True,
            "active_models": sorted(active_model_names()),
            "compute_process_count": len(compute_processes()),
            "memory_used_mib": int(first[0].strip()),
            "memory_total_mib": int(first[1].strip()),
            "utilization_percent": int(first[2].strip()),
        }
    except (
        GPUUnavailable,
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        ValueError,
        IndexError,
    ) as exc:
        return {"available": False, "reason": str(exc)}
