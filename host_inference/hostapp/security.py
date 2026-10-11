"""Authentication, authorisation and rate limiting for the hosted app.

One concern: deciding who the caller is and whether they may proceed.  Route
modules call ``ctx.auth`` and ``ctx.limiter`` instead of reaching for module
globals, which keeps them testable without patching imports.
"""

from __future__ import annotations

from collections import defaultdict, deque
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time

from flask import request
import requests

from .config import (
    API_RATE_MAX_PER_MIN,
    API_RATE_MIN_GAP_SEC,
    AUTH_ROLES,
    CHAT_RATE_MAX_PER_MIN,
    CHAT_RATE_MIN_GAP_SEC,
    RATE_WINDOW_SEC,
)

SUPABASE_USER_TIMEOUT_SEC = 10
SUPABASE_PROFILE_TIMEOUT_SEC = 8
# Client IP headers set by the CDN / proxy in front of the app, most specific first.
CLIENT_IP_HEADERS = ("CF-Connecting-IP", "Fly-Client-IP", "X-Real-IP")
# The burst min-gap guards state-changing calls.  Idempotent reads must never be
# rejected on timing alone: a reader opening two exact book links, or a page
# firing several API calls in parallel, is normal browsing, not abuse.  The
# per-minute ceiling still applies to every method.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
IDLE_TIMEOUT_SECONDS = 300
DAILY_QUERY_LIMIT = 35
QUERY_COOLDOWN_AFTER = 7
QUERY_COOLDOWN_SECONDS = 3600
QUERY_DAY_SECONDS = 86400
DEFAULT_QUOTA_DB = (
    Path(tempfile.gettempdir()) / "archipelago-cache" / "query_quota.sqlite3"
    if os.environ.get("VERCEL")
    else Path(__file__).resolve().parent.parent / "cache" / "query_quota.sqlite3"
)
RUNTIME_RPC_TIMEOUT_SEC = 10


def _runtime_rpc(name: str, payload: dict) -> object:
    """Call a service-only Supabase RPC for durable serverless state."""
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("Supabase runtime state is not configured.")
    response = requests.post(
        f"{url}/rest/v1/rpc/{name}",
        json=payload,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=RUNTIME_RPC_TIMEOUT_SEC,
    )
    response.raise_for_status()
    return response.json()


class AuthGuard:
    """Resolve the calling principal from a Supabase session or an open deployment."""

    def __init__(self) -> None:
        self._last_activity: dict[str, float] = {}
        self._expired: set[str] = set()
        self._lock = threading.Lock()

    def end_session(self, token: str) -> None:
        """Invalidate the current bearer token locally after logout."""
        if token:
            token_id = hashlib.sha256(token.encode()).hexdigest()
            if os.environ.get("VERCEL"):
                _runtime_rpc("archipelago_runtime_touch_session", {"p_token_id": token_id, "p_end": True})
            with self._lock:
                self._last_activity.pop(token_id, None)
                self._expired.add(token_id)

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

    def principal(self) -> tuple[dict | None, str | None]:
        """Return ``(principal, error)``.

        With auth disabled every caller is a read-only guest.  With auth enabled
        the bearer token or session cookie must resolve to a permitted role.
        """
        if not self.required():
            return {"role": "student", "username": "guest", "token": ""}, None
        url, key = self.supabase()
        if not url or not key:
            return None, "Supabase Auth is not configured."
        token = self._bearer_token()
        if not token:
            return None, "A Supabase session is required."
        token_id = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        if os.environ.get("VERCEL"):
            try:
                active = _runtime_rpc("archipelago_runtime_touch_session", {"p_token_id": token_id})
            except (RuntimeError, requests.RequestException, ValueError):
                return None, "Session verification is temporarily unavailable."
            if active is not True:
                return None, "Your session timed out after five minutes of inactivity. Sign in again."
        if not os.environ.get("VERCEL"):
            with self._lock:
                last_active = self._last_activity.get(token_id)
                if token_id in self._expired or (
                    last_active is not None and now - last_active >= IDLE_TIMEOUT_SECONDS
                ):
                    self._expired.add(token_id)
                    self._last_activity.pop(token_id, None)
                    return (
                        None,
                        "Your session timed out after five minutes of inactivity. Sign in again.",
                    )
        headers = {"apikey": key, "Authorization": f"Bearer {token}"}
        try:
            user_response = requests.get(
                f"{url}/auth/v1/user", headers=headers, timeout=SUPABASE_USER_TIMEOUT_SEC
            )
            profile_response = (
                requests.get(
                    f"{url}/rest/v1/profiles",
                    params={
                        "select": "username,role",
                        "id": f"eq.{user_response.json().get('id', '')}",
                    },
                    headers=headers,
                    timeout=SUPABASE_PROFILE_TIMEOUT_SEC,
                )
                if user_response.status_code == 200
                else None
            )
        except requests.RequestException:
            return None, "Supabase identity verification is unavailable."
        if (
            user_response.status_code != 200
            or profile_response is None
            or profile_response.status_code != 200
        ):
            return None, "Your Supabase session could not be verified."
        profiles = profile_response.json()
        if not isinstance(profiles, list) or len(profiles) != 1:
            return None, "Your account does not have an assigned Archipelago role."
        role = str(profiles[0].get("role") or "")
        if role not in AUTH_ROLES:
            return None, "Your account role is not permitted in Archipelago."
        principal = {
            "id": str(user_response.json().get("id") or ""),
            "role": role,
            "username": profiles[0].get("username") or "",
            "token": token,
        }
        if not principal["id"]:
            return None, "Your account identity is incomplete."
        with self._lock:
            self._last_activity[token_id] = now
        return principal, None


