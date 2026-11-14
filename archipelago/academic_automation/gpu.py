"""Shared local GPU lease and explicit desktop consent for academic jobs."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import time

import requests  # type: ignore[import-untyped]

from archipelago.ingestion.gpu_lease import (
    GPU_LOCK_PATH,
    GPUJobTypeRejected,
    GPUWorkerBusy,
    shared_gpu_lease,
    unload_ollama_model,
)

GPU_PROBE_TIMEOUT = 5
CONSENT_TIMEOUT = 300
GRACEFUL_STOP_TIMEOUT = 15.0
OLLAMA_PS_URL = "http://127.0.0.1:11434/api/ps"
_PROTECTED_PROCESS_TOKENS = (
    "xorg",
    "xwayland",
    "gnome-shell",
    "kwin",
    "mutter",
    "sway",
    "wayfire",
    "hyprland",
    "nvidia",
    "systemd",
    "dbus",
    "pipewire",
)


@dataclass(frozen=True)
class BlockingCudaProcess:
    """Metadata for a non-Ollama CUDA process occupying the GPU."""

    pid: int
    process_name: str
    used_mib: int
    cmdline: str
    uid: int | None
    is_system_protected: bool
    supports_graceful_stop: bool


def _read_cmdline(pid: int) -> str:
    """Read /proc/<pid>/cmdline safely without failing on exited processes."""
    try:
        return (
            (Path("/proc") / str(pid) / "cmdline")
            .read_bytes()
            .replace(b"\x00", b" ")
            .decode(errors="replace")
            .strip()
        )
    except OSError:
        return ""


def _read_uid(pid: int) -> int | None:
    """Read real UID from /proc/<pid>/status."""
    try:
        for line in (Path("/proc") / str(pid) / "status").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Uid:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    return int(parts[1])
    except OSError:
        pass
    return None


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


def _read_ppid(pid: int) -> int | None:
    """Read parent PID from /proc/<pid>/status."""
    try:
        for line in (Path("/proc") / str(pid) / "status").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("PPid:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    return int(parts[1])
    except OSError:
        pass
    return None


def _is_ollama_process(pid: int) -> bool:
    """Allow the active ingestion worker, its child processes, and Ollama runners."""
    if pid == os.getpid() or _read_ppid(pid) == os.getpid():
        return True
    cmd = _read_cmdline(pid).casefold()
    if not cmd:
        # Process already exited between nvidia-smi and /proc read
        return True
    ppid = _read_ppid(pid)
    if ppid is not None and "ollama" in _read_cmdline(ppid).casefold():
        return True
    return "ollama" in cmd or "llama-server" in cmd or "archipelago" in cmd


def inspect_blocking_cuda_processes() -> list[BlockingCudaProcess]:
    """List non-Ollama CUDA processes with ownership and safe-stop eligibility."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name,used_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=GPU_PROBE_TIMEOUT,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise GPUUnavailable("GPU process probe unavailable") from exc

    current_uid = os.getuid()
    blockers: list[BlockingCudaProcess] = []
    for line in result.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        pid = int(parts[0])
        if _is_ollama_process(pid):
            continue
        proc_name = parts[1]
        used_mib = int(parts[2]) if parts[2].isdigit() else 0
        cmdline = _read_cmdline(pid)
        uid = _read_uid(pid)
        lowered = f"{proc_name} {cmdline}".casefold()
        is_protected = (uid is not None and uid != current_uid) or any(
            tok in lowered for tok in _PROTECTED_PROCESS_TOKENS
        )
        supports_graceful = (not is_protected) and ("python" in lowered)
        blockers.append(
            BlockingCudaProcess(
                pid=pid,
                process_name=proc_name,
                used_mib=used_mib,
                cmdline=cmdline or proc_name,
                uid=uid,
                is_system_protected=is_protected,
                supports_graceful_stop=supports_graceful,
            )
        )
    return blockers


def unload_idle_archipelago_models(target_model: str | None = None) -> list[str]:
    """Unload Archipelago-owned Ollama models before checking GPU exclusivity."""
    unloaded: list[str] = []
    for loaded_name in sorted(active_model_names()):
        if (
            loaded_name
            and (target_model is None or loaded_name != target_model)
            and unload_ollama_model(loaded_name)
        ):
            unloaded.append(loaded_name)
    return unloaded


