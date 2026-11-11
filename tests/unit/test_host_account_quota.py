"""Account query quota checks for hosted AI requests."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.security import AuthGuard, RateLimiter  # noqa: E402


def test_daily_quota_pauses_after_ten_and_keeps_accounts_separate(monkeypatch, tmp_path):
    now = [100_000.0]
    monkeypatch.setattr("hostapp.security.time.time", lambda: now[0])
    monkeypatch.setenv("ARCHIPELAGO_QUOTA_DB", str(tmp_path / "quota.sqlite3"))
    limiter = RateLimiter()
    for _ in range(10):
        limited, quota = limiter.check_daily_chat("student-a")
        assert not limited
    assert quota["remaining"] == 30
    limited, quota = limiter.check_daily_chat("student-a")
    assert limited
    assert quota["remaining"] == 30
    assert limiter.quota_status("student-a")["used"] == 10
    assert limiter.check_daily_chat("student-b")[0] is False

    duplicate_db = RateLimiter()
    accepted, first = duplicate_db.check_daily_chat("student-b", "request-1")
    assert not accepted
    duplicate, repeated = duplicate_db.check_daily_chat("student-b", "request-1")
    assert duplicate and repeated["limit_reason"] == "duplicate"
    assert duplicate_db.quota_status("student-b")["used"] == first["used"]

    now[0] += 3601
    assert limiter.check_daily_chat("student-a")[0] is False
    assert RateLimiter().quota_status("student-a")["used"] == 11
    for _ in range(12, 41):
        limited, quota = limiter.check_daily_chat("student-a")
        if limited:
            now[0] += 3601
            limited, quota = limiter.check_daily_chat("student-a")
        assert not limited
    assert quota["remaining"] == 0
    assert limiter.check_daily_chat("student-a")[0] is True
    now[0] = 2 * 86400 + 1
    assert limiter.quota_status("student-a")["used"] == 0
    assert limiter.check_daily_chat("student-a")[1]["used"] == 1


def test_idle_session_expires_and_logout_revokes_token(monkeypatch):
    class Response:
        status_code = 200

        def __init__(self, value):
            self.value = value

        def json(self):
            return self.value

    now = [1000.0]
    monkeypatch.setattr("hostapp.security.time.monotonic", lambda: now[0])
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setattr(
        "hostapp.security.requests.get",
        lambda url, **_kwargs: Response(
            {"id": "student-a"}
            if url.endswith("/user")
            else [{"username": "student-a", "role": "student"}]
        ),
    )
    guard = AuthGuard()
    app = Flask(__name__)
    with app.test_request_context(headers={"Authorization": "Bearer account-token"}):
        assert guard.principal()[0]["id"] == "student-a"
        now[0] += 301
        principal, error = guard.principal()
        assert principal is None and "timed out" in error
        guard.end_session("account-token")
        assert guard.principal()[0] is None


def test_completed_quiz_is_saved_once_per_account(monkeypatch, tmp_path):
    monkeypatch.setenv("ARCHIPELAGO_QUOTA_DB", str(tmp_path / "quota.sqlite3"))
    limiter = RateLimiter()
    first = {"completed": True, "evaluation": {"score": "3/3"}}
    limiter.save_completed_quiz("student-a", "convolution", first)
    limiter.save_completed_quiz(
        "student-a", "convolution", {"completed": True, "evaluation": {"score": "0/3"}}
    )
    assert RateLimiter().completed_quiz("student-a", "convolution") == first
    assert limiter.completed_quiz("student-b", "convolution") is None
