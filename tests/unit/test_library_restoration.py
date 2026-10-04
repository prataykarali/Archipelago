"""Restoration retries missing independent artifacts without destroying real data."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "host_inference"))
from hostapp import corpus_bootstrap as bootstrap
import library_index

pytestmark = pytest.mark.unit


def graph(path: Path, fixture: bool = False) -> None:
    """Write a deliberately synthetic 84-node export."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"nodes": [{"id": f"test-{i}"} for i in range(84)], "stats": {"fixture": fixture}}))


def test_large_fixture_still_requires_restoration(tmp_path):
    path = tmp_path / "okf_graph.json"
    graph(path, fixture=True)
    assert bootstrap.is_stub(path)
    graph(path)
    assert not bootstrap.is_stub(path)


def test_missing_catalog_fetched_even_with_complete_graph(tmp_path, monkeypatch):
    graph(tmp_path / "okf_graph.json")
    calls = []

    def fetch(repo, remote, destination, token):
        calls.append(remote)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = {"books": [{"id": "synthetic", "title": "Synthetic"}]} if "pearson" in remote else {"hf_paths": ["papers/synthetic.pdf"]}
        destination.write_text(json.dumps(data))
        return True

    monkeypatch.setenv("HF_DATASET_REPO", "synthetic/repo")
    monkeypatch.setattr(bootstrap, "_hf_download", fetch)
    report = bootstrap.provision(tmp_path)
    assert calls == ["catalogs/pearson_bookshelf.json", "library_manifest.json"]
    assert report["ok"]
    assert (tmp_path / "host_inference/cache/pearson_bookshelf.json").exists()
    assert not bootstrap.is_stub(tmp_path / "okf_graph.json")


def test_failed_catalog_does_not_replace_real_graph(tmp_path, monkeypatch):
    path = tmp_path / "okf_graph.json"
    graph(path)
    original = path.read_bytes()
    monkeypatch.setenv("HF_DATASET_REPO", "synthetic/repo")
    monkeypatch.setattr(bootstrap, "_hf_download", lambda *args: False)
    report = bootstrap.provision(tmp_path)
    assert not report["ok"]
    assert "data/catalogs/pearson_bookshelf.json" in report["missing"]
    assert path.read_bytes() == original


def test_invalid_download_never_overwrites_graph(tmp_path, monkeypatch):
    path = tmp_path / "okf_graph.json"
    graph(path, fixture=True)
    original = path.read_bytes()

    def invalid(repo, remote, destination, token):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text('{"error": "unavailable"}')
        return True

    monkeypatch.setenv("HF_DATASET_REPO", "synthetic/repo")
    monkeypatch.setattr(bootstrap, "_hf_download", invalid)
    report = bootstrap.provision(tmp_path)
    assert path.read_bytes() == original
    assert report["source"] == "fixture" and not report["ok"]
    assert len(report["missing"]) == 3


def test_corrupt_graph_restored_to_explicit_fixture(tmp_path, monkeypatch):
    graph(tmp_path / bootstrap.FIXTURE_DIR / "okf_graph.json", fixture=True)
    (tmp_path / "okf_graph.json").write_text("<html>Bad</html>")
    monkeypatch.delenv("HF_DATASET_REPO", raising=False)
    report = bootstrap.provision(tmp_path)
    assert report["source"] == "fixture"
    assert report["concepts"] == 84
    assert not report["ok"]


def test_ambiguous_basename_is_not_guessed(monkeypatch):
    monkeypatch.setattr(library_index, "load_hf_paths", lambda: ["papers/same.pdf", "textbooks/same.pdf"])
    assert library_index.resolve_hf_path("same.pdf") == ""
    assert library_index.resolve_hf_path("papers/same.pdf") == "papers/same.pdf"


def test_non_object_json_cannot_crash_stub_detection(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text("[]")
    assert bootstrap.is_stub(path)