def desktop_gpu_conflict_consent(
    job_id: str,
    title: str,
    blockers: list[BlockingCudaProcess],
) -> str:
    """Ask the owner how to handle a GPU conflict; never auto-select stop."""
    if not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
        return "defer"
    summary = "; ".join(
        f"PID {b.pid} ({b.process_name}, {b.used_mib} MiB: {b.cmdline[:60]})"
        for b in blockers[:3]
    )
    choices = ("defer", "stop_and_ingest", "cancel")
    try:
        result = subprocess.run(
            [
                "zenity",
                "--list",
                "--title=Archipelago GPU admission conflict",
                f"--text=Job {job_id[:8]} ({title[:100]}) needs exclusive RTX 2050 access.\nBlocked by: {summary}\nChoose an action:",
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


def gracefully_stop_process(
    blocker: BlockingCudaProcess,
    *,
    timeout_s: float = GRACEFUL_STOP_TIMEOUT,
) -> tuple[bool, str]:
    """Verify exact PID identity and send SIGINT then SIGTERM (never SIGKILL/pkill)."""
    if blocker.is_system_protected or not blocker.supports_graceful_stop:
        return False, "unsafe_or_protected_workload"
    if blocker.uid is not None and blocker.uid != os.getuid():
        return False, "uid_mismatch"
    if _read_cmdline(blocker.pid) != blocker.cmdline:
        return False, "pid_identity_changed"

    try:
        os.kill(blocker.pid, signal.SIGINT)
    except ProcessLookupError:
        return True, "already_exited"
    except PermissionError:
        return False, "permission_denied"

    deadline = time.monotonic() + timeout_s
    sigterm_sent = False
    while time.monotonic() < deadline:
        if not (Path("/proc") / str(blocker.pid)).exists() and blocker.pid not in compute_processes():
            return True, "exited_gracefully"
        if not sigterm_sent and time.monotonic() >= deadline - (timeout_s * 0.4):
            if _read_cmdline(blocker.pid) != blocker.cmdline:
                return False, "pid_identity_changed"
            try:
                os.kill(blocker.pid, signal.SIGTERM)
                sigterm_sent = True
            except ProcessLookupError:
                return True, "exited_gracefully"
            except PermissionError:
                return False, "permission_denied"
        time.sleep(0.3)
    return False, "graceful_stop_timed_out"


def admit_gpu_for_job(
    job_id: str,
    title: str,
    model: str,
    *,
    conflict_prompt_fn=desktop_gpu_conflict_consent,
) -> tuple[str, str]:
    """Unload idle Archipelago models and resolve any non-Ollama GPU blocker safely.

    Returns (action, detail) where action is one of:
    'admitted', 'deferred', 'cancelled'.
    """
    unload_idle_archipelago_models(target_model=None)
    blockers = inspect_blocking_cuda_processes()
    if not blockers:
        assert_exclusive_occupancy(model)
        return "admitted", "gpu_idle"

    choice = conflict_prompt_fn(job_id, title, blockers)
    if choice == "cancel":
        return "cancelled", "operator_cancelled_on_gpu_conflict"
    if choice != "stop_and_ingest":
        names = ", ".join(f"PID {b.pid} ({b.process_name}, {b.used_mib} MiB)" for b in blockers)
        return "deferred", f"GPU occupied by {names}"

    for blocker in blockers:
        stopped, reason = gracefully_stop_process(blocker)
        if not stopped:
            return "deferred", f"Safe stop unavailable for PID {blocker.pid}: {reason}"

    try:
        assert_exclusive_occupancy(model)
    except GPUUnavailable as exc:
        return "deferred", str(exc)
    return "admitted", "graceful_stop_admitted"


def assert_exclusive_occupancy(model: str) -> None:
    """Reject a second loaded model or unrelated compute process."""
    loaded = active_model_names()
    if loaded - {model}:
        raise GPUUnavailable("Another Ollama model is loaded on the GPU")
    busy = {pid for pid in compute_processes() if not _is_ollama_process(pid)}
    if busy:
        details = ", ".join(f"{pid}:{_read_cmdline(pid)[:60]}" for pid in sorted(busy))
        raise GPUUnavailable(f"Another process is using the GPU ({details})")


@contextmanager
def exclusive_gpu(
    model: str,
    *,
    lock_path: Path = GPU_LOCK_PATH,
    job_type: str = "academic_pdf_ingestion",
) -> Iterator[None]:
    """Hold one cross-process lease, reject other GPU models, and unload on exit."""
    try:
        with shared_gpu_lease(lock_path, job_type=job_type):
            assert_exclusive_occupancy(model)
            try:
                yield
            finally:
                unload_ollama_model(model)
    except (GPUWorkerBusy, GPUJobTypeRejected) as exc:
        raise GPUUnavailable(str(exc)) from exc


def desktop_consent(title: str, *, model: str, pending_count: int = 1) -> str:
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
                f"--text={pending_count} eligible academic job(s) pending.\n{title[:160]}\nModel: {model}\nVRAM budget: 4096 MiB; at most 40 pages / 50 KB per candidate.\nChoose one action.",
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
