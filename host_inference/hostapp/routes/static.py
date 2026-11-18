"""Static asset routes for the hosted UI.

One concern: serving the UI tree and its asset directory, and refusing to leak
dotfiles, source directories or API paths through the catch-all.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, make_response, send_from_directory

from ..config import ASSET, UI
from ..context import AppContext
from ..page_fragments import assembled_page

API_PREFIX = "api/"
STATIC_CACHE_MAX_AGE = 300
_BLOCKED_EXTENSIONS = (
    ".md",
    ".bak",
    ".old",
    ".orig",
    ".tmp",
    ".swp",
    ".sqlite3",
    ".sqlite",
    ".db",
    ".py",
    ".pyc",
    ".env",
    ".log",
    ".sql",
    ".ini",
    ".cfg",
    ".toml",
    ".yaml",
    ".yml",
)
_BLOCKED_NAMES = frozenset(
    {
        "research.html",
        "audit.md",
        "agents.md",
        "claude.md",
        "vercel.json",
        "requirements.txt",
    }
)


def _is_blocked_static_path(filename: str) -> bool:
    """Return True if ``filename`` targets dotfiles, backups, AUDIT.md, or traversal."""
    if not filename or "\\" in filename or ".." in filename or filename.startswith("/"):
        return True
    if filename.startswith(API_PREFIX):
        return True
    parts = [part for part in filename.split("/") if part]
    if not parts:
        return True
    for part in parts:
        lower_part = part.lower()
        if part.startswith(".") or part.endswith("~"):
            return True
        if "stripped_backup" in lower_part or lower_part in _BLOCKED_NAMES:
            return True
    lowered = filename.lower()
    return lowered in _BLOCKED_NAMES or lowered.endswith(_BLOCKED_EXTENSIONS)


def _safe_file_under(base_dir: Path, filename: str) -> bool:
    try:
        base_resolved = base_dir.resolve()
        candidate = (base_resolved / filename).resolve()
        return candidate.is_relative_to(base_resolved) and candidate.is_file()
    except (OSError, ValueError):
        return False


def register(app: Flask, ctx: AppContext) -> None:
    """Register static routes on ``app``."""

    @app.get("/ui/assets/<path:filename>")
    @app.get("/assets/<path:filename>")
    def ui_assets(filename):
        if _is_blocked_static_path(filename):
            return jsonify({"error": "not_found"}), 404
        if _safe_file_under(ASSET, filename):
            resp = send_from_directory(ASSET, filename)
            resp.headers["Cache-Control"] = f"public, max-age={STATIC_CACHE_MAX_AGE}"
            return resp
        if _safe_file_under(UI / "assets", filename):
            resp = send_from_directory(UI / "assets", filename)
            resp.headers["Cache-Control"] = f"public, max-age={STATIC_CACHE_MAX_AGE}"
            return resp
        return jsonify({"error": "not_found"}), 404

    @app.get("/<path:filename>")
    def static_files(filename):
        if _is_blocked_static_path(filename):
            return jsonify({"error": "not_found"}), 404
        if filename in {"index.html", "library.html"}:
            resp = make_response(assembled_page(UI, filename))
            resp.headers["Cache-Control"] = "private, no-store"
            return resp
        if _safe_file_under(UI, filename):
            resp = send_from_directory(UI, filename)
            if filename.lower().endswith(".html"):
                resp.headers["Cache-Control"] = "private, no-store"
            else:
                resp.headers["Cache-Control"] = f"public, max-age={STATIC_CACHE_MAX_AGE}"
            return resp
        return jsonify({"error": "not_found"}), 404
