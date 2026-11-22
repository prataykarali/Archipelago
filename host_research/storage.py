"""Read the shared research index without exposing server credentials."""

from __future__ import annotations

import atexit
import hashlib
import os
import sqlite3
import threading
import time

import requests

STORE_TIMEOUT_SECONDS = 10
MAX_ROWS = 100
AUTH_CACHE_TTL_SECONDS = 30.0
AUTH_CACHE_MAX_ENTRIES = 256
_AUTH_CACHE_LOCK = threading.Lock()
_AUTH_CACHE: dict[str, tuple[float, dict[str, str]]] = {}
_REVOKED_TOKENS: set[str] = set()
_HTTP_SESSIONS: list[requests.Session] = []
_SQLITE_HANDLES: list[sqlite3.Connection] = []
SUPABASE_AUTH_PATH = "/auth/v1/user"
SUPABASE_RECORDS_PATH = "/rest/v1/research_intake_records"
SUPABASE_TOPICS_PATH = "/rest/v1/research_topic_inventory"
SUPABASE_PROFILES_PATH = "/rest/v1/profiles"
STAFF_ROLES = frozenset({"faculty", "librarian", "administrator"})


def register_http_session(session: requests.Session) -> requests.Session:
    """Track a requests.Session so it is closed cleanly on shutdown."""
    with _AUTH_CACHE_LOCK:
        if session not in _HTTP_SESSIONS:
            _HTTP_SESSIONS.append(session)
    return session


def register_sqlite_handle(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Track a SQLite connection so it is checkpointed and closed on shutdown."""
    with _AUTH_CACHE_LOCK:
        if conn not in _SQLITE_HANDLES:
            _SQLITE_HANDLES.append(conn)
    return conn


def close_storage_resources() -> None:
    """Close tracked HTTP sessions, SQLite handles, and clear in-memory caches."""
    with _AUTH_CACHE_LOCK:
        sessions = list(_HTTP_SESSIONS)
        _HTTP_SESSIONS.clear()
        handles = list(_SQLITE_HANDLES)
        _SQLITE_HANDLES.clear()
        _AUTH_CACHE.clear()
    for session in sessions:
        try:
            session.close()
        except Exception:
            pass
    for conn in handles:
        try:
            conn.close()
        except Exception:
            pass


atexit.register(close_storage_resources)


def revoke_token(token: str) -> None:
    """Invalidate a bearer or cookie session token on logout."""
    if not token:
        return
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with _AUTH_CACHE_LOCK:
        _REVOKED_TOKENS.add(token_hash)
        stale = [k for k in _AUTH_CACHE if k.endswith(f":{token_hash}")]
        for k in stale:
            _AUTH_CACHE.pop(k, None)


def _config() -> tuple[str, str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    public_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    secret_key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    return url, public_key, secret_key


def verify_user(token: str) -> dict[str, str] | None:
    """Resolve a shared Supabase session and its assigned staff role."""
    url, public_key, _secret_key = _config()
    if not url or not public_key or not token or len(token) > 4096:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cache_key = f"{hashlib.sha256(f'{url}:{public_key}'.encode()).hexdigest()}:{token_hash}"
    now = time.monotonic()
    with _AUTH_CACHE_LOCK:
        if token_hash in _REVOKED_TOKENS:
            return None
        if not os.getenv("PYTEST_CURRENT_TEST"):
            cached = _AUTH_CACHE.get(cache_key)
            if cached and cached[0] > now:
                return dict(cached[1])
    response = requests.get(
        url + SUPABASE_AUTH_PATH,
        headers={"apikey": public_key, "Authorization": f"Bearer {token}"},
        timeout=STORE_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        return None
    user = response.json()
    user_id = user.get("id") if isinstance(user, dict) else None
    if not isinstance(user_id, str) or not user_id:
        return None
    profile_response = requests.get(
        url + SUPABASE_PROFILES_PATH,
        params={"select": "username,role", "id": f"eq.{user_id}"},
        headers={"apikey": public_key, "Authorization": f"Bearer {token}"},
        timeout=STORE_TIMEOUT_SECONDS,
    )
    profile_response.raise_for_status()
    profiles = profile_response.json()
    if not isinstance(profiles, list) or len(profiles) != 1:
        return None
    role = str(profiles[0].get("role") or "")
    if role not in STAFF_ROLES:
        return None
    principal = {"id": user_id, "role": role, "username": str(profiles[0].get("username") or "")}
    if not os.getenv("PYTEST_CURRENT_TEST"):
        with _AUTH_CACHE_LOCK:
            if len(_AUTH_CACHE) >= AUTH_CACHE_MAX_ENTRIES:
                _AUTH_CACHE.clear()
            _AUTH_CACHE[cache_key] = (now + AUTH_CACHE_TTL_SECONDS, dict(principal))
    return principal


def topic_inventory() -> list[dict[str, object]]:
    """Read the current research topic summary from shared Supabase."""
    url, _public_key, secret_key = _config()
    if not url or not secret_key:
        raise RuntimeError("shared_storage_unconfigured")
    response = requests.get(
        url + SUPABASE_TOPICS_PATH,
        params={
            "select": "topic,paper_count,last_ingested_at",
            "order": "last_ingested_at.desc",
            "limit": 100,
        },
        headers={"apikey": secret_key, "Authorization": f"Bearer {secret_key}"},
        timeout=STORE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("invalid_storage_response")
    return [row for row in rows if isinstance(row, dict)]


def recent_records(limit: int = MAX_ROWS, topic: str = "") -> list[dict[str, object]]:
    """Read saved paper metadata for an authenticated research view."""
    url, _public_key, secret_key = _config()
    if not url or not secret_key:
        raise RuntimeError("shared_storage_unconfigured")
    params: dict[str, str | int] = {
        "select": "record_key,title,source_url,source_name,topic,published_at,updated_at,metadata",
        "kind": "eq.paper",
        "order": "updated_at.desc",
        "limit": min(max(limit, 1), MAX_ROWS),
    }
    if topic:
        params["topic"] = f"eq.{topic}"
    response = requests.get(
        url + SUPABASE_RECORDS_PATH,
        params=params,
        headers={"apikey": secret_key, "Authorization": f"Bearer {secret_key}"},
        timeout=STORE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("invalid_storage_response")
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and (
            not isinstance(row.get("metadata"), dict) or row["metadata"].get("active") is not False
        )
    ]
