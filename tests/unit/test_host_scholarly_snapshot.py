"""Hosted scholarly snapshot keeps publication and fallback status visible."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

from flask import Flask
import requests

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.routes import scholarly  # noqa: E402


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"source_status": {"arxiv": {"mode": "live", "live_records": 1}}}


def _context(role: str | None):
    principal = {"id": "test-user", "role": role} if role else None
    return SimpleNamespace(auth=SimpleNamespace(principal=lambda: (principal, None)))


def test_published_snapshot_is_served(monkeypatch):
    """A valid published manifest reaches the hosted API unchanged."""
    monkeypatch.setenv("ARCHIPELAGO_RESEARCH_ENABLED", "1")
    monkeypatch.setattr(scholarly.requests, "get", lambda *args, **kwargs: _Response())
    monkeypatch.setitem(scholarly._cache, "expires", 0.0)
    monkeypatch.setitem(scholarly._cache, "payload", None)
    app = Flask(__name__)
    scholarly.register(app, _context("faculty"))
    response = app.test_client().get("/api/scholarly/snapshot")
    assert response.status_code == 200
    assert response.json["delivery"] == "published_snapshot"
    assert response.json["source_status"]["arxiv"]["live_records"] == 1


def test_packaged_snapshot_is_labeled_when_remote_fails(monkeypatch, tmp_path):
    """A network failure never turns a packaged snapshot into live data."""
    monkeypatch.setenv("ARCHIPELAGO_RESEARCH_ENABLED", "1")

    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("offline")

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"source_status": {"opac": {"mode": "fallback"}}}))
    monkeypatch.setattr(scholarly.requests, "get", unavailable)
    monkeypatch.setattr(scholarly, "SNAPSHOT_PATH", path)
    monkeypatch.setitem(scholarly._cache, "expires", 0.0)
    monkeypatch.setitem(scholarly._cache, "payload", None)
    app = Flask(__name__)
    scholarly.register(app, _context("librarian"))
    response = app.test_client().get("/api/scholarly/snapshot")
    assert response.status_code == 200
    assert response.json["delivery"] == "packaged_snapshot"


def test_snapshot_requires_staff_even_when_feature_is_disabled(monkeypatch):
    monkeypatch.delenv("ARCHIPELAGO_RESEARCH_ENABLED", raising=False)
    for role, status in ((None, 401), ("student", 403), ("faculty", 503)):
        app = Flask(__name__)
        scholarly.register(app, _context(role))
        assert app.test_client().get("/api/scholarly/snapshot").status_code == status
