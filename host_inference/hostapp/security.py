"""Authentication, authorisation and rate limiting for the hosted app.

One concern: deciding who the caller is and whether they may proceed.  Route
modules call ``ctx.auth`` and ``ctx.limiter`` instead of reaching for module
globals, which keeps them testable without patching imports.
"""

from __future__ import annotations

import base64
from collections import defaultdict, deque
from contextlib import closing
from datetime import UTC, datetime
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit

from flask import request
import requests

from .config import (
    ABSOLUTE_SESSION_LIFETIME_SECONDS,
    ALLOWED_ORIGINS,
    API_RATE_MAX_PER_MIN,
    API_RATE_MIN_GAP_SEC,
    AUTH_RATE_MAX_PER_MIN,
    AUTH_RATE_MIN_GAP_SEC,
    AUTH_ROLES,
    CHAT_RATE_MAX_PER_MIN,
    CHAT_RATE_MIN_GAP_SEC,
    ELEVATED_ROLES,
    HANDOFF_TICKET_TTL_SECONDS,
    IDLE_TIMEOUT_SECONDS,
    RATE_WINDOW_SEC,
)
from .runtime_state import hosted_runtime, runtime_rpc
from .session_store import session_action, verified_session_ids

# Bounded (connect_sec, read_sec) HTTP timeouts so auth/profile calls never stall 95s.
SUPABASE_USER_TIMEOUT_SEC: tuple[float, float] = (3.0, 5.0)
SUPABASE_PROFILE_TIMEOUT_SEC: tuple[float, float] = (3.0, 5.0)
# Client IP headers set by Vercel's trusted edge proxy, never client-spoofable headers.
CLIENT_IP_HEADERS = ("X-Vercel-Forwarded-For", "X-Real-IP")
# The burst min-gap guards state-changing calls.  Idempotent reads must never be
# rejected on timing alone: a reader opening two exact book links, or a page
# firing several API calls in parallel, is normal browsing, not abuse.  The
# per-minute ceiling still applies to every method.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
PRINCIPAL_CACHE_TTL_SECONDS = 45.0
HOURLY_QUERY_LIMIT = 10
QUERY_WINDOW_SECONDS = 3600
MAX_TRACKED_SESSIONS = 4096
MAX_TRACKED_BUCKETS = 4096
MAX_TOKEN_LENGTH = 4096

AUTH_FAILURE_CODES = (
    ("jwt token expired", "jwt_expired"),
    ("revoked", "revoked_credentials"),
    ("maximum lifetime", "absolute_expired"),
    ("inactivity", "idle_expired"),
    ("identity verification is unavailable", "upstream_unavailable"),
    ("durable session verification is unavailable", "upstream_unavailable"),
    ("session is required", "missing_session"),
    ("could not be verified", "invalid_credentials"),
)


def auth_failure_code(error: str | None) -> str:
    """Return a stable public reason without exposing a bearer token."""
    lowered = (error or "").lower()
    for phrase, code in AUTH_FAILURE_CODES:
        if phrase in lowered:
            return code
    return "unauthorized"


_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CONTROL_OR_SPACE_RE = re.compile(r"[\x00-\x20\x7f]")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_LIBRARIAN_ORIGIN_RE = re.compile(
    r"^https://archipelago-librarian(?:-[a-z0-9-]+-shinaura)?\.vercel\.app$"
)

_SHARED_LOCK = threading.Lock()
_SHARED_REVOKED_BY_SCOPE: dict[str, set[str]] = defaultdict(set)
_SHARED_TICKETS_BY_SCOPE: dict[str, dict[str, dict]] = defaultdict(dict)
_PROCESS_CSRF_KEY = secrets.token_hex(32)


def _runtime_scope() -> str:
    """Isolate shared in-memory state per pytest test while sharing across instances in a test."""
    current_test = os.environ.get("PYTEST_CURRENT_TEST", "")
    return current_test.split(" ")[0] if current_test else "production"


def is_allowed_handoff_origin(origin: str) -> bool:
    """Return True when ``origin`` is an exact allowlisted Archipelago/Librarian origin."""
    if not isinstance(origin, str):
        return False
    cleaned = origin.strip()
    if not cleaned or cleaned == "*" or _CONTROL_CHAR_RE.search(cleaned):
        return False
    if os.getenv("VERCEL"):
        return cleaned in ALLOWED_ORIGINS
    return cleaned in ALLOWED_ORIGINS or bool(_LIBRARIAN_ORIGIN_RE.fullmatch(cleaned))


