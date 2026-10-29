"""Read the shared research index without exposing server credentials."""

from __future__ import annotations

import os

import requests

STORE_TIMEOUT_SECONDS = 10
MAX_ROWS = 100
SUPABASE_AUTH_PATH = "/auth/v1/user"
SUPABASE_RECORDS_PATH = "/rest/v1/research_intake_records"


def _config() -> tuple[str, str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    public_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    secret_key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    return url, public_key, secret_key


def verify_user(token: str) -> bool:
    """Check a browser bearer token against the shared Supabase Auth project."""
    url, public_key, _secret_key = _config()
    if not url or not public_key or not token:
        return False
    response = requests.get(
        url + SUPABASE_AUTH_PATH,
        headers={"apikey": public_key, "Authorization": f"Bearer {token}"},
        timeout=STORE_TIMEOUT_SECONDS,
    )
    return response.status_code == 200 and bool(response.json().get("id"))


def recent_records(limit: int = MAX_ROWS) -> list[dict[str, object]]:
    """Read saved paper metadata for an authenticated research view."""
    url, _public_key, secret_key = _config()
    if not url or not secret_key:
        raise RuntimeError("shared_storage_unconfigured")
    response = requests.get(
        url + SUPABASE_RECORDS_PATH,
        params={
            "select": "record_key,title,source_url,source_name,topic,published_at,updated_at,metadata",
            "kind": "eq.paper",
            "order": "updated_at.desc",
            "limit": min(max(limit, 1), MAX_ROWS),
        },
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
