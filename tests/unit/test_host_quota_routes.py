"""Only verified students pay for hosted AI invocations."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

from flask import Flask
import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.middleware import register_middleware  # noqa: E402
from hostapp.routes import chat  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "role,expected_calls",
    [
        ("student", 1),
        ("faculty", 0),
        ("librarian", 0),
        ("administrator", 0),
    ],
)
def test_only_students_consume_ai_quota(monkeypatch, role, expected_calls):
    calls = []

    class Engine:
        def answer(self, _query):
            return {"route": "GRAPH_SYNTHESIS", "text": "Grounded", "payload": {}}

        def stream_chat(self, _query, **_kwargs):
            yield "{}\n[STREAM_START]\nAnswer"

    class Limiter:
        def check_chat(self):
            return False, 0

        def check_api(self):
            return False, 0

        def check_daily_chat(self, user_id, request_id):
            calls.append((user_id, request_id))
            return False, {"used": 1, "remaining": 39}

        def quota_status(self, _user_id):
            return {"used": 1, "remaining": 39, "retry_after": 0}

    monkeypatch.setattr(chat, "provider_config", lambda: {"provider": "existing"})
    app = Flask(__name__)
    ctx = SimpleNamespace(
        auth=SimpleNamespace(
            required=lambda: True, principal=lambda: ({"id": "verified-user", "role": role}, None)
        ),
        limiter=Limiter(),
        engine=Engine(),
        cache_metrics=SimpleNamespace(record_request=lambda: None, record_miss=lambda: None),
    )
    register_middleware(app, ctx)
    chat.register(app, ctx)
    client = app.test_client()
    response = client.post("/api/chat", json={"query": "Explain a concept"})
    assert response.status_code == 200
    assert len(calls) == expected_calls
    status = client.get("/api/chat/quota")
    assert status.status_code == 200
    assert status.json.get("unrestricted", False) is (role != "student")
    assert len(calls) == expected_calls


def test_local_guest_chat_does_not_require_student_identity(monkeypatch):
    """An auth-disabled development guest can still use the configured AI route."""

    class Engine:
        def answer(self, _query):
            return {"route": "GRAPH_SYNTHESIS", "text": "Grounded", "payload": {}}

        def stream_chat(self, _query, **_kwargs):
            yield "{}\n[STREAM_START]\nAnswer"

    class Limiter:
        def check_chat(self):
            return False, 0

        def check_api(self):
            return False, 0

        def check_daily_chat(self, _user_id, _request_id):
            raise AssertionError("Guest requests must not consume a student quota")

    monkeypatch.setattr(chat, "provider_config", lambda: {"provider": "existing"})
    app = Flask(__name__)
    ctx = SimpleNamespace(
        auth=SimpleNamespace(
            required=lambda: False,
            principal=lambda: ({"role": "student", "username": "guest"}, None),
        ),
        limiter=Limiter(),
        engine=Engine(),
        cache_metrics=SimpleNamespace(record_request=lambda: None, record_miss=lambda: None),
    )
    register_middleware(app, ctx)
    chat.register(app, ctx)
    assert (
        app.test_client().post("/api/chat", json={"query": "Explain a concept"}).status_code == 200
    )


def test_reply_format_api_preserves_stream_and_validates_selection(monkeypatch):
    """The UI can request a longer selected format without changing stream framing."""
    calls = []

    class Engine:
        def answer(self, _query):
            return {"route": "GRAPH_SYNTHESIS", "text": "Grounded", "payload": {}}

        def stream_chat(self, _query, **options):
            calls.append(options)
            yield "{}\n[STREAM_START]\nDetailed answer"

    class Limiter:
        def check_chat(self):
            return False, 0

        def check_api(self):
            return False, 0

    monkeypatch.setattr(chat, "provider_config", lambda: None)
    monkeypatch.setattr(chat, "enrich_with_research", lambda prepared, _query: prepared)
    app = Flask(__name__)
    ctx = SimpleNamespace(
        auth=SimpleNamespace(required=lambda: False, principal=lambda: (None, None)),
        limiter=Limiter(),
        engine=Engine(),
        cache_metrics=SimpleNamespace(record_request=lambda: None, record_miss=lambda: None),
    )
    register_middleware(app, ctx)
    chat.register(app, ctx)
    client = app.test_client()

    listed = client.get("/api/reply-templates")
    assert listed.status_code == 200
    assert len(listed.json["templates"]) == 130
    response = client.post(
        "/api/chat",
        json={"query": "Explain RAG", "reply_template_id": "RES-112", "reply_detail": "expanded"},
    )
    assert response.status_code == 200
    assert response.get_data(as_text=True).startswith("{}\n[STREAM_START]\n")
    assert calls[0]["reply_template_id"] == "RES-112"
    assert calls[0]["reply_detail"] == "expanded"
    assert (
        client.post(
            "/api/chat", json={"query": "Explain RAG", "reply_template_id": "RES-999"}
        ).status_code
        == 400
    )
