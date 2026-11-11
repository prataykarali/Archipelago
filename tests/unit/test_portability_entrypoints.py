"""Container entrypoint portability checks."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.unit

# ─── Entrypoint modules are importable ──────────────────────────────────────


@pytest.mark.parametrize(
    "relative",
    ["scripts/worker_health.py", "scripts/run_sync_service.py"],
)
def test_entrypoint_modules_import_cleanly(relative):
    import importlib.util

    path = REPO_ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    assert hasattr(module, "main")


def test_worker_entrypoint_defines_signal_handling():
    source = (REPO_ROOT / "scripts" / "run_ingestion_worker.py").read_text(encoding="utf-8")
    assert "SIGTERM" in source, "the container must shut down cleanly"
    assert "install_log_redaction" in source, "worker logs must be redacted"


def test_worker_entrypoint_puts_the_repo_on_sys_path():
    source = (REPO_ROOT / "scripts" / "run_ingestion_worker.py").read_text(encoding="utf-8")
    assert "sys.path.insert" in source
