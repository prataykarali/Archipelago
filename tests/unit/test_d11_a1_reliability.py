"""Unit and contract tests for D11-A.1 runtime reliability repair."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_UI = REPO_ROOT / "host_inference" / "ui"
CANONICAL_UI = REPO_ROOT / "ui" / "chat"
MIGRATION_SQL = (
    REPO_ROOT
    / "supabase"
    / "migrations"
    / "20261127000000_d11_a1_session_reason_and_eval_quota.sql"
)


@pytest.mark.unit
def test_migration_preserves_revoked_reason_and_eval_quota_override() -> None:
    sql = MIGRATION_SQL.read_text(encoding="utf-8")
    assert "add column if not exists revoked_reason text" in sql
    assert "coalesce(v_row.revoked_reason, 'revoked_credentials')" in sql
    assert "create table if not exists public.archipelago_runtime_quota_overrides" in sql
    assert "check (hourly_limit between 1 and 200)" in sql
    assert "coalesce(o.hourly_limit, 10)" in sql


@pytest.mark.unit
def test_frontend_deadlines_and_sequence_safe_cleanup_aligned() -> None:
    for root in (HOST_UI, CANONICAL_UI):
        origin_js = (root / "js" / "00-current-origin.js").read_text(encoding="utf-8")
        assert "CHAT_RESPONSE_TIMEOUT_MS = 90000" in origin_js
        assert "STREAM_IDLE_TIMEOUT_MS = 75000" in origin_js

        send_js = (root / "js" / "08-send-message.js").read_text(encoding="utf-8")
        assert "thisQuerySequence === state.currentQuerySequence" in send_js
        assert "archipelagoClearChatSignInPrompt" in send_js

        cleanup_js = (root / "js" / "08-stream-cleanup.js").read_text(encoding="utf-8")
        assert "window.archipelagoChatAuthChecking = false" in cleanup_js
        assert ".msg-bubble-wrap.is-thinking" in cleanup_js

        err_js = (root / "js" / "08-stream-error.js").read_text(encoding="utf-8")
        assert "incomplete_stream" in err_js

        bridge_js = (root / "auth_bridge.js").read_text(encoding="utf-8")
        assert "passiveCheckInFlight" in bridge_js
        assert "VERIFY_SESSION_TIMEOUT_MS" in bridge_js
        assert "/api/auth/keepalive" in bridge_js
        assert "X-User-Interaction" in bridge_js

        req_js = (root / "js" / "08-send-request.js").read_text(encoding="utf-8")
        assert "X-Queries-Limit" in req_js


@pytest.mark.unit
def test_llm_structured_error_logging_redacts_secrets(caplog: pytest.LogCaptureFixture) -> None:
    from host_inference.engine import llm

    secret_key = "sk-test-super-secret-value-12345"
    cfg: llm.ProviderConfig = {
        "base_url": "https://example.invalid/v1",
        "key": secret_key,
        "model": "cohere/command-a",
        "provider": "xkiro",
    }

    with (
        caplog.at_level(logging.WARNING, logger="host_inference.engine.llm"),
        patch.object(llm.requests, "post", side_effect=requests.Timeout("timed out")),
    ):
        tokens = list(llm.stream_completion(cfg, "grounded evidence", query="what is paging?"))

    assert tokens == []
    err = llm.last_provider_error()
    assert err is not None
    assert err["provider"] == "xkiro"
    assert err["error_type"] == "timeout"
    assert secret_key not in caplog.text


@pytest.mark.unit
def test_session_cookie_max_age_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from host_inference.hostapp.routes.auth import _session_cookie_max_age

    monkeypatch.setenv("ARCHIPELAGO_SESSION_MAX_AGE_SECONDS", "14400")
    assert _session_cookie_max_age() == 14400

    monkeypatch.delenv("ARCHIPELAGO_SESSION_MAX_AGE_SECONDS", raising=False)
    assert _session_cookie_max_age() == 3600


@pytest.mark.unit
def test_hosted_principal_caches_profile_but_always_checks_durable_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from flask import Flask

    from host_inference.hostapp.security import AuthGuard

    app = Flask(__name__)
    guard = AuthGuard()
    user_id = "11111111-1111-1111-1111-111111111111"
    session_id = "22222222-2222-2222-2222-222222222222"

    user_resp = MagicMock(status_code=200)
    user_resp.json.return_value = {"id": user_id}
    prof_resp = MagicMock(status_code=200)
    prof_resp.json.return_value = [{"username": "author", "role": "student"}]

    session_calls = []

    def fake_session_action(op: str, sid: str, uid: str, **_kw: object) -> dict[str, str]:
        session_calls.append((op, sid, uid))
        return {"status": "active" if len(session_calls) == 1 else "revoked_credentials"}

    monkeypatch.setattr("host_inference.hostapp.security.hosted_runtime", lambda: True)
    monkeypatch.setattr(
        "host_inference.hostapp.security.verified_session_ids",
        lambda _tok, _uid: (session_id, user_id),
    )
    monkeypatch.setattr("host_inference.hostapp.security.session_action", fake_session_action)

    with (
        patch("host_inference.hostapp.security.requests.get", side_effect=[user_resp, prof_resp]) as mock_get,
        app.test_request_context("/api/auth/me", method="GET"),
    ):
        principal_1, err_1 = guard._hosted_principal("fake.jwt.token", "https://sb.test", "pub")
        assert err_1 is None
        assert principal_1 is not None and principal_1["role"] == "student"
        assert mock_get.call_count == 2

        # Second call reuses profile cache (0 extra requests.get calls) but STILL checks durable session!
        principal_2, err_2 = guard._hosted_principal("fake.jwt.token", "https://sb.test", "pub")
        assert principal_2 is None
        assert err_2 is not None and "revoked" in err_2.lower()
        assert mock_get.call_count == 2
        assert len(session_calls) == 2
