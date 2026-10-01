import collections
import os
import time
import threading
from functools import wraps
from typing import Any, Callable

from flask import request, jsonify, g

TIERS = {
    'anonymous': 5,
    'student': 30,
    'librarian': 100,
    'administrator': 200
}
DEFAULT_LIMIT = 100
WINDOW_SECONDS = 60

class RateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""
    def __init__(self):
        self._windows = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()
    
    def check(self, key: str, limit: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - WINDOW_SECONDS
        
        with self._lock:
            window = self._windows[key]
            while window and window[0] < cutoff:
                window.popleft()
                
            if len(window) >= limit:
                oldest = window[0]
                retry_after = max(1, int(WINDOW_SECONDS - (now - oldest)) + 1)
                return False, retry_after
            
            window.append(now)
            return True, 0

_limiter = RateLimiter()

def rate_limit(tier: str = None):
    """Flask decorator for rate limiting based on user tier."""
    def decorator(f: Callable):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if os.environ.get("ARCHIPELAGO_RATE_LIMIT_DISABLED") == "1":
                return f(*args, **kwargs)
                
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
            
            user_tier = getattr(g, 'user_tier', tier)
            limit = TIERS.get(user_tier, DEFAULT_LIMIT)
            
            allowed, retry_after = _limiter.check(client_ip, limit)
            if not allowed:
                resp = jsonify({"error": "Rate limit exceeded", "retry_after_s": retry_after})
                resp.status_code = 429
                resp.headers["Retry-After"] = str(retry_after)
                return resp
                
            return f(*args, **kwargs)
        return wrapped
    return decorator
