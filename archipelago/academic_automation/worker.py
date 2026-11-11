"""Stage permitted academic content under local consent and exclusive GPU use."""

from __future__ import annotations

from contextlib import nullcontext
import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import time
from typing import Any

from okf.pipeline import PipelineAborted

from .gpu import (
    GPUUnavailable,
    assert_exclusive_occupancy,
    desktop_consent,
    exclusive_gpu,
    gpu_snapshot,
)
from .store import AcademicStore

MAX_CONTENT_BYTES = 100 * 1024 * 1024
MAX_PROGRESS_PERCENT = 100
MAX_ACADEMIC_PAGES = 40
GPU_RECHECK_SECONDS = 10
MAX_JOB_SECONDS = 3600
APPROVED_SUFFIXES = frozenset({".pdf", ".md", ".txt", ".markdown"})


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _allowed_file(job: dict[str, Any], root: Path) -> Path:
    """Require a bounded immutable local file inside the approved candidate area."""
    candidate_root = (root / "data" / "academic_candidates").resolve()
    path = Path(str(job["content_path"])).resolve()
    if not path.is_relative_to(candidate_root) or path.suffix.lower() not in APPROVED_SUFFIXES:
        raise ValueError("Candidate path or file type is not permitted")
    if not path.is_file() or path.stat().st_size > MAX_CONTENT_BYTES:
        raise ValueError("Candidate file is absent or too large")
    if _file_hash(path) != job["content_sha256"]:
        raise ValueError("Candidate content changed since approval")
    return path


def _model() -> str:
    from okf.config import MODEL_NAME

    return (
        os.getenv("ARCHIPELAGO_ACADEMIC_MODEL")
        or os.getenv("ARCHIPELAGO_INGESTION_MODEL")
        or MODEL_NAME
    )


