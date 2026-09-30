"""Query Cache for Archipelago Inference.

Follows the reference architecture:
STUDENT -> Normalize Query -> Redis / Cache -> HIT (Return) | MISS (...)
"""
from __future__ import annotations

import re
import time
import threading
from collections import OrderedDict
from typing import Any, Optional

_LOCK = threading.Lock()
_CACHE: OrderedDict[str, tuple[float, Any]] = OrderedDict()
_DEFAULT_TTL = 300.0  # 5 minutes
_MAX_ENTRIES = 512


def normalize_query(query: str) -> str:
    """Normalize query text: lowercase, strip punctuation, collapse whitespace."""
    if not query:
        return ""
    q = query.lower().strip()
    q = re.sub(r"[\?\!\.,;:\-_/\\]+", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def get_cached_response(query: str) -> Optional[Any]:
    """Return cached response if present and not expired, else None."""
    norm = normalize_query(query)
    if not norm:
        return None
    now = time.time()
    with _LOCK:
        if norm in _CACHE:
            expire_at, value = _CACHE[norm]
            if now <= expire_at:
                _CACHE.move_to_end(norm)
                return value
            else:
                del _CACHE[norm]
    return None


def set_cached_response(query: str, response: Any, ttl: float = _DEFAULT_TTL) -> None:
    """Store response in cache with TTL and LRU eviction."""
    norm = normalize_query(query)
    if not norm:
        return
    expire_at = time.time() + ttl
    with _LOCK:
        if norm in _CACHE:
            _CACHE.move_to_end(norm)
        _CACHE[norm] = (expire_at, response)
        while len(_CACHE) > _MAX_ENTRIES:
            _CACHE.popitem(last=False)


def clear_cache() -> None:
    """Clear all cached responses."""
    with _LOCK:
        _CACHE.clear()
