"""Release safety and owner controls with production authentication enabled."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

validate_release_context = importlib.import_module("live_wsgi").validate_release_context


@pytest.fixture
def context(tmp_path):
    artifacts = {
        "okf_graph.json": {"nodes": [{"id": "a"}]},
        "pearson_bookshelf.json": {"books": [{"id": "b", "title": "Book"}]},
        "library_manifest.json": {"hf_paths": ["approved.pdf"]},
    }
    for name, payload in artifacts.items():
        (tmp_path / name).write_text(json.dumps(payload))
    return SimpleNamespace(engine=SimpleNamespace(
        graph=SimpleNamespace(nodes={"a": {}}, corpus_source="full"),
        books=[{"id": "b"}], cache_info={"source": "supabase", "cache": str(tmp_path)},
    ))


def test_valid_remote_release(context):
    validate_release_context(context, {"minimum_concepts": 1, "minimum_pearson_books": 1})


@pytest.mark.parametrize("kind", ["unavailable", "fixture", "graph_shrink", "catalog_shrink", "manifest"])
def test_bad_source_never_replaces_live_release(context, kind):
    policy = {"minimum_concepts": 1, "minimum_pearson_books": 1}
    if kind == "unavailable":
        context.engine.cache_info["source"] = "unavailable"
    elif kind == "fixture":
        context.engine.graph.corpus_source = "fixture"
    elif kind == "graph_shrink":
        policy["minimum_concepts"] = 2
    elif kind == "catalog_shrink":
        policy["minimum_pearson_books"] = 2
    else:
        (Path(context.engine.cache_info["cache"]) / "library_manifest.json").write_text('{"hf_paths": 1}')
    with pytest.raises(RuntimeError, match="Release blocked"):
        validate_release_context(context, policy)


def test_anonymous_owner_controls_remain_available_with_auth_required(monkeypatch, tmp_path):
    from hostapp.factory import create_app
    from hostapp.security import AuthGuard

    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("ARCHIPELAGO_QUIZ_DB", str(tmp_path / "sessions.sqlite3"))
    from cache_service import cache_metrics, cache_service, request_dedup

    app = create_app(SimpleNamespace(
        engine=SimpleNamespace(graph=SimpleNamespace(nodes={}, corpus_source="full"),
                               books=[], cache_info={}),
        auth=AuthGuard(),
        limiter=SimpleNamespace(check_chat=lambda: (False, 0), check_api=lambda: (False, 0)),
        inventory=None, cache_service=cache_service, cache_metrics=cache_metrics,
        request_dedup=request_dedup,
    ))
    client = app.test_client()
    response = client.get("/api/chat/learning-memory")
    assert response.status_code == 200
    assert response.json["enabled"] is False
    assert response.headers["Cache-Control"] == "no-store, private"
    assert client.delete("/api/chat/learning-memory").json["deleted"] is True
    assert client.get("/api/staff/learning-summary").status_code == 401
    assert client.post("/api/ingest").status_code == 403
