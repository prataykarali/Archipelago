"""Rate Limiting and Negative Caching Service for Link Resolution."""
from __future__ import annotations

from collections import defaultdict
import datetime
import logging
import time
from typing import Any

logger = logging.getLogger("archipelago.resolver.cache")


class RateLimiter:
    """Sliding-window rate limiter per client key."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_key: str = "default") -> bool:
        """Check if request for client_key is allowed under rate limits."""
        now = time.time()
        cutoff = now - self.window_seconds
        # Clean expired timestamps
        history = [t for t in self.requests[client_key] if t > cutoff]
        self.requests[client_key] = history

        if len(history) >= self.max_requests:
            return False

        self.requests[client_key].append(now)
        return True


class ResolverCache:
    """Positive & Negative Cache for resolved links."""

    def __init__(self, positive_ttl_sec: int = 86400, negative_ttl_sec: int = 600):
        self.positive_ttl_sec = positive_ttl_sec  # 24 hours
        self.negative_ttl_sec = negative_ttl_sec  # 10 minutes
        self.cache: dict[str, tuple[dict[str, Any], float]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        """Get cached resolution result if not expired."""
        if key not in self.cache:
            return None
        val, expiry = self.cache[key]
        if time.time() > expiry:
            del self.cache[key]
            return None
        return val

    def set_positive(self, key: str, data: dict[str, Any]) -> None:
        """Cache successful resolution."""
        expiry = time.time() + self.positive_ttl_sec
        self.cache[key] = (data, expiry)

    def set_negative(
        self,
        key: str,
        error_msg: str = "404 Not Found",
        context: dict[str, Any] | None = None,
    ) -> None:
        """Cache failed resolution so repeated expensive lookups are avoided.

        The cached record keeps the caller's context (id, title, url) so a cache
        hit returns the same shape as the original miss, plus a marker saying it
        came from cache.
        """
        expiry = time.time() + self.negative_ttl_sec
        record: dict[str, Any] = dict(context or {})
        record.update({
            "working": False,
            "error": error_msg,
            "status": 404,
            "url": None,
            "cached_negative": True,
            "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        self.cache[key] = (record, expiry)

    def clear(self) -> None:
        self.cache.clear()
