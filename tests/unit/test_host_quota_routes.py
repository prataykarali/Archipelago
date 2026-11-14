"""Route-level tests for student 10/hour rolling quota, staff exemption, and IP burst limits."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

from flask import Flask
import pytest

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.middleware import register_middleware  # noqa: E402
from hostapp.routes import chat  # noqa: E402
from hostapp.security import RateLimiter  # noqa: E402

pytestmark = pytest.mark.unit


class _DummyEngine:
    def answer(self, _query):
        return {"route": "GRAPH_SYNTHESIS", "text": "Grounded", "payload": {}}

    def stream_chat(self, _query, **options):
        yield "{}\n[STREAM_START]\nAnswer"


def _make_app(role: str, user_id: str | None, limiter, auth_required: bool = True):
    app = Flask(__name__)
    principal = ({"id": user_id, "role": role}, None) if user_id else ({"role": role, "username": "guest"}, None)
    ctx = SimpleNamespace(
        auth=SimpleNamespace(required=lambda: auth_required, principal=lambda: principal),
        limiter=limiter,
        engine=_DummyEngine(),
        cache_metrics=SimpleNamespace(record_request=lambda: None, record_miss=lambda: None),
    )
    register_middleware(app, ctx)
    chat.register(app, ctx)
    return app


@pytest.mark.parametrize(
    "role,expected_calls",
    [
        ("student", 1),
        ("faculty", 0),
        ("librarian", 0),
        ("administrator", 0),
    ],
)
def test_only_students_consume_ai_quota(role, expected_calls):
    calls = []

    class Limiter:
        def check_chat(self):
            return False, 0

        def check_api(self):
            return False, 0

        def check_daily_chat(self, user_id, request_id):
            calls.append((user_id, request_id))
            return False, {"used": 1, "remaining": 9, "retry_after": 0, "reset_at": "2026-11-14T13:00:00Z"}

        def quota_status(self, _user_id):
            return {"used": 1, "remaining": 9, "retry_after": 0, "reset_at": "2026-11-14T13:00:00Z"}

    app = _make_app(role, "verified-user", Limiter())
    client = app.test_client()
    response = client.post("/api/chat", json={"query": "Explain a concept"})
    assert response.status_code == 200
    assert len(calls) == expected_calls
    status = client.get("/api/chat/quota")
    assert status.status_code == 200
    assert status.json.get("unrestricted", False) is (role != "student")
    assert len(calls) == expected_calls


def test_student_rolling_hour_quota_across_academic_research_and_followup_routes(monkeypatch, tmp_path):
    now = [100_000.0]
    monkeypatch.setattr("hostapp.security.time.time", lambda: now[0])
    monkeypatch.setenv("ARCHIPELAGO_QUOTA_DB", str(tmp_path / "quota.sqlite3"))
    monkeypatch.setattr(chat, "enrich_with_research", lambda prepared, _q: prepared)
    monkeypatch.setattr(
        chat,
        "_research_run_reply",
        lambda body, _q, _h: "{}\n[STREAM_START]\nResearch reply" if body.get("research_run_id") else None,
    )

    limiter = RateLimiter()
    monkeypatch.setattr(limiter, "check_chat", lambda: (False, 0))
    app = _make_app("student", "student-1", limiter)
    client = app.test_client()

    # 4 Academic Chat queries
    for i in range(4):
        res = client.post("/api/chat", json={"query": f"Academic question {i}"})
        assert res.status_code == 200
        assert res.headers["X-Queries-Used"] == str(i + 1)
        assert res.headers["X-Queries-Remaining"] == str(9 - i)

    # 3 Research Chat queries
    for i in range(3):
        res = client.post("/api/chat", json={"query": f"Research question {i}", "research_run_id": "run-1"})
        assert res.status_code == 200
        assert res.headers["X-Queries-Used"] == str(5 + i)

    # 3 Follow-up Chat queries
    for i in range(3):
        res = client.post(
            "/api/chat",
            json={"query": f"Follow up {i}", "history": [{"role": "user", "content": "prev"}]},
        )
        assert res.status_code == 200
        assert res.headers["X-Queries-Used"] == str(8 + i)
        assert res.headers["X-Queries-Remaining"] == str(2 - i)

    # 11th query returns 429 with clear message, retry_after, and reset_at
    eleventh = client.post("/api/chat", json={"query": "Eleventh question"})
    assert eleventh.status_code == 429
    assert eleventh.headers["Retry-After"] == "3600"
    assert eleventh.json["error"] == "query_limit"
    assert eleventh.json["detail"].startswith("Hourly chat limit reached (10/10). You can ask another question after ")
    assert eleventh.json["retry_after"] == 3600
    assert eleventh.json["reset_at"] == "1970-01-02T04:46:40Z"
    assert eleventh.json["remaining"] == 0

    # After 3600s, window expires and student can ask again
    now[0] += 3600.0
    recovered = client.post("/api/chat", json={"query": "Recovered question"})
    assert recovered.status_code == 200
    assert recovered.headers["X-Queries-Used"] == "1"


def test_student_request_id_idempotency_returns_409_without_double_charging(monkeypatch, tmp_path):
    monkeypatch.setattr("hostapp.security.time.time", lambda: 100_000.0)
    monkeypatch.setenv("ARCHIPELAGO_QUOTA_DB", str(tmp_path / "quota.sqlite3"))
    monkeypatch.setattr(chat, "enrich_with_research", lambda prepared, _q: prepared)

    limiter = RateLimiter()
    monkeypatch.setattr(limiter, "check_chat", lambda: (False, 0))
    app = _make_app("student", "student-idem", limiter)
    client = app.test_client()

    req_id = str(uuid.uuid4())
    first = client.post("/api/chat", json={"query": "Hello", "request_id": req_id})
    assert first.status_code == 200
    assert first.headers["X-Queries-Used"] == "1"

    replay = client.post("/api/chat", json={"query": "Hello", "request_id": req_id})
    assert replay.status_code == 409
    assert replay.json["error"] == "duplicate_request"
    assert client.get("/api/chat/quota").json["used"] == 1


@pytest.mark.parametrize("role", ["faculty", "librarian", "administrator"])
def test_staff_unlimited_per_account_but_subject_to_global_ip_burst_limit(monkeypatch, tmp_path, role):
    monkeypatch.setenv("ARCHIPELAGO_QUOTA_DB", str(tmp_path / "quota.sqlite3"))
    monkeypatch.setattr(chat, "enrich_with_research", lambda prepared, _q: prepared)

    limiter = RateLimiter()
    monkeypatch.setattr(limiter, "check_chat", lambda: (False, 0))
    app = _make_app(role, f"{role}-1", limiter)
    client = app.test_client()

    for i in range(12):
        res = client.post("/api/chat", json={"query": f"Staff query {i}"})
        assert res.status_code == 200
        assert "X-Queries-Used" not in res.headers

    # Global IP burst rate limit still applies to staff
    monkeypatch.setattr(limiter, "check_chat", lambda: (True, 15))
    burst_limited = client.post("/api/chat", json={"query": "Burst query"})
    assert burst_limited.status_code == 429
    assert burst_limited.headers["Retry-After"] == "15"


def test_local_guest_chat_does_not_require_student_identity(monkeypatch):
    """An auth-disabled development guest can still use the configured AI route."""

    class Limiter:
        def check_chat(self):
            return False, 0

        def check_api(self):
            return False, 0

        def check_daily_chat(self, _user_id, _request_id):
            raise AssertionError("Guest requests must not consume a student quota")

    monkeypatch.setattr(chat, "enrich_with_research", lambda prepared, _q: prepared)
    app = _make_app("student", None, Limiter(), auth_required=False)
    assert app.test_client().post("/api/chat", json={"query": "Explain a concept"}).status_code == 200


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
