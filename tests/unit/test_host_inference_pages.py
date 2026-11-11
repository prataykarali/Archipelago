"""Hosted reader and app composition checks."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

from flask import Flask
import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))


@pytest.fixture
def hosted_app(monkeypatch):
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    import engine as hosted_engine

    class Graph:
        nodes = {  # noqa: RUF012
            "graph_retrieval": {"summary": "Retrieval over a graph."},
            "embeddings": {"summary": "Vector representations."},
            "indexing": {"summary": "Organizing searchable data."},
        }
        out = {"graph_retrieval": [("REQUIRES", "indexing")]}  # noqa: RUF012
        inn = {"graph_retrieval": [("UNLOCKS", "embeddings")]}  # noqa: RUF012

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


def test_pearson_link_preserves_deep_link_without_rendering_credentials(hosted_app, monkeypatch):
    import hostapp.routes.reader as reader_routes

    monkeypatch.setattr(
        reader_routes,
        "load_books",
        lambda: [
            {
                "id": "book-1",
                "title": "Reader title",
                "book_type": "pdf",
                "subscription_id": "sub-1",
            }
        ],
    )
    response = hosted_app.app.test_client().get("/open/book-1?page=7")

    assert response.status_code == 200
    assert b"Sign in to Pearson" in response.data
    direct = hosted_app.app.test_client().get("/open/book-1?page=7&direct=1")
    assert direct.status_code == 302
    assert direct.headers["Location"].endswith("#book/book-1/page/7")
    assert b"password" not in response.data.lower()


def test_server_is_a_thin_shim_over_the_hostapp_factory(hosted_app):
    from hostapp import CONTEXT_KEY

    assert hosted_app.app.extensions[CONTEXT_KEY] is not None
    assert callable(hosted_app.create_app)


def test_create_app_accepts_an_injected_context(hosted_app):
    import hostapp

    ctx = hosted_app.app.extensions[hostapp.CONTEXT_KEY]
    app = hostapp.create_app(ctx)

    assert app.test_client().get("/api/graph/subgraph?q=graph+retrieval").status_code == 200


def test_academic_graph_hubs_use_saved_concepts(hosted_app):
    response = hosted_app.app.test_client().get("/api/graph/hubs")

    assert response.status_code == 200
    data = response.get_json()
    assert data["counts"]["concepts"] == 3
    ids = {item["data"]["id"] for item in data["nodes"]}
    assert ids == {"graph_retrieval"}
    assert all(edge["data"]["source"] in ids for edge in data["edges"])


def test_global_graph_pages_cover_every_hosted_concept(hosted_app):
    client = hosted_app.app.test_client()
    first = client.get("/api/graph/page?limit=2").get_json()
    second = client.get(f"/api/graph/page?limit=2&offset={first['next_offset']}").get_json()
    ids = {item["data"]["id"] for page in (first, second) for item in page["nodes"]}
    assert first["counts"]["concepts"] == 3
    assert ids == {"graph_retrieval", "embeddings", "indexing"}
    assert all(edge["data"]["source"] in ids for page in (first, second) for edge in page["edges"])


def test_hosted_global_graph_keeps_source_trail_without_synthetic_edges(hosted_app):
    graph = hosted_app.app.extensions["archipelago"].engine.graph
    graph.nodes["graph_retrieval"]["sources"] = [
        {"doc_id": "papers/retrieval.pdf", "page_number": 3}
    ]
    result = hosted_app.app.test_client().get("/api/graph/page?q=graph_retrieval").get_json()
    node = result["nodes"][0]["data"]
    assert node["source_documents"] == [
        {"id": "papers/retrieval.pdf", "title": "retrieval", "page_number": 3}
    ]
    assert all(edge["data"]["rel_label"] != "SOURCED_FROM" for edge in result["edges"])


def test_academic_neighborhood_exposes_saved_node_facts(hosted_app):
    from hostapp import CONTEXT_KEY

    graph = hosted_app.app.extensions[CONTEXT_KEY].engine.graph
    graph.nodes["graph_retrieval"]["sources"] = [
        {"doc_id": "papers/Graph_Retrieval.pdf", "page_number": 7}
    ]
    response = hosted_app.app.test_client().get(
        "/api/graph/subgraph?target_id=graph_retrieval&max_nodes=10"
    )

    assert response.status_code == 200
    data = response.get_json()
    target = next(node["data"] for node in data["nodes"] if node["data"]["id"] == "graph_retrieval")
    assert target["summary"] == "Retrieval over a graph."
    assert target["degree"] == 2
    assert target["source_count"] == 1
    assert target["source_documents"] == [
        {"id": "papers/Graph_Retrieval.pdf", "title": "Graph Retrieval", "page_number": 7}
    ]
    assert len(data["edges"]) == 2


def test_research_page_renders_new_atlas_and_versioned_controls() -> None:
    from hostapp.research_pages import render_research_page

    html = render_research_page("papers").get_data(as_text=True)
    assert "Ideas are islands" in html
    assert "Ingest 25 papers locally" in html
    assert "research_home.js?v=20261026i" in html


def test_research_login_preserves_progress_job_link() -> None:
    """A staff member can sign back in to the exact running job."""
    from hostapp.routes import pages

    app = Flask(__name__)
    auth = SimpleNamespace(principal=lambda: (None, "expired"))
    pages.register(app, SimpleNamespace(auth=auth))
    response = app.test_client().get("/research/progress?job=bc8526dc-445a-469e-b307-2cf33f4ce2ea")
    assert response.status_code == 302
    assert "next=%2Fresearch%2Fprogress%3Fjob%3Dbc8526dc" in response.location


def test_health_reports_live_counts_not_hardcoded(hosted_app):
    body = hosted_app.app.test_client().get("/api/readiness").get_json()

    assert body["ok"] is True
    assert body["concepts"] == len(hosted_app.app.extensions["archipelago"].engine.graph.nodes)
    assert body["ingestion"] is False


def test_hosted_chat_api_streams_prepared_answer(hosted_app):
    context = hosted_app.app.extensions["archipelago"]
    context.engine.answer = lambda query: {"route": "DIRECT", "text": query}
    context.engine.stream_chat = lambda query, **_kwargs: iter(["Grounded response to ", query])

    response = hosted_app.app.test_client().post("/api/chat", json={"query": "graph retrieval"})

    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == "Grounded response to graph retrieval"
