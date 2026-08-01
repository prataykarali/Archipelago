"""Rate limiter for public / Hugging Face demos."""
import os

from archipelago.inference.rate_limit import SlidingWindowLimiter, check_chat_rate_limit


class _FakeReq:
    def __init__(self, ip="1.2.3.4", xff=None):
        self.remote_addr = ip
        self.headers = {}
        if xff:
            self.headers["X-Forwarded-For"] = xff


def test_per_client_limit_blocks_after_cap(monkeypatch):
    monkeypatch.delenv("ARCHIPELAGO_RATE_LIMIT_DISABLED", raising=False)
    monkeypatch.setenv("ARCHIPELAGO_RATE_LIMIT_PER_MIN", "3")
    monkeypatch.setenv("ARCHIPELAGO_RATE_LIMIT_BURST", "10")
    monkeypatch.setenv("ARCHIPELAGO_RATE_LIMIT_GLOBAL", "1000")
    lim = SlidingWindowLimiter()
    key = "test-client-a"
    for _ in range(3):
        ok, meta = lim.check(key, per_min=3, burst=10, global_per_min=1000)
        assert ok, meta
    ok, meta = lim.check(key, per_min=3, burst=10, global_per_min=1000)
    assert not ok
    assert meta["scope"] == "per_client"
    assert meta["retry_after_s"] >= 1


def test_burst_limit_blocks_fast_spam(monkeypatch):
    monkeypatch.delenv("ARCHIPELAGO_RATE_LIMIT_DISABLED", raising=False)
    lim = SlidingWindowLimiter()
    key = "burst-client"
    for _ in range(4):
        ok, _ = lim.check(key, per_min=100, burst=4, global_per_min=1000)
        assert ok
    ok, meta = lim.check(key, per_min=100, burst=4, global_per_min=1000)
    assert not ok
    assert meta["scope"] == "burst"


def test_disabled_env_bypasses(monkeypatch):
    monkeypatch.setenv("ARCHIPELAGO_RATE_LIMIT_DISABLED", "1")
    lim = SlidingWindowLimiter()
    for _ in range(50):
        ok, meta = lim.check("x", per_min=1, burst=1, global_per_min=1)
        assert ok
        assert meta.get("disabled") is True


def test_check_chat_rate_limit_uses_xff(monkeypatch):
    monkeypatch.setenv("ARCHIPELAGO_RATE_LIMIT_DISABLED", "1")
    ok, meta = check_chat_rate_limit(_FakeReq(xff="9.9.9.9, 1.1.1.1"), "sess1")
    assert ok


def test_rate_limit_response_message(app_context=None):
    from archipelago.inference.rate_limit import rate_limit_response
    from archipelago.inference.state import app
    with app.test_request_context():
        resp = rate_limit_response({"retry_after_s": 15, "scope": "per_client"})
        data = resp.get_json()
        assert resp.status_code == 429
        assert "library is too busy ! you are in queue, retrying after-15s" in data["error"]

