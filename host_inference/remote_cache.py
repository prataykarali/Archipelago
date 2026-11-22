"""Load the concept graph and Pearson catalog from Supabase, then disk cache."""

from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time

import requests

ROOT = Path(__file__).resolve().parent
PACKAGED_CACHE = ROOT / "cache"
CACHE = Path("/tmp/archipelago/cache") if os.environ.get("VERCEL") else PACKAGED_CACHE
BUCKET = "archipelago-cache"
FILES = ("okf_graph.json", "pearson_bookshelf.json", "library_manifest.json")
HYDRATE_TIMEOUT_SECONDS = 10
HYDRATE_COOLDOWN_SECONDS = 30.0
_CACHE_LOCK = threading.Lock()
_LAST_HYDRATE_ATTEMPT: float = 0.0
_MEM_CACHE: dict[str, tuple[float, object]] = {}


def _production_mode() -> bool:
    return os.environ.get("ARCHIPELAGO_ENV", "development").strip().lower() in {
        "production",
        "prod",
    }


def _headers() -> dict[str, str] | None:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url or not key:
        return None
    return {"url": url, "Authorization": f"Bearer {key}", "apikey": key}


def _fallback(name: str) -> Path | None:
    for candidate in (
        PACKAGED_CACHE / name,
        ROOT / "fixtures" / name,
        ROOT / name,
        ROOT / "data" / name,
        ROOT.parent / name,
        ROOT.parent / "data" / "catalogs" / name,
    ):
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
                    timeout=HYDRATE_TIMEOUT_SECONDS,
                )
                if response.status_code == 200 and len(response.content) > 200:
                    if name == "okf_graph.json" and target.is_file():
                        try:
                            existing_count = len(json.loads(target.read_text()).get("concepts", {}))
                            remote_count = len(json.loads(response.content).get("concepts", {}))
                            if existing_count > remote_count:
                                loaded += 1
                                continue
                        except Exception:
                            pass
                    target.write_bytes(response.content)
                    loaded += 1
            except (requests.RequestException, OSError):
                pass
        if loaded == len(FILES):
            source = "supabase"

    if source == "supabase":
        return {"source": source, "cache": str(CACHE)}

    if _production_mode():
        for name in FILES:
            source_file = PACKAGED_CACHE / name if (PACKAGED_CACHE / name).is_file() else (ROOT / "fixtures" / name)
            target = CACHE / name
            if source_file.is_file() and not target.is_file():
                target.write_bytes(source_file.read_bytes())
        if (CACHE / "okf_graph.json").is_file():
            return {"source": "bundled", "cache": str(CACHE)}
        return {"source": source, "cache": str(CACHE)}

    for name in FILES:
        target = CACHE / name
        if target.is_file():
            continue
        src = _fallback(name)
        if src is not None:
            target.write_bytes(src.read_bytes())
    return {
        "source": "local" if (CACHE / "okf_graph.json").is_file() else "missing",
        "cache": str(CACHE),
    }


def pearson_page_url(book: dict, page: int = 1) -> str:
    """Exact Pearson reader URL: viewer + version + subscription + #book/{id}/page/{n}."""
    page_n = max(1, int(page or 1))
    if book.get("page_count") and int(book["page_count"]) > 1:
        page_n = min(page_n, int(book["page_count"]))
    viewer = "pdfviewer.html" if str(book.get("book_type") or "").lower() == "pdf" else "index.html"
    sub = str(book.get("subscription_id") or "").strip()
    sub_query = f"&subscriptionId={sub}" if sub else ""
    page_part = f"/page/{page_n}"
    return f"https://ebooks.elibrary.in.pearson.com/wr/{viewer}?version=1.0.317.1{sub_query}#book/{book.get('id')}{page_part}"


def public_book(book: dict) -> dict:
    """Browser payload. Subscription ids stay on the server."""
    return {
        "id": book.get("id"),
        "title": book.get("title"),
        "author": book.get("author") or "Institutional collection",
        "year": "",
        "domain": book.get("domain") or "CS & AI",
        "desc": "Institutional e-book. Open opens the exact Pearson page for your library login.",
        "isbn": book.get("isbn") or "",
        "isPearson": True,
        "page_count": book.get("page_count") or 1,
        "primaryColor": "#1d4ed8",
        "accentColor": "#93c5fd",
        "pdfUrl": "",
        "open_url": f"/open/{book.get('id')}?page=1",
        "reader_base_url": f"/open/{book.get('id')}?page=1",
    }


def _hydrate_if_needed() -> None:
    global _LAST_HYDRATE_ATTEMPT
    now = time.monotonic()
    with _CACHE_LOCK:
        if _LAST_HYDRATE_ATTEMPT and (now - _LAST_HYDRATE_ATTEMPT) < HYDRATE_COOLDOWN_SECONDS:
            return
        _LAST_HYDRATE_ATTEMPT = now
    hydrate()


def load_books() -> list[dict]:
    path = CACHE / "pearson_bookshelf.json"
    if not path.is_file():
        _hydrate_if_needed()
    if not path.is_file():
        return []
    try:
        mtime = path.stat().st_mtime
        key = f"books:{path}"
        with _CACHE_LOCK:
            cached = _MEM_CACHE.get(key)
            if cached and cached[0] == mtime and isinstance(cached[1], list):
                return list(cached[1])
        payload = json.loads(path.read_text(encoding="utf-8"))
        books = list(payload.get("books") or [])
        with _CACHE_LOCK:
            _MEM_CACHE[key] = (mtime, books)
        return list(books)
    except (OSError, json.JSONDecodeError):
        return []


def load_library_manifest() -> dict:
    """Return the browser-safe library shelf exported to private Supabase storage."""
    path = CACHE / "library_manifest.json"
    if not path.is_file():
        _hydrate_if_needed()
    if not path.is_file():
        return {}
    try:
        mtime = path.stat().st_mtime
        key = f"manifest:{path}"
        with _CACHE_LOCK:
            cached = _MEM_CACHE.get(key)
            if cached and cached[0] == mtime and isinstance(cached[1], dict):
                return dict(cached[1])
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = payload if isinstance(payload, dict) else {}
        with _CACHE_LOCK:
            _MEM_CACHE[key] = (mtime, manifest)
        return dict(manifest)
    except (OSError, json.JSONDecodeError):
        return {}
