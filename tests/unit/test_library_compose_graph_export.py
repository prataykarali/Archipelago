"""The library appliance must share one graph export across its services."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_SCRIPT = REPO_ROOT / "scripts/run_ingestion_worker.py"


def _worker_module():
    spec = importlib.util.spec_from_file_location("library_worker_graph_export_test", WORKER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_links_legacy_graph_export_to_shared_volume(monkeypatch, tmp_path):
    worker = _worker_module()
    monkeypatch.setattr(worker, "REPO_ROOT", tmp_path)
    target = tmp_path / "graph-state" / "okf_graph.json"
    monkeypatch.setenv(worker.GRAPH_EXPORT_ENV, str(target))

    worker.ensure_shared_graph_export()
    worker.ensure_shared_graph_export()

    legacy = tmp_path / "okf_graph.json"
    assert legacy.is_symlink()
    legacy.write_text('{"stats":{"total_concepts":1}}', encoding="utf-8")
    assert target.read_text(encoding="utf-8") == legacy.read_text(encoding="utf-8")


def test_worker_refuses_to_replace_existing_graph_export(monkeypatch, tmp_path):
    worker = _worker_module()
    monkeypatch.setattr(worker, "REPO_ROOT", tmp_path)
    monkeypatch.setenv(worker.GRAPH_EXPORT_ENV, str(tmp_path / "graph-state" / "okf_graph.json"))
    legacy = tmp_path / "okf_graph.json"
    legacy.write_text("existing graph", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not the shared volume link"):
        worker.ensure_shared_graph_export()
    assert legacy.read_text(encoding="utf-8") == "existing graph"
