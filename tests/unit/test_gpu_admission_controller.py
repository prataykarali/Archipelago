"""Tests for the safe, approval-based GPU admission controller and queue recovery."""

from __future__ import annotations

from pathlib import Path
import signal
from unittest.mock import patch

from archipelago.academic_automation import AcademicStore
from archipelago.academic_automation.gpu import (
    BlockingCudaProcess,
    admit_gpu_for_job,
    exclusive_gpu,
    gracefully_stop_process,
)
from archipelago.academic_automation.worker import run_once


def _make_blocker(
    *,
    pid: int = 999999,
    process_name: str = "python",
    cmdline: str = "python ltc_train.py",
    uid: int | None = None,
    protected: bool = False,
    supports_graceful: bool = True,
) -> BlockingCudaProcess:
    import os

    return BlockingCudaProcess(
        pid=pid,
        process_name=process_name,
        used_mib=70,
        cmdline=cmdline,
        uid=os.getuid() if uid is None else uid,
        is_system_protected=protected,
        supports_graceful_stop=supports_graceful,
    )


def test_admit_gpu_idle_unloads_archipelago_models() -> None:
    unloaded: list[str] = []
    with (
        patch("archipelago.academic_automation.gpu.active_model_names", return_value={"qwen3.5:0.8b"}),
        patch("archipelago.academic_automation.gpu.unload_ollama_model", side_effect=lambda m: unloaded.append(m) or True),
        patch("archipelago.academic_automation.gpu.inspect_blocking_cuda_processes", return_value=[]),
        patch("archipelago.academic_automation.gpu.assert_exclusive_occupancy") as assert_mock,
    ):
        action, detail = admit_gpu_for_job("job-1", "Willard2023", "qwen3.5:0.8b")
    assert action == "admitted"
    assert detail == "gpu_idle"
    assert unloaded == ["qwen3.5:0.8b"]
    assert_mock.assert_called_once_with("qwen3.5:0.8b")


def test_admit_gpu_occupied_defers_without_killing() -> None:
    blocker = _make_blocker()
    with (
        patch("archipelago.academic_automation.gpu.active_model_names", return_value=set()),
        patch("archipelago.academic_automation.gpu.inspect_blocking_cuda_processes", return_value=[blocker]),
        patch("archipelago.academic_automation.gpu.gracefully_stop_process") as stop_mock,
    ):
        action, detail = admit_gpu_for_job(
            "job-1",
            "Willard2023",
            "qwen3.5:0.8b",
            conflict_prompt_fn=lambda *_args: "defer",
        )
    assert action == "deferred"
    assert "999999" in detail
    stop_mock.assert_not_called()


def test_admit_gpu_owner_cancels_keeps_workload_untouched() -> None:
    blocker = _make_blocker()
    with (
        patch("archipelago.academic_automation.gpu.active_model_names", return_value=set()),
        patch("archipelago.academic_automation.gpu.inspect_blocking_cuda_processes", return_value=[blocker]),
        patch("archipelago.academic_automation.gpu.gracefully_stop_process") as stop_mock,
    ):
        action, _detail = admit_gpu_for_job(
            "job-1",
            "Willard2023",
            "qwen3.5:0.8b",
            conflict_prompt_fn=lambda *_args: "cancel",
        )
    assert action == "cancelled"
    stop_mock.assert_not_called()


def test_admit_gpu_owner_approves_safe_interruption_then_admits() -> None:
    blocker = _make_blocker()
    with (
        patch("archipelago.academic_automation.gpu.active_model_names", return_value=set()),
        patch("archipelago.academic_automation.gpu.inspect_blocking_cuda_processes", return_value=[blocker]),
        patch("archipelago.academic_automation.gpu.gracefully_stop_process", return_value=(True, "exited_gracefully")) as stop_mock,
        patch("archipelago.academic_automation.gpu.assert_exclusive_occupancy") as assert_mock,
    ):
        action, detail = admit_gpu_for_job(
            "job-1",
            "Willard2023",
            "qwen3.5:0.8b",
            conflict_prompt_fn=lambda *_args: "stop_and_ingest",
        )
    assert action == "admitted"
    assert detail == "graceful_stop_admitted"
    stop_mock.assert_called_once_with(blocker)
    assert_mock.assert_called_once_with("qwen3.5:0.8b")


