"""Supabase Auth principals, configuration, and request verification."""

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
SUPABASE_SECRET_KEY_ENV = "SUPABASE_SECRET_KEY"
SUPABASE_SERVICE_ROLE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
ENVIRONMENT_ENV = "ARCHIPELAGO_ENV"
CHAT_URL_ENV = "ARCHIPELAGO_CHAT_URL"
GRAPH_URL_ENV = "ARCHIPELAGO_GRAPH_URL"
TOKEN_COOKIE = "archipelago_token"
DEV_ACCESS_TOKEN = "local-dev-token"
AUTH_DOMAIN_SUFFIX = "iem.archipelago.invalid"

VALID_ROLES = frozenset({"student", "faculty", "librarian", "administrator"})
MANAGER_ROLES = frozenset({"librarian", "administrator"})
PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod"})
TRUTHY = frozenset({"1", "true", "yes"})
LOOPBACK_ADDRESSES = frozenset({"127.0.0.1", "::1", "localhost"})
PROFILE_COLUMNS = "id,username,role,display_name,created_at,updated_at"
MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 6


@dataclass(frozen=True)
class AuthPrincipal:
    """An authenticated Archipelago user and their application role."""

    user_id: str
    username: str
    role: str
    access_token: str


def is_auth_required() -> bool:
    """Return whether API routes require sessions; production cannot disable auth."""
    environment = os.getenv(ENVIRONMENT_ENV, "development").strip().lower()
    if environment in PRODUCTION_ENVIRONMENTS:
        return True
    return os.getenv(AUTH_REQUIRED_ENV, "1").strip().lower() in TRUTHY


def is_dev_auth_allowed() -> bool:
    """Allow explicitly opted-in dev identities only outside production."""
    enabled = os.getenv(DEV_AUTH_ENV, "0").strip().lower() in TRUTHY
    environment = os.getenv(ENVIRONMENT_ENV, "development").strip().lower()
    return enabled and environment not in PRODUCTION_ENVIRONMENTS


def _is_loopback_request(request: Request) -> bool:
    """Check the direct socket peer; never trust forwarded client headers."""
    return request.remote_addr in LOOPBACK_ADDRESSES


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
        "chatUrl": os.getenv(CHAT_URL_ENV, "").strip().rstrip("/") or None,
        "graphUrl": os.getenv(GRAPH_URL_ENV, "").strip().rstrip("/") or None,
    }


def get_service_role_key() -> str:
    """Return the administrative service-role key for backend user management."""
    return (
        os.getenv(SUPABASE_SECRET_KEY_ENV, "").strip()
        or os.getenv(SUPABASE_SERVICE_ROLE_KEY_ENV, "").strip()
    )


def account_email(username: str, role: str) -> str:
    """Build the internal Auth email used for username/password sign-in."""
    return f"{username.lower()}@{role}.{AUTH_DOMAIN_SUFFIX}"


def _admin_headers() -> dict[str, str]:
    """Use opaque secret keys as API keys; legacy JWTs also need Bearer auth."""
    key = get_service_role_key()
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _bearer_headers(access_token: str) -> dict[str, str]:
    config = public_config()
    return {
        "apikey": str(config["publishableKey"]),
        "Authorization": f"Bearer {access_token}",
    }


def _dev_principal(request: Request) -> AuthPrincipal | None:
    """Build a dev principal from explicit headers, or None when not opted in."""
    if not (is_dev_auth_allowed() and _is_loopback_request(request)):
        return None
    dev_role = request.headers.get("X-User-Role", "").strip().lower()
    if dev_role not in VALID_ROLES:
        return None
    dev_username = request.headers.get("X-User-Name", "").strip() or dev_role
    dev_id = request.headers.get("X-User-Id", "").strip() or f"local-{dev_role}-id"
    return AuthPrincipal(
        user_id=dev_id,
        username=dev_username,
        role=dev_role,
        access_token=DEV_ACCESS_TOKEN,
    )


def _extract_access_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return request.cookies.get(TOKEN_COOKIE, "").strip()


def _verify_user(config: dict[str, Any], access_token: str) -> tuple[str | None, str | None]:
    """Return (user_id, error) after validating the bearer token with Supabase."""
    try:
        user_response = requests.get(
            f"{config['url']}/auth/v1/user",
            headers=_bearer_headers(access_token),
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
    return user_id, None


def _lookup_profile(
    config: dict[str, Any], access_token: str, user_id: str
) -> tuple[dict | None, str | None]:
    """Return (profile, error) for one authenticated user."""
    try:
        profile_response = requests.get(
            f"{config['url']}/rest/v1/profiles",
            params={"select": "username,role", "id": f"eq.{user_id}"},
            headers=_bearer_headers(access_token),
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
    return profiles[0], None


def authenticate_request(request: Request) -> tuple[AuthPrincipal | None, str | None]:
    """Validate a Supabase Bearer token or an explicitly enabled dev identity."""
    dev_principal = _dev_principal(request)
    if dev_principal is not None:
        return dev_principal, None

    config = public_config()
    if not config["configured"]:
        if is_auth_required():
            return None, "Supabase Auth is not configured."
        return None, "Authentication is disabled; no user session is available."

    access_token = _extract_access_token(request)
    if not access_token:
        return None, "A Supabase access token is required."

    user_id, error = _verify_user(config, access_token)
    if error is not None:
        return None, error

    profile, error = _lookup_profile(config, access_token, str(user_id))
    if error is not None:
        return None, error

    role = str(profile.get("role", "")).strip()
    if role not in VALID_ROLES:
        return None, "Your account has an invalid Archipelago role."
    username = str(profile.get("username", "")).strip()
    return AuthPrincipal(
        user_id=str(user_id),
        username=username,
        role=role,
        access_token=access_token,
    ), None
