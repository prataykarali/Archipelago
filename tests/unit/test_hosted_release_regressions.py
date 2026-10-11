"""Regression checks for the public hosted application's release boundaries."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.unit

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))


def test_concept_question_does_not_become_a_paper_lookup() -> None:
    """A title-token collision must not steal a graph or concept question."""
    from engine import Engine

    engine = Engine()
    concept = engine.answer("What are the prerequisites for backpropagation?")
    paper = engine.answer("Open the Rumelhart backpropagation paper at page 2")

    assert concept["route"] != "BOOK_PAGE"
    assert paper["route"] == "BOOK_PAGE"
    assert paper["payload"]["citations"][0]["page_number"] == 2


def test_hosted_ingestion_fails_closed_without_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Staff routes must never pretend a missing worker indexed a document."""
    from hostapp.factory import CONTEXT_KEY, create_app

    monkeypatch.setenv("ARCHIPELAGO_ENV", "production")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.delenv("ARCHIPELAGO_INGESTION_ENABLED", raising=False)
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
