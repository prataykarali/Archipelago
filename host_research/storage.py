"""Read the shared research index without exposing server credentials."""

from __future__ import annotations

import os

import requests

STORE_TIMEOUT_SECONDS = 10
MAX_ROWS = 100
SUPABASE_AUTH_PATH = "/auth/v1/user"
SUPABASE_RECORDS_PATH = "/rest/v1/research_intake_records"
SUPABASE_TOPICS_PATH = "/rest/v1/research_topic_inventory"
SUPABASE_PROFILES_PATH = "/rest/v1/profiles"
STAFF_ROLES = frozenset({"faculty", "librarian", "administrator"})


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
    if not url or not public_key or not token:
        return None
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
    return {"id": user_id, "role": role, "username": str(profiles[0].get("username") or "")}


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
