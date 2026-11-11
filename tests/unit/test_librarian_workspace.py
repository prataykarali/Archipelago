"""Check staff workspace routes, role boundaries, and record validation."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2] / "host_research"


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    """Load the second Vercel service with isolated imports."""
    monkeypatch.syspath_prepend(str(ROOT))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    module.app.config["TESTING"] = True
    return module


@pytest.mark.unit
def test_landing_and_staff_pages(transport: object) -> None:
    """Opening the site shows choices and each staff page resolves."""
    client = transport.app.test_client()
    assert b"Choose your space" in client.get("/").data
    for path in (
        "/librarian",
        "/librarian/catalog",
        "/librarian/circulation",
        "/librarian/orders",
        "/librarian/fines",
    ):
        assert client.get(path).status_code == 200
    assert client.get("/librarian/unknown").status_code == 404


@pytest.mark.unit
def test_staff_edit_role_boundary(transport: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unauthenticated and faculty writes fail; librarian writes reach storage."""
    client = transport.app.test_client()
    payload = {"record_key": "42", "title": "Example"}
    assert client.post("/api/librarian/catalog", json=payload).status_code == 401
    monkeypatch.setattr(
        transport, "verify_user", lambda token: {"id": "u", "role": token, "username": "staff"}
    )
    assert (
        client.post(
            "/api/librarian/catalog", json=payload, headers={"Authorization": "Bearer faculty"}
        ).status_code
        == 403
    )
    monkeypatch.setattr(
        transport, "save_record", lambda kind, data, actor: {"record_key": data["record_key"]}
    )
    response = client.post(
        "/api/librarian/catalog", json=payload, headers={"Authorization": "Bearer librarian"}
    )
    assert response.status_code == 200
    assert response.json["source"] == "archipelago_staff"


@pytest.mark.unit
def test_record_validation_rejects_unverified_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject unsafe links before contacting shared storage."""
    monkeypatch.syspath_prepend(str(ROOT))
    store = importlib.import_module("librarian_store")
    with pytest.raises(ValueError, match="source_url_must_be_https"):
        store.save_record(
            "catalog", {"record_key": "42", "source_url": "javascript:alert(1)"}, "actor"
        )


@pytest.mark.unit
def test_opac_failure_returns_dated_export_without_claiming_live(
    transport: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed live lookup may use a matching, clearly dated catalog row."""
    monkeypatch.setattr(
        transport,
        "verify_user",
        lambda token: {"id": "u", "role": "librarian", "username": "staff"},
    )
    monkeypatch.setattr(
        transport, "lookup_book", lambda identifier: (_ for _ in ()).throw(requests.Timeout())
    )
    monkeypatch.setattr(
        transport,
        "load_snapshot",
        lambda: {
            "holdings": [{"biblionumber": "42", "Title": "Example"}],
            "source_updated_at": "2026-10-03",
            "stale": True,
        },
    )
    response = transport.app.test_client().get(
        "/api/library/opac/live?biblionumber=42",
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 200
    assert response.json["source_kind"] == "dated_koha_export"
    assert response.json["stale"] is True
