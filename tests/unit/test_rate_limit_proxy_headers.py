"""Verify RateLimiter.client_ip() cannot be bypassed with client-supplied X-Forwarded-For headers."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "host_inference") not in sys.path:
    sys.path.insert(0, str(ROOT / "host_inference"))

from hostapp.security import RateLimiter  # noqa: E402


def test_untrusted_x_forwarded_for_ignored_without_proxy_env(monkeypatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("ARCHIPELAGO_TRUST_PROXY", raising=False)
    app = Flask(__name__)
    with app.test_request_context(
        "/api/chat",
        headers={"X-Forwarded-For": "10.99.99.99"},
        environ_base={"REMOTE_ADDR": "203.0.113.5"},
    ):
        assert RateLimiter.client_ip() == "203.0.113.5"


def test_trusted_vercel_uses_vercel_header_and_rightmost_xff(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    app = Flask(__name__)
    with app.test_request_context(
        "/api/chat",
        headers={
            "X-Forwarded-For": "10.0.0.1, 198.51.100.7",
            "X-Vercel-Forwarded-For": "198.51.100.42",
        },
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        assert RateLimiter.client_ip() == "198.51.100.42"

    with app.test_request_context(
        "/api/chat",
        headers={"X-Forwarded-For": "10.0.0.1, 198.51.100.7"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        assert RateLimiter.client_ip() == "198.51.100.7"