def is_safe_redirect_target(
    target: str | None,
    allowlisted_origins: tuple[str, ...] = (),
) -> bool:
    """Return True only for relative internal paths or exact allowlisted origins."""
    if not isinstance(target, str) or not target:
        return False
    if target != target.strip() or _CONTROL_CHAR_RE.search(target) or "\\" in target:
        return False
    parsed = urlsplit(target)
    if parsed.username or parsed.password:
        return False
    if target.startswith("/"):
        return not (
            target.startswith("//") or "://" in parsed.path or parsed.scheme or parsed.netloc
        )
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        origin = f"{parsed.scheme}://{parsed.netloc}"
        allowed = set(allowlisted_origins)
        if (
            origin in allowed
            and (not parsed.path or parsed.path.startswith("/"))
            and not parsed.path.startswith("//")
        ):
            return True
    return False


def safe_redirect_path(
    target: str | None,
    default: str = "/chat",
    allowlisted_origins: tuple[str, ...] = (),
) -> str:
    """Return ``target`` if safe for redirection, otherwise ``default``."""
    return target if is_safe_redirect_target(target, allowlisted_origins) else default


def _is_rejected_jwt_or_token(token: str) -> bool:
    """Reject malformed tokens, oversized tokens, or JWTs using alg=none / missing signatures."""
    if not token or len(token) > MAX_TOKEN_LENGTH or _CONTROL_OR_SPACE_RE.search(token):
        return True
    if token.startswith("eyJ") or token.count(".") >= 2:
        parts = token.split(".")
        if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2].strip():
            return True
        try:
            padded = parts[0] + "=" * (-len(parts[0]) % 4)
            header = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        except Exception:
            return True
        if not isinstance(header, dict):
            return True
        alg = str(header.get("alg") or "").strip().lower()
        if not alg or alg == "none":
            return True
    return False


def _is_expired_jwt(token: str) -> bool:
    """Use unsigned JWT claims only to reject an already expired token."""
    if token.count(".") != 2:
        return False
    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        expiry = claims.get("exp") if isinstance(claims, dict) else None
        return isinstance(expiry, (int, float)) and time.time() >= expiry
    except (ValueError, UnicodeError):
        return False


def _jwt_claims(token: str) -> dict:
    """Read untrusted claims for identifiers; callers must verify the token."""
    if token.count(".") != 2:
        return {}
    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        result = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        return result if isinstance(result, dict) else {}
    except (ValueError, UnicodeError):
        return {}


def _format_iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


DEFAULT_QUOTA_DB = (
    Path("/tmp/archipelago/query_quota.sqlite3")
    if os.environ.get("VERCEL")
    else Path(__file__).resolve().parent.parent / "cache" / "query_quota.sqlite3"
)


