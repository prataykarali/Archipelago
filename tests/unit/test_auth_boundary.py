"""Auth-boundary regression across the three services.

With ``ARCHIPELAGO_AUTH_REQUIRED=1`` every *protected* mutating endpoint must
reject an unauthenticated caller (401/403), and the endpoints that are
deliberately public (chat, roadmap, quiz, page-view, session login/logout) must
NOT be rejected as unauthenticated.

The rate limiter is cleared between probes so a 429 can never masquerade as a
success for a protected route.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST = REPO_ROOT / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

AUTH_REJECTED = (401, 403)

# (method, registered rule) that must reject anonymous callers.
PROTECTED = {
    "graph_server": [
        ("POST", "/api/anything"),
        ("PUT", "/api/anything"),
        ("PATCH", "/api/anything"),
        ("DELETE", "/api/anything"),
    ],
    "chat_server": [
        ("POST", "/api/chat"),
        ("POST", "/api/chat/adaptive-step"),
        ("POST", "/api/chat/diagnostic-mcqs"),
        ("POST", "/api/chat/telemetry"),
        ("POST", "/api/chat/verify-mcq"),
        ("POST", "/api/dashboards/overview"),
        ("DELETE", "/api/documents/some-doc"),
        ("POST", "/api/ingest"),
        ("POST", "/api/ingest/job-1/cancel"),
        ("POST", "/api/librarian/staging/publish"),
        ("POST", "/api/librarian/upload"),
        ("POST", "/api/page-view"),
        ("POST", "/api/roadmap"),
        ("POST", "/api/users"),
        ("PUT", "/api/users/user-1"),
        ("DELETE", "/api/users/user-1"),
    ],
    "hostapp": [
        ("POST", "/api/library/import"),
        ("POST", "/api/auth/session"),
    ],
}

# (method, path) that must remain reachable without a session.
PUBLIC = {
    "chat_server": [
        ("DELETE", "/api/auth/session"),
    ],
    "hostapp": [
        ("POST", "/api/chat"),
        ("POST", "/api/roadmap"),
        ("POST", "/api/quiz"),
        ("POST", "/api/page-view"),
        ("POST", "/api/chat/telemetry"),
        ("POST", "/api/chat/adaptive-step"),
    ],
}


def _fill(rule: str) -> str:
    """Replace Flask converters with a concrete placeholder."""
    rule = re.sub(r"<path:[^>]+>", "placeholder", rule)
    return re.sub(r"<[^>]+>", "placeholder", rule)


@pytest.fixture(autouse=True)
def _require_auth(monkeypatch):
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("ARCHIPELAGO_ENV", "production")


def _apps() -> dict:
    """Build (or reuse) each service app."""
    from hostapp.factory import create_app

    import chat_server
    import graph_server

    return {
        "graph_server": graph_server.app,
        "chat_server": chat_server.app,
        "hostapp": create_app(),
    }


def _clear_limiter(app) -> None:
    ctx = getattr(app, "extensions", {}).get("archipelago")
    limiter = getattr(ctx, "limiter", None)
    if limiter is None:
        return
    limiter._chat.clear()
    limiter._api.clear()


def _call(app, method: str, path: str):
    client = app.test_client()
    _clear_limiter(app)
    if method == "DELETE":
        return client.delete(path)
    return getattr(client, method.lower())(path, json={})


def test_protected_mutating_endpoints_reject_anonymous() -> None:
    apps = _apps()
    failures = []
    for service, checks in PROTECTED.items():
        app = apps[service]
        for method, rule in checks:
            response = _call(app, method, _fill(rule))
            if response.status_code not in AUTH_REJECTED:
                failures.append(f"{service} {method} {rule} -> {response.status_code}")
    assert not failures, "mutating endpoints allowed an anonymous caller:\n" + "\n".join(failures)


def test_public_endpoints_are_not_auth_rejected() -> None:
    apps = _apps()
    failures = []
    for service, checks in PUBLIC.items():
        app = apps[service]
        for method, path in checks:
            response = _call(app, method, path)
            if response.status_code in AUTH_REJECTED:
                failures.append(f"{service} {method} {path} -> {response.status_code}")
    assert not failures, "public endpoints rejected anonymous callers:\n" + "\n".join(failures)
