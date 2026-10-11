"""Regression checks for the public hosted application's release boundaries."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.unit

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))


def test_concept_question_does_not_become_a_paper_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """A title-token collision must not steal a graph or concept question."""
    from engine import Engine

    engine = Engine(graph_path=HOST / "fixtures" / "okf_graph.json")
    monkeypatch.setattr(
        engine.catalog,
        "reply",
        lambda _query: {
            "text": "Indexed source page",
            "citation": {"page_number": 2, "doc_id": "indexed-book"},
        },
    )
    concept = engine.answer("What are the prerequisites for backpropagation?")
    paper = engine.answer("Open the indexed textbook at page 2")

    assert concept["route"] != "BOOK_PAGE"
    assert paper["route"] == "BOOK_PAGE"
    assert paper["payload"]["citations"][0]["page_number"] == 2


def test_hosted_ingestion_fails_closed_without_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Staff routes must never pretend a missing worker indexed a document."""
    from hostapp.factory import CONTEXT_KEY, create_app

    monkeypatch.setenv("ARCHIPELAGO_ENV", "production")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.delenv("ARCHIPELAGO_INGESTION_ENABLED", raising=False)
    from engine import Engine
    import hostapp.factory as factory

    monkeypatch.setattr(factory, "provision", lambda: None)
    import engine as hosted_engine

    monkeypatch.setattr(
        hosted_engine, "Engine", lambda: Engine(graph_path=HOST / "fixtures" / "okf_graph.json")
    )
    app = create_app()
    client = app.test_client()

    assert client.get("/api/ingest/capabilities").json["upload_api_enabled"] is False
    assert client.post("/api/ingest/index", json={"doc_id": "example"}).status_code == 401
    assert client.get("/api/ingest/unknown").status_code == 401

    class LibrarianAuth:
        def principal(self):
            return {"role": "librarian", "username": "test"}, None

        def required(self):
            return True

    app.extensions[CONTEXT_KEY].auth = LibrarianAuth()
    assert client.post("/api/ingest/index", json={"doc_id": "example"}).status_code == 501
    assert client.get("/api/ingest/unknown").status_code == 404
    app.extensions[CONTEXT_KEY].limiter._api_last_mutation.clear()
    assert client.post("/api/ingest", data={}).status_code == 503


def test_public_auth_pages_have_no_shared_login_shortcut() -> None:
    """The hosted HTML must require each user to enter their own credential."""
    for name in ("landing.html", "login.html"):
        html = (HOST / "ui" / name).read_text(encoding="utf-8")
        assert "Quick 1-Click Access" not in html
        assert "quickFill(" not in html
        assert "doLandingQuickLogin(" not in html


def test_librarian_sign_in_opens_management_console() -> None:
    """Both sign-in surfaces must take staff to the existing console."""
    login = (HOST / "ui" / "login.html").read_text(encoding="utf-8")
    landing = (HOST / "ui" / "landing.html").read_text(encoding="utf-8")
    bridge = (HOST / "ui" / "auth_bridge.js").read_text(encoding="utf-8")
    library = (HOST / "ui" / "library.html").read_text(encoding="utf-8")
    staff = (HOST / "ui" / "staff.html").read_text(encoding="utf-8")

    assert '["librarian", "administrator"].includes(role) ? "/staff"' in login
    assert '"/staff"' in landing
    assert 'routes.push(["Librarian", "/staff"])' in bridge
    assert 'id="librarian-panel"' in staff
    assert 'id="librarian-panel"' not in library


def test_cinematic_pages_and_local_staff_links() -> None:
    """Keep the requested video backdrops and workstation tools in place."""
    ui = HOST / "ui"
    landing = (ui / "landing.html").read_text(encoding="utf-8")
    library = (ui / "library.html").read_text(encoding="utf-8")
    chat = (ui / "index.html").read_text(encoding="utf-8")
    assert "<video" not in landing
    assert 'src="/assets/iem-logo.png"' in landing
    assert 'src="/assets/uem-logo.png"' in landing
    assert "@keyframes reveal-text" in landing
    assert 'data-avatar-clip="hi"' in chat
    assert 'data-archipelago-scene' in chat
    assert "hf_20260717_120352_eb988725-1351-43b3-8095-16e4a1005e3d.mp4" in library
    assert 'data-archipelago-scene' not in landing
    assert 'data-archipelago-scene' not in library
    staff = (ui / "staff.html").read_text(encoding="utf-8")
    assert 'href="/graph?source=local"' in staff
    assert 'http://127.0.0.1:5151' in staff
    graph = (ui / "graph.html").read_text(encoding="utf-8")
    assert 'http://127.0.0.1:5150/api/graph' in graph
    from hostapp.middleware import CONTENT_SECURITY_POLICY

    assert "media-src 'self' https://d8j0ntlcm91z4.cloudfront.net" in CONTENT_SECURITY_POLICY


def test_local_tools_require_staff_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """A student cannot use a hosted redirect to open the local console."""
    import engine as hosted_engine
    import hostapp.factory as factory
    from hostapp.factory import CONTEXT_KEY

    real_engine = hosted_engine.Engine
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setattr(factory, "provision", lambda: None)
    monkeypatch.setattr(
        hosted_engine,
        "Engine",
        lambda: real_engine(graph_path=HOST / "fixtures" / "okf_graph.json"),
    )
    app = factory.create_app()
    client = app.test_client()
    assert client.get("/local-console").headers["Location"].startswith("/login?")

    class RoleAuth:
        role = "student"

        def principal(self):
            return {"role": self.role, "username": "test"}, None

        def required(self):
            return True

    auth = RoleAuth()
    app.extensions[CONTEXT_KEY].auth = auth
    assert client.get("/local-console").headers["Location"] == "/chat"
    assert client.get("/staff").headers["Location"] == "/chat"
    auth.role = "faculty"
    assert client.get("/local-graph").headers["Location"] == "/chat"
    assert client.get("/graph?source=local").headers["Location"] == "/chat"
    auth.role = "librarian"
    assert client.get("/local-console").headers["Location"] == "/staff"
    assert client.get("/staff").status_code == 200
    assert client.get("/local-graph").headers["Location"] == "/graph?source=local"
    auth.role = "administrator"
    assert client.get("/local-console").status_code == 302


def test_pearson_gateway_preserves_book_after_sign_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """The automatic Pearson sign-in retains the selected book and page."""
    import engine as hosted_engine
    import hostapp.factory as factory
    import hostapp.routes.reader as reader
    from remote_cache import pearson_page_url

    book = {
        "id": "fixture-book",
        "title": "Digital Signal Processing",
        "book_type": "pdf",
        "subscription_id": "fixture-subscription",
    }
    real_engine = hosted_engine.Engine
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    monkeypatch.setattr(factory, "provision", lambda: None)
    monkeypatch.setattr(
        hosted_engine,
        "Engine",
        lambda: real_engine(graph_path=HOST / "fixtures" / "okf_graph.json"),
    )
    monkeypatch.setattr(reader, "load_books", lambda: [book])
    client = factory.create_app().test_client()
    response = client.get("/open/fixture-book?page=7")

    assert response.status_code == 302
    assert response.headers["Location"].startswith(
        "https://admin.elibrary.in.pearson.com/sso/login?"
    )
    from urllib.parse import parse_qs, urlsplit

    params = parse_qs(urlsplit(response.headers["Location"]).query)
    assert params["service"] == [pearson_page_url(book, 7)]
    assert params["eulogin"] == ["true"]
