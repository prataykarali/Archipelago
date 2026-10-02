"""Supabase-backed user listing and creation with role permission checks."""

from __future__ import annotations

import datetime
import logging
from typing import Any
import uuid

import requests

from archipelago.supabase_auth import part01_verify as verify
from archipelago.supabase_auth.part01_verify import (
    MANAGER_ROLES,
    MIN_PASSWORD_LENGTH,
    MIN_USERNAME_LENGTH,
    PROFILE_COLUMNS,
    VALID_ROLES,
    AuthPrincipal,
    account_email,
)
from archipelago.supabase_auth.part02_local_store import (
    _local_user_store_allowed,
    _read_local_users,
    _write_local_users,
)

logger = logging.getLogger("archipelago.supabase_auth")

LIST_TIMEOUT_SECONDS = 10
CREATE_AUTH_TIMEOUT_SECONDS = 15
CREATE_PROFILE_TIMEOUT_SECONDS = 10
USER_ID_HEX_LENGTH = 8


def _supabase_admin_ready() -> tuple[str | None, dict[str, str] | None, bool]:
    """Return (url, admin_headers, ready) for server-side user management.

    Reads the key and public config through the verify module so runtime
    overrides (tests, key rotation) are honoured.
    """
    config = verify.public_config()
    key = verify.get_service_role_key()
    if config["configured"] and key:
        return config["url"], verify._admin_headers(), True
    return None, None, False


def _require_manager(principal: AuthPrincipal, action: str) -> str | None:
    """Return an error message when the principal may not perform `action`."""
    if principal.role not in MANAGER_ROLES:
        return f"You do not have permission to {action} users."
    return None


def list_managed_users(principal: AuthPrincipal) -> tuple[list[dict[str, Any]] | None, str | None]:
    """List accounts visible to the calling principal according to their role."""
    denied = _require_manager(principal, "manage")
    if denied:
        return None, denied

    url, headers, ready = _supabase_admin_ready()
    if ready:
        try:
            if principal.role == "administrator":
                params = {"select": PROFILE_COLUMNS, "order": "created_at.desc"}
            else:
                params = {
                    "select": PROFILE_COLUMNS,
                    "or": f"(role.eq.student,id.eq.{principal.user_id})",
                    "order": "created_at.desc",
                }
            resp = requests.get(
                f"{url}/rest/v1/profiles",
                params=params,
                headers=headers,
                timeout=LIST_TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                return resp.json(), None
        except requests.RequestException as exc:
            logger.warning("Supabase profile list failed, falling back to local: %s", exc)

    if not _local_user_store_allowed():
        return None, "Supabase server-side user management is not configured."

    # Local fallback is permitted only for explicit loopback development auth.
    local_users = _read_local_users()
    if principal.role == "administrator":
        return local_users, None
    filtered = [
        u for u in local_users if u.get("role") == "student" or u.get("id") == principal.user_id
    ]
    return filtered, None


def _patch_profile(url: str, headers: dict[str, str], uid: str, payload: dict[str, Any]) -> None:
    """Best-effort profile write; the Auth record is the source of truth."""
    try:
        requests.patch(
            f"{url}/rest/v1/profiles",
            params={"id": f"eq.{uid}"},
            headers={**headers, "Prefer": "return=minimal"},
            json=payload,
            timeout=CREATE_PROFILE_TIMEOUT_SECONDS,
        )
    except Exception:
        pass


def _auth_error_message(response: requests.Response) -> str:
    """Extract the most specific failure message Supabase returned."""
    err_msg = response.text
    try:
        err_json = response.json()
        err_msg = err_json.get("msg") or err_json.get("message") or err_msg
    except Exception:
        pass
    return f"Account creation failed: {err_msg}"


def create_managed_user(
    principal: AuthPrincipal, data: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Create a new user with role-based permission checks."""
    denied = _require_manager(principal, "create")
    if denied:
        return None, denied

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    role = str(data.get("role", "student")).strip().lower()
    display_name = str(data.get("display_name", "")).strip() or username

    if not username or len(username) < MIN_USERNAME_LENGTH:
        return None, f"Username must be at least {MIN_USERNAME_LENGTH} characters."
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return None, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    if role not in VALID_ROLES:
        return None, f"Invalid role: '{role}'."

    # Role enforcement: Librarian can only create student accounts
    if principal.role == "librarian" and role != "student":
        return None, "Librarians may only create student accounts."

    url, headers, ready = _supabase_admin_ready()
    if ready:
        try:
            auth_resp = requests.post(
                f"{url}/auth/v1/admin/users",
                headers=headers,
                json={
                    "email": account_email(username, role),
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "username": username,
                        "display_name": display_name,
                        "role": role,
                    },
                },
                timeout=CREATE_AUTH_TIMEOUT_SECONDS,
            )
            if auth_resp.status_code in {200, 201}:
                uid = auth_resp.json().get("id")
                _patch_profile(
                    url,
                    headers,
                    uid,
                    {"username": username, "role": role, "display_name": display_name},
                )
                return {
                    "id": uid,
                    "username": username,
                    "role": role,
                    "display_name": display_name,
                }, None
            return None, _auth_error_message(auth_resp)
        except requests.RequestException as exc:
            logger.warning("Supabase user create failed, falling back to local: %s", exc)

    if not _local_user_store_allowed():
        return None, "Supabase server-side user management is not configured."

    # Local fallback is permitted only for explicit loopback development auth.
    local_users = _read_local_users()
    if any(u.get("username", "").lower() == username.lower() for u in local_users):
        return None, f"Username '{username}' is already registered."
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_entry = {
        "id": f"user-{uuid.uuid4().hex[:USER_ID_HEX_LENGTH]}",
        "username": username,
        "role": role,
        "display_name": display_name,
        "created_at": now_str,
        "updated_at": now_str,
    }
    local_users.insert(0, new_entry)
    _write_local_users(local_users)
    return new_entry, None
