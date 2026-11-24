"""Regression checks for distinct hosted-session failure reasons."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
import uuid

from flask import Flask
import pytest

pytestmark = pytest.mark.unit
HOST_ROOT = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST_ROOT) not in sys.path:
    sys.path.insert(0, str(HOST_ROOT))

from hostapp import security  # noqa: E402


def _token(expiry: int) -> str:
    """Build a signed-shape test JWT; no signature trust is implied."""

    def encode(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    return f"{encode({'alg': 'HS256'})}.{encode({'exp': expiry})}.signature"


@pytest.mark.parametrize(
    ("elapsed", "expected_code"),
    [
        ("idle", "idle_expired"),
        ("absolute", "absolute_expired"),
        ("revoked", "revoked_credentials"),
    ],
)
def test_session_failure_reason_is_specific(monkeypatch, elapsed: str, expected_code: str) -> None:
    """The client can distinguish idle, absolute and revoked sessions."""
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    monkeypatch.setenv("ARCHIPELAGO_IDLE_TIMEOUT_SECONDS", "300")
    monkeypatch.setenv("ARCHIPELAGO_SESSION_MAX_AGE_SECONDS", "3600")
    monkeypatch.setattr(security.time, "monotonic", lambda: 4000.0)
    guard = security.AuthGuard()
    token = f"test-{elapsed}"
    token_id = hashlib.sha256(token.encode()).hexdigest()
    guard._last_activity[token_id] = 3500.0 if elapsed == "idle" else 3999.0
    guard._session_started[token_id] = 0.0 if elapsed == "absolute" else 3999.0
    if elapsed == "revoked":
        guard.end_session(token)
    app = Flask(__name__)
    with app.test_request_context("/api/auth/me", headers={"Authorization": f"Bearer {token}"}):
        principal, error = guard.principal()
    assert principal is None
    assert security.auth_failure_code(error) == expected_code


def test_expired_jwt_is_rejected_before_identity_lookup(monkeypatch) -> None:
    """A stale JWT cannot pass through a cached principal."""
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    monkeypatch.setattr(security.time, "time", lambda: 200.0)
    guard = security.AuthGuard()
    token = _token(100)
    app = Flask(__name__)
    with app.test_request_context("/api/auth/me", headers={"Authorization": f"Bearer {token}"}):
        principal, error = guard.principal()
    assert principal is None
    assert security.auth_failure_code(error) == "jwt_expired"


def test_hosted_instances_share_session_status(monkeypatch) -> None:
    """Every hosted guard consults the same durable RPC before authorizing."""
    from hostapp import session_store

    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")  # noqa: E731
    token = f"{encode({'alg': 'HS256'})}.{encode({'sub': user_id, 'session_id': session_id, 'exp': 9999999999})}.signature"
    status = {"value": "missing_session"}
    calls: list[str] = []

    class FakeResponse:
        status_code = 200

        def __init__(self, payload: object) -> None:
            self.payload = payload

        def json(self) -> object:
            return self.payload

    def fake_get(url: str, **_kwargs: object) -> FakeResponse:
        if url.endswith("/auth/v1/user"):
            return FakeResponse({"id": user_id})
        return FakeResponse([{"username": "librarian", "role": "librarian"}])

    def fake_rpc(_name: str, payload: dict[str, object]) -> dict[str, str]:
        operation = str(payload["p_operation"])
        calls.append(operation)
        if operation == "register" and status["value"] == "missing_session":
            status["value"] = "active"
        if operation == "revoke":
            status["value"] = "revoked_credentials"
        return {"status": status["value"]}

    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    monkeypatch.setenv("ARCHIPELAGO_CSRF_SECRET", "shared-test-secret")
    monkeypatch.setattr(security, "hosted_runtime", lambda: True)
    monkeypatch.setattr(security.requests, "get", fake_get)
    monkeypatch.setattr(session_store, "runtime_rpc", fake_rpc)
    app = Flask(__name__)
    first = security.AuthGuard()
    second = security.AuthGuard()
    auth = {"Authorization": f"Bearer {token}"}
    with app.test_request_context("/api/auth/session", method="POST", headers=auth):
        assert first.principal()[0] is not None
        first.rotate_session(token)
    with app.test_request_context("/api/auth/me", headers=auth):
        assert second.principal()[0] is not None
    refreshed = f"{encode({'alg': 'HS256'})}.{encode({'sub': user_id, 'session_id': session_id, 'exp': 9999999998})}.signature"
    with app.test_request_context("/api/auth/me", headers={"Authorization": f"Bearer {refreshed}"}):
        assert second.principal()[0] is not None
    first.end_session(token)
    with app.test_request_context("/api/auth/me", headers=auth):
        principal, error = second.principal()
    assert principal is None
    assert security.auth_failure_code(error) == "revoked_credentials"
    with app.test_request_context("/api/auth/session", method="POST", headers=auth):
        principal, error = second.principal()
    assert principal is None
    assert security.auth_failure_code(error) == "revoked_credentials"
    assert calls == ["register", "check", "check", "revoke", "check", "register"]


def test_hosted_session_rpc_failure_denies_access(monkeypatch) -> None:
    """A durable-store outage never falls back to process-local activity."""
    from hostapp import session_store

    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    token = _token(9999999999)
    claims = {"sub": user_id, "session_id": session_id, "exp": 9999999999}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    token = f"{token.split('.')[0]}.{payload}.signature"

    class FakeResponse:
        status_code = 200

        def __init__(self, body: object) -> None:
            self.body = body

        def json(self) -> object:
            return self.body

    def fake_get(url: str, **_kwargs: object) -> FakeResponse:
        return FakeResponse(
            {"id": user_id}
            if url.endswith("/auth/v1/user")
            else [{"username": "u", "role": "student"}]
        )

    def broken_rpc(_name: str, _payload: dict[str, object]) -> None:
        raise RuntimeError("unavailable")

    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    monkeypatch.setattr(security, "hosted_runtime", lambda: True)
    monkeypatch.setattr(security.requests, "get", fake_get)
    monkeypatch.setattr(session_store, "runtime_rpc", broken_rpc)
    app = Flask(__name__)
    with app.test_request_context("/api/auth/me", headers={"Authorization": f"Bearer {token}"}):
        principal, error = security.AuthGuard().principal()
    assert principal is None
    assert security.auth_failure_code(error) == "upstream_unavailable"


def test_hosted_csrf_requires_shared_secret(monkeypatch) -> None:
    """Different Vercel instances derive one CSRF token or fail closed."""
    monkeypatch.setattr(security, "hosted_runtime", lambda: True)
    monkeypatch.delenv("ARCHIPELAGO_CSRF_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="Shared CSRF secret"):
        security.AuthGuard().csrf_token_for("test-token")
    monkeypatch.setenv("ARCHIPELAGO_CSRF_SECRET", "shared-test-secret")
    assert security.AuthGuard().csrf_token_for("test-token") == security.AuthGuard().csrf_token_for(
        "test-token"
    )
