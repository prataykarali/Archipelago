"""Serverless scratch paths keep the hosted bundle read-only."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

from flask import Flask
import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from runtime_paths import runtime_cache_dir  # noqa: E402
import vercel_wsgi  # noqa: E402

pytestmark = pytest.mark.unit


def test_local_runtime_uses_host_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("ARCHIPELAGO_RUNTIME_CACHE_DIR", raising=False)
    assert runtime_cache_dir() == HOST / "cache"


def test_vercel_runtime_uses_writable_scratch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("ARCHIPELAGO_RUNTIME_CACHE_DIR", raising=False)
    assert runtime_cache_dir() == Path(tempfile.gettempdir()) / "archipelago-cache"


def test_explicit_runtime_cache_takes_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("ARCHIPELAGO_RUNTIME_CACHE_DIR", str(tmp_path))
    assert runtime_cache_dir() == tmp_path


def test_vercel_entrypoint_rejects_fixture_and_stamps_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from hostapp import factory

    artifacts = {
        "okf_graph.json": {"nodes": [{"id": "concept"}]},
        "pearson_bookshelf.json": {"books": [{"id": "book", "title": "Book"}]},
        "library_manifest.json": {"hf_paths": ["approved.pdf"]},
    }
    for name, payload in artifacts.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    graph = SimpleNamespace(nodes={"concept": {}}, corpus_source="full")
    context = SimpleNamespace(
        engine=SimpleNamespace(
            graph=graph,
            books=[{"id": "book"}],
            cache_info={"source": "supabase", "cache": str(tmp_path)},
        )
    )
    monkeypatch.setattr(vercel_wsgi, "MINIMUM_LIVE_CONCEPTS", 1)
    monkeypatch.setattr(vercel_wsgi, "MINIMUM_LIVE_PEARSON_BOOKS", 1)
    monkeypatch.setattr(factory, "create_app", lambda _context: Flask(__name__))
    monkeypatch.setenv("ARCHIPELAGO_ENV", "development")
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "test-release")

    app = vercel_wsgi.create_vercel_app(context)
    assert app.test_client().get("/").headers["X-Archipelago-Release"] == "test-release"

    graph.corpus_source = "fixture"
    with pytest.raises(RuntimeError, match="Release blocked"):
        vercel_wsgi.create_vercel_app(context)
