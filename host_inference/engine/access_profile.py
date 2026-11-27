"""Access-profile policy for SIGIR open-access isolation vs UEM institutional mode.

One concern: read ``ARCHIPELAGO_ACCESS_PROFILE`` and provide pure helpers that
exclude Pearson catalogue recommendations, ``/open/`` institutional redirects,
and closed-source e-book cards when running in ``open_access`` mode while
preserving 100% of UEM institutional functionality under the default
``institutional`` profile.
"""

from __future__ import annotations

import os
from typing import Any

ACCESS_PROFILE_ENV = "ARCHIPELAGO_ACCESS_PROFILE"
ACCESS_PROFILE_INSTITUTIONAL = "institutional"
ACCESS_PROFILE_OPEN_ACCESS = "open_access"

_OPEN_ACCESS_ALIASES = frozenset({"open_access", "open-access", "sigir_open_access", "open"})
_PEARSON_URL_MARKERS = ("/open/", "elibrary.in.pearson.com", "ebooks.elibrary.in.pearson.com")
_PEARSON_PUBLISHER_MARKER = "pearson"
_INSTITUTIONAL_RESOURCE_TYPE = "institutional_e_book"
_PEARSON_SOURCE_CATEGORY = "pearson_catalogue_only"


def active_access_profile() -> str:
    """Return ``open_access`` or ``institutional`` (default) from the environment."""
    raw = os.getenv(ACCESS_PROFILE_ENV, ACCESS_PROFILE_INSTITUTIONAL).strip().lower()
    if raw in _OPEN_ACCESS_ALIASES:
        return ACCESS_PROFILE_OPEN_ACCESS
    return ACCESS_PROFILE_INSTITUTIONAL


def is_open_access_profile() -> bool:
    """True when the deployment is restricted to open-access corpus sources only."""
    return active_access_profile() == ACCESS_PROFILE_OPEN_ACCESS


def is_pearson_url(url: object) -> bool:
    """True when ``url`` points to an institutional ``/open/`` or Pearson reader route."""
    text = str(url or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in _PEARSON_URL_MARKERS)


def is_institutional_card(card: object) -> bool:
    """True when ``card`` represents a Pearson or closed-source institutional e-book."""
    if not isinstance(card, dict):
        return False
    if card.get("is_pearson") or card.get("isPearson"):
        return True
    if str(card.get("source_category") or "").strip().lower() == _PEARSON_SOURCE_CATEGORY:
        return True
    if str(card.get("resource_type") or "").strip().lower() == _INSTITUTIONAL_RESOURCE_TYPE:
        return True
    publisher = str(card.get("publisher") or "").strip().lower()
    if _PEARSON_PUBLISHER_MARKER in publisher:
        return True
    for field in ("url", "pdf_url", "open_url", "reader_url", "reader_base_url"):
        if is_pearson_url(card.get(field)):
            return True
    return False


def filter_open_access_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop Pearson and ``/open/`` citations when ``open_access`` mode is active."""
    if not is_open_access_profile():
        return list(citations)
    return [c for c in citations if isinstance(c, dict) and not is_institutional_card(c)]


def strip_institutional_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach access-profile flags and strip closed-source cards in ``open_access`` mode."""
    profile = active_access_profile()
    open_only = profile == ACCESS_PROFILE_OPEN_ACCESS
    payload["access_profile"] = profile
    payload["open_access_only"] = open_only
    if not open_only:
        return payload

    if isinstance(payload.get("citations"), list):
        payload["citations"] = filter_open_access_citations(payload["citations"])
    for key in ("inventory", "digital_resources", "inventory_cards"):
        if isinstance(payload.get(key), list):
            kept = [item for item in payload[key] if not is_institutional_card(item)]
            payload[key] = kept
    return payload


__all__ = [
    "ACCESS_PROFILE_ENV",
    "ACCESS_PROFILE_INSTITUTIONAL",
    "ACCESS_PROFILE_OPEN_ACCESS",
    "active_access_profile",
    "filter_open_access_citations",
    "is_institutional_card",
    "is_open_access_profile",
    "is_pearson_url",
    "strip_institutional_payload",
]