def stage_job(store: AcademicStore, job: dict[str, Any], root: Path) -> dict[str, Any]:
    """Extract to a cloned graph, validate preservation, then wait for review."""
    from okf.graph.ingest import ingest_to_kuzu
    from okf.graph.safe_staging import (
        extract_graph_inventory,
        prepare_staging_database,
        validate_staging_against_production,
    )
    from okf.pipeline import compute_doc_id, run_pipeline_staged

    job_id = str(job["job_id"])
    source = _allowed_file(job, root)
    if job["rights"] != "open_permitted":
        raise ValueError("Full-text rights are not verified")
    job_dir = root / "data" / "academic_jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    graph_path = root / "okf_graph.db"
    if not graph_path.exists():
        raise FileNotFoundError("Canonical graph is unavailable")
    baseline_hash = _file_hash(graph_path)
    baseline = extract_graph_inventory(graph_path)
    extraction_path = job_dir / "extraction.db"
    stage_path = job_dir / "staging.db"
    store.update_job(job_id, "running", progress={"stage": "parsing", "percent": 0})
    last_gpu_check = 0.0

    def progress(stage: str, percent: int, detail: dict[str, Any]) -> None:
        nonlocal last_gpu_check
        if (store.job(job_id) or {}).get("status") == "cancelled":
            raise PipelineAborted("Academic job cancelled")
        if job["mode"] == "gpu" and time.monotonic() - last_gpu_check >= GPU_RECHECK_SECONDS:
            assert_exclusive_occupancy(_model())
            last_gpu_check = time.monotonic()
        store.update_job(
            job_id,
            "running",
            progress={
                "stage": stage,
                "percent": min(MAX_PROGRESS_PERCENT, percent),
                "detail": detail,
            },
        )

    previous_model = os.environ.get("ARCHIPELAGO_INGESTION_MODEL")
    previous_cpu = os.environ.get("ARCHIPELAGO_ACADEMIC_CPU_ONLY")
    import okf.config as okf_config

    previous_pages = okf_config.MAX_PAGES_PER_DOC
    okf_config.MAX_PAGES_PER_DOC = min(previous_pages or MAX_ACADEMIC_PAGES, MAX_ACADEMIC_PAGES)
    os.environ["ARCHIPELAGO_INGESTION_MODEL"] = _model()
    if job["mode"] == "cpu":
        os.environ["ARCHIPELAGO_ACADEMIC_CPU_ONLY"] = "1"
    try:
        results, scratch_db, _scratch_export = run_pipeline_staged(
            source_path=str(source),
            temp_db_path=str(extraction_path),
            on_progress=progress,
            check_cancelled=lambda: (store.job(job_id) or {}).get("status") == "cancelled",
        )
    finally:
        okf_config.MAX_PAGES_PER_DOC = previous_pages
        if previous_model is None:
            os.environ.pop("ARCHIPELAGO_INGESTION_MODEL", None)
        else:
            os.environ["ARCHIPELAGO_INGESTION_MODEL"] = previous_model
        if previous_cpu is None:
            os.environ.pop("ARCHIPELAGO_ACADEMIC_CPU_ONLY", None)
        else:
            os.environ["ARCHIPELAGO_ACADEMIC_CPU_ONLY"] = previous_cpu
    scratch_db.close()
    del scratch_db
    gc.collect()
    doc_id = compute_doc_id(str(source))
    incoming = [row for row in results if str(row.get("doc_id")) == doc_id]
    if not incoming:
        raise ValueError("No source-linked concepts were extracted")
    prepare_staging_database(stage_path, graph_path)
    connection, staged_db, _merged_export = ingest_to_kuzu(
        incoming,
        db_path=str(stage_path),
        incremental=True,
    )
    connection.close()
    staged_db.close()
    del connection, staged_db
    gc.collect()
    baseline_edges = {(row["from_id"], row["to_id"], row["type"]) for row in baseline["edges"]}
    validation = validate_staging_against_production(
        stage_path,
        baseline["concept_ids"],
        baseline_edges,
    )
    if _file_hash(graph_path) != baseline_hash:
        raise RuntimeError("Canonical graph changed during staging")
    if (store.job(job_id) or {}).get("status") == "cancelled":
        raise PipelineAborted("Academic job cancelled")
    (job_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    (job_dir / "validation.json").write_text(
        json.dumps(validation, sort_keys=True), encoding="utf-8"
    )
    store.update_job(
        job_id,
        "review_ready",
        staging_path=str(stage_path),
        baseline_version=baseline_hash,
        progress={
            "stage": "review",
            "percent": MAX_PROGRESS_PERCENT,
            "new_concepts": validation["added_concepts"],
            "new_edges": validation["added_edges"],
        },
    )
    return validation


def run_once(store: AcademicStore, root: Path) -> dict[str, Any] | None:
    """Process at most one approved job, leaving offline or denied work queued."""
    job = store.next_job()
    if job is None:
        return None
    job_id = str(job["job_id"])
    try:
        if job["status"] == "cpu_requested":
            job["mode"] = "cpu"
        if job["mode"] == "gpu" and not gpu_snapshot().get("available"):
            store.defer(job_id, reason="Local GPU worker or occupancy probe unavailable")
            return {"job_id": job_id, "status": "awaiting_approval"}
        if job["mode"] == "gpu" and not store.has_grant(job_id):
            action = desktop_consent(job["record_key"], model=_model())
            if action == "cancel":
                store.cancel(job_id, "local_operator")
                return {"job_id": job_id, "status": "cancelled"}
            if action == "cpu":
                store.set_mode(job_id, "cpu")
                job["mode"] = "cpu"
            if action == "defer":
                store.defer(job_id, reason="Local GPU approval deferred")
                return {"job_id": job_id, "status": "awaiting_approval"}
            if job["mode"] == "gpu":
                scope = "job" if action == "approve_once" else "trusted_academic_open_content"
                store.grant(
                    scope=scope, job_id=job_id if scope == "job" else None, actor="local_operator"
                )
        lease = exclusive_gpu(_model()) if job["mode"] == "gpu" else nullcontext()
        with lease:
            previous_handler = signal.getsignal(signal.SIGALRM)

            def on_timeout(_signal: int, _frame: Any) -> None:
                raise TimeoutError("Academic job exceeded its processing budget")

            signal.signal(signal.SIGALRM, on_timeout)
            signal.alarm(MAX_JOB_SECONDS)
            try:
                validation = stage_job(store, job, root)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous_handler)
        return {"job_id": job_id, "status": "review_ready", "validation": validation}
    except PipelineAborted:
        if (store.job(job_id) or {}).get("status") == "cancelled":
            return {"job_id": job_id, "status": "cancelled"}
        status = store.retry(job_id, "Pipeline aborted before review")
        return {"job_id": job_id, "status": status}
    except GPUUnavailable as exc:
        store.defer(job_id, reason=str(exc))
        return {"job_id": job_id, "status": "awaiting_approval", "reason": str(exc)}
    except (OSError, ValueError, RuntimeError, KeyError, TimeoutError) as exc:
        if (store.job(job_id) or {}).get("status") == "cancelled":
            return {"job_id": job_id, "status": "cancelled"}
        status = store.retry(job_id, f"{type(exc).__name__}: {exc}")
        return {"job_id": job_id, "status": status}
