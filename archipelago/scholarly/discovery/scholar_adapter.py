"""Google Scholar human verification links.

Google Scholar does not provide this project a machine search API. Search links
are navigation aids and must never become paper records or evidence.
"""

from __future__ import annotations

from typing import Any

from archipelago.scholarly.discovery.scholar_deeplink import generate_scholar_url


class GoogleScholarAdapter:
    """Build outbound Scholar links without automated Scholar requests."""

    def __init__(self, session_cookie: str | None = None) -> None:
        self.session_cookie = session_cookie

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Return no records because a link is not a fetched publication."""
        return []

    def verification_url(self, query: str) -> str:
        """Return a one-click search URL for a human researcher."""
        return str(generate_scholar_url(query))
