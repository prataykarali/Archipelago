from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from library_inventory import inventory_stats, parse_inventory_csv


def test_inventory_csv_validates_counts_and_computes_stats():
    rows = parse_inventory_csv(
        b"book_id,title,total_copies,available_copies,location\n"
        b"bk-1,Graph Systems,5,3,Central Library\n"
        b"bk-2,Data Mining,2,2,Block B\n"
    )

    assert rows[0]["available_ratio"] == "3 / 5"
    assert rows[0]["location"] == "Central Library"
    assert inventory_stats(rows) == {
        "total_records": 2,
        "total_copies": 7,
        "available_copies": 5,
    }


@pytest.mark.parametrize(
    "payload",
    [
        b"title,total_copies,available_copies\nBook,1,1\n",
        b"book_id,title,total_copies,available_copies\nbk,Book,2,3\n",
        b"book_id,title,total_copies,available_copies\nbk,Book,nope,0\n",
        b"book_id,title,total_copies,available_copies\nbk,Book,1,1\nbk,Duplicate,1,1\n",
    ],
)
def test_inventory_csv_rejects_invalid_rows(payload):
    with pytest.raises(ValueError):
        parse_inventory_csv(payload)


@pytest.fixture
def hosted_app(monkeypatch):
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    import engine as hosted_engine

    class Graph:
        nodes = {
            "graph_retrieval": {"summary": "Retrieval over a graph."},
            "embeddings": {"summary": "Vector representations."},
            "indexing": {"summary": "Organizing searchable data."},
        }
        out = {"graph_retrieval": [("REQUIRES", "indexing")]}
        inn = {"graph_retrieval": [("UNLOCKS", "embeddings")]}

        def rank(self, query, top_k=1):
            return [(0.9, "graph_retrieval")]

        def label(self, node_id):
            return node_id.replace("_", " ").title()

    fake_engine = SimpleNamespace(graph=Graph(), books=[], cache_info={"source": "test"})
    monkeypatch.setattr(hosted_engine, "Engine", lambda: fake_engine)
    sys.modules.pop("server", None)
    server = importlib.import_module("server")
    yield server
    sys.modules.pop("server", None)


def test_graph_page_and_bounded_graph_api_work(hosted_app):
    client = hosted_app.app.test_client()

    page = client.get("/graph")
    response = client.get("/api/graph/subgraph?q=graph+retrieval&max_nodes=10")

    assert page.status_code == 200
    assert b"Explore connected concepts" in page.data
    assert response.status_code == 200
    data = response.get_json()
    assert data["target_id"] == "graph_retrieval"
    assert len(data["nodes"]) == 3
    assert all("data" in edge for edge in data["edges"])


def test_librarian_inventory_import_persists_and_reports_actual_totals(hosted_app, monkeypatch):
    client = hosted_app.app.test_client()
    saved = {}
    # Routes read collaborators from the injected context, not module globals.
    ctx = hosted_app.app.extensions["archipelago"]
    monkeypatch.setattr(ctx.auth, "principal", lambda: ({"role": "librarian"}, None))
    monkeypatch.setattr(ctx.inventory, "save", lambda rows: saved.update(rows=rows))

    response = client.post(
        "/api/library/import",
        data={"file": ( __import__("io").BytesIO(
            b"book_id,title,total_copies,available_copies\nbk,Graph Book,4,2\n"
        ), "inventory.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["holdings_stats"] == {
        "total_records": 1,
        "total_copies": 4,
        "available_copies": 2,
    }
    assert saved["rows"][0]["title"] == "Graph Book"


def test_pearson_link_preserves_deep_link_without_rendering_credentials(hosted_app, monkeypatch):
    import hostapp.routes.reader as reader_routes

    monkeypatch.setattr(reader_routes, "load_books", lambda: [{
        "id": "book-1",
        "title": "Reader title",
        "book_type": "pdf",
        "subscription_id": "sub-1",
    }])
    response = hosted_app.app.test_client().get("/open/book-1?page=7")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("#book/book-1/page/7")
    assert b"password" not in response.data.lower()


def test_xkiro_rate_limit_uses_grounded_fallback(monkeypatch):
    import engine as hosted_engine

    class RateLimitedResponse:
        status_code = 429

        def close(self):
            pass

    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, payload=kwargs["json"])
        return RateLimitedResponse()

    monkeypatch.setenv("XKIRO_API_KEY", "configured-test-key")
    monkeypatch.setattr(hosted_engine.requests, "post", fake_post)
    instance = hosted_engine.Engine.__new__(hosted_engine.Engine)
    instance.graph = SimpleNamespace(nodes={
        "graph_retrieval": {"id": "graph_retrieval", "summary": "Graph retrieval follows indexed links."},
    })
    instance.answer = lambda query: {
        "route": "GRAPH_SYNTHESIS",
        "text": "Grounded fallback with [citation].",
        "payload": {"anchor_concept": {"id": "graph_retrieval"}, "logs": []},
    }

    chunks = list(instance.stream_chat("explain graph retrieval"))
    metadata = json.loads(chunks[0].split("\n[STREAM_START]\n", 1)[0])

    assert captured["payload"]["max_tokens"] == 160
    assert "1–2 crisp sentences" in captured["payload"]["messages"][0]["content"]
    assert metadata["model"]["provider"] == "xkiro"
    assert chunks[-1] == "Grounded fallback with [citation]."


def test_server_is_a_thin_shim_over_the_hostapp_factory(hosted_app):
    from hostapp import CONTEXT_KEY

    assert hosted_app.app.extensions[CONTEXT_KEY] is not None
    assert callable(hosted_app.create_app)


def test_create_app_accepts_an_injected_context(hosted_app):
    import hostapp

    ctx = hosted_app.app.extensions[hostapp.CONTEXT_KEY]
    app = hostapp.create_app(ctx)

    assert app.test_client().get("/api/graph/subgraph?q=graph+retrieval").status_code == 200


def test_health_reports_live_counts_not_hardcoded(hosted_app):
    body = hosted_app.app.test_client().get("/api/readiness").get_json()

    assert body["ok"] is True
    assert body["concepts"] == len(hosted_app.app.extensions["archipelago"].engine.graph.nodes)
    assert body["ingestion"] is False
