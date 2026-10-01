"""Authentication, authorisation and rate limiting for the hosted app.

One concern: deciding who the caller is and whether they may proceed.  Route
modules call ``ctx.auth`` and ``ctx.limiter`` instead of reaching for module
globals, which keeps them testable without patching imports.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

import requests
from flask import request

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


class AuthGuard:
    """Resolve the calling principal from a Supabase session or an open deployment."""

    def required(self) -> bool:
        """True when a verified Supabase session is mandatory."""
        raw = os.getenv("ARCHIPELAGO_AUTH_REQUIRED", "").strip().lower()
        if raw in {"0", "false", "no"}:
            return False
        if raw in {"1", "true", "yes"}:
            return True
        return os.getenv("ARCHIPELAGO_ENV", "development").lower() in {"production", "prod"}

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
        headers = {"apikey": key, "Authorization": f"Bearer {token}"}
        try:
            user_response = requests.get(f"{url}/auth/v1/user", headers=headers, timeout=SUPABASE_USER_TIMEOUT_SEC)
            profile_response = (
                requests.get(
                    f"{url}/rest/v1/profiles",
                    params={"select": "username,role", "id": f"eq.{user_response.json().get('id', '')}"},
                    headers=headers,
                    timeout=SUPABASE_PROFILE_TIMEOUT_SEC,
                )
                if user_response.status_code == 200
                else None
            )
        except requests.RequestException:
            return None, "Supabase identity verification is unavailable."
        if user_response.status_code != 200 or profile_response is None or profile_response.status_code != 200:
            return None, "Your Supabase session could not be verified."
        profiles = profile_response.json()
        if not isinstance(profiles, list) or len(profiles) != 1:
            return None, "Your account does not have an assigned Archipelago role."
        role = str(profiles[0].get("role") or "")
        if role not in AUTH_ROLES:
            return None, "Your account role is not permitted in Archipelago."
        return {"role": role, "username": profiles[0].get("username") or "", "token": token}, None


class RateLimiter:
    """Sliding-window per-client-IP limiter with separate chat and API buckets."""

    def __init__(self) -> None:
        self._chat: dict[str, deque] = defaultdict(deque)
        self._api: dict[str, deque] = defaultdict(deque)

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
    def _check(bucket_map: dict[str, deque], max_per_min: int, min_gap_sec: float) -> tuple[bool, int]:
        ip = RateLimiter.client_ip()
        now = time.time()
        bucket = bucket_map[ip]
        while bucket and now - bucket[0] > RATE_WINDOW_SEC:
            bucket.popleft()
        if bucket and now - bucket[-1] < min_gap_sec:
            return True, 1
        if len(bucket) >= max_per_min:
            return True, max(1, int(RATE_WINDOW_SEC - (now - bucket[0])))
        bucket.append(now)
        return False, 0

    def check_chat(self) -> tuple[bool, int]:
        """Check the strict chat bucket."""
        return self._check(self._chat, CHAT_RATE_MAX_PER_MIN, CHAT_RATE_MIN_GAP_SEC)

    def check_api(self) -> tuple[bool, int]:
        """Check the general API bucket."""
        return self._check(self._api, API_RATE_MAX_PER_MIN, API_RATE_MIN_GAP_SEC)
