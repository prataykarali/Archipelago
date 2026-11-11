"""Read and update existing Supabase runtime state on hosted instances."""

from __future__ import annotations

import os
from typing import Any

import requests

RUNTIME_TIMEOUT_SECONDS = 10


def hosted_runtime() -> bool:
    """Use durable runtime state on ephemeral Vercel instances."""
    return bool(os.environ.get("VERCEL"))


def runtime_rpc(name: str, payload: dict[str, Any]) -> Any:
    """Call a pre-existing server-only RPC, failing closed on storage errors."""
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url or not key:
        raise RuntimeError("Durable account state is not configured")
    response = requests.post(
        f"{url}/rest/v1/rpc/{name}",
        json=payload,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=RUNTIME_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
