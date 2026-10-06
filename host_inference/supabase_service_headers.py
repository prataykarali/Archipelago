"""Build server-only Supabase headers for legacy JWT and modern opaque keys."""

from __future__ import annotations


def service_headers(key: str, *, json_body: bool = False) -> dict[str, str]:
    """Send opaque secret keys in apikey only; legacy JWTs also need Bearer."""
    headers = {"apikey": key}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers
