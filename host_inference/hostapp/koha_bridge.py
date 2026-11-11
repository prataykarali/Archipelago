"""Read the shared public Koha metadata snapshot for the Library page."""

from __future__ import annotations

from functools import lru_cache
import os
import time

import requests

BUCKET = "archipelago-cache"
OBJECT = "koha_catalog_snapshot.json"
REQUEST_TIMEOUT_SECONDS = 12
CACHE_SECONDS = 300


def load_koha_snapshot() -> dict[str, object] | None:
    """Return a validated shared snapshot without exposing storage credentials."""
    return _load_for_bucket(int(time.time() // CACHE_SECONDS))


@lru_cache(maxsize=2)
def _load_for_bucket(_bucket: int) -> dict[str, object] | None:
    """Bound repeated reads in a warm serverless instance."""
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base or not key:
        return None
    try:
        response = requests.get(
            f"{base}/storage/v1/object/{BUCKET}/{OBJECT}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict) or data.get("source") != "authorized_koha_ods_export":
        return None
    return data


def _count(value: object) -> int:
    """Coerce a nonnegative copy count from the Koha export."""
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def public_holdings(snapshot: dict[str, object]) -> list[dict[str, object]]:
    """Map dated Koha rows to the existing Library table contract."""
    source = snapshot.get("holdings")
    if not isinstance(source, list):
        return []
    rows = []
    for item in source:
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("biblionumber") or "").strip()
        title = str(item.get("Title") or "").strip()
        if not identifier.isdigit() or not title:
            continue
        total = _count(item.get("No. of copies"))
        available = min(_count(item.get("Available Copies")), total)
        rows.append(
            {
                "book_id": identifier,
                "biblionumber": identifier,
                "title": title,
                "authors": str(item.get("Author") or "").strip(),
                "publisher": str(item.get("Publisher") or "").strip(),
                "accession": str(item.get("Accn Nos.") or "").strip(),
                "total_copies": total,
                "available_copies": available,
                "no_of_copies": total,
                "available_ratio": f"{available} / {total}",
                "isbn": str(item.get("isbn") or "").strip(),
                "call_number": str(item.get("call_number") or "").strip(),
                "rack_number": str(item.get("rack_number") or "").strip(),
                "opac_url": f"https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber={identifier}",
            }
        )
    return rows
