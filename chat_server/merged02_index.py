"""Auto-split from monolith — blocks are verbatim."""

from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from flask import redirect, request, send_from_directory

from .merged01_repo_root import (  # noqa: F401
    _ASSET_ROOTS,
    ASSETS_DIR,
    STATIC_DIR,
    _has_valid_auth_session,
    _is_auth_enforced,
    app,
)
from .page_fragments import assembled_page


@app.route("/")
def index():
    """Serves the landing page (Built for the curious) — publicly accessible."""
    return send_from_directory(str(STATIC_DIR), "landing.html")


@app.route("/landing")
def landing():
    """Serves the cinematic landing page — publicly accessible."""
    return send_from_directory(str(STATIC_DIR), "landing.html")


@app.route("/chat")
@app.route("/chat/")
def chat_ui():
    """Serves the main Chat interface index.html on the same port.

    Reading and asking are open to every campus user; only mutating surfaces
    (graph console, librarian intake) stay role-gated.
    """
    return assembled_page(STATIC_DIR, "index.html")


@app.route("/library_showcase_3d.js")
def library_showcase_3d():
    """Serve 3D showcase engine."""
    return send_from_directory(str(STATIC_DIR), "library_showcase_3d.js")


@app.route("/library")
@app.route("/library/")
def library_details():
    """Serves library details (current institutional data snapshot).

    The catalogue is public knowledge; only librarian management actions inside
    the page remain role-gated.
    """
    return assembled_page(STATIC_DIR, "library.html")


@app.route("/reader.html")
def reader_static_page():
    """Serves the dedicated PDF.js reader page (open, like every citation link)."""
    return send_from_directory(str(STATIC_DIR), "reader.html")


def _requested_page(value: str | None) -> int:
    try:
        return max(1, min(int(value or 1), 100000))
    except (TypeError, ValueError):
        return 1


def _with_page_fragment(target_url: str, page: int) -> str:
    """Preserve a requested page in provider-specific reader URLs."""
    parsed = urlsplit(target_url)
    if "pearson" in parsed.netloc.lower():
        fragment = re.sub(r"/page/\d+", "", parsed.fragment)
        fragment = f"{fragment}/page/{page}" if fragment else f"page/{page}"
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, fragment))
    if parsed.path.startswith(("/read/", "/open/")):
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["page"] = str(page)
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
        )
    return target_url


@app.route("/read")
@app.route("/read/<path:resource_id>")
@app.route("/read/book/<path:resource_id>")
def reader_view(resource_id: str = ""):
    """Dedicated internal PDF reader view (PDF.js).
    Supports ?doc=PATH&page=N for direct page jumping.
    If resource is Pearson, redirects to /open/<id>?page=N to launch external flow.
    Open to every campus user: this is where citation page links land.
    """
    doc_arg = (
        request.args.get("doc")
        or request.args.get("id")
        or request.args.get("src")
        or request.args.get("book")
        or ""
    )
    clean_id = (resource_id or doc_arg).removeprefix("book/").strip()
    page = _requested_page(request.args.get("page"))

    # Check if Pearson book
    if clean_id:
        try:
            from archipelago.resolver.pearson import _fuzzy_match_book, _load_pearson_catalog

            cat = _load_pearson_catalog()
            if (
                _fuzzy_match_book(cat, clean_id, clean_id, clean_id)
                or "pearson" in clean_id.lower()
                or "0fcd531f" in clean_id
            ):
                return redirect(f"/open/{quote(clean_id, safe='/')}?page={page}", code=302)
        except Exception:
            pass

    return send_from_directory(str(STATIC_DIR), "reader.html")


@app.route("/performance")
@app.route("/performance/")
def performance_dashboard():
    """Serves the Performance Metrics ops dashboard."""
    return send_from_directory(str(STATIC_DIR), "performance.html")


@app.route("/safety")
@app.route("/safety/")
def safety_dashboard():
    """Serves the Safety Layer / Routing Gate dashboard."""
    return send_from_directory(str(STATIC_DIR), "safety.html")


@app.route("/login")
@app.route("/login/")
def login_page():
    """Serves the authentication login page."""
    return send_from_directory(str(STATIC_DIR), "login.html")


@app.route("/ui/assets/<path:filename>")
def media_assets(filename):
    """Serve button icons (buttons/) and videos (ui/assets/) under /ui/assets/."""
    safe = Path(filename)
    if ".." in safe.parts:
        return ("Not found", 404)
    for root in _ASSET_ROOTS:
        candidate = root / filename
        if candidate.is_file() or candidate.is_symlink():
            return send_from_directory(str(root), filename, conditional=True)
    fallback = _ASSET_ROOTS[0] if _ASSET_ROOTS else ASSETS_DIR
    return send_from_directory(str(fallback), filename, conditional=True)


@app.route("/<path:filename>")
def static_files(filename):
    """Serves any static resources within the chat_ui directory"""
    if filename in {"index.html", "library.html"}:
        return assembled_page(STATIC_DIR, filename)
    return send_from_directory(str(STATIC_DIR), filename)