class AuthGuard:
    """Resolve the calling principal from a Supabase session or an open deployment."""

    def __init__(self) -> None:
        self._last_activity: dict[str, float] = {}
        self._session_started: dict[str, float] = {}
        self._principal_cache: dict[str, tuple[dict, float]] = {}
        self._expired: set[str] = set()
        self._lock = threading.Lock()

    @staticmethod
    def _idle_timeout_seconds() -> float:
        raw = os.getenv("ARCHIPELAGO_IDLE_TIMEOUT_SECONDS", "").strip()
        if raw:
            try:
                return max(1.0, float(raw))
            except ValueError:
                pass
        return float(IDLE_TIMEOUT_SECONDS)

    @staticmethod
    def _absolute_lifetime_seconds() -> float:
        raw = os.getenv("ARCHIPELAGO_SESSION_MAX_AGE_SECONDS", "").strip()
        if raw:
            try:
                return max(1.0, float(raw))
            except ValueError:
                pass
        return float(ABSOLUTE_SESSION_LIFETIME_SECONDS)

    @staticmethod
    def _is_background_poll() -> bool:
        """True when a request is passive status polling that must not reset idle expiry."""
        try:
            if request.headers.get("X-Background-Poll", "").strip().lower() in {"1", "true", "yes"}:
                return True
            if request.headers.get("X-Session-Passive", "").strip().lower() in {"1", "true", "yes"}:
                return True
            if request.args.get("poll", "").strip().lower() in {"1", "true", "yes"}:
                return True
        except RuntimeError:
            return False
        return False

    def csrf_token_for(self, token: str) -> str:
        """Derive a per-session CSRF token bound to ``token``."""
        if not token:
            return ""
        secret = os.getenv("ARCHIPELAGO_CSRF_SECRET", "").strip()
        if hosted_runtime() and not secret:
            raise RuntimeError("Shared CSRF secret is not configured")
        secret = secret or _PROCESS_CSRF_KEY
        return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_csrf_token(self, token: str, candidate: str) -> bool:
        """Constant-time verification of a session-bound CSRF token."""
        if not token or not candidate:
            return False
        expected = self.csrf_token_for(token)
        return hmac.compare_digest(expected, candidate.strip())

    def is_revoked(self, token: str) -> bool:
        """Return True if ``token`` has been logged out or invalidated."""
        if not token or _is_rejected_jwt_or_token(token) or _is_expired_jwt(token):
            return True
        if hosted_runtime():
            try:
                claims = _jwt_claims(token)
                user_id = str(claims.get("sub") or "")
                ids = verified_session_ids(token, user_id)
                if ids is None:
                    return True
                result = session_action(
                    "check",
                    *ids,
                    idle_seconds=int(self._idle_timeout_seconds()),
                    max_age_seconds=int(self._absolute_lifetime_seconds()),
                    passive=True,
                )
                return result["status"] != "active"
            except RuntimeError:
                return True
        token_id = hashlib.sha256(token.encode()).hexdigest()
        scope = _runtime_scope()
        with self._lock, _SHARED_LOCK:
            return token_id in self._expired or token_id in _SHARED_REVOKED_BY_SCOPE[scope]

    def rotate_session(self, token: str, previous_token: str = "") -> str:
        """Rotate session tracking on login or privilege change and return a CSRF token."""
        if hosted_runtime():
            if not token:
                return ""
            # principal() has verified and registered the new token first.
            if previous_token and previous_token != token:
                current_id = _jwt_claims(token).get("session_id")
                previous_id = _jwt_claims(previous_token).get("session_id")
                if current_id != previous_id:
                    self.end_session(previous_token)
            return self.csrf_token_for(token)
        if previous_token and previous_token != token:
            self.end_session(previous_token)
        if not token:
            return ""
        token_id = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        scope = _runtime_scope()
        with self._lock, _SHARED_LOCK:
            self._expired.discard(token_id)
            _SHARED_REVOKED_BY_SCOPE[scope].discard(token_id)
            self._session_started[token_id] = now
            self._last_activity[token_id] = now
        return self.csrf_token_for(token)

    def end_session(self, token: str) -> None:
        """Invalidate the current bearer token locally and across instances after logout."""
        if token:
            token_id = hashlib.sha256(token.encode()).hexdigest()
            with self._lock:
                self._principal_cache.pop(token_id, None)
            if hosted_runtime():
                url, key = self.supabase()
                try:
                    verified = requests.get(
                        f"{url}/auth/v1/user",
                        headers={"apikey": key, "Authorization": f"Bearer {token}"},
                        timeout=SUPABASE_USER_TIMEOUT_SEC,
                    )
                    if verified.status_code != 200:
                        return
                    user_id = str(verified.json().get("id") or "")
                    ids = verified_session_ids(token, user_id)
                    if ids is None:
                        return
                    session_action(
                        "revoke",
                        *ids,
                        idle_seconds=int(self._idle_timeout_seconds()),
                        max_age_seconds=int(self._absolute_lifetime_seconds()),
                    )
                except (requests.RequestException, ValueError) as exc:
                    raise RuntimeError("Durable session revocation unavailable") from exc
                return
            token_id = hashlib.sha256(token.encode()).hexdigest()
            scope = _runtime_scope()
            with self._lock, _SHARED_LOCK:
                self._last_activity.pop(token_id, None)
                self._session_started.pop(token_id, None)
                self._principal_cache.pop(token_id, None)
                self._expired.add(token_id)
                _SHARED_REVOKED_BY_SCOPE[scope].add(token_id)
                if len(self._expired) > MAX_TRACKED_SESSIONS:
                    self._expired.clear()
                    self._expired.add(token_id)

    def issue_handoff_ticket(
        self,
        principal: dict,
        target_origin: str,
        nonce: str = "",
    ) -> tuple[dict | None, str | None]:
        """Issue a single-use, short-lived, origin-bound handoff ticket (never carrying refresh_token)."""
        if not principal or not principal.get("id") or not principal.get("token"):
            return None, "An authenticated session is required."
        if principal.get("role") not in ELEVATED_ROLES:
            return None, "A staff account is required for session handoff."
        cleaned_origin = (target_origin or "").strip().rstrip("/")
        if not is_allowed_handoff_origin(cleaned_origin):
            return None, "Target origin is not permitted for session handoff."
        cleaned_nonce = (nonce or "").strip()[:128]
        if _CONTROL_CHAR_RE.search(cleaned_nonce):
            return None, "Invalid handoff nonce."
        raw_ticket = secrets.token_urlsafe(32)
        ticket_id = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
        now = time.monotonic()
        expires_at = now + float(HANDOFF_TICKET_TTL_SECONDS)
        scope = _runtime_scope()
        with _SHARED_LOCK:
            store = _SHARED_TICKETS_BY_SCOPE[scope]
            expired_keys = [k for k, v in store.items() if now >= v["expires_at"] or v["used"]]
            for k in expired_keys:
                store.pop(k, None)
            store[ticket_id] = {
                "id": str(principal["id"]),
                "role": str(principal["role"]),
                "username": str(principal.get("username") or ""),
                "token": str(principal["token"]),
                "target_origin": cleaned_origin,
                "nonce": cleaned_nonce,
                "expires_at": expires_at,
                "used": False,
            }
        return {
            "ticket": raw_ticket,
            "target_origin": cleaned_origin,
            "expires_in": HANDOFF_TICKET_TTL_SECONDS,
            "nonce": cleaned_nonce,
        }, None

    def redeem_handoff_ticket(
        self,
        ticket: str,
        origin: str = "",
        nonce: str = "",
    ) -> tuple[dict | None, str | None]:
        """Atomically redeem a single-use handoff ticket once for its bound origin."""
        cleaned_ticket = (ticket or "").strip()
        if (
            not cleaned_ticket
            or len(cleaned_ticket) > 256
            or _CONTROL_OR_SPACE_RE.search(cleaned_ticket)
        ):
            return None, "Handoff ticket is invalid, expired, or already used."
        ticket_id = hashlib.sha256(cleaned_ticket.encode("utf-8")).hexdigest()
        now = time.monotonic()
        scope = _runtime_scope()
        with _SHARED_LOCK:
            store = _SHARED_TICKETS_BY_SCOPE[scope]
            entry = store.pop(ticket_id, None)
        if entry is None or entry.get("used") or now >= entry.get("expires_at", 0.0):
            return None, "Handoff ticket is invalid, expired, or already used."
        entry["used"] = True
        cleaned_origin = (origin or "").strip().rstrip("/")
        if not cleaned_origin or cleaned_origin != entry["target_origin"]:
            return None, "Handoff ticket origin mismatch."
        expected_nonce = entry.get("nonce") or ""
        cleaned_nonce = (nonce or "").strip()
        if expected_nonce and cleaned_nonce != expected_nonce:
            return None, "Handoff ticket nonce mismatch."
        if self.is_revoked(entry["token"]):
            return None, "The underlying session has been logged out."
        token_id = hashlib.sha256(entry["token"].encode()).hexdigest()
        principal = {
            "id": entry["id"],
            "role": entry["role"],
            "username": entry["username"],
            "token": entry["token"],
            "target_origin": entry["target_origin"],
            "nonce": expected_nonce,
        }
        with self._lock:
            self._session_started[token_id] = now
            self._last_activity[token_id] = now
            self._principal_cache[token_id] = (dict(principal), now)
        return principal, None

    def required(self) -> bool:
        """True when a verified Supabase session is mandatory."""
        raw = os.getenv("ARCHIPELAGO_AUTH_REQUIRED", "").strip().lower()
        if raw in {"0", "false", "no"}:
            return False
        if raw in {"1", "true", "yes"}:
            return True
        return True

    def supabase(self) -> tuple[str, str]:
        """Return ``(url, publishable_key)`` for Supabase, either possibly empty."""
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        return url, key

    def _bearer_token(self) -> str:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header.removeprefix("Bearer ").strip()
        return request.cookies.get("archipelago_token", "").strip()

    def _hosted_principal(self, token: str, url: str, key: str) -> tuple[dict | None, str | None]:
        """Verify identity and atomically check shared session state on every request."""
        operation = (
            "register"
            if request.path == "/api/auth/session" and request.method == "POST"
            else "check"
        )
        token_id = hashlib.sha256(token.encode()).hexdigest()
        now_mono = time.monotonic()
        cached_entry: dict | None = None
        if operation != "register":
            with self._lock:
                entry = self._principal_cache.get(token_id)
                if entry is not None and (now_mono - entry[1]) < PRINCIPAL_CACHE_TTL_SECONDS:
                    cached_entry = dict(entry[0])

        if cached_entry is not None and cached_entry.get("session_id"):
            ids = (str(cached_entry["session_id"]), str(cached_entry["id"]))
            user_id = str(cached_entry["id"])
            role = str(cached_entry["role"])
            username = str(cached_entry.get("username") or "")
        else:
            headers = {"apikey": key, "Authorization": f"Bearer {token}"}
            try:
                user_response = requests.get(
                    f"{url}/auth/v1/user", headers=headers, timeout=SUPABASE_USER_TIMEOUT_SEC
                )
                if user_response.status_code != 200:
                    return None, "Your Supabase session could not be verified."
                user_payload = user_response.json()
                user_id = str(user_payload.get("id") or "") if isinstance(user_payload, dict) else ""
                ids = verified_session_ids(token, user_id)
                if ids is None:
                    return None, "Your Supabase session could not be verified."
                profile_response = requests.get(
                    f"{url}/rest/v1/profiles",
                    params={"select": "username,role", "id": f"eq.{user_id}"},
                    headers=headers,
                    timeout=SUPABASE_PROFILE_TIMEOUT_SEC,
                )
                if profile_response.status_code != 200:
                    return None, "Supabase identity verification is unavailable."
                profiles = profile_response.json()
            except (requests.RequestException, ValueError):
                return None, "Supabase identity verification is unavailable."
            if (
                not isinstance(profiles, list)
                or len(profiles) != 1
                or not isinstance(profiles[0], dict)
            ):
                return None, "Your account does not have an assigned Archipelago role."
            role = str(profiles[0].get("role") or "")
            if role not in AUTH_ROLES:
                return None, "Your account role is not permitted in Archipelago."
            username = str(profiles[0].get("username") or "")
            with self._lock:
                if len(self._principal_cache) >= MAX_TRACKED_SESSIONS:
                    self._principal_cache.clear()
                self._principal_cache[token_id] = (
                    {
                        "id": user_id,
                        "role": role,
                        "username": username,
                        "session_id": ids[0],
                    },
                    now_mono,
                )
        try:
            result = session_action(
                operation,
                *ids,
                idle_seconds=int(self._idle_timeout_seconds()),
                max_age_seconds=int(self._absolute_lifetime_seconds()),
                passive=self._is_background_poll(),
            )
        except RuntimeError:
            return None, "Durable session verification is unavailable."
        status = result["status"]
        if status != "active":
            with self._lock:
                self._principal_cache.pop(token_id, None)
            messages = {
                "idle_expired": "This session expired after inactivity. Sign in again.",
                "absolute_expired": "This session reached its maximum lifetime. Sign in again.",
                "revoked_credentials": "This session has been revoked. Sign in again.",
                "missing_session": "A Supabase session is required.",
            }
            return None, messages[status]
        return {
            "id": user_id,
            "role": role,
            "username": username,
            "token": token,
        }, None

    def principal(self) -> tuple[dict | None, str | None]:
        """Return ``(principal, error)`` and record measured ``auth_ms`` on the request."""
        t_auth_start = time.perf_counter()
        try:
            return self._resolve_principal()
        finally:
            try:
                request.archipelago_auth_ms = round(  # type: ignore[attr-defined]
                    (time.perf_counter() - t_auth_start) * 1000, 1
                )
            except RuntimeError:
                pass

    def _resolve_principal(self) -> tuple[dict | None, str | None]:
        """Resolve the calling principal from Supabase or guest mode."""
        if not self.required():
            return {"role": "student", "username": "guest", "token": ""}, None
        url, key = self.supabase()
        if not url or not key:
            return None, "Supabase Auth is not configured."
        token = self._bearer_token()
        if not token:
            return None, "A Supabase session is required."
        if _is_rejected_jwt_or_token(token):
            return None, "Your Supabase session could not be verified."
        if _is_expired_jwt(token):
            return None, "Your JWT token expired. Sign in again."
        if hosted_runtime():
            return self._hosted_principal(token, url, key)
        token_id = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        idle_timeout = self._idle_timeout_seconds()
        absolute_lifetime = self._absolute_lifetime_seconds()
        is_poll = self._is_background_poll()
        scope = _runtime_scope()
        with self._lock, _SHARED_LOCK:
            last_active = self._last_activity.get(token_id)
            started_at = self._session_started.get(token_id)
            is_revoked = token_id in self._expired or token_id in _SHARED_REVOKED_BY_SCOPE[scope]
            idle_expired = last_active is not None and (now - last_active) >= idle_timeout
            abs_expired = started_at is not None and (now - started_at) >= absolute_lifetime
            if is_revoked or idle_expired or abs_expired:
                self._expired.add(token_id)
                self._last_activity.pop(token_id, None)
                self._session_started.pop(token_id, None)
                self._principal_cache.pop(token_id, None)
                if is_revoked:
                    return None, "This session has been revoked. Sign in again."
                if abs_expired:
                    return None, "This session reached its maximum lifetime. Sign in again."
                return None, "This session expired after inactivity. Sign in again."
            cached = self._principal_cache.get(token_id)
            if cached is not None and (now - cached[1]) < PRINCIPAL_CACHE_TTL_SECONDS:
                if not is_poll or token_id not in self._last_activity:
                    self._last_activity[token_id] = now
                return dict(cached[0]), None
        headers = {"apikey": key, "Authorization": f"Bearer {token}"}
        try:
            user_response = requests.get(
                f"{url}/auth/v1/user", headers=headers, timeout=SUPABASE_USER_TIMEOUT_SEC
            )
            user_payload = user_response.json() if user_response.status_code == 200 else {}
            if not isinstance(user_payload, dict):
                user_payload = {}
            user_id = str(user_payload.get("id") or "").strip()
            profile_response = (
                requests.get(
                    f"{url}/rest/v1/profiles",
                    params={
                        "select": "username,role",
                        "id": f"eq.{user_id}",
                    },
                    headers=headers,
                    timeout=SUPABASE_PROFILE_TIMEOUT_SEC,
                )
                if user_response.status_code == 200 and _USER_ID_RE.fullmatch(user_id)
                else None
            )
        except (requests.RequestException, ValueError):
            return None, "Supabase identity verification is unavailable."
        if (
            user_response.status_code != 200
            or profile_response is None
            or profile_response.status_code != 200
        ):
            return None, "Your Supabase session could not be verified."
        try:
            profiles = profile_response.json()
        except ValueError:
            return None, "Your Supabase session could not be verified."
        if (
            not isinstance(profiles, list)
            or len(profiles) != 1
            or not isinstance(profiles[0], dict)
        ):
            return None, "Your account does not have an assigned Archipelago role."
        role = str(profiles[0].get("role") or "")
        if role not in AUTH_ROLES:
            return None, "Your account role is not permitted in Archipelago."
        principal = {
            "id": user_id,
            "role": role,
            "username": profiles[0].get("username") or "",
            "token": token,
        }
        if not principal["id"]:
            return None, "Your account identity is incomplete."
        with self._lock:
            if len(self._principal_cache) >= MAX_TRACKED_SESSIONS:
                self._principal_cache.clear()
                self._last_activity.clear()
                self._session_started.clear()
            prev = self._principal_cache.get(token_id)
            if prev is not None and prev[0].get("role") != role:
                self._session_started[token_id] = now
            else:
                self._session_started.setdefault(token_id, now)
            if not is_poll or token_id not in self._last_activity:
                self._last_activity[token_id] = now
            self._principal_cache[token_id] = (dict(principal), now)
        return principal, None


