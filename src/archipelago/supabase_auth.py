"""Supabase Auth verification and role lookup for the Flask API."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any

from flask import Request
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger("archipelago.supabase_auth")

AUTH_CONFIG_TIMEOUT_SECONDS = 5
AUTH_USER_TIMEOUT_SECONDS = 10
AUTH_REQUIRED_ENV = "ARCHIPELAGO_AUTH_REQUIRED"
DEV_AUTH_ENV = "ARCHIPELAGO_ALLOW_DEV_AUTH"
SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_PUBLISHABLE_KEY_ENV = "SUPABASE_PUBLISHABLE_KEY"
VALID_ROLES = frozenset({"student", "faculty", "librarian", "administrator"})


@dataclass(frozen=True)
class AuthPrincipal:
    """An authenticated Archipelago user and their application role."""

    user_id: str
    username: str
    role: str
    access_token: str


def is_auth_required() -> bool:
    """Return whether API routes require sessions; production cannot disable auth."""
    environment = os.getenv("ARCHIPELAGO_ENV", "development").strip().lower()
    if environment in {"production", "prod"}:
        return True
    return os.getenv(AUTH_REQUIRED_ENV, "1").strip().lower() in {"1", "true", "yes"}


def is_dev_auth_allowed() -> bool:
    """Allow explicitly opted-in dev identities only outside production."""
    enabled = os.getenv(DEV_AUTH_ENV, "0").strip().lower() in {"1", "true", "yes"}
    environment = os.getenv("ARCHIPELAGO_ENV", "development").strip().lower()
    return enabled and environment not in {"production", "prod"}


def _is_loopback_request(request: Request) -> bool:
    """Check the direct socket peer; never trust forwarded client headers."""
    return request.remote_addr in {"127.0.0.1", "::1", "localhost"}


def public_config() -> dict[str, Any]:
    """Return browser-safe Supabase configuration, never server credentials."""
    url = os.getenv(SUPABASE_URL_ENV, "").strip().rstrip("/")
    publishable_key = os.getenv(SUPABASE_PUBLISHABLE_KEY_ENV, "").strip()
    configured = bool(url and publishable_key)
    return {
        "configured": configured,
        "required": is_auth_required(),
        "url": url if configured else None,
        "publishableKey": publishable_key if configured else None,
        "chatUrl": os.getenv("ARCHIPELAGO_CHAT_URL", "").strip().rstrip("/") or None,
        "graphUrl": os.getenv("ARCHIPELAGO_GRAPH_URL", "").strip().rstrip("/") or None,
    }


def authenticate_request(request: Request) -> tuple[AuthPrincipal | None, str | None]:
    """Validate a Supabase Bearer token or an explicitly enabled dev identity."""
    if is_dev_auth_allowed() and _is_loopback_request(request):
        dev_role = request.headers.get("X-User-Role", "").strip().lower()
        if dev_role in VALID_ROLES:
            dev_username = request.headers.get("X-User-Name", "").strip() or dev_role
            dev_id = request.headers.get("X-User-Id", "").strip() or f"local-{dev_role}-id"
            return AuthPrincipal(
                user_id=dev_id,
                username=dev_username,
                role=dev_role,
                access_token="local-dev-token",
            ), None

    config = public_config()
    if not config["configured"]:
        if is_auth_required():
            return None, "Supabase Auth is not configured."
        return None, "Authentication is disabled; no user session is available."

    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        access_token = authorization.removeprefix("Bearer ").strip()
    else:
        access_token = request.cookies.get("archipelago_token", "").strip()
    if not access_token:
        return None, "A Supabase access token is required."

    headers = {
        "apikey": str(config["publishableKey"]),
        "Authorization": f"Bearer {access_token}",
    }
    try:
        user_response = requests.get(
            f"{config['url']}/auth/v1/user",
            headers=headers,
            timeout=AUTH_USER_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        logger.warning("Supabase Auth user verification was unreachable")
        return None, "Authentication service is temporarily unavailable."
    if user_response.status_code != 200:
        return None, "Your session is invalid or expired. Please sign in again."

    user = user_response.json()
    user_id = str(user.get("id", "")).strip()
    if not user_id:
        return None, "The authentication service returned an invalid user."

    try:
        profile_response = requests.get(
            f"{config['url']}/rest/v1/profiles",
            params={"select": "username,role", "id": f"eq.{user_id}"},
            headers=headers,
            timeout=AUTH_CONFIG_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        logger.warning("Supabase profile lookup was unreachable")
        return None, "Profile service is temporarily unavailable."
    if profile_response.status_code != 200:
        return None, "Your account profile is not available."

    profiles = profile_response.json()
    if not isinstance(profiles, list) or len(profiles) != 1:
        return None, "Your account has not been assigned an Archipelago role."
    profile = profiles[0]
    role = str(profile.get("role", "")).strip()
    if role not in VALID_ROLES:
        return None, "Your account has an invalid Archipelago role."
    username = str(profile.get("username", "")).strip()
    return AuthPrincipal(user_id=user_id, username=username, role=role, access_token=access_token), None


SUPABASE_SECRET_KEY_ENV = "SUPABASE_SECRET_KEY"
SUPABASE_SERVICE_ROLE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"


def get_service_role_key() -> str:
    """Return the administrative service-role key for backend user management."""
    return (
        os.getenv(SUPABASE_SECRET_KEY_ENV, "").strip()
        or os.getenv(SUPABASE_SERVICE_ROLE_KEY_ENV, "").strip()
    )


def account_email(username: str, role: str) -> str:
    """Build the internal Auth email used for username/password sign-in."""
    return f"{username.lower()}@{role}.iem.archipelago.invalid"


def _admin_headers() -> dict[str, str]:
    key = get_service_role_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


import json
from pathlib import Path
import uuid
import datetime

_LOCAL_USERS_FILE = Path(__file__).resolve().parents[2] / "data" / "local_users.json"


def _ensure_local_users_file() -> Path:
    _LOCAL_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _LOCAL_USERS_FILE.exists():
        # Empty by default: local development must never manufacture demo roles.
        _LOCAL_USERS_FILE.write_text("[]", encoding="utf-8")
    return _LOCAL_USERS_FILE


def _read_local_users() -> list[dict[str, Any]]:
    path = _ensure_local_users_file()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_local_users(users: list[dict[str, Any]]) -> None:
    path = _ensure_local_users_file()
    path.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _local_user_store_allowed() -> bool:
    """Restrict the file-backed user directory to explicit, non-production dev auth."""
    return not is_auth_required() and is_dev_auth_allowed()


def list_managed_users(principal: AuthPrincipal) -> tuple[list[dict[str, Any]] | None, str | None]:
    """List accounts visible to the calling principal according to their role."""
    if principal.role not in {"librarian", "administrator"}:
        return None, "You do not have permission to manage users."

    config = public_config()
    key = get_service_role_key()
    if config["configured"] and key:
        url = config["url"]
        headers = _admin_headers()
        try:
            if principal.role == "administrator":
                resp = requests.get(
                    f"{url}/rest/v1/profiles",
                    params={"select": "id,username,role,display_name,created_at,updated_at", "order": "created_at.desc"},
                    headers=headers,
                    timeout=10,
                )
            else:
                resp = requests.get(
                    f"{url}/rest/v1/profiles",
                    params={
                        "select": "id,username,role,display_name,created_at,updated_at",
                        "or": f"(role.eq.student,id.eq.{principal.user_id})",
                        "order": "created_at.desc",
                    },
                    headers=headers,
                    timeout=10,
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
    else:
        filtered = [u for u in local_users if u.get("role") == "student" or u.get("id") == principal.user_id]
        return filtered, None


def create_managed_user(principal: AuthPrincipal, data: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Create a new user with role-based permission checks."""
    if principal.role not in {"librarian", "administrator"}:
        return None, "You do not have permission to create users."

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    role = str(data.get("role", "student")).strip().lower()
    display_name = str(data.get("display_name", "")).strip() or username

    if not username or len(username) < 3:
        return None, "Username must be at least 3 characters."
    if not password or len(password) < 6:
        return None, "Password must be at least 6 characters."

    if role not in VALID_ROLES:
        return None, f"Invalid role: '{role}'."

    # Role enforcement: Librarian can only create student accounts
    if principal.role == "librarian" and role != "student":
        return None, "Librarians may only create student accounts."

    config = public_config()
    key = get_service_role_key()
    if config["configured"] and key:
        url = config["url"]
        headers = _admin_headers()
        email = account_email(username, role)
        try:
            auth_resp = requests.post(
                f"{url}/auth/v1/admin/users",
                headers=headers,
                json={
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "username": username,
                        "display_name": display_name,
                        "role": role,
                    },
                },
                timeout=15,
            )
            if auth_resp.status_code in {200, 201}:
                user_info = auth_resp.json()
                uid = user_info.get("id")
                try:
                    requests.patch(
                        f"{url}/rest/v1/profiles",
                        params={"id": f"eq.{uid}"},
                        headers={**headers, "Prefer": "return=minimal"},
                        json={"username": username, "role": role, "display_name": display_name},
                        timeout=10,
                    )
                except Exception:
                    pass
                return {
                    "id": uid,
                    "username": username,
                    "role": role,
                    "display_name": display_name,
                }, None
            else:
                err_msg = auth_resp.text
                try:
                    err_json = auth_resp.json()
                    err_msg = err_json.get("msg") or err_json.get("message") or err_msg
                except Exception:
                    pass
                return None, f"Account creation failed: {err_msg}"
        except requests.RequestException as exc:
            logger.warning("Supabase user create failed, falling back to local: %s", exc)

    if not _local_user_store_allowed():
        return None, "Supabase server-side user management is not configured."

    # Local fallback is permitted only for explicit loopback development auth.
    local_users = _read_local_users()
    if any(u.get("username", "").lower() == username.lower() for u in local_users):
        return None, f"Username '{username}' is already registered."
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_id = f"user-{uuid.uuid4().hex[:8]}"
    new_entry = {
        "id": new_id,
        "username": username,
        "role": role,
        "display_name": display_name,
        "created_at": now_str,
        "updated_at": now_str,
    }
    local_users.insert(0, new_entry)
    _write_local_users(local_users)
    return new_entry, None


