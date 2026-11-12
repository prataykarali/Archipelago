"""Persist staff-managed library notes separately from Koha records."""

from __future__ import annotations

import os

import requests

STORE_TIMEOUT_SECONDS = 10
RECORD_TYPES = frozenset({"catalog", "circulation", "orders", "fines"})
MAX_TEXT_LENGTH = 2000
MAX_KEY_LENGTH = 120
MAX_QUANTITY = 1_000_000
MAX_AMOUNT = 10_000_000
RECORDS_PATH = "/rest/v1/archipelago_librarian_records"


def _connection() -> tuple[str, dict[str, str]]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SECRET_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    ).strip()
    if not url or not key:
        raise RuntimeError("shared_storage_unconfigured")
    return url, {"apikey": key, "Authorization": f"Bearer {key}"}


def list_records(record_type: str) -> list[dict[str, object]]:
    """Read the latest Archipelago records for one staff workspace."""
    if record_type not in RECORD_TYPES:
        raise ValueError("invalid_record_type")
    url, headers = _connection()
    response = requests.get(
        url + RECORDS_PATH,
        params={
            "record_type": f"eq.{record_type}",
            "select": "*",
            "order": "updated_at.desc",
            "limit": 200,
        },
        headers=headers,
        timeout=STORE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("invalid_storage_response")
    return rows


def save_record(record_type: str, data: object, actor: str) -> dict[str, object]:
    """Validate and upsert a staff note, then append its audit snapshot."""
    if record_type not in RECORD_TYPES or not isinstance(data, dict):
        raise ValueError("invalid_record")
    key = data.get("record_key")
    if not isinstance(key, str) or not 1 <= len(key.strip()) <= MAX_KEY_LENGTH:
        raise ValueError("invalid_record_key")
    row: dict[str, object] = {
        "record_type": record_type,
        "record_key": key.strip(),
        "updated_by": actor,
    }
    for field in ("title", "status", "shelf", "note", "source_url"):
        value = data.get(field, "")
        if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
            raise ValueError(f"invalid_{field}")
        row[field] = value.strip()
    if row["source_url"] and not str(row["source_url"]).startswith("https://"):
        raise ValueError("source_url_must_be_https")
    for field, limit in (("quantity", MAX_QUANTITY), ("amount", MAX_AMOUNT)):
        value = data.get(field)
        if value in (None, ""):
            row[field] = None
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= limit
        ):
            raise ValueError(f"invalid_{field}")
        else:
            row[field] = value
    url, headers = _connection()
    response = requests.post(
        url + RECORDS_PATH,
        params={"on_conflict": "record_type,record_key"},
        json=row,
        headers={**headers, "Prefer": "resolution=merge-duplicates,return=representation"},
        timeout=STORE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    saved = response.json()[0]
    return saved