class RateLimiter:
    """Sliding-window per-client-IP limiter with separate chat and API buckets."""

    def __init__(self) -> None:
        self._chat: dict[str, deque] = defaultdict(deque)
        self._api: dict[str, deque] = defaultdict(deque)
        self._auth: dict[str, deque] = defaultdict(deque)
        self._chat_last_mutation: dict[str, float] = {}
        self._api_last_mutation: dict[str, float] = {}
        self._auth_last_mutation: dict[str, float] = {}
        self._bucket_lock = threading.Lock()
        self._daily_lock = threading.Lock()
        self._quota_db = Path(os.getenv("ARCHIPELAGO_QUOTA_DB", str(DEFAULT_QUOTA_DB)))

    def _quota_connection(self) -> sqlite3.Connection:
        self._quota_db.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._quota_db, timeout=5, isolation_level=None)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS quota "
            "(user_id TEXT PRIMARY KEY, day_start REAL NOT NULL, "
            "used INTEGER NOT NULL, cooldown_until REAL NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS quota_events "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, created_at REAL NOT NULL)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS quota_events_user_created_idx "
            "ON quota_events (user_id, created_at)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS completed_quiz "
            "(user_id TEXT NOT NULL, target TEXT NOT NULL, result TEXT NOT NULL, "
            "PRIMARY KEY (user_id, target))"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS ai_request "
            "(user_id TEXT NOT NULL, request_id TEXT NOT NULL, "
            "PRIMARY KEY (user_id, request_id))"
        )
        return connection

    def completed_quiz(self, user_id: str, target: str) -> dict | None:
        """Return this account's first completed diagnostic, if present."""
        if hosted_runtime():
            return runtime_rpc(
                "archipelago_runtime_quiz_result",
                {"p_user_id": user_id, "p_target": target},
            )
        with closing(self._quota_connection()) as connection:
            row = connection.execute(
                "SELECT result FROM completed_quiz WHERE user_id = ? AND target = ?",
                (user_id, target),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_completed_quiz(self, user_id: str, target: str, result: dict) -> None:
        """Persist the first result so repeated starts cannot issue a new quiz."""
        if hosted_runtime():
            runtime_rpc(
                "archipelago_runtime_quiz_result",
                {"p_user_id": user_id, "p_target": target, "p_result": result},
            )
            return
        with closing(self._quota_connection()) as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO completed_quiz (user_id, target, result) VALUES (?, ?, ?)",
                (user_id, target, json.dumps(result)),
            )

    def check_daily_chat(self, user_id: str, request_id: str = "") -> tuple[bool, dict]:
        """Count accepted chat queries per student in a rolling 3600-second window."""
        if hosted_runtime():
            quota = runtime_rpc(
                "archipelago_runtime_consume" if request_id else "archipelago_runtime_query",
                {"p_user_id": user_id, "p_request_id": request_id}
                if request_id
                else {"p_user_id": user_id, "p_consume": True},
            )
            return bool(quota["limited"]), quota
        now = time.time()
        window_start = now - QUERY_WINDOW_SECONDS
        with self._daily_lock, closing(self._quota_connection()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT COUNT(*), MIN(created_at) FROM quota_events "
                "WHERE user_id = ? AND created_at > ?",
                (user_id, window_start),
            ).fetchone()
            used = int(row[0] or 0)
            oldest_at = float(row[1]) if row[1] is not None else None

            if (
                request_id
                and connection.execute(
                    "SELECT 1 FROM ai_request WHERE user_id = ? AND request_id = ?",
                    (user_id, request_id),
                ).fetchone()
            ):
                limited_now = used >= HOURLY_QUERY_LIMIT
                reset_ts = (oldest_at + QUERY_WINDOW_SECONDS) if oldest_at is not None else None
                retry_after = (
                    max(1, math.ceil(reset_ts - now)) if limited_now and reset_ts is not None else 0
                )
                return True, {
                    "limited": True,
                    "limit_reason": "duplicate",
                    "limit": HOURLY_QUERY_LIMIT,
                    "window_seconds": QUERY_WINDOW_SECONDS,
                    "used": used,
                    "remaining": max(0, HOURLY_QUERY_LIMIT - used),
                    "retry_after": retry_after,
                    "reset_at": _format_iso_utc(reset_ts) if reset_ts is not None else None,
                }

            if used >= HOURLY_QUERY_LIMIT and oldest_at is not None:
                reset_ts = oldest_at + QUERY_WINDOW_SECONDS
                retry_after = max(1, math.ceil(reset_ts - now))
                return True, {
                    "limited": True,
                    "limit_reason": "hourly_limit",
                    "limit": HOURLY_QUERY_LIMIT,
                    "window_seconds": QUERY_WINDOW_SECONDS,
                    "used": used,
                    "remaining": 0,
                    "retry_after": retry_after,
                    "reset_at": _format_iso_utc(reset_ts),
                }

            if request_id:
                connection.execute(
                    "INSERT INTO ai_request (user_id, request_id) VALUES (?, ?)",
                    (user_id, request_id),
                )
            connection.execute(
                "INSERT INTO quota_events (user_id, created_at) VALUES (?, ?)",
                (user_id, now),
            )
            used += 1
            if oldest_at is None:
                oldest_at = now
            reset_ts = oldest_at + QUERY_WINDOW_SECONDS
            return False, {
                "limited": False,
                "limit": HOURLY_QUERY_LIMIT,
                "window_seconds": QUERY_WINDOW_SECONDS,
                "used": used,
                "remaining": max(0, HOURLY_QUERY_LIMIT - used),
                "retry_after": 0,
                "reset_at": _format_iso_utc(reset_ts),
            }

    def quota_status(self, user_id: str) -> dict:
        """Read this account's rolling-hour query count without consuming a request."""
        if hosted_runtime():
            return runtime_rpc(
                "archipelago_runtime_query",
                {"p_user_id": user_id, "p_consume": False},
            )
        now = time.time()
        window_start = now - QUERY_WINDOW_SECONDS
        with closing(self._quota_connection()) as connection:
            row = connection.execute(
                "SELECT COUNT(*), MIN(created_at) FROM quota_events "
                "WHERE user_id = ? AND created_at > ?",
                (user_id, window_start),
            ).fetchone()
        used = int(row[0] or 0)
        oldest_at = float(row[1]) if row[1] is not None else None
        if used >= HOURLY_QUERY_LIMIT and oldest_at is not None:
            reset_ts = oldest_at + QUERY_WINDOW_SECONDS
            retry_after = max(1, math.ceil(reset_ts - now))
            return {
                "limited": True,
                "limit": HOURLY_QUERY_LIMIT,
                "window_seconds": QUERY_WINDOW_SECONDS,
                "used": used,
                "remaining": 0,
                "retry_after": retry_after,
                "reset_at": _format_iso_utc(reset_ts),
            }
        reset_at = (
            _format_iso_utc(oldest_at + QUERY_WINDOW_SECONDS) if oldest_at is not None else None
        )
        return {
            "limited": False,
            "limit": HOURLY_QUERY_LIMIT,
            "window_seconds": QUERY_WINDOW_SECONDS,
            "used": used,
            "remaining": max(0, HOURLY_QUERY_LIMIT - used),
            "retry_after": 0,
            "reset_at": reset_at,
        }

    @staticmethod
    def client_ip() -> str:
        """Extract the client IP without trusting client-spoofable forwarding headers."""
        trust_proxy = (
            bool(os.environ.get("VERCEL")) or os.environ.get("ARCHIPELAGO_TRUST_PROXY") == "1"
        )
        if trust_proxy:
            for header in CLIENT_IP_HEADERS:
                value = request.headers.get(header)
                if value and value.strip():
                    return value.strip().split(",")[-1].strip()
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded and forwarded.strip():
                return forwarded.strip().split(",")[-1].strip()
        return request.remote_addr or "127.0.0.1"

    @staticmethod
    def _check_key(
        key: str,
        bucket_map: dict[str, deque],
        last_mutation_map: dict[str, float],
        max_per_min: int,
        min_gap_sec: float,
        enforce_min_gap: bool = True,
    ) -> tuple[bool, int]:
        now = time.time()
        if len(bucket_map) > MAX_TRACKED_BUCKETS and key not in bucket_map:
            bucket_map.clear()
            last_mutation_map.clear()
        bucket = bucket_map[key]
        if not bucket:
            last_mutation_map.pop(key, None)
        while bucket and now - bucket[0] > RATE_WINDOW_SEC:
            bucket.popleft()
        last_mutation = last_mutation_map.get(key)
        if enforce_min_gap and last_mutation is not None and now - last_mutation < min_gap_sec:
            return True, 1
        if len(bucket) >= max_per_min:
            return True, max(1, int(RATE_WINDOW_SEC - (now - bucket[0])))
        bucket.append(now)
        if enforce_min_gap:
            last_mutation_map[key] = now
        return False, 0

    @staticmethod
    def _check(
        bucket_map: dict[str, deque],
        last_mutation_map: dict[str, float],
        max_per_min: int,
        min_gap_sec: float,
        enforce_min_gap: bool = True,
    ) -> tuple[bool, int]:
        ip = RateLimiter.client_ip()
        limited, retry_after = RateLimiter._check_key(
            ip,
            bucket_map,
            last_mutation_map,
            max_per_min,
            min_gap_sec,
            enforce_min_gap,
        )
        if limited:
            return True, retry_after
        principal = getattr(request, "archipelago_principal", None)
        user_id = str(principal.get("id") or "").strip() if isinstance(principal, dict) else ""
        if user_id and user_id != "guest":
            acct_limited, acct_retry = RateLimiter._check_key(
                f"acct:{user_id}",
                bucket_map,
                last_mutation_map,
                max_per_min,
                min_gap_sec,
                False,
            )
            if acct_limited:
                return True, acct_retry
        return False, 0

    @staticmethod
    def _is_state_changing() -> bool:
        """True for methods whose burst rate is worth policing."""
        return request.method not in SAFE_METHODS

    def check_chat(self) -> tuple[bool, int]:
        """Check the strict chat bucket (burst-gated on state-changing calls)."""
        with self._bucket_lock:
            return self._check(
                self._chat,
                self._chat_last_mutation,
                CHAT_RATE_MAX_PER_MIN,
                CHAT_RATE_MIN_GAP_SEC,
                self._is_state_changing(),
            )

    def check_api(self) -> tuple[bool, int]:
        """Check the general API bucket (burst-gated on state-changing calls)."""
        with self._bucket_lock:
            return self._check(
                self._api,
                self._api_last_mutation,
                API_RATE_MAX_PER_MIN,
                API_RATE_MIN_GAP_SEC,
                self._is_state_changing(),
            )

    def check_auth(self) -> tuple[bool, int]:
        """Check the authentication mutation bucket to throttle credential/token abuse."""
        with self._bucket_lock:
            return self._check(
                self._auth,
                self._auth_last_mutation,
                AUTH_RATE_MAX_PER_MIN,
                AUTH_RATE_MIN_GAP_SEC,
                self._is_state_changing(),
            )
