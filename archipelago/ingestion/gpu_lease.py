"""Cross-process local lease shared by academic and research GPU workers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import fcntl
from pathlib import Path

GPU_LOCK_PATH = Path.home() / ".cache" / "archipelago" / "gpu-worker.lock"


class GPUWorkerBusy(RuntimeError):
    """Another Archipelago worker holds the GPU lease."""


@contextmanager
def shared_gpu_lease(lock_path: Path = GPU_LOCK_PATH) -> Iterator[None]:
    """Allow only one Archipelago heavy model job across local processes."""
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
