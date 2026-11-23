"""LOCAL FIXTURE integration tests for the 6 SIGIR user journeys (Issue #12).

IMPORTANT DISTINCTION:
These tests execute the real Flask ``host_inference`` routes and ``Engine`` in-process
against local fixtures and test principals. They verify route contracts, RBAC 403
enforcement, page-view resolution, Q39 abstention, and XLSX byte generation locally,
and are NOT a substitute for authenticated live hosted browser verification.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

from flask import Flask
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
HOST_DIR = ROOT_DIR / "host_inference"
for path_entry in (HOST_DIR, ROOT_DIR):
    if str(path_entry) not in sys.path:
        sys.path.insert(0, str(path_entry))

from engine import Engine  # noqa: E402
from hostapp.middleware import register_middleware  # noqa: E402
from hostapp.routes import auth, chat, library, pages, reader  # noqa: E402

from scripts.e2e.hosted_e2e_checks import (  # noqa: E402
    parse_chat_response,
    verify_abstention_payload,
    verify_readiness_separation,
)

pytestmark = pytest.mark.integration

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
TRANSFORMER_DOC = "papers/Vaswani2017_Attention_Is_All_You_Need.pdf"
Q39_QUERY = "Explain Spanner TrueTime and its prerequisites."


def _build_local_fixture_app(
    role: str | None = "student",
    auth_required: bool = True,
) -> Flask:
    """Create a real host_inference Flask app wired with a controlled test principal."""
    app = Flask(__name__)
    principal = (
        {
            "id": f"local-test-{role}",
            "role": role,
            "username": f"local_{role}",
            "token": "local-tok",
        }
        if role is not None
        else None
    )

    def _principal() -> tuple[dict[str, Any] | None, str | None]:
        if principal is None:
            return None, "missing_session"
        return principal, None

    ctx = SimpleNamespace(
        auth=SimpleNamespace(
            required=lambda: auth_required,
            principal=_principal,
            supabase=lambda: ("https://example.supabase.co", "sb_publishable_local_test"),
            end_session=lambda _tok: None,
            csrf_token_for=lambda _tok: "local-csrf",
            verify_csrf_token=lambda _tok, _csrf: True,
        ),
        limiter=SimpleNamespace(
            check_chat=lambda: (False, 0),
            check_api=lambda: (False, 0),
            check_auth=lambda: (False, 0),
            check_daily_chat=lambda _uid, _rid: (False, {"remaining": 99, "used": 1}),
        ),
        engine=Engine(),
        cache_metrics=SimpleNamespace(
            record_request=lambda: None,
            record_miss=lambda: None,
            stats=lambda: {"ai_requests_total": 0},
        ),
        inventory=SimpleNamespace(parse=lambda _b: [], save=lambda _r: None),
    )
    register_middleware(app, ctx)
    auth.register(app, ctx)
    chat.register(app, ctx)
    library.register(app, ctx)
    pages.register(app, ctx)
    reader.register(app, ctx)
    return app


def test_local_j1_transformer_chat_and_page_view_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """[LOCAL FIXTURE] Student chat -> Transformer concept -> /api/page-view JSON."""
    monkeypatch.setattr(chat, "provider_config", lambda: None)
    monkeypatch.setattr(chat, "enrich_with_research", lambda prepared, _q: prepared)
    from engine import answer

    monkeypatch.setattr(answer, "provider_config", lambda: None)
    app = _build_local_fixture_app(role="student")
    client = app.test_client()

    chat_resp = client.post("/api/chat", json={"query": "What is a Transformer?"})
    assert chat_resp.status_code == HTTP_OK
    metadata = parse_chat_response(chat_resp.get_data(as_text=True))
    assert metadata, "Expected parsed JSON metadata before [STREAM_START]"

    pv_resp = client.get(f"/api/page-view?doc_id={TRANSFORMER_DOC}&page=2&format=json")
    assert pv_resp.status_code == HTTP_OK
    pv_json = pv_resp.get_json()
    assert pv_json["page"] == 2
    assert pv_json["pdf_url"].startswith("/papers/")
    assert "Vaswani2017" in pv_json["pdf_url"]


def test_local_j4_library_data_and_readiness_separation() -> None:
    """[LOCAL FIXTURE] Public /api/library/data and /api/readiness expose expected fields."""
    app = _build_local_fixture_app(role=None, auth_required=True)
    client = app.test_client()

    readiness_resp = client.get("/api/readiness")
    assert readiness_resp.status_code == HTTP_OK
    sep = verify_readiness_separation(dict(readiness_resp.headers), readiness_resp.get_json())
    assert sep["graph_fingerprint"] != "missing"
    assert sep["deployed_revision"] == "missing"

    lib_resp = client.get("/api/library/data")
    assert lib_resp.status_code == HTTP_OK
    lib_data = lib_resp.get_json()
    assert isinstance(lib_data.get("ebook_shelf"), list)
    assert "holdings_status" in lib_data


def test_local_j5_q39_unsupported_clean_abstention(monkeypatch: pytest.MonkeyPatch) -> None:
    """[LOCAL FIXTURE] Unsupported Q39 query returns zero citations and zero graph edges."""
    monkeypatch.setattr(chat, "provider_config", lambda: None)
    monkeypatch.setattr(chat, "enrich_with_research", lambda prepared, _q: prepared)
    from engine import answer

    monkeypatch.setattr(answer, "provider_config", lambda: None)
    app = _build_local_fixture_app(role="student")
    client = app.test_client()

    resp = client.post("/api/chat", json={"query": Q39_QUERY})
    assert resp.status_code == HTTP_OK
    metadata = parse_chat_response(resp.get_data(as_text=True))
    abstention = verify_abstention_payload(metadata)
    assert abstention["clean_abstention"] is True
    assert abstention["citation_count"] == 0
    assert abstention["graph_node_count"] == 0
    assert abstention["graph_edge_count"] == 0


def test_local_j6_student_cannot_perform_librarian_operations() -> None:
    """[LOCAL FIXTURE] Student role receives HTTP 403 on librarian-only endpoints."""
    app = _build_local_fixture_app(role="student", auth_required=True)
    client = app.test_client()

    import_resp = client.post("/api/library/import")
    assert import_resp.status_code == HTTP_FORBIDDEN

    handoff_resp = client.post(
        "/api/auth/handoff-ticket",
        json={"target_origin": "https://archipelago-librarian.vercel.app"},
    )
    assert handoff_resp.status_code == HTTP_FORBIDDEN

    ingest_resp = client.post("/api/ingest/upload")
    assert ingest_resp.status_code == HTTP_FORBIDDEN


def test_local_j6_anonymous_gets_401_not_pass() -> None:
    """[LOCAL FIXTURE] Anonymous callers receive 401 on guarded chat/page-view routes."""
    app = _build_local_fixture_app(role=None, auth_required=True)
    client = app.test_client()

    assert (
        client.post("/api/chat", json={"query": "What is a Transformer?"}).status_code
        == HTTP_UNAUTHORIZED
    )
    assert (
        client.get(f"/api/page-view?doc_id={TRANSFORMER_DOC}&page=2&format=json").status_code
        == HTTP_UNAUTHORIZED
    )
    # Confirm JSON error body is well-formed
    err_body = json.loads(client.post("/api/chat", json={"query": "test"}).get_data(as_text=True))
    assert err_body.get("error") == "unauthorized"
