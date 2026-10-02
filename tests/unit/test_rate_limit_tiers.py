"""Feature regression — middleware rate limiter, per tier.

``archipelago.middleware.rate_limiter`` guards the Flask services with a
sliding-window limiter whose ceiling depends on the caller's tier
(anonymous 5, student 30, librarian 100, administrator 200 per 60 s).

Asserts the per-tier ceilings, the 429 + ``Retry-After`` contract, client
isolation (keyed on ``X-Forwarded-For`` first hop), the operator kill-switch,
and that ``g.user_tier`` overrides the decorator default.
"""
from __future__ import annotations

import pytest
from flask import Flask, g

from archipelago.middleware.rate_limiter import (
    DEFAULT_LIMIT,
    TIERS,
    WINDOW_SECONDS,
    RateLimiter,
    rate_limit,
)


@pytest.fixture(autouse=True)
def clean_limiter(monkeypatch):
    """Reset the module-level limiter and ensure it is enabled."""
    monkeypatch.delenv("ARCHIPELAGO_RATE_LIMIT_DISABLED", raising=False)
    import archipelago.middleware.rate_limiter as mod

    mod._limiter = RateLimiter()
    yield


def _tier_app(tier: str) -> Flask:
    app = Flask(__name__)

    @app.get("/limited")
    @rate_limit(tier=tier)
    def limited():
        return {"ok": True}

    return app


def _hit(client, ip="10.0.0.1"):
    return client.get("/limited", headers={"X-Forwarded-For": ip})


def test_tier_ceilings_are_documented_values():
    assert TIERS == {"anonymous": 5, "student": 30, "librarian": 100, "administrator": 200}
    assert DEFAULT_LIMIT == 100
    assert WINDOW_SECONDS == 60


@pytest.mark.parametrize("tier", ["anonymous", "student", "librarian", "administrator"])
def test_each_tier_blocks_exactly_at_its_ceiling(tier):
    limit = TIERS[tier]
    client = _tier_app(tier).test_client()

    statuses = [_hit(client).status_code for _ in range(limit + 1)]
    assert statuses[:limit] == [200] * limit
    assert statuses[limit] == 429


def test_429_carries_retry_after_header_within_window():
    client = _tier_app("anonymous").test_client()
    for _ in range(TIERS["anonymous"]):
        assert _hit(client).status_code == 200

    blocked = _hit(client)
    assert blocked.status_code == 429
    retry_after = int(blocked.headers["Retry-After"])
    assert 1 <= retry_after <= WINDOW_SECONDS + 1
    assert blocked.get_json()["retry_after_s"] == retry_after


def test_client_identity_is_keyed_on_first_forwarded_hop():
    client = _tier_app("anonymous").test_client()
    for _ in range(TIERS["anonymous"]):
        assert _hit(client, ip="1.1.1.1").status_code == 200
    assert _hit(client, ip="1.1.1.1").status_code == 429
    # A different client is unaffected.
    assert _hit(client, ip="2.2.2.2").status_code == 200


def test_unknown_tier_falls_back_to_default_limit():
    client = _tier_app("visitor").test_client()
    statuses = [_hit(client).status_code for _ in range(DEFAULT_LIMIT + 1)]
    assert statuses[DEFAULT_LIMIT] == 429
    assert set(statuses[:DEFAULT_LIMIT]) == {200}


def test_g_user_tier_overrides_decorator_default():
    app = Flask(__name__)

    @app.before_request
    def _identity():
        g.user_tier = "anonymous"

    @app.get("/limited")
    @rate_limit(tier="administrator")
    def limited():
        return {"ok": True}

    client = app.test_client()
    statuses = [client.get("/limited").status_code for _ in range(TIERS["anonymous"] + 1)]
    # The anonymous caps applies (5), not the decorator's 200.
    assert statuses[TIERS["anonymous"]] == 429


def test_disabled_env_bypasses_the_limiter(monkeypatch):
    monkeypatch.setenv("ARCHIPELAGO_RATE_LIMIT_DISABLED", "1")
    client = _tier_app("anonymous").test_client()
    statuses = [_hit(client).status_code for _ in range(TIERS["anonymous"] + 10)]
    assert set(statuses) == {200}


def test_limiter_is_thread_safe_under_concurrency():
    limiter = RateLimiter()
    import threading

    allowed = []
    lock = threading.Lock()

    def worker():
        for _ in range(50):
            ok, _ = limiter.check("shared-key", limit=100)
            with lock:
                allowed.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 8 * 50 = 400 attempts against a limit of 100 in one window.
    assert sum(1 for a in allowed if a) == 100
    assert len(allowed) == 400
