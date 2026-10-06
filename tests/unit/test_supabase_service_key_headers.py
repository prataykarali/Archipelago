"""Modern opaque Supabase keys must never be sent as bearer JWTs."""

from __future__ import annotations

import pytest

from archipelago.inference.supabase_sync_client import SupabaseSyncClient
from archipelago.supabase_auth import part01_verify as verify

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("key", "expected_bearer"),
    [
        ("sb_secret_synthetic", None),
        ("legacy-synthetic-jwt", "Bearer legacy-synthetic-jwt"),
    ],
)
def test_admin_and_sync_headers_match_key_type(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    expected_bearer: str | None,
) -> None:
    """Auth Admin and local sync use the same Supabase key convention."""
    monkeypatch.setattr(verify, "get_service_role_key", lambda: key)
    admin = verify._admin_headers()
    sync = SupabaseSyncClient(url="https://example.supabase.co", key=key).headers

    for headers in (admin, sync):
        assert headers["apikey"] == key
        assert headers.get("Authorization") == expected_bearer


def test_sync_fails_closed_without_server_key() -> None:
    """An unset secret must not issue an unauthenticated write request."""
    client = SupabaseSyncClient(url="https://example.supabase.co", key="")

    assert client.sync_documents([{"id": "example"}]) is False
