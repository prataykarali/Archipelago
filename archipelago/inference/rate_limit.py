"""Rate limiter for public / Hugging Face demos."""
from __future__ import annotations

import collections
import os
import time
from typing import Any


_RATE_LIMIT_DISABLED_ENV: str = "ARCHIPELAGO_RATE_LIMIT_DISABLED"
_RATE_LIMIT_PER_MIN_ENV: str = "ARCHIPELAGO_RATE_LIMIT_PER_MIN"
_RATE_LIMIT_BURST_ENV: str = "ARCHIPELAGO_RATE_LIMIT_BURST"
_RATE_LIMIT_GLOBAL_ENV: str = "ARCHIPELAGO_RATE_LIMIT_GLOBAL"

_DEFAULT_PER_MIN: int = 20
_DEFAULT_BURST: int = 50
_DEFAULT_GLOBAL: int = 500
_WINDOW_SECONDS: int = 60
_BURST_SECONDS: float = 10.0


class SlidingWindowLimiter:
    """Per-client sliding-window rate limiter with burst + global caps."""

    def __init__(self) -> None:
        self._per_min: int = int(os.environ.get(_RATE_LIMIT_PER_MIN_ENV, str(_DEFAULT_PER_MIN)))
        self._burst: int = int(os.environ.get(_RATE_LIMIT_BURST_ENV, str(_DEFAULT_BURST)))
        self._global_limit: int = int(os.environ.get(_RATE_LIMIT_GLOBAL_ENV, str(_DEFAULT_GLOBAL)))
        self._windows: dict[str, collections.deque[float]] = {}
        self._global_window: collections.deque[float] = collections.deque()

    def check(
        self,
        client_key: str,
        *,
        per_min: int | None = None,
        burst: int | None = None,
        global_per_min: int | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Return (allowed, meta). Records the request when allowed."""
        if os.environ.get(_RATE_LIMIT_DISABLED_ENV):
            return True, {"disabled": True}

        per_min_lim = int(per_min if per_min is not None else self._per_min)
        burst_lim = int(burst if burst is not None else self._burst)
        global_lim = int(global_per_min if global_per_min is not None else self._global_limit)

        now = time.monotonic()
        cutoff = now - _WINDOW_SECONDS
        burst_cutoff = now - _BURST_SECONDS

        while self._global_window and self._global_window[0] < cutoff:
            self._global_window.popleft()
        if len(self._global_window) >= global_lim:
            oldest = self._global_window[0] if self._global_window else now
            retry = max(1, int(_WINDOW_SECONDS - (now - oldest)) + 1)
            return False, {"scope": "global", "retry_after_s": retry}

        if client_key not in self._windows:
            self._windows[client_key] = collections.deque()
        window = self._windows[client_key]
        while window and window[0] < cutoff:
            window.popleft()

        burst_count = sum(1 for t in window if t >= burst_cutoff)
        if burst_count >= burst_lim:
            oldest_burst = next((t for t in window if t >= burst_cutoff), now)
            retry = max(1, int(_BURST_SECONDS - (now - oldest_burst)) + 1)
            return False, {"scope": "burst", "retry_after_s": retry}

        if len(window) >= per_min_lim:
            oldest = window[0]
            retry = max(1, int(_WINDOW_SECONDS - (now - oldest)) + 1)
            return False, {"scope": "per_client", "retry_after_s": retry}

        self._global_window.append(now)
        window.append(now)
        return True, {"scope": "ok"}

    def allows(self, client_ip: str) -> bool:
        ok, _ = self.check(client_ip)
        return ok

    def reset(self) -> None:
        self._windows.clear()
        self._global_window.clear()


def client_key_from_request(request: Any, session_id: str = "") -> str:
    """Build a stable client key from XFF / remote_addr + session."""
    headers = getattr(request, "headers", {}) or {}
    xff = ""
    if hasattr(headers, "get"):
        xff = headers.get("X-Forwarded-For", "") or ""
    elif isinstance(headers, dict):
        xff = headers.get("X-Forwarded-For", "") or ""
    if xff:
        ip = xff.split(",")[0].strip()
    else:
        ip = getattr(request, "remote_addr", None) or "unknown"
    sid = (session_id or "").strip()
    return f"{ip}|{sid}" if sid else ip


def _get_client_ip(request: Any) -> str:
    return client_key_from_request(request, "").split("|")[0]


_limiter = SlidingWindowLimiter()


def check_chat_rate_limit(request: Any, session_id: str = "") -> tuple[bool, dict[str, Any] | str]:
    key = client_key_from_request(request, session_id)
    ok, meta = _limiter.check(key)
    if ok:
        return True, meta
    return False, meta


def rate_limit_response(info: dict[str, Any] | None = None):
    """Return a Flask 429 response with the queue message tests expect."""
    from flask import jsonify

    info = info or {}
    retry = int(info.get("retry_after_s") or 15)
    msg = f"library is too busy ! you are in queue, retrying after-{retry}s"
    resp = jsonify({"error": msg, "retry_after_s": retry, "scope": info.get("scope", "per_client")})
    resp.status_code = 429
    return resp
