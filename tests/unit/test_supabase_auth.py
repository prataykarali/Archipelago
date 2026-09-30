"""Tests for the Supabase login boundary in the Flask runtime."""
from __future__ import annotations

import pytest

from src.api import app as api_module
from src.archipelago.supabase_auth import AuthPrincipal


@pytest.fixture()
def client():
    api_module.app.config["TESTING"] = True
    with api_module.app.test_client() as test_client:
        yield test_client


def configure_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a non-secret Supabase test deployment."""
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")


def test_auth_config_never_exposes_service_role_key(client, monkeypatch: pytest.MonkeyPatch):
    configure_auth(monkeypatch)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "must-not-be-returned")

    response = client.get("/api/auth/config")

    assert response.status_code == 200
    assert response.get_json() == {
        "configured": True,
        "required": True,
        "url": "https://example.supabase.co",
        "publishableKey": "test-publishable-key",
        "chatUrl": None,
        "graphUrl": None,
    }


def test_protected_api_rejects_missing_session(client, monkeypatch: pytest.MonkeyPatch):
    configure_auth(monkeypatch)

    response = client.post("/api/chat", json={"query": "What is a graph?"})

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"


def test_authenticated_profile_is_returned(client, monkeypatch: pytest.MonkeyPatch):
    configure_auth(monkeypatch)
    principal = AuthPrincipal(
        user_id="00000000-0000-0000-0000-000000000001",
        username="12024002028038",
        role="student",
        access_token="test-token",
    )
    monkeypatch.setattr(api_module.supabase_auth, "authenticate_request", lambda _: (principal, None))

    response = client.get("/api/auth/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.get_json()["role"] == "student"


def test_student_cannot_upload_when_auth_is_enabled(client, monkeypatch: pytest.MonkeyPatch):
    configure_auth(monkeypatch)
    principal = AuthPrincipal(
        user_id="00000000-0000-0000-0000-000000000001",
        username="12024002028038",
        role="student",
        access_token="test-token",
    )
    monkeypatch.setattr(api_module.supabase_auth, "authenticate_request", lambda _: (principal, None))

    response = client.post("/api/upload", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"


def test_student_cannot_access_user_management(client, monkeypatch: pytest.MonkeyPatch):
    configure_auth(monkeypatch)
    principal = AuthPrincipal(
        user_id="00000000-0000-0000-0000-000000000001",
        username="12024002028038",
        role="student",
        access_token="test-token",
    )
    monkeypatch.setattr(api_module.supabase_auth, "authenticate_request", lambda _: (principal, None))

    response = client.get("/api/users", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"


def test_librarian_can_list_users(client, monkeypatch: pytest.MonkeyPatch):
    configure_auth(monkeypatch)
    principal = AuthPrincipal(
        user_id="00000000-0000-0000-0000-000000000002",
        username="librarian",
        role="librarian",
        access_token="test-token",
    )
    monkeypatch.setattr(api_module.supabase_auth, "authenticate_request", lambda _: (principal, None))
    monkeypatch.setattr(api_module.supabase_auth, "list_managed_users", lambda p: ([{"username": "12024002028038", "role": "student"}], None))

    response = client.get("/api/users", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert len(response.get_json()["users"]) == 1


def test_librarian_cannot_create_administrator(monkeypatch: pytest.MonkeyPatch):
    principal = AuthPrincipal(
        user_id="00000000-0000-0000-0000-000000000002",
        username="librarian",
        role="librarian",
        access_token="test-token",
    )
    from src.archipelago import supabase_auth
    result, err = supabase_auth.create_managed_user(principal, {"username": "new_admin", "password": "password123", "role": "administrator"})
    assert result is None
    assert "Librarians may only create student accounts" in err


def test_user_updates_fail_closed_without_supabase_service_key(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from src.archipelago import supabase_auth
    monkeypatch.setattr(supabase_auth, "get_service_role_key", lambda: "")
    monkeypatch.setattr(supabase_auth, "_LOCAL_USERS_FILE", tmp_path / "users.json")
    
    # Local JSON fallback must not become an alternate production identity store.
    initial_users = [
        {"id": "lib-01", "username": "librarian", "role": "librarian", "display_name": "Librarian"},
        {"id": "std-01", "username": "student_one", "role": "student", "display_name": "Student 1"},
        {"id": "adm-01", "username": "admin_one", "role": "administrator", "display_name": "Admin 1"},
    ]
    supabase_auth._write_local_users(initial_users)

    lib_principal = AuthPrincipal(
        user_id="lib-01",
        username="librarian",
        role="librarian",
        access_token="test-token",
    )

    # Both student and self updates require the configured Supabase service key.
    res, err = supabase_auth.update_managed_user(lib_principal, "std-01", {"username": "student_updated"})
    assert res is None
    assert "not configured" in err

    res, err = supabase_auth.update_managed_user(lib_principal, "lib-01", {"username": "librarian_new"})
    assert res is None
    assert "not configured" in err
    assert supabase_auth._read_local_users()[1]["username"] == "student_one"


def test_librarian_can_delete_student_but_not_admin(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from src.archipelago import supabase_auth
    monkeypatch.setattr(supabase_auth, "get_service_role_key", lambda: "")
    monkeypatch.setattr(supabase_auth, "_LOCAL_USERS_FILE", tmp_path / "users.json")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    monkeypatch.setenv("ARCHIPELAGO_ALLOW_DEV_AUTH", "1")

    initial_users = [
        {"id": "lib-01", "username": "librarian", "role": "librarian", "display_name": "Librarian"},
        {"id": "std-01", "username": "student_one", "role": "student", "display_name": "Student 1"},
        {"id": "adm-01", "username": "admin_one", "role": "administrator", "display_name": "Admin 1"},
    ]
    supabase_auth._write_local_users(initial_users)

    lib_principal = AuthPrincipal(
        user_id="lib-01",
        username="librarian",
        role="librarian",
        access_token="test-token",
    )

    # 1. Librarian cannot delete self
    ok, err = supabase_auth.delete_managed_user(lib_principal, "lib-01")
    assert not ok
    assert "You cannot delete your own account" in err

    # 2. Librarian cannot delete admin
    ok, err = supabase_auth.delete_managed_user(lib_principal, "adm-01")
    assert not ok
    assert "Librarians may only delete student accounts" in err

    # 3. Librarian can delete student
    ok, err = supabase_auth.delete_managed_user(lib_principal, "std-01")
    assert ok
    assert err is None

    # Verify student is deleted
    remaining = supabase_auth._read_local_users()
    assert not any(u["id"] == "std-01" for u in remaining)


def test_administrator_full_crud_permissions(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from src.archipelago import supabase_auth
    monkeypatch.setattr(supabase_auth, "get_service_role_key", lambda: "")
    monkeypatch.setattr(supabase_auth, "_LOCAL_USERS_FILE", tmp_path / "users.json")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    monkeypatch.setenv("ARCHIPELAGO_ALLOW_DEV_AUTH", "1")

    initial_users = [
        {"id": "adm-01", "username": "admin", "role": "administrator", "display_name": "Admin"},
        {"id": "std-01", "username": "student_one", "role": "student", "display_name": "Student 1"},
    ]
    supabase_auth._write_local_users(initial_users)

    admin_principal = AuthPrincipal(
        user_id="adm-01",
        username="admin",
        role="administrator",
        access_token="admin-token",
    )

    # 1. Create a new librarian
    new_user, err = supabase_auth.create_managed_user(admin_principal, {
        "username": "new_librarian",
        "password": "password123",
        "role": "librarian",
        "display_name": "New Librarian"
    })
    assert err is None
    assert new_user["role"] == "librarian"

    # 2. Update student username and role to librarian
    upd_user, err = supabase_auth.update_managed_user(admin_principal, "std-01", {
        "username": "promoted_student",
        "role": "librarian"
    })
    assert err is None
    assert upd_user["username"] == "promoted_student"
    assert upd_user["role"] == "librarian"

    # 3. Delete promoted user
    ok, err = supabase_auth.delete_managed_user(admin_principal, "std-01")
    assert ok
    assert err is None

