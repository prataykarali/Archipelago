"""Local development user directory (non-production fallback only)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from archipelago.supabase_auth.part01_verify import is_auth_required, is_dev_auth_allowed

logger = logging.getLogger("archipelago.supabase_auth")

LOCAL_USERS_FILE = Path(__file__).resolve().parents[2] / "data" / "local_users.json"


def _ensure_local_users_file() -> Path:
    LOCAL_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LOCAL_USERS_FILE.exists():
        # Empty by default: local development must never manufacture demo roles.
        LOCAL_USERS_FILE.write_text("[]", encoding="utf-8")
    return LOCAL_USERS_FILE


def _read_local_users() -> list[dict[str, Any]]:
    path = _ensure_local_users_file()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_local_users(users: list[dict[str, Any]]) -> None:
    path = _ensure_local_users_file()
    path.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _local_user_store_allowed() -> bool:
    """Restrict the file-backed user directory to explicit, non-production dev auth."""
    return not is_auth_required() and is_dev_auth_allowed()


def find_local_user_index(users: list[dict[str, Any]], target_id: str) -> int | None:
    """Locate a local user record by id."""
    return next((i for i, u in enumerate(users) if u.get("id") == target_id), None)
