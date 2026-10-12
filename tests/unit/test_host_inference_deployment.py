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
    import hostapp.factory as factory

    monkeypatch.setattr(factory, "provision", lambda: None)

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


def test_catalog_preserves_full_library_shelf_and_reader_links(hosted_app, monkeypatch):
    import hostapp.routes.library as library_routes

    shelf = [
        {"id": "pearson-book", "title": "Signal Processing", "isPearson": True},
        {"id": "paper.pdf", "title": "Research Paper", "isPearson": False},
    ]
    monkeypatch.setattr(library_routes, "load_library_manifest", lambda: {"ebook_shelf": shelf})
    monkeypatch.setattr(
        library_routes,
        "resolve_hf_path",
        lambda value: "books/papers/paper.pdf" if value == "paper.pdf" else "",
    )

    response = hosted_app.app.test_client().get("/api/catalog/all")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == len(shelf)
    assert payload["documents"][0]["open_url"] == "/open/pearson-book?page=1"
    assert payload["documents"][1]["pdf"] == "books/papers/paper.pdf"


def test_librarian_inventory_import_persists_and_reports_actual_totals(hosted_app, monkeypatch):
    client = hosted_app.app.test_client()
    saved = {}
    # Routes read collaborators from the injected context, not module globals.
    ctx = hosted_app.app.extensions["archipelago"]
    monkeypatch.setattr(ctx.auth, "principal", lambda: ({"role": "librarian"}, None))
    monkeypatch.setattr(ctx.inventory, "save", lambda rows: saved.update(rows=rows))

    response = client.post(
        "/api/library/import",
        data={
            "file": (
                __import__("io").BytesIO(
                    b"book_id,title,total_copies,available_copies\nbk,Graph Book,4,2\n"
                ),
                "inventory.csv",
            )
        },
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

    assert response.status_code == 302
    from urllib.parse import parse_qs, urlsplit

    params = parse_qs(urlsplit(response.headers["Location"]).query)
    assert params["service"][0].endswith("&skipLastRead=true#book/book-1/page/7")


def test_reflowable_pearson_book_opens_reader_instead_of_bookshelf():
    from remote_cache import pearson_page_url

    url = pearson_page_url({"id": "reflow-1", "book_type": "reflowable"}, 9)
    assert "/wr/viewer.html?" in url
    assert url.endswith("&skipLastRead=true#book/reflow-1/page/9")


def test_librarian_chat_does_not_spend_quota(hosted_app, monkeypatch):
    ctx = hosted_app.app.extensions["archipelago"]
    monkeypatch.setattr(ctx.auth, "required", lambda: True)
    monkeypatch.setattr(
        ctx.auth, "principal", lambda: ({"id": "staff-a", "role": "librarian"}, None)
    )
    monkeypatch.setattr(
        ctx.limiter,
        "check_chat",
        lambda: (_ for _ in ()).throw(AssertionError("rate limited")),
    )
    monkeypatch.setattr(
        ctx.limiter,
        "check_daily_chat",
        lambda _user: (_ for _ in ()).throw(AssertionError("quota charged")),
    )
    monkeypatch.setattr(
        ctx.engine, "answer", lambda _query: {"route": "GRAPH_SYNTHESIS"}, raising=False
    )
    monkeypatch.setattr(
        ctx.engine,
        "stream_chat",
        lambda _query, result=None: iter(["{}\n[STREAM_START]\n", "reply"]),
        raising=False,
    )
    client = hosted_app.app.test_client()
    assert client.get("/api/chat/quota").json["unlimited"] is True
    assert client.post("/api/chat", json={"query": "Explain attention"}).status_code == 200


def test_xkiro_rate_limit_uses_grounded_fallback(monkeypatch):
    import engine as hosted_engine
    import hostapp.factory as factory

    monkeypatch.setattr(factory, "provision", lambda: None)

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
    instance.answer = lambda query: {
        "route": "GRAPH_SYNTHESIS",
        "text": "Grounded fallback with [citation].",
        "payload": {"anchor_concept": {"id": "graph_retrieval"}, "logs": []},
    }

    chunks = list(instance.stream_chat("explain graph retrieval"))
    metadata = json.loads(chunks[0].split("\n[STREAM_START]\n", 1)[0])

    assert captured["payload"]["max_tokens"] == 700
    assert "two or three substantial paragraphs" in captured["payload"]["messages"][0]["content"]
    assert (
        json.loads(captured["payload"]["messages"][1]["content"])["user_question"]
        == "explain graph retrieval"
    )
    assert metadata["model"]["provider"] == "xkiro"
    assert chunks[-1] == "Grounded fallback with [citation]."
    assert "Live AI is temporarily unavailable" in chunks[-2]


def test_stream_chat_uses_nvidia_when_xkiro_is_empty(monkeypatch):
    """A failed primary must reach the backup before serving a static draft."""
    import engine.answer as answer_module

    monkeypatch.setenv("XKIRO_API_KEY", "test-x")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-n")
    calls = []

    def fake_response(config, _text, _query):
        calls.append(config["provider"])
        if config["provider"] == "nvidia":
            yield "Live NVIDIA answer."

    monkeypatch.setattr(answer_module, "provider_response", fake_response)
    instance = answer_module.Engine.__new__(answer_module.Engine)
    instance.answer = lambda _query: {
        "route": "GRAPH_SYNTHESIS",
        "text": "Grounded draft.",
        "payload": {"logs": []},
    }

    chunks = list(instance.stream_chat("explain retrieval"))

    assert calls == ["xkiro", "nvidia"]
    assert "Live NVIDIA answer." in chunks
    assert "Grounded draft." not in chunks[1:]


def test_stream_chat_sends_question_and_shows_page_links_first(monkeypatch):
    """A live reply uses the user's question and shows sources above the prose."""
    import engine.answer as answer_module

    monkeypatch.setenv("XKIRO_API_KEY", "test-x")
    seen = []

    def fake_response(_config, _text, query):
        seen.append(query)
        yield "A tailored explanation."

    monkeypatch.setattr(answer_module, "provider_response", fake_response)
    instance = answer_module.Engine.__new__(answer_module.Engine)
    instance.answer = lambda _query: {
        "route": "DEMO",
        "text": "Fixed evidence.\n\n**Paper page.** [Attention p.3](/read?doc=attention.pdf&page=3)",
        "payload": {"logs": []},
    }

    chunks = list(instance.stream_chat("How does attention mechanism work?"))

    assert seen == ["How does attention mechanism work?"]
    assert chunks[1].startswith("**Sources and pages**")
    assert "/read?doc=attention.pdf&page=3" in chunks[1]
    assert chunks[2] == "A tailored explanation."
    assert "Fixed evidence." not in "".join(chunks[1:])


def test_stream_chat_uses_citation_metadata_when_draft_has_no_page_link(monkeypatch):
    import engine.answer as answer_module

    monkeypatch.setenv("XKIRO_API_KEY", "test-x")
    monkeypatch.setattr(
        answer_module, "provider_response", lambda _config, _text, _query: iter(["Live answer."])
    )
    instance = answer_module.Engine.__new__(answer_module.Engine)
    instance.answer = lambda _query: {
        "route": "CROSS_DOMAIN",
        "text": "Grounded evidence without a link line.",
        "payload": {
            "logs": [],
            "citations": [
                {
                    "doc_title": "A Paper",
                    "page_number": 4,
                    "url": "https://huggingface.co/datasets/example/papers/a.pdf",
                }
            ],
        },
    }
    chunks = list(instance.stream_chat("Explain gradient descent"))
    assert "A Paper — page 4" in chunks[1]
    assert "huggingface.co" in chunks[1]
    assert chunks[2] == "Live answer."


def test_greeting_does_not_spend_ai_quota(hosted_app, monkeypatch):
    """Only requests sent to a model spend the daily AI allowance."""
    ctx = hosted_app.app.extensions["archipelago"]
    charges = []
    monkeypatch.setattr(ctx.auth, "required", lambda: True)
    monkeypatch.setattr(
        ctx.auth, "principal", lambda: ({"id": "student-a", "role": "student"}, None)
    )
    monkeypatch.setattr(ctx.limiter, "check_chat", lambda: (False, 0))
    monkeypatch.setattr(
        ctx.limiter,
        "check_daily_chat",
        lambda user_id: (charges.append(user_id) or False, {"remaining": 34, "used": 1}),
    )
    monkeypatch.setattr(
        ctx.engine,
        "answer",
        lambda query: {"route": "GREETING" if query == "hi" else "GRAPH_SYNTHESIS"},
        raising=False,
    )
    monkeypatch.setattr(
        ctx.engine,
        "stream_chat",
        lambda _query, result=None: iter(
            [json.dumps({"routing": result}) + "\n[STREAM_START]\n", "reply"]
        ),
        raising=False,
    )

    client = hosted_app.app.test_client()
    assert client.post("/api/chat", json={"query": "hi"}).status_code == 200
    assert charges == []
    assert client.post("/api/chat", json={"query": "explain attention"}).status_code == 200
    assert charges == ["student-a"]


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
