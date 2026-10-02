"""Supabase-backed user update and deletion with role permission checks."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import requests

from archipelago.supabase_auth.part01_verify import (
    MIN_PASSWORD_LENGTH,
    MIN_USERNAME_LENGTH,
    VALID_ROLES,
    AuthPrincipal,
    account_email,
)
from archipelago.supabase_auth.part02_local_store import (
    _local_user_store_allowed,
    _read_local_users,
    _write_local_users,
    find_local_user_index,
)
from archipelago.supabase_auth.part03_manage_create import (
    CREATE_AUTH_TIMEOUT_SECONDS,
    LIST_TIMEOUT_SECONDS,
    _patch_profile,
    _require_manager,
    _supabase_admin_ready,
)

logger = logging.getLogger("archipelago.supabase_auth")

LIBRARIAN_SCOPE_ERROR = "Librarians may only modify student accounts or their own profile."
LIBRARIAN_ROLE_ERROR = "Librarians cannot change account roles."
LIBRARIAN_DELETE_ERROR = "Librarians may only delete student accounts."
SELF_DELETE_ERROR = "You cannot delete your own account."
NOT_CONFIGURED_ERROR = "Supabase server-side user management is not configured."


def _librarian_update_violation(
    principal: AuthPrincipal, target_id: str, target_role: str, data: dict[str, Any]
) -> str | None:
    """Return an error when a librarian exceeds their scope on an update."""
    if principal.role != "librarian":
        return None
    if target_id != principal.user_id and target_role != "student":
        return LIBRARIAN_SCOPE_ERROR
    if "role" in data and data["role"] != target_role:
        return LIBRARIAN_ROLE_ERROR
    return None


def _resolve_new_role(principal: AuthPrincipal, target_role: str, data: dict[str, Any]) -> str:
    """Administrators may change roles; everyone else keeps the current role."""
    if "role" in data and principal.role == "administrator":
        candidate = str(data["role"]).strip().lower()
        if candidate in VALID_ROLES:
            return candidate
    return target_role


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _fetch_supabase_profile(url: str, headers: dict[str, str], target_id: str) -> dict | None:
    """Return one profile row, or None when missing/unreachable."""
    try:
        resp = requests.get(
            f"{url}/rest/v1/profiles",
            params={"id": f"eq.{target_id}"},
            headers=headers,
            timeout=LIST_TIMEOUT_SECONDS,
        )
        if resp.status_code == 200:
            profiles = resp.json()
            if profiles and isinstance(profiles, list):
                return profiles[0]
    except requests.RequestException as exc:
        logger.warning("Supabase user update failed, falling back to local: %s", exc)
    return None


def update_managed_user(
    principal: AuthPrincipal, target_id: str, data: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Update an existing user's username, password, display_name, or role."""
    denied = _require_manager(principal, "update")
    if denied:
        return None, denied

    url, headers, ready = _supabase_admin_ready()
    if ready:
        target_profile = _fetch_supabase_profile(url, headers, target_id)
        if target_profile is not None:
            target_role = target_profile.get("role", "student")
            current_username = target_profile.get("username", "")

            violation = _librarian_update_violation(principal, target_id, target_role, data)
            if violation:
                return None, violation

            new_username = (
                str(data.get("username", "")).strip() if "username" in data else current_username
            )
            new_password = str(data.get("password", "")).strip() if "password" in data else ""
            new_display_name = (
                str(data.get("display_name", "")).strip()
                if "display_name" in data
                else target_profile.get("display_name", "")
            )
            new_role = _resolve_new_role(principal, target_role, data)

            if new_username and len(new_username) < MIN_USERNAME_LENGTH:
                return None, f"Username must be at least {MIN_USERNAME_LENGTH} characters."
            if new_password and len(new_password) < MIN_PASSWORD_LENGTH:
                return None, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

            auth_update: dict[str, Any] = {
                "user_metadata": {
                    "username": new_username,
                    "display_name": new_display_name,
                    "role": new_role,
                }
            }
            if new_password:
                auth_update["password"] = new_password
            if new_username != current_username or new_role != target_role:
                auth_update["email"] = account_email(new_username, new_role)

            put_resp = requests.put(
                f"{url}/auth/v1/admin/users/{target_id}",
                headers=headers,
                json=auth_update,
                timeout=CREATE_AUTH_TIMEOUT_SECONDS,
            )
            if put_resp.status_code in {200, 201}:
                _patch_profile(
                    url,
                    headers,
                    target_id,
                    {
                        "username": new_username,
                        "role": new_role,
                        "display_name": new_display_name,
                        "updated_at": _now_iso(),
                    },
                )
                return {
                    "id": target_id,
                    "username": new_username,
                    "role": new_role,
                    "display_name": new_display_name,
                }, None

    if not _local_user_store_allowed():
        return None, NOT_CONFIGURED_ERROR

    # Local fallback is permitted only for explicit loopback development auth.
    local_users = _read_local_users()
    target_idx = find_local_user_index(local_users, target_id)
    if target_idx is None:
        return None, "User not found."
    target_user = local_users[target_idx]
    target_role = target_user.get("role", "student")

    violation = _librarian_update_violation(principal, target_id, target_role, data)
    if violation:
        return None, violation

    new_username = (
        str(data.get("username", "")).strip()
        if "username" in data
        else target_user.get("username", "")
    )
    new_display_name = (
        str(data.get("display_name", "")).strip()
        if "display_name" in data
        else target_user.get("display_name", "")
    )
    new_role = _resolve_new_role(principal, target_role, data)

    if new_username and len(new_username) < MIN_USERNAME_LENGTH:
        return None, f"Username must be at least {MIN_USERNAME_LENGTH} characters."

    if new_username.lower() != target_user.get("username", "").lower():
        taken = any(
            u.get("username", "").lower() == new_username.lower() and u.get("id") != target_id
            for u in local_users
        )
        if taken:
            return None, f"Username '{new_username}' is already taken."

    target_user["username"] = new_username
    target_user["display_name"] = new_display_name
    target_user["role"] = new_role
    target_user["updated_at"] = _now_iso()
    _write_local_users(local_users)
    return target_user, None


