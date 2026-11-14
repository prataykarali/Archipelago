"""Static asset routes for the hosted UI.

One concern: serving the UI tree and its asset directory, and refusing to leak
dotfiles, source directories or API paths through the catch-all.
"""

from __future__ import annotations

from flask import Flask, jsonify, send_from_directory

from ..config import ASSET, UI
from ..context import AppContext
from ..page_fragments import assembled_page

API_PREFIX = "api/"


STATIC_CACHE_MAX_AGE = 300


def register(app: Flask, ctx: AppContext) -> None:
    """Register static routes on ``app``."""

    @app.get("/ui/assets/<path:filename>")
    @app.get("/assets/<path:filename>")
    def ui_assets(filename):
        if (ASSET / filename).is_file():
            resp = send_from_directory(ASSET, filename)
            resp.headers["Cache-Control"] = f"public, max-age={STATIC_CACHE_MAX_AGE}"
            return resp
        if (UI / "assets" / filename).is_file():
            resp = send_from_directory(UI / "assets", filename)
            resp.headers["Cache-Control"] = f"public, max-age={STATIC_CACHE_MAX_AGE}"
            return resp
        return jsonify({"error": "not_found"}), 404

    @app.get("/<path:filename>")
    def static_files(filename):
        if (
            filename.startswith(".")
            or filename.startswith(API_PREFIX)
            or ".." in filename
            or filename == "research.html"
        ):
            return jsonify({"error": "not_found"}), 404
        if filename in {"index.html", "library.html"}:
            return assembled_page(UI, filename)
        if (UI / filename).is_file():
            resp = send_from_directory(UI, filename)
            resp.headers["Cache-Control"] = f"public, max-age={STATIC_CACHE_MAX_AGE}"
            return resp
        return jsonify({"error": "not_found"}), 404
