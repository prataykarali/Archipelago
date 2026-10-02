"""Health probes for the local ingestion worker.

The Docker appliance needs to know whether the worker is *doing its job*, not
merely whether the process is alive. The worker has no HTTP surface — it is a
background thread consuming a job queue — so this module exposes the smallest
useful contract:

``liveness``
    The process is up and the job store is reachable. Used by Docker's
    ``HEALTHCHECK``; must never depend on the graph being writable.

``readiness``
    The worker can accept an upload: the queue directory exists and the SLM
    extractor has a client. Reported separately from liveness so a
    not-yet-loaded model degrades to "not ready" rather than a restart loop.

Both are plain functions returning a JSON-serialisable mapping so the CLI, the
container healthcheck, and the tests all read the same source of truth.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import sys
from typing import Any

logger = logging.getLogger(__name__)

# Readiness fails when the extraction SLM has no reachable client: ingestion
# would accept a job it cannot finish.
REQUIRED_MODEL_ENV = "ARCHIPELAGO_OLLAMA_MODEL"
DEFAULT_MODEL_ENV = "lib-qwen:latest"


def _ok(**fields: Any) -> dict[str, Any]:
    return {"status": "ok", "healthy": True, **fields}


def _bad(reason: str, **fields: Any) -> dict[str, Any]:
    return {"status": "unhealthy", "healthy": False, "reason": reason, **fields}


def liveness(jobs_dir: Path | str) -> dict[str, Any]:
    """Process is alive and the job store directory is usable."""
    jobs = Path(jobs_dir)
    if not jobs.exists():
        return _bad(f"jobs directory missing: {jobs}", jobs_dir=str(jobs))
    if not jobs.is_dir():
        return _bad(f"jobs path is not a directory: {jobs}", jobs_dir=str(jobs))
    try:
        probe = jobs / ".healthprobe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return _bad(f"jobs directory not writable: {exc}", jobs_dir=str(jobs))
    return _ok(jobs_dir=str(jobs))


def readiness(jobs_dir: Path | str, model_name: str | None = None) -> dict[str, Any]:
    """The worker can accept an upload.

    Checks liveness first, then that an extraction client is constructible. The
    model check is advisory: ingestion also accepts pre-extracted results, and a
    missing Ollama should read as "not ready", never as a crash.
    """
    live = liveness(jobs_dir)
    if not live["healthy"]:
        return live

    model = model_name or _configured_model()
    reachable, detail = _model_reachable(model)
    return {
        "status": "ready" if reachable else "degraded",
        "healthy": True,
        "ready": reachable,
        "jobs_dir": live["jobs_dir"],
        "model": model,
        "model_detail": detail,
    }


def _configured_model() -> str:
    """Model name from the environment, with the documented default."""
    import os

    return os.environ.get(REQUIRED_MODEL_ENV, "").strip() or DEFAULT_MODEL_ENV


def _model_reachable(model: str) -> tuple[bool, str]:
    """Best-effort reachability probe. Never raises.

    The repo root is put on ``sys.path`` first: this script runs as
    ``python scripts/worker_health.py``, where the script's own directory is the
    only entry on the path, so ``archipelago`` would not import otherwise.
    """
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from archipelago.ingestion.lib_qwen_extractor import LibQwenConceptExtractor

        extractor = LibQwenConceptExtractor(model_name=model)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if not getattr(extractor, "client", None):
        return False, "no extraction client configured"
    return True, "client available"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. ``liveness``/``readiness``; exit 0 when healthy."""
    args = list(argv if argv is not None else sys.argv[1:])
    mode = args[0] if args else "readiness"
    jobs_dir = args[1] if len(args) > 1 else "jobs"

    if mode == "liveness":
        payload = liveness(jobs_dir)
    elif mode == "readiness":
        payload = readiness(jobs_dir)
    else:
        print(json.dumps(_bad(f"unknown mode: {mode}")), file=sys.stderr)
        return 2

    print(json.dumps(payload))
    return 0 if payload.get("healthy") else 1


if __name__ == "__main__":
    raise SystemExit(main())
