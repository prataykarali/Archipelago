"""Load the concept graph and Pearson catalog from Supabase, then disk cache."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
OPEN_ACCESS_FILES = ("okf_graph.json", "library_manifest.json")
OPEN_ACCESS_PROFILES = frozenset({"open_access", "open-access", "sigir_open_access"})
HYDRATE_TIMEOUT_SECONDS: tuple[float, float] = (2.0, 3.0)
HYDRATE_COOLDOWN_SECONDS = 30.0
_CACHE_LOCK = threading.Lock()
_LAST_HYDRATE_ATTEMPT: float = 0.0
_MEM_CACHE: dict[str, tuple[float, object]] = {}


def _is_open_access() -> bool:
    return os.environ.get("ARCHIPELAGO_ACCESS_PROFILE", "").strip().lower() in OPEN_ACCESS_PROFILES


def _hydrate_files() -> tuple[str, ...]:
    return OPEN_ACCESS_FILES if _is_open_access() else FILES


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
        ROOT.parent / "host_inference" / "fixtures" / name,
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
    global _LAST_HYDRATE_ATTEMPT
    with _CACHE_LOCK:
        _LAST_HYDRATE_ATTEMPT = time.monotonic()
    CACHE.mkdir(parents=True, exist_ok=True)
    target_files = _hydrate_files()
    source = "unavailable"
    loaded = 0
    auth = _headers()
    if auth:
        base = auth.pop("url")

        def _fetch_one(name: str) -> bool:
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
                                return True
                        except Exception:
                            pass
                    target.write_bytes(response.content)
                    return True
            except (requests.RequestException, OSError):
                return False
            return False

        if len(target_files) > 1:
            with ThreadPoolExecutor(max_workers=len(target_files)) as pool:
                loaded = sum(1 for ok in pool.map(_fetch_one, target_files) if ok)
        else:
            loaded = sum(1 for name in target_files if _fetch_one(name))
        if loaded == len(target_files):
            source = "supabase"

    if source == "supabase":
        return {"source": source, "cache": str(CACHE)}

    if _production_mode():
        for name in target_files:
            source_file = PACKAGED_CACHE / name if (PACKAGED_CACHE / name).is_file() else (ROOT / "fixtures" / name)
            target = CACHE / name
            if source_file.is_file() and not target.is_file():
                target.write_bytes(source_file.read_bytes())
        if (CACHE / "okf_graph.json").is_file():
            return {"source": "bundled", "cache": str(CACHE)}
        return {"source": source, "cache": str(CACHE)}

    for name in target_files:
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


def pearson_page_url(book: dict, page: int | None = None) -> str:
    """Exact Pearson reader URL: viewer + version + subscription + #book/{id}[/page/{n}]."""
    is_pdf = str(book.get("book_type") or "pdf").strip().lower() == "pdf"
    viewer = "pdfviewer.html" if is_pdf else "index.html"
    sub = str(book.get("subscription_id") or "").strip()
    sub_query = f"&subscriptionId={sub}" if sub else ""
    page_part = ""
    if is_pdf and page is not None:
        page_n = max(1, int(page))
        if book.get("page_count") and int(book["page_count"]) > 1:
            page_n = min(page_n, int(book["page_count"]))
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
        "desc": "Institutional e-book (catalogue-only metadata). Opens official Pearson reader for your library login.",
        "isbn": book.get("isbn") or "",
        "isPearson": True,
        "book_type": str(book.get("book_type") or "pdf").strip().lower(),
        "page_verified": False,
        "page_count": book.get("page_count") or 1,
        "primaryColor": "#1d4ed8",
        "accentColor": "#93c5fd",
        "pdfUrl": "",
        "open_url": f"/open/{book.get('id')}",
        "reader_base_url": f"/open/{book.get('id')}",
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
        fallback = _fallback("pearson_bookshelf.json")
        if fallback and fallback.is_file():
            path = fallback
        else:
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
        fallback = _fallback("library_manifest.json")
        if fallback and fallback.is_file():
            path = fallback
        else:
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