def delete_managed_user(principal: AuthPrincipal, target_id: str) -> tuple[bool, str | None]:
    """Delete a user account with role-based checks."""
    denied = _require_manager(principal, "delete")
    if denied:
        return False, denied

    if target_id == principal.user_id:
        return False, SELF_DELETE_ERROR

    url, headers, ready = _supabase_admin_ready()
    if ready:
        target_profile = _fetch_supabase_profile(url, headers, target_id)
        if target_profile is not None:
            target_role = target_profile.get("role", "student")
            if principal.role == "librarian" and target_role != "student":
                return False, LIBRARIAN_DELETE_ERROR
            try:
                del_resp = requests.delete(
                    f"{url}/auth/v1/admin/users/{target_id}",
                    headers=headers,
                    timeout=CREATE_AUTH_TIMEOUT_SECONDS,
                )
                if del_resp.status_code in {200, 204}:
                    return True, None
            except requests.RequestException as exc:
                logger.warning("Supabase user delete failed, falling back to local: %s", exc)

    if not _local_user_store_allowed():
        return False, NOT_CONFIGURED_ERROR

    # Local fallback is permitted only for explicit loopback development auth.
    local_users = _read_local_users()
    target_idx = find_local_user_index(local_users, target_id)
    if target_idx is None:
        return False, "Target user not found."
    target_role = local_users[target_idx].get("role", "student")

    if principal.role == "librarian" and target_role != "student":
        return False, LIBRARIAN_DELETE_ERROR

    del local_users[target_idx]
    _write_local_users(local_users)
    return True, None
