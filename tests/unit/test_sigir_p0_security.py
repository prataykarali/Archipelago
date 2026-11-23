"""Regression checks for private reader aliases and cross-user research dossiers.

These tests intentionally use only fake principals and fake storage; they must
never read private production data or require real account credentials.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
import pytest

ROOT = Path(__file__).resolve().parents[2]
for location in (ROOT / "host_inference", ROOT):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from hostapp.middleware import _is_protected_reader_path, register_middleware


class FakeAuth:
    def __init__(self, principal=None):
        self.user = principal

    def required(self):
        return True

    def principal(self):
        return (self.user, None if self.user else "login required")


class FakeLimiter:
    def check_api(self):
        return (False, 0)

    def check_chat(self):
        return (False, 0)


@pytest.mark.unit
@pytest.mark.parametrize("path", [
    "/read", "/read/some-book", "/open/book-id", "/papers/book.pdf", "/pdfs/book.pdf"
])
def test_reader_aliases_are_protected(path):
    assert _is_protected_reader_path(path)


@pytest.mark.unit
@pytest.mark.parametrize("path", ["/reading", "/pdf", "/library", "/api/readiness"])
def test_non_reader_routes_not_mistaken_for_private_aliases(path):
    assert not _is_protected_reader_path(path)


@pytest.mark.unit
@pytest.mark.parametrize("path", [
    "/read", "/read/subpath", "/open/book-id", "/papers/book.pdf", "/pdfs/book.pdf"
])
def test_anonymous_reader_routes_rejected_by_actual_middleware(path):
    app = Flask(__name__)
    auth = FakeAuth()
    ctx = SimpleNamespace(auth=auth, limiter=FakeLimiter())
    register_middleware(app, ctx)

    app.add_url_rule("/read", "read_base", lambda: "reader")
    app.add_url_rule("/read/<path:subpath>", "read_sub", lambda subpath: "reader")
    app.add_url_rule("/open/<path:book>", "open_book", lambda book: "book")
    app.add_url_rule("/papers/<path:doc>", "papers", lambda doc: "pdf")
    app.add_url_rule("/pdfs/<path:doc>", "pdfs", lambda doc: "pdf")

    assert app.test_client().get(path).status_code == 401

    auth.user = {"id": "owner-1", "role": "student", "token": "test"}
    assert app.test_client().get(path).status_code == 200


@pytest.mark.unit
def test_dossier_does_not_fallback_to_manager_for_another_student(monkeypatch):
    from hostapp.routes.research_intelligence import register
    from archipelago.scholarly.intelligence import run_dossier, storage
    import uuid

    app = Flask(__name__)
    auth = FakeAuth({"id": "student-a", "role": "student", "token": "test"})
    calls = []

    class FakeStore:
        def get_run(self, run_id, owner_id=None, manager=False):
            calls.append((owner_id, manager))
            if manager or owner_id == "student-b":
                return {"run_id": run_id, "owner_id": "student-b", "papers": []}
            return None

    monkeypatch.setattr(storage, "hosted_store", lambda: FakeStore())
    monkeypatch.setattr(run_dossier, "build_run_dossier", lambda data: data)
    monkeypatch.delenv("VERCEL", raising=False)

    register(app, SimpleNamespace(auth=auth))
    run_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
    url = f"/api/research/intelligence/runs/{run_id}/dossier"

    response = app.test_client().get(url)
    assert response.status_code == 404
    assert calls == [("student-a", False)]

    auth.user = {"id": "admin-1", "role": "administrator", "token": "test"}
    response_manager = app.test_client().get(url)
    assert response_manager.status_code == 200
    assert calls[-1] == ("admin-1", True)
