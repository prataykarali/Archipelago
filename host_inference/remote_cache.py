"""Load the concept graph and Pearson catalog from Supabase, then disk cache."""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
BUCKET = "archipelago-cache"
FILES = ("okf_graph.json", "pearson_bookshelf.json", "library_manifest.json")


def _production_mode() -> bool:
    return os.environ.get("ARCHIPELAGO_ENV", "development").strip().lower() in {"production", "prod"}


def _headers() -> dict[str, str] | None:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", "").strip() or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return None
    return {"url": url, "Authorization": f"Bearer {key}", "apikey": key}


def _fallback(name: str) -> Path | None:
    for candidate in (ROOT / name, ROOT / "data" / name, ROOT.parent / name, ROOT.parent / "data" / "catalogs" / name):
        if candidate.is_file():
            return candidate
    return None


def hydrate() -> dict[str, str]:
    """Refresh the disposable runtime cache from the Supabase source of truth.

    Production must not silently serve a graph or catalog bundled into an image
    after Supabase has become unavailable. Local fallback remains available for
    the ingestion workstation and development-only workflows.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    source = "unavailable"
    loaded = 0
    auth = _headers()
    if auth:
        base = auth.pop("url")
        for name in FILES:
            target = CACHE / name
            try:
                response = requests.get(
                    f"{base}/storage/v1/object/{BUCKET}/{name}",
                    headers=auth,
                    timeout=60,
                )
                if response.status_code == 200 and len(response.content) > 200:
                    target.write_bytes(response.content)
                    loaded += 1
            except requests.RequestException:
                pass
        if loaded == len(FILES):
            source = "supabase"

    if source == "supabase":
        return {"source": source, "cache": str(CACHE)}

    if _production_mode():
        return {"source": source, "cache": str(CACHE)}

    for name in FILES:
        target = CACHE / name
        if target.is_file():
            continue
        src = _fallback(name)
        if src is not None:
            target.write_bytes(src.read_bytes())
    return {"source": "local" if (CACHE / "okf_graph.json").is_file() else "missing", "cache": str(CACHE)}


def pearson_page_url(book: dict, page: int = 1) -> str:
    """Book URL, with exact PDF page fragments where Pearson supports them."""
    is_pdf = str(book.get("book_type") or "").lower() == "pdf"
    viewer = "pdfviewer.html" if is_pdf else "viewer.html"
    sub = str(book.get("subscription_id") or "").strip()
    sub_query = f"&subscriptionId={sub}" if sub else ""
    page_part = f"/page/{max(1, int(page))}" if is_pdf else ""
    return (
        f"https://ebooks.elibrary.in.pearson.com/wr/{viewer}?version=1.0.317.1{sub_query}#book/{book.get('id')}{page_part}"
    )


def public_book(book: dict) -> dict:
    """Browser payload. Subscription ids stay on the server."""
    return {
        "id": book.get("id"),
        "title": book.get("title"),
        "author": book.get("author") or "Institutional collection",
        "year": "",
        "domain": book.get("domain") or "CS & AI",
        "desc": "Institutional e-book. Open the book, then select the cited page in Pearson.",
        "isbn": book.get("isbn") or "",
        "isPearson": True,
        "page_count": book.get("page_count") or 1,
        "primaryColor": "#1d4ed8",
        "accentColor": "#93c5fd",
        "pdfUrl": "",
        "open_url": f"/open/{book.get('id')}?page=1",
        "reader_base_url": f"/open/{book.get('id')}?page=1",
    }


def load_books() -> list[dict]:
    path = CACHE / "pearson_bookshelf.json"
    if not path.is_file():
        hydrate()
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("books") or [])


def load_library_manifest() -> dict:
    """Return the browser-safe library shelf exported to private Supabase storage."""
    path = CACHE / "library_manifest.json"
    if not path.is_file():
        hydrate()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