class RateLimiter:
    """Sliding-window per-client-IP limiter with separate chat and API buckets."""

    def __init__(self) -> None:
        self._chat: dict[str, deque] = defaultdict(deque)
        self._api: dict[str, deque] = defaultdict(deque)
        self._chat_last_mutation: dict[str, float] = {}
        self._api_last_mutation: dict[str, float] = {}
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
            "CREATE TABLE IF NOT EXISTS completed_quiz "
            "(user_id TEXT NOT NULL, target TEXT NOT NULL, result TEXT NOT NULL, "
            "PRIMARY KEY (user_id, target))"
        )
        return connection

    def completed_quiz(self, user_id: str, target: str) -> dict | None:
        """Return this account's first completed diagnostic, if present."""
        if os.environ.get("VERCEL"):
            result = _runtime_rpc("archipelago_runtime_quiz_result", {
                "p_user_id": user_id, "p_target": target,
            })
            return result if isinstance(result, dict) else None
        with closing(self._quota_connection()) as connection:
            row = connection.execute(
                "SELECT result FROM completed_quiz WHERE user_id = ? AND target = ?",
                (user_id, target),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_completed_quiz(self, user_id: str, target: str, result: dict) -> None:
        """Persist the first result so repeated starts cannot issue a new quiz."""
        if os.environ.get("VERCEL"):
            _runtime_rpc("archipelago_runtime_quiz_result", {
                "p_user_id": user_id, "p_target": target, "p_result": result,
            })
            return
        with closing(self._quota_connection()) as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO completed_quiz (user_id, target, result) VALUES (?, ?, ?)",
                (user_id, target, json.dumps(result)),
            )

    def check_daily_chat(self, user_id: str) -> tuple[bool, dict]:
        """Count accepted AI queries per account and enforce hourly pauses."""
        if os.environ.get("VERCEL"):
            result = _runtime_rpc("archipelago_runtime_query", {
                "p_user_id": user_id, "p_consume": True,
            })
            if not isinstance(result, dict):
                raise RuntimeError("Invalid query quota response.")
            return bool(result.get("limited")), result
        now = time.time()
        with self._daily_lock, closing(self._quota_connection()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT day_start, used, cooldown_until FROM quota WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            start, count, cooldown = row if row else (now, 0, 0.0)
            if now - start >= QUERY_DAY_SECONDS:
                start, count, cooldown = now, 0, 0.0
            if count >= DAILY_QUERY_LIMIT:
                return True, {
                    "remaining": 0,
                    "retry_after": int(start + QUERY_DAY_SECONDS - now) + 1,
                }
            if cooldown > now:
                return True, {
                    "remaining": DAILY_QUERY_LIMIT - count,
                    "retry_after": int(cooldown - now) + 1,
                }
            count += 1
            cooldown = now + QUERY_COOLDOWN_SECONDS if count % QUERY_COOLDOWN_AFTER == 0 else 0.0
            connection.execute(
                "INSERT INTO quota (user_id, day_start, used, cooldown_until) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
                "day_start=excluded.day_start, used=excluded.used, "
                "cooldown_until=excluded.cooldown_until",
                (user_id, start, count, cooldown),
            )
            return False, {
                "remaining": DAILY_QUERY_LIMIT - count,
                "used": count,
                "cooldown_after_this_query": cooldown > now,
            }

    def quota_status(self, user_id: str) -> dict:
        """Read this account's query count without consuming a request."""
        if os.environ.get("VERCEL"):
            result = _runtime_rpc("archipelago_runtime_query", {"p_user_id": user_id})
            if not isinstance(result, dict):
                raise RuntimeError("Invalid query quota response.")
            return result
        now = time.time()
        with closing(self._quota_connection()) as connection:
            row = connection.execute(
                "SELECT day_start, used, cooldown_until FROM quota WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row or now - row[0] >= QUERY_DAY_SECONDS:
            return {"used": 0, "remaining": DAILY_QUERY_LIMIT, "retry_after": 0}
        start, used, cooldown = row
        retry = int(cooldown - now) + 1 if cooldown > now else 0
        if used >= DAILY_QUERY_LIMIT:
            retry = int(start + QUERY_DAY_SECONDS - now) + 1
        return {"used": used, "remaining": DAILY_QUERY_LIMIT - used, "retry_after": retry}

    @staticmethod
    def client_ip() -> str:
        """Extract the client IP behind reverse proxies and CDNs."""
        for header in CLIENT_IP_HEADERS:
            value = request.headers.get(header)
            if value and value.strip():
                return value.strip().split(",")[0].strip()
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded and forwarded.strip():
            return forwarded.strip().split(",")[0].strip()
        return request.remote_addr or "127.0.0.1"

    @staticmethod
    def _check(
        bucket_map: dict[str, deque],
        last_mutation_map: dict[str, float],
        max_per_min: int,
        min_gap_sec: float,
        enforce_min_gap: bool = True,
    ) -> tuple[bool, int]:
        ip = RateLimiter.client_ip()
        now = time.time()
        bucket = bucket_map[ip]
        while bucket and now - bucket[0] > RATE_WINDOW_SEC:
            bucket.popleft()
        last_mutation = last_mutation_map.get(ip)
        if enforce_min_gap and last_mutation is not None and now - last_mutation < min_gap_sec:
            return True, 1
        if len(bucket) >= max_per_min:
            return True, max(1, int(RATE_WINDOW_SEC - (now - bucket[0])))
        bucket.append(now)
        if enforce_min_gap:
            last_mutation_map[ip] = now
        return False, 0

    @staticmethod
    def _is_state_changing() -> bool:
        """True for methods whose burst rate is worth policing."""
        return request.method not in SAFE_METHODS

    def check_chat(self) -> tuple[bool, int]:
        """Check the strict chat bucket (burst-gated on state-changing calls)."""
        return self._check(
            self._chat,
            self._chat_last_mutation,
            CHAT_RATE_MAX_PER_MIN,
            CHAT_RATE_MIN_GAP_SEC,
            self._is_state_changing(),
        )

    def check_api(self) -> tuple[bool, int]:
        """Check the general API bucket (burst-gated on state-changing calls)."""
        return self._check(
            self._api,
            self._api_last_mutation,
            API_RATE_MAX_PER_MIN,
            API_RATE_MIN_GAP_SEC,
            self._is_state_changing(),
        )
