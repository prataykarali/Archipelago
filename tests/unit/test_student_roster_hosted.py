"""Student roster import and first-login credential boundaries."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

from flask import Flask
import pytest

pytestmark = pytest.mark.unit

FAKE_INITIAL_PASSWORD = "-".join(("unit", "fixture", "only", "value"))
FAKE_NEW_PASSWORD = "-".join(("unit", "fixture", "new", "value"))

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp import student_roster  # noqa: E402
from hostapp.middleware import register_middleware  # noqa: E402
from hostapp.routes import auth, users  # noqa: E402
from hostapp.security import AuthGuard  # noqa: E402
from supabase_service_headers import service_headers  # noqa: E402


def _principal(role: str = "administrator", must_change: bool = False) -> dict:
    return {
        "role": role,
        "user_id": "user-1",
        "username": "staff",
        "token": "session-token",
        "must_change_password": must_change,
    }


def _app(principal: dict | None) -> Flask:
    app = Flask(__name__)
    guard = SimpleNamespace(
        principal=lambda: (principal, None if principal else "No session"),
        supabase=lambda: ("https://example.supabase.co", "publishable"),
        required=lambda: True,
    )
    context = SimpleNamespace(auth=guard)
    auth.register(app, context)
    users.register(app, context)
    return app


def _upload(client, path: str, source: bytes, authenticated: bool = True):
    return client.post(
        path,
        data={
            "source_label": "2026 approved roster",
            "file": (BytesIO(source), "students.csv"),
        },
        headers={"Authorization": "Bearer session-token"} if authenticated else {},
    )


def test_roster_rejects_bad_enrollment_and_duplicates() -> None:
    valid = b"enrollment,display_name\n12024002028038,Student One\n"
    assert student_roster.parse_roster(valid) == [
        {"username": "12024002028038", "display_name": "Student One"}
    ]
    with pytest.raises(ValueError, match="14 digits"):
        student_roster.parse_roster(b"enrollment\n123\n")
    with pytest.raises(ValueError, match="duplicate"):
        student_roster.parse_roster(valid + b"12024002028038,Again\n")


def test_roster_rejects_oversize_and_spreadsheet_formula_names() -> None:
    oversized = b"enrollment\n" + b"x" * student_roster.MAX_ROSTER_BYTES
    with pytest.raises(ValueError, match="1 MB limit"):
        student_roster.parse_roster(oversized)
    with pytest.raises(ValueError, match="invalid display name"):
        student_roster.parse_roster(
            b"enrollment,display_name\n12024002028038,=HYPERLINK(https://example.org)\n"
        )


def test_server_headers_support_opaque_and_legacy_keys() -> None:
    opaque = service_headers("sb_secret_example", json_body=True)
    assert opaque == {"apikey": "sb_secret_example", "Content-Type": "application/json"}
    legacy = service_headers("legacy-jwt")
    assert legacy == {"apikey": "legacy-jwt", "Authorization": "Bearer legacy-jwt"}


def test_anonymous_and_student_cannot_import() -> None:
    raw = b"enrollment\n12024002028038\n"
    assert _upload(_app(None).test_client(), "/api/users/import", raw).status_code == 401
    assert (
        _upload(_app(_principal()).test_client(), "/api/users/import", raw, False).status_code
        == 401
    )
    assert (
        _upload(_app(_principal("student")).test_client(), "/api/users/import", raw).status_code
        == 403
    )


def test_preview_and_apply_skip_existing_and_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        users,
        "service_config",
        lambda: ("https://example.supabase.co", "server-key", "hidden-secret"),
    )
    monkeypatch.setattr(users, "import_permission", lambda *_args: "")
    monkeypatch.setattr(users, "existing_students", lambda *_args: {"12024002028038"})
    monkeypatch.setattr(users, "provision_students", lambda *_args: (1, 0))
    monkeypatch.setattr(users, "audit_import", lambda *args: calls.append(args))
    raw = b"enrollment,display_name\n12024002028038,Existing\n12024002028039,New\n"
    client = _app(_principal()).test_client()
    preview = _upload(client, "/api/users/import/preview", raw)
    assert preview.status_code == 200
    assert preview.json == {"received": 2, "existing": 1, "to_create": 1}
    assert not calls
    applied = _upload(client, "/api/users/import", raw)
    assert applied.status_code == 200
    assert applied.json == {"received": 2, "existing": 1, "created": 1, "failed": 0}
    assert len(calls) == 1


def test_password_change_requires_bearer_and_clears_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "server-key")
    monkeypatch.setenv("ARCHIPELAGO_BOOTSTRAP_PASSWORD", FAKE_INITIAL_PASSWORD)
    updates: list[dict] = []
    monkeypatch.setattr(
        auth.requests,
        "put",
        lambda *args, **kwargs: updates.append(kwargs["json"]) or SimpleNamespace(status_code=200),
    )
    client = _app(_principal("student", must_change=True)).test_client()
    assert (
        client.post(
            "/api/auth/change-password", json={"new_password": FAKE_NEW_PASSWORD}
        ).status_code
        == 401
    )
    headers = {"Authorization": "Bearer session-token"}
    assert (
        client.post(
            "/api/auth/change-password",
            headers=headers,
            json={"new_password": FAKE_INITIAL_PASSWORD},
        ).status_code
        == 400
    )
    response = client.post(
        "/api/auth/change-password", headers=headers, json={"new_password": FAKE_NEW_PASSWORD}
    )
    assert response.status_code == 200
    assert updates == [
        {"password": FAKE_NEW_PASSWORD, "app_metadata": {"must_change_password": False}}
    ]


def test_first_login_cannot_call_protected_api() -> None:
    app = _app(_principal("student", must_change=True))
    context = SimpleNamespace(
        auth=SimpleNamespace(
            principal=lambda: (_principal("student", must_change=True), None),
            required=lambda: True,
        ),
        limiter=SimpleNamespace(check_api=lambda: (False, 0), check_chat=lambda: (False, 0)),
    )
    register_middleware(app, context)
    app.add_url_rule("/api/staff/secret", view_func=lambda: "secret")
    client = app.test_client()
    assert (
        client.get("/api/staff/secret", headers={"Authorization": "Bearer token"}).status_code
        == 403
    )
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer token"}).status_code == 200


def test_bootstrap_flag_comes_from_server_owned_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHIPELAGO_ENV", "production")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable")

    def fake_get(url, **_kwargs):
        if url.endswith("/auth/v1/user"):
            return SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "id": "user-1",
                    "user_metadata": {"must_change_password": False},
                    "app_metadata": {"must_change_password": True},
                },
            )
        return SimpleNamespace(
            status_code=200, json=lambda: [{"role": "student", "username": "12024002028038"}]
        )

    monkeypatch.setattr("hostapp.security.requests.get", fake_get)
    app = Flask(__name__)
    with app.test_request_context(headers={"Authorization": "Bearer session-token"}):
        principal, error = AuthGuard().principal()
    assert error is None
    assert principal["must_change_password"] is True
