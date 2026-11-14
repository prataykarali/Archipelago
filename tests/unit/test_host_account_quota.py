"""Account query quota checks for hosted AI requests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

from flask import Flask

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.security import AuthGuard, RateLimiter  # noqa: E402


def test_rolling_hour_quota_accepts_ten_rejects_eleventh_and_recovers(monkeypatch, tmp_path):
    now = [100_000.0]
    monkeypatch.setattr("hostapp.security.time.time", lambda: now[0])
    monkeypatch.setenv("ARCHIPELAGO_QUOTA_DB", str(tmp_path / "quota.sqlite3"))
    limiter = RateLimiter()

    # Queries 1-10 accepted with staggered timestamps (0s..90s).
    for i in range(10):
        limited, quota = limiter.check_daily_chat("student-a")
        assert not limited
        assert quota["used"] == i + 1
        assert quota["remaining"] == 10 - (i + 1)
        assert quota["retry_after"] == 0
        assert quota["reset_at"]
        now[0] += 10.0

    # Query 11 rejected before the oldest query (at 100_000.0) expires at 103_600.0.
    limited, quota = limiter.check_daily_chat("student-a")
    assert limited
    assert quota["used"] == 10
    assert quota["remaining"] == 0
    assert quota["retry_after"] == 3500
    assert quota["reset_at"] == "1970-01-02T04:46:40Z"
    assert limiter.quota_status("student-a")["used"] == 10

    # Independent account is unaffected.
    assert limiter.check_daily_chat("student-b")[0] is False
    assert limiter.quota_status("student-b")["used"] == 1

    # Replayed request_id idempotency: no double-charging.
    accepted, first = limiter.check_daily_chat("student-b", "request-1")
    assert not accepted
    duplicate, repeated = limiter.check_daily_chat("student-b", "request-1")
    assert duplicate and repeated["limit_reason"] == "duplicate"
    assert limiter.quota_status("student-b")["used"] == first["used"]

    # Just before the oldest query expires (at 103_599.0), still limited.
    now[0] = 103_599.0
    assert limiter.check_daily_chat("student-a")[0] is True

    # At 103_600.0, the oldest query (from 100_000.0) expires -> 1 slot opens.
    now[0] = 103_600.0
    assert limiter.quota_status("student-a")["used"] == 9
    limited, quota = limiter.check_daily_chat("student-a")
    assert not limited
    assert quota["used"] == 10
    assert quota["remaining"] == 0

    # After 3600s past the newest query, all prior queries expire.
    now[0] = 107_300.0
    assert limiter.quota_status("student-a")["used"] == 0
    limited, quota = limiter.check_daily_chat("student-a")
    assert not limited
    assert quota["used"] == 1
    assert quota["remaining"] == 9


def test_rolling_hour_quota_concurrent_requests(monkeypatch, tmp_path):
    monkeypatch.setattr("hostapp.security.time.time", lambda: 200_000.0)
    monkeypatch.setenv("ARCHIPELAGO_QUOTA_DB", str(tmp_path / "quota.sqlite3"))
    limiter = RateLimiter()

    def submit(_idx: int) -> bool:
        limited, _ = limiter.check_daily_chat("student-concurrent")
        return limited

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(15)))

    assert results.count(False) == 10
    assert results.count(True) == 5
    assert limiter.quota_status("student-concurrent")["used"] == 10


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
