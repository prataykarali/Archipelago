"""
Archipelago Chat UI Server
Serves the premium, standalone chat workspace UI on port 5052.
"""

from collections.abc import Iterator

from flask import Flask, Response, request, send_from_directory
from flask.typing import ResponseReturnValue
import mimetypes
import os
from pathlib import Path

import requests as _requests

mimetypes.add_type("video/mp4", ".mp4")

_STREAM_CHUNK_BYTES = 64 * 1024  # 64 KiB chunks for streaming proxy responses
_DEFAULT_INFERENCE_CHAT_URL = "http://127.0.0.1:5051/api/chat"
INFERENCE_CHAT_URL = os.environ.get(
    "ARCHIPELAGO_INFERENCE_URL", _DEFAULT_INFERENCE_CHAT_URL
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "chat_ui"
# buttons/ (icons) + ui/assets/ (videos) both map to /ui/assets/*
_ASSET_ROOTS = tuple(
    p for p in (BASE_DIR / "buttons", BASE_DIR / "ui" / "assets") if p.is_dir()
)
# Canonical librarian avatar videos — ASSETS_DIR is the asset root holding them.
_VIDEO_ASSET_NAMES = ("library_hi.mp4", "library_think.mp4", "archi_main.mp4")
ASSETS_DIR = next(
    (
        root
        for root in _ASSET_ROOTS
        if all((root / name).exists() for name in _VIDEO_ASSET_NAMES)
    ),
    _ASSET_ROOTS[-1] if _ASSET_ROOTS else (BASE_DIR / "ui" / "assets"),
)

app = Flask(__name__, static_folder=str(STATIC_DIR))

# CORS configuration
@app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response

@app.route("/")
def index():
    """Serves the cinematic landing page (single CTA into chat)."""
    return send_from_directory(str(STATIC_DIR), "landing.html")


@app.route("/chat")
@app.route("/chat/")
def chat_ui():
    """Serves the main Chat interface index.html on the same port."""
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/library")
@app.route("/library/")
def library_details():
    """Serves library details (current institutional data snapshot)."""
    return send_from_directory(str(STATIC_DIR), "library.html")


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


@app.route("/api/library/data")
def library_data():
    """Returns library catalog + e-book shelf + full resource inventory (no secrets)."""
    from archipelago.inference.library_catalog_api import build_library_data_payload

    return build_library_data_payload(BASE_DIR)


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat_proxy() -> ResponseReturnValue:
    """Proxy chat prompts to the upstream inference server, streaming the reply."""
    if request.method == "OPTIONS":
        return ("", 204)

    payload = request.get_json(silent=True) or {}
    try:
        upstream = _requests.post(INFERENCE_CHAT_URL, json=payload, stream=True)
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502

    def stream_upstream() -> Iterator[bytes]:
        for chunk in upstream.iter_content(chunk_size=_STREAM_CHUNK_BYTES):
            yield chunk

    return Response(
        stream_upstream(),
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/octet-stream"),
    )


def _inference_base() -> str:
    """Derive inference origin from ARCHIPELAGO_INFERENCE_URL (…/api/chat)."""
    url = INFERENCE_CHAT_URL.rstrip("/")
    if url.endswith("/api/chat"):
        return url[: -len("/api/chat")]
    if url.endswith("/api/chat/"):
        return url[: -len("/api/chat/")]
    return url


@app.route("/api/dashboards/<path:subpath>", methods=["GET", "POST", "OPTIONS"])
def dashboards_proxy(subpath: str) -> ResponseReturnValue:
    """Proxy performance/safety dashboard APIs to the inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/dashboards/{subpath}"
    try:
        if request.method == "GET":
            upstream = _requests.get(target, params=request.args, timeout=15)
        else:
            upstream = _requests.post(
                target,
                json=request.get_json(silent=True) or {},
                timeout=30,
            )
    except Exception as exc:
        app.logger.warning("Dashboard upstream unreachable: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )


@app.route("/<path:filename>")
def static_files(filename):
    """Serves any static resources within the chat_ui directory"""
    return send_from_directory(str(STATIC_DIR), filename)


if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Archipelago Chat UI Server                      ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Landing:      http://localhost:5052/            ║")
    print("║  Chat:         http://localhost:5052/chat        ║")
    print("║  Library:      http://localhost:5052/library     ║")
    print("║  Performance:  http://localhost:5052/performance ║")
    print("║  Safety:       http://localhost:5052/safety      ║")
    print("╚══════════════════════════════════════════════════╝\n")
    app.run(host=os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1"), port=5052, debug=False)
