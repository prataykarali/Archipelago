"""Resolve a local-only ingestion origin without accepting a cloud destination."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

LOCAL_INGEST_URL_ENV = "ARCHIPELAGO_LOCAL_INGEST_URL"
LOCAL_HOSTS = frozenset(
    {
        "127.0.0.1",
        "localhost",
        "archipelago-ingestion",
        "archipelago-inference",
    }
)


def local_ingest_origin() -> str | None:
    """Return an explicitly configured appliance URL or fail closed."""
    origin = os.getenv(LOCAL_INGEST_URL_ENV, "").strip().rstrip("/")
    if not origin:
        return None
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOCAL_HOSTS
        or port == 0
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return None
    return origin
