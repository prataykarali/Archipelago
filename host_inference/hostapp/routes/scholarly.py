"""Serve the dated scholarly discovery snapshot to hosted library pages."""

from __future__ import annotations

import json
import os
from threading import Lock
import time
from typing import Any

from flask import Flask, jsonify
from flask.typing import ResponseReturnValue
import requests

from ..config import HOST_ROOT
from ..context import AppContext
from ..research_access import staff_allowed

SNAPSHOT_PATH = HOST_ROOT / "fixtures/live_scholarly_manifest.json"
DEFAULT_REPO = "Prataykarali/graphier"
CACHE_SECONDS = 300
HTTP_TIMEOUT_SECONDS = 6
_cache_lock = Lock()
_cache: dict[str, object] = {"expires": 0.0, "payload": None}


def _snapshot() -> tuple[dict[str, Any] | None, str]:
    """Prefer the published manifest; use packaged data as a dated fallback."""
    now = time.monotonic()
    with _cache_lock:
        cached = _cache["payload"]
        expires = _cache["expires"]
        if isinstance(cached, dict) and isinstance(expires, (int, float)) and now < expires:
            return cached, "published_cache"

    repo = os.environ.get("ARCHIPELAGO_SCHOLARLY_HF_REPO", DEFAULT_REPO)
    url = (
        f"https://huggingface.co/datasets/{repo}/resolve/main/catalogs/live_scholarly_manifest.json"
    )
    headers: dict[str, str] = {}
    token = os.environ.get("HF_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("source_status"), dict):
            with _cache_lock:
                _cache["payload"] = payload
                _cache["expires"] = now + CACHE_SECONDS
            return payload, "published_snapshot"
    except (requests.RequestException, ValueError):
        pass

    if SNAPSHOT_PATH.is_file():
        try:
            payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("source_status"), dict):
                return payload, "packaged_snapshot"
        except (OSError, ValueError):
            pass
    return None, "unavailable"


def register(app: Flask, ctx: AppContext) -> None:
    """Register a read-only manifest endpoint with explicit snapshot status."""

    @app.get("/api/scholarly/snapshot")
    def scholarly_snapshot() -> ResponseReturnValue:
        principal, _error = ctx.auth.principal()
        if principal is None or not principal.get("id"):
            return jsonify({"error": "unauthorized"}), 401
        if not staff_allowed(principal.get("role")):
            return jsonify({"error": "forbidden"}), 403
        if os.getenv("ARCHIPELAGO_RESEARCH_ENABLED", "0").lower() not in {"1", "true", "yes"}:
            return jsonify({"error": "research_disabled"}), 503
        payload, delivery = _snapshot()
        if payload is None:
            return jsonify({"status": "unavailable", "items": [], "resources": []}), 503
        return jsonify({**payload, "delivery": delivery})
