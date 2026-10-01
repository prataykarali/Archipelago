"""Static asset routes for the hosted UI.

One concern: serving the UI tree and its asset directory, and refusing to leak
dotfiles, source directories or API paths through the catch-all.
"""
from __future__ import annotations

from flask import Flask, jsonify, send_from_directory

from ..config import ASSET, UI
from ..context import AppContext

API_PREFIX = "api/"


def register(app: Flask, ctx: AppContext) -> None:
    """Register static routes on ``app``."""

    @app.get("/ui/assets/<path:filename>")
    def ui_assets(filename):
        return send_from_directory(ASSET, filename)

    @app.get("/<path:filename>")
    def static_files(filename):
        if filename.startswith(".") or filename.startswith(API_PREFIX) or ".." in filename:
            return jsonify({"error": "not_found"}), 404
        if (UI / filename).is_file():
            return send_from_directory(UI, filename)
        return jsonify({"error": "not_found"}), 404
