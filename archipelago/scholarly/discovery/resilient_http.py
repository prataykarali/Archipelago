"""Resilient HTTP client with per-provider rate limits, Retry-After, backoff, TTL cache, and circuit breaker."""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import hashlib
import json
import random
import threading
import time
from typing import Any

import requests

DEFAULT_MIN_INTERVALS: dict[str, float] = {
    "openalex": 0.10,
    "crossref": 0.10,
    "semantic_scholar": 0.50,
    "arxiv": 1.00,
    "dblp": 0.50,
    "openaire": 0.20,
    "datacite": 0.15,
    "europe_pmc": 0.15,
    "pubmed": 0.35,
    "orcid": 0.25,
    "opencitations": 0.20,
    "google_research": 0.50,
}

DEFAULT_MAX_RETRIES = 2
MAX_RETRY_AFTER_SECONDS = 5.0
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_COOLDOWN_SECONDS = 60.0


@dataclass
class CacheEntry:
    expires_at: float
    status_code: int
    content: bytes
    headers: dict[str, str]


@dataclass
class CircuitState:
    consecutive_failures: int = 0
    open_until: float = 0.0
    last_reason: str | None = None


class ProviderReliabilityClient:
    """Thread-safe per-provider rate limiter, TTL cache, bounded retries, and circuit breaker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_at: dict[str, float] = {}
        self._cache: dict[str, CacheEntry] = {}
        self._circuits: dict[str, CircuitState] = {}

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._circuits.clear()

    def _cache_key(self, provider: str, url: str, params: dict[str, Any] | None) -> str:
        payload = json.dumps({"p": provider, "u": url, "q": params or {}}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _wait_for_slot(self, provider: str) -> None:
        interval = DEFAULT_MIN_INTERVALS.get(provider, 0.15)
        with self._lock:
            now = time.monotonic()
            last = self._last_request_at.get(provider, 0.0)
            wait = interval - (now - last)
            self._last_request_at[provider] = now + max(0.0, wait)
        if wait > 0:
            time.sleep(wait)

    def _is_circuit_open(self, provider: str) -> tuple[bool, str | None]:
        with self._lock:
            state = self._circuits.get(provider)
            if state and state.open_until > time.monotonic():
                return True, state.last_reason
            return False, None

    def _record_success(self, provider: str) -> None:
        with self._lock:
            state = self._circuits.get(provider)
            if state:
                state.consecutive_failures = 0
                state.open_until = 0.0
                state.last_reason = None

    def _record_failure(self, provider: str, reason: str) -> None:
        with self._lock:
            state = self._circuits.setdefault(provider, CircuitState())
            state.consecutive_failures += 1
            state.last_reason = reason
            if state.consecutive_failures >= CIRCUIT_FAILURE_THRESHOLD:
                state.open_until = time.monotonic() + CIRCUIT_COOLDOWN_SECONDS

    @staticmethod
    def parse_retry_after(header_value: str | None) -> float | None:
        if not header_value:
            return None
        text = header_value.strip()
        if text.isdigit():
            return min(MAX_RETRY_AFTER_SECONDS, max(0.2, float(text)))
        try:
            dt = parsedate_to_datetime(text)
            delta = dt.timestamp() - time.time()
            if delta > 0:
                return min(MAX_RETRY_AFTER_SECONDS, delta)
        except (TypeError, ValueError):
            return None
        return None

    def get(
        self,
        session: requests.Session,
        provider: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 15,
        ttl_seconds: float = 900.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> tuple[requests.Response | None, str | None]:
        """Execute GET with TTL cache, circuit breaker, rate limit, and Retry-After backoff."""
        key = self._cache_key(provider, url, params)
        if ttl_seconds > 0:
            with self._lock:
                entry = self._cache.get(key)
                if entry and entry.expires_at > time.monotonic():
                    resp = requests.Response()
                    resp.status_code = entry.status_code
                    resp._content = entry.content
                    resp.headers.update(entry.headers)
                    resp.url = url
                    return resp, None

        is_open, open_reason = self._is_circuit_open(provider)
        if is_open:
            return None, f"circuit_open:{open_reason or 'rate_limited'}"

        last_error: str | None = None
        for attempt in range(max_retries + 1):
            self._wait_for_slot(provider)
            try:
                resp = session.get(url, params=params, headers=headers, timeout=timeout)
            except requests.RequestException as exc:
                last_error = type(exc).__name__
                if attempt < max_retries:
                    time.sleep(min(4.0, 0.4 * (2**attempt) + random.uniform(0.05, 0.25)))
                    continue
                self._record_failure(provider, last_error)
                return None, last_error

            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = "http_429" if resp.status_code == 429 else f"http_{resp.status_code}"
                if attempt < max_retries:
                    retry_after = self.parse_retry_after(resp.headers.get("Retry-After"))
                    delay = retry_after if retry_after is not None else (0.5 * (2**attempt) + random.uniform(0.05, 0.25))
                    time.sleep(min(MAX_RETRY_AFTER_SECONDS, delay))
                    continue
                self._record_failure(provider, last_error)
                return resp, last_error

            self._record_success(provider)
            if resp.ok and ttl_seconds > 0:
                with self._lock:
                    self._cache[key] = CacheEntry(
                        expires_at=time.monotonic() + ttl_seconds,
                        status_code=resp.status_code,
                        content=resp.content,
                        headers=dict(resp.headers),
                    )
            return resp, None

        return None, last_error or "retry_exhausted"


_DEFAULT_CLIENT = ProviderReliabilityClient()


def reliability_client() -> ProviderReliabilityClient:
    """Return the shared process-wide provider reliability client."""
    return _DEFAULT_CLIENT
