"""Load the concept graph and Pearson catalog from Supabase, then disk cache."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import requests

ROOT = Path(__file__).resolve().parent
CACHE = Path(
    os.environ.get("ARCHIPELAGO_CACHE_DIR")
    or (
        Path(tempfile.gettempdir()) / "archipelago-cache"
        if os.environ.get("VERCEL")
        else ROOT / "cache"
    )
)
BUCKET = "archipelago-cache"
FILES = ("okf_graph.json", "pearson_bookshelf.json", "library_manifest.json")
HF_GRAPH_URL = (
    "https://huggingface.co/datasets/Prataykarali/graphier/resolve/main/graph/okf_graph.json"
)
HF_BOOKS_URL = "https://huggingface.co/datasets/Prataykarali/Library_books/resolve/main/catalogs/pearson_bookshelf.json"
HF_SOURCE_FILES = {"okf_graph.json": HF_GRAPH_URL, "pearson_bookshelf.json": HF_BOOKS_URL}
HF_LIBRARY_REPO = "Prataykarali/Library_books"
HF_TREE_TIMEOUT_SECONDS = 20


def _hydrate_from_hugging_face() -> int:
    """Fetch the graph and Pearson shelf from their published datasets."""
    token = os.environ.get("HF_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    loaded = 0
    for name, url in HF_SOURCE_FILES.items():
        target = CACHE / name
        if target.is_file():
            loaded += 1
            continue
        try:
            response = requests.get(url, headers=headers, timeout=45)
            response.raise_for_status()
            payload = response.json()
            field = "books" if name == "pearson_bookshelf.json" else "concepts"
            if isinstance(payload, dict) and payload.get(field):
                target.write_bytes(response.content)
                loaded += 1
        except (requests.RequestException, ValueError, OSError):
            continue
    return loaded


def _hydrate_hf_manifest() -> bool:
    """Build the PDF shelf from the private Hugging Face dataset file list."""
    target = CACHE / "library_manifest.json"
    if target.is_file():
        return True
    token = os.environ.get("HF_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = requests.get(
            f"https://huggingface.co/api/datasets/{HF_LIBRARY_REPO}/tree/main",
            headers=headers,
            params={"recursive": "true"},
            timeout=HF_TREE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        files = response.json()
        if not isinstance(files, list):
            return False
        paths = sorted(
            {
                item["path"]
                for item in files
                if isinstance(item, dict)
                and isinstance(item.get("path"), str)
                and item["path"].lower().endswith(".pdf")
            }
        )
        if not paths:
            return False
        target.write_text(json.dumps({"hf_paths": paths}), encoding="utf-8")
        return True
    except (requests.RequestException, ValueError, OSError):
        return False


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
        ROOT / name,
        ROOT / "data" / name,
        ROOT.parent / name,
        ROOT.parent / "data" / "catalogs" / name,
    ):
        if candidate.is_file():
            return candidate
    return None


def hydrate() -> dict[str, str]:
    """Load the graph and library shelf from Hugging Face into runtime storage."""
    CACHE.mkdir(parents=True, exist_ok=True)
    source = "unavailable"
    loaded = 0
    if os.environ.get("VERCEL"):
        loaded = _hydrate_from_hugging_face()
        _hydrate_hf_manifest()
        if loaded == len(HF_SOURCE_FILES) and (CACHE / "library_manifest.json").is_file():
            return {"source": "huggingface", "cache": str(CACHE)}
    auth = _headers()
    if auth:
        base = auth.pop("url")
        for name in FILES:
            target = CACHE / name
            if target.is_file() and os.environ.get("VERCEL"):
                continue
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
        if all((CACHE / name).is_file() for name in FILES):
            source = "huggingface" if os.environ.get("VERCEL") else "supabase"

    if source in {"supabase", "huggingface"}:
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
    return {
        "source": "local" if (CACHE / "okf_graph.json").is_file() else "missing",
        "cache": str(CACHE),
    }


def pearson_page_url(book: dict, page: int = 1) -> str:
    """Pearson reader URL with a page hint; Pearson can restore last-read position."""
    page_n = max(1, int(page or 1))
    if book.get("page_count") and int(book["page_count"]) > 1:
        page_n = min(page_n, int(book["page_count"]))
    viewer = (
        "pdfviewer.html" if str(book.get("book_type") or "").lower() == "pdf" else "viewer.html"
    )
    sub = str(book.get("subscription_id") or "").strip()
    sub_query = f"&subscriptionId={sub}" if sub else ""
    page_part = f"/page/{page_n}"
    # Pearson's reader otherwise restores its saved position after SSO. Its
    # skipLastRead query flag makes the page in the fragment take precedence.
    return f"https://ebooks.elibrary.in.pearson.com/wr/{viewer}?version=1.0.317.1{sub_query}&skipLastRead=true#book/{book.get('id')}{page_part}"


def public_book(book: dict) -> dict:
    """Browser payload. Subscription ids stay on the server."""
    return {
        "id": book.get("id"),
        "title": book.get("title"),
        "author": book.get("author") or "Institutional collection",
        "year": "",
        "domain": book.get("domain") or "CS & AI",
        "desc": "Institutional e-book. Pearson may ask you to sign in before opening the title.",
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
