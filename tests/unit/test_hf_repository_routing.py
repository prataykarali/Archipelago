"""Keep paper references and graph artifacts in their assigned repositories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archipelago.scholarly.bridge.hf_export import publish_library_papers, publish_okf_dataset
from host_inference.publish_cache import upload_hf

pytestmark = pytest.mark.unit


def test_research_job_sends_paper_pointers_to_library_and_okf_to_graphier(monkeypatch) -> None:
    uploads: list[dict] = []

    class FakeApi:
        def __init__(self, token: str):
            assert token == "test-token"

        def upload_file(self, **kwargs) -> None:
            uploads.append(kwargs)

    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.delenv("HF_LIBRARY_REPO", raising=False)
    monkeypatch.delenv("ARCHIPELAGO_SCHOLARLY_HF_REPO", raising=False)
    monkeypatch.setattr("huggingface_hub.HfApi", FakeApi)
    paper = {
        "record_key": "key-one",
        "title": "A Paper",
        "source_url": "https://arxiv.org/abs/1234.5678",
        "source_name": "arxiv",
        "topic": "attention",
        "updated_by": "private-user-id",
        "metadata": {
            "arxiv_id": "1234.5678",
            "access_state": "METADATA_ONLY",
            "verified_extractions": [
                {
                    "group": "experiments",
                    "field": "datasets",
                    "value": "Research benchmark",
                    "evidence_text": "A longer raw abstract sentence should not be copied into the library.",
                    "verification_status": "abstract_quote_matched",
                }
            ],
        },
    }
    library = publish_library_papers("job-one", [paper])
    graph = publish_okf_dataset("job-one", [{"schema": "research_okf"}])

    assert library["repo_id"] == "Prataykarali/Library_books"
    assert graph["repo_id"] == "Prataykarali/graphier"
    assert uploads[0]["path_in_repo"] == "catalogs/research_papers/job-one.jsonl"
    assert uploads[1]["path_in_repo"] == "datasets/research_okf/job-one.jsonl"
    manifest = json.loads(uploads[0]["path_or_fileobj"].getvalue().decode())
    assert manifest["source_url"] == paper["source_url"]
    assert "updated_by" not in manifest
    assert "content" not in manifest
    assert manifest["verified_facts"][0]["value"] == "Research benchmark"
    assert "evidence_text" not in manifest["verified_facts"][0]


def test_inference_cache_publishes_graph_and_catalog_separately(monkeypatch) -> None:
    uploads: list[tuple[str, str]] = []

    class FakeApi:
        def __init__(self, token: str):
            assert token == "test-token"

        def upload_file(self, **kwargs) -> None:
            uploads.append((kwargs["repo_id"], kwargs["path_in_repo"]))

    monkeypatch.setattr("huggingface_hub.HfApi", FakeApi)
    upload_hf({"HF_TOKEN": "test-token"}, b"{}", b"{}")
    assert uploads == [
        ("Prataykarali/graphier", "graph/okf_graph.json"),
        ("Prataykarali/Library_books", "pearson_public.json"),
    ]


def test_cold_boot_fetches_graph_and_catalog_from_separate_repositories(
    monkeypatch, tmp_path
) -> None:
    from host_inference.hostapp import corpus_bootstrap

    calls: list[tuple[str, str]] = []
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.delenv("HF_LIBRARY_REPO", raising=False)
    monkeypatch.delenv("ARCHIPELAGO_SCHOLARLY_HF_REPO", raising=False)

    def fake_download(repo: str, remote: str, destination: Path, _token: str) -> bool:
        calls.append((repo, remote))
        destination.parent.mkdir(parents=True, exist_ok=True)
        if remote.endswith("okf_graph.json"):
            destination.write_text(
                json.dumps({"nodes": [{"id": f"c{i}"} for i in range(51)]}), encoding="utf-8"
            )
        else:
            destination.write_text("{}", encoding="utf-8")
        return True

    monkeypatch.setattr(corpus_bootstrap, "_hf_download", fake_download)
    report = corpus_bootstrap.provision(tmp_path)
    assert report["ok"] is True
    assert calls == [
        ("Prataykarali/graphier", "graph/okf_graph.json"),
        ("Prataykarali/Library_books", "catalogs/pearson_bookshelf.json"),
    ]