def update_managed_user(
    principal: AuthPrincipal, target_id: str, data: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Update an existing user's username, password, display_name, or role."""
    if principal.role not in {"librarian", "administrator"}:
        return None, "You do not have permission to update users."

    config = public_config()
    key = get_service_role_key()
    if config["configured"] and key:
        url = config["url"]
        headers = _admin_headers()
        try:
            prof_resp = requests.get(
                f"{url}/rest/v1/profiles",
                params={"id": f"eq.{target_id}"},
                headers=headers,
                timeout=10,
            )
            if prof_resp.status_code == 200:
                profiles = prof_resp.json()
                if profiles and isinstance(profiles, list):
                    target_profile = profiles[0]
                    target_role = target_profile.get("role", "student")
                    current_username = target_profile.get("username", "")

                    if principal.role == "librarian":
                        if target_id != principal.user_id and target_role != "student":
                            return None, "Librarians may only modify student accounts or their own profile."
                        if "role" in data and data["role"] != target_role:
                            return None, "Librarians cannot change account roles."

                    new_username = str(data.get("username", "")).strip() if "username" in data else current_username
                    new_password = str(data.get("password", "")).strip() if "password" in data else ""
                    new_display_name = str(data.get("display_name", "")).strip() if "display_name" in data else target_profile.get("display_name", "")
                    new_role = target_role
                    if "role" in data and principal.role == "administrator":
                        r = str(data["role"]).strip().lower()
                        if r in VALID_ROLES:
                            new_role = r

                    if new_username and len(new_username) < 3:
                        return None, "Username must be at least 3 characters."
                    if new_password and len(new_password) < 6:
                        return None, "Password must be at least 6 characters."

                    auth_update: dict[str, Any] = {}
                    if new_password:
                        auth_update["password"] = new_password
                    if new_username != current_username or new_role != target_role:
                        auth_update["email"] = account_email(new_username, new_role)
                    auth_update["user_metadata"] = {
                        "username": new_username,
                        "display_name": new_display_name,
                        "role": new_role,
                    }

                    put_resp = requests.put(
                        f"{url}/auth/v1/admin/users/{target_id}",
                        headers=headers,
                        json=auth_update,
                        timeout=15,
                    )
                    if put_resp.status_code in {200, 201}:
                        profile_update = {
                            "username": new_username,
                            "role": new_role,
                            "display_name": new_display_name,
                            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        }
                        requests.patch(
                            f"{url}/rest/v1/profiles",
                            params={"id": f"eq.{target_id}"},
                            headers={**headers, "Prefer": "return=minimal"},
                            json=profile_update,
                            timeout=10,
                        )
                        return {
                            "id": target_id,
                            "username": new_username,
                            "role": new_role,
                            "display_name": new_display_name,
                        }, None
        except requests.RequestException as exc:
            logger.warning("Supabase user update failed, falling back to local: %s", exc)

    if not _local_user_store_allowed():
        return None, "Supabase server-side user management is not configured."

    # Local fallback is permitted only for explicit loopback development auth.
    local_users = _read_local_users()
    target_idx = next((i for i, u in enumerate(local_users) if u.get("id") == target_id), None)
    if target_idx is None:
        return None, "User not found."
    target_user = local_users[target_idx]
    target_role = target_user.get("role", "student")

    if principal.role == "librarian":
        if target_id != principal.user_id and target_role != "student":
            return None, "Librarians may only modify student accounts or their own profile."
        if "role" in data and data["role"] != target_role:
            return None, "Librarians cannot change account roles."

    new_username = str(data.get("username", "")).strip() if "username" in data else target_user.get("username", "")
    new_display_name = str(data.get("display_name", "")).strip() if "display_name" in data else target_user.get("display_name", "")
    new_role = target_role
    if "role" in data and principal.role == "administrator":
        r = str(data["role"]).strip().lower()
        if r in VALID_ROLES:
            new_role = r

    if new_username and len(new_username) < 3:
        return None, "Username must be at least 3 characters."

    if new_username.lower() != target_user.get("username", "").lower():
        if any(u.get("username", "").lower() == new_username.lower() and u.get("id") != target_id for u in local_users):
            return None, f"Username '{new_username}' is already taken."

    target_user["username"] = new_username
    target_user["display_name"] = new_display_name
    target_user["role"] = new_role
    target_user["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _write_local_users(local_users)
    return target_user, None


def delete_managed_user(principal: AuthPrincipal, target_id: str) -> tuple[bool, str | None]:
    """Delete a user account with role-based checks."""
    if principal.role not in {"librarian", "administrator"}:
        return False, "You do not have permission to delete users."

    if target_id == principal.user_id:
        return False, "You cannot delete your own account."

    config = public_config()
    key = get_service_role_key()
    if config["configured"] and key:
        url = config["url"]
        headers = _admin_headers()
        try:
            prof_resp = requests.get(
                f"{url}/rest/v1/profiles",
                params={"id": f"eq.{target_id}"},
                headers=headers,
                timeout=10,
            )
            if prof_resp.status_code == 200:
                profiles = prof_resp.json()
                if profiles:
                    target_role = profiles[0].get("role", "student")
                    if principal.role == "librarian" and target_role != "student":
                        return False, "Librarians may only delete student accounts."
                    del_resp = requests.delete(
                        f"{url}/auth/v1/admin/users/{target_id}",
                        headers=headers,
                        timeout=15,
                    )
                    if del_resp.status_code in {200, 204}:
                        return True, None
        except requests.RequestException as exc:
            logger.warning("Supabase user delete failed, falling back to local: %s", exc)

    if not _local_user_store_allowed():
        return False, "Supabase server-side user management is not configured."

    # Local fallback is permitted only for explicit loopback development auth.
    local_users = _read_local_users()
    target_idx = next((i for i, u in enumerate(local_users) if u.get("id") == target_id), None)
    if target_idx is None:
        return False, "Target user not found."
    target_user = local_users[target_idx]
    target_role = target_user.get("role", "student")

    if principal.role == "librarian" and target_role != "student":
        return False, "Librarians may only delete student accounts."

    del local_users[target_idx]
    _write_local_users(local_users)
    return True, None