def test_gracefully_stop_rejects_protected_or_changed_process() -> None:
    protected = _make_blocker(process_name="Xorg", cmdline="/usr/lib/Xorg", protected=True, supports_graceful=False)
    with patch("os.kill") as kill_mock:
        ok, reason = gracefully_stop_process(protected, timeout_s=0.5)
    assert ok is False
    assert reason == "unsafe_or_protected_workload"
    kill_mock.assert_not_called()

    changed = _make_blocker(pid=12345, cmdline="python ltc_train.py")
    with (
        patch("archipelago.academic_automation.gpu._read_cmdline", return_value="python something_else.py"),
        patch("os.kill") as kill_mock,
    ):
        ok2, reason2 = gracefully_stop_process(changed, timeout_s=0.5)
    assert ok2 is False
    assert reason2 == "pid_identity_changed"
    kill_mock.assert_not_called()


def test_gracefully_stop_sends_sigint_and_observes_clean_exit() -> None:
    blocker = _make_blocker(pid=54321, cmdline="python ltc_train.py")
    calls: list[tuple[int, int]] = []
    with (
        patch("archipelago.academic_automation.gpu._read_cmdline", return_value="python ltc_train.py"),
        patch("os.kill", side_effect=lambda p, s: calls.append((p, s))),
        patch("pathlib.Path.exists", return_value=False),
        patch("archipelago.academic_automation.gpu.compute_processes", return_value=set()),
    ):
        ok, reason = gracefully_stop_process(blocker, timeout_s=1.0)
    assert ok is True
    assert reason == "exited_gracefully"
    assert calls == [(54321, signal.SIGINT)]


def test_exclusive_gpu_unloads_model_on_failure(tmp_path: Path) -> None:
    unloaded: list[str] = []
    lock_file = tmp_path / "gpu.lock"
    with (
        patch("archipelago.academic_automation.gpu.assert_exclusive_occupancy"),
        patch("archipelago.academic_automation.gpu.unload_ollama_model", side_effect=lambda m: unloaded.append(m) or True),
    ):
        try:
            with exclusive_gpu("qwen3.5:0.8b", lock_path=lock_file):
                raise RuntimeError("model load failed")
        except RuntimeError:
            pass
    assert unloaded == ["qwen3.5:0.8b"]


def test_queue_recovery_is_idempotent_and_targets_intended_job(tmp_path: Path) -> None:
    store = AcademicStore(tmp_path / "state.sqlite3")
    pdf = tmp_path / "cand.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with store._connect() as db:
        db.execute(
            "INSERT INTO jobs(job_id,idempotency_key,record_key,status,priority,mode,rights,content_path,content_sha256,created_at,updated_at,error) "
            "VALUES('job-blocked','k1','arxiv:1','queued',0,'gpu','open_permitted',?,'abc','2026-11-14T00:00:00Z','2026-11-14T00:00:00Z','BLOCKED: GPU busy')",
            (str(pdf),),
        )
        db.execute(
            "INSERT INTO jobs(job_id,idempotency_key,record_key,status,priority,mode,rights,content_path,content_sha256,created_at,updated_at,error) "
            "VALUES('job-other','k2','arxiv:2','awaiting_approval',0,'gpu','open_permitted',?,'def','2026-11-14T00:00:00Z','2026-11-14T00:00:00Z',NULL)",
            (str(pdf),),
        )

    rec1 = store.recover_resource_blocked_jobs(job_id="job-blocked")
    assert rec1 == ["job-blocked"]
    assert store.job("job-blocked")["status"] == "awaiting_approval"
    assert store.recover_resource_blocked_jobs(job_id="job-blocked") == []

    # Target only job-blocked; worker defers on GPU conflict without touching job-other
    with (
        patch("archipelago.academic_automation.worker.gpu_snapshot", return_value={"available": True}),
        patch("archipelago.academic_automation.worker.admit_gpu_for_job", return_value=("deferred", "GPU busy")),
    ):
        res = run_once(store, tmp_path, target_job_id="job-blocked")
    assert res["job_id"] == "job-blocked"
    assert store.job("job-other")["status"] == "awaiting_approval"
