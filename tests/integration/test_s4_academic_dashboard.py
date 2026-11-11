"""The academic status route protects local job and provider metadata."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from archipelago.academic_automation.store import AcademicStore

pytestmark = pytest.mark.integration


def test_status_requires_staff_and_reads_durable_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import graph_server

    state = tmp_path / "academic.sqlite3"
    store = AcademicStore(state)
    store.provider_result("koha_export")
    monkeypatch.setenv("ARCHIPELAGO_ACADEMIC_STATE", str(state))
    monkeypatch.setattr(graph_server.supabase_auth, "is_auth_required", lambda: True)
    monkeypatch.setattr(
        graph_server.supabase_auth, "authenticate_request", lambda _request: (None, "missing token")
    )
    client = graph_server.app.test_client()
    assert client.get("/api/academic-automation/status").status_code == 401
    monkeypatch.setattr(
        graph_server.supabase_auth,
        "authenticate_request",
        lambda _request: (SimpleNamespace(role="student", access_token="x"), None),
    )
    assert client.get("/api/academic-automation/status").status_code == 403
    monkeypatch.setattr(
        graph_server.supabase_auth,
        "authenticate_request",
        lambda _request: (SimpleNamespace(role="librarian", access_token="x"), None),
    )
    monkeypatch.setattr(graph_server, "gpu_snapshot", lambda: {"available": False})
    response = client.get("/api/academic-automation/status")
    assert response.status_code == 200
    assert response.json["providers"][0]["name"] == "koha_export"
    assert response.json["jobs"] == []


def test_review_decision_requires_verified_librarian(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing, student, or local development identity cannot approve."""
    import graph_server

    monkeypatch.setattr(graph_server.supabase_auth, "is_auth_required", lambda: True)
    client = graph_server.app.test_client()
    url = "/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe/decision"
    monkeypatch.setattr(
        graph_server.supabase_auth, "authenticate_request", lambda _request: (None, "missing token")
    )
    assert client.post(url, json={"decision": "approve"}).status_code == 401
    for role, token in (("student", "verified"), ("librarian", "local-dev-token")):
        monkeypatch.setattr(
            graph_server.supabase_auth,
            "authenticate_request",
            lambda _request, role=role, token=token: (
                SimpleNamespace(role=role, access_token=token),
                None,
            ),
        )
        assert client.post(url, json={"decision": "approve"}).status_code == 403
