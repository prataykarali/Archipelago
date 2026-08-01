"""
Archipelago Chat UI Server
Serves the premium, standalone chat workspace UI on port 5152.
"""

from flask import Flask, send_from_directory, request, Response
import os
import mimetypes
from pathlib import Path
import requests as _requests
from dotenv import load_dotenv

load_dotenv()  # reads .env locally; no-op on Northflank

mimetypes.add_type("video/mp4", ".mp4")

_WATCHDOG = "/tmp/archipelago_last_request"
BASE_DIR = Path(__file__).parent
REPO_ROOT = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "chat_ui"
# Multi-root /ui/assets lookup:
#   1) repo/buttons          — icon PNGs (graph_btn, brain_btn, …)
#   2) repo/ui/assets        — hero + avatar videos (final_archi, library_*)
#   3) frontend/ui/assets    — mixed legacy copies / symlinks
_ASSET_ROOTS = tuple(
    p for p in (
        REPO_ROOT / "buttons",
        REPO_ROOT / "ui" / "assets",
        BASE_DIR / "ui" / "assets",
    )
    if p.is_dir()
)
ASSETS_DIR = _ASSET_ROOTS[0] if _ASSET_ROOTS else (REPO_ROOT / "ui" / "assets")
_STREAM_CHUNK_BYTES = 1

app = Flask(__name__, static_folder=str(STATIC_DIR))
# Default matches inference_app (:5051). SoFerence booth can override to :5151
# via ARCHIPELAGO_INFERENCE_URL in the systemd unit / env.
_API_TARGET = os.environ.get("ARCHIPELAGO_INFERENCE_URL", "http://127.0.0.1:5051")


# CORS configuration
@app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response

@app.route("/")
def index():
    """Serves the main Chat interface index.html"""
    try:
        os.utime(_WATCHDOG, None)
    except Exception:
        pass
    resp = send_from_directory(str(STATIC_DIR), "index.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

AURELLIS_DIR = BASE_DIR / "ui" / "aurellis"
BRIGEND_DIR = BASE_DIR / "ui" / "brigend"
# Fonts live directly under ui/warfield/ (WARFIELD-Regular.ttf, WARFIELD-Bold.ttf).
WARFIELD_DIR = BASE_DIR / "ui" / "warfield"

@app.route("/ui/assets/<path:filename>")
def media_assets(filename):
    """Serve button icons + hero/avatar videos same-origin.

    Looks up ``filename`` across buttons/, ui/assets/, and frontend/ui/assets/
    so icons and videos both resolve under ``/ui/assets/<name>``.
    """
    try:
        os.utime(_WATCHDOG, None)
    except Exception:
        pass
    # Reject path traversal
    safe = Path(filename)
    if ".." in safe.parts:
        return Response("Not found", status=404)
    for root in _ASSET_ROOTS:
        candidate = root / filename
        if candidate.is_file() or candidate.is_symlink():
            return send_from_directory(str(root), filename, conditional=True)
    # Fall through to first root (Flask 404 if missing)
    fallback = _ASSET_ROOTS[0] if _ASSET_ROOTS else ASSETS_DIR
    return send_from_directory(str(fallback), filename, conditional=True)

@app.route("/ui/aurellis/<path:filename>")
def aurellis_font_assets(filename):
    """Serves Aurellis font assets same-origin."""
    try:
        os.utime(_WATCHDOG, None)
    except Exception:
        pass
    return send_from_directory(str(AURELLIS_DIR), filename, conditional=True)

@app.route("/ui/brigend/<path:filename>")
def brigend_font_assets(filename):
    """Serves Brigend font assets same-origin."""
    try:
        os.utime(_WATCHDOG, None)
    except Exception:
        pass
    return send_from_directory(str(BRIGEND_DIR), filename, conditional=True)

@app.route("/ui/warfield/<path:filename>")
def warfield_font_assets(filename):
    """Serves Warfield font assets same-origin."""
    try:
        os.utime(_WATCHDOG, None)
    except Exception:
        pass
    return send_from_directory(str(WARFIELD_DIR), filename, conditional=True)


# NOTE: Specific proxies MUST be registered before the catch-all static route.
# A stale process that only had ``/<path>`` returned Flask HTML 404 for every
# book/PDF open (iframe "Not Found") even when inference had the file.

@app.route("/pdfs/<path:filename>")
def proxy_pdf(filename):
    """Stream corpus PDFs from the inference server (5151) same-origin.

    The chat UI (5152) builds PDF viewer URLs against window.location.origin,
    but the ``/pdfs/<path>`` route only lives on the inference server. Without
    this proxy the reading-mode iframe and Page/Split tabs hit a 404 and
    render blank. Stream the upstream bytes (with remote 302 fallback handled
    by the inference server) so page links and book clicks resolve.
    """
    try:
        os.utime(_WATCHDOG, None)
    except Exception:
        pass
    try:
        upstream = _requests.get(
            _API_TARGET + "/pdfs/" + filename,
            stream=True,
            timeout=120,
            allow_redirects=True,
        )
        if upstream.status_code == 404:
            # Surface the inference server's "not in pilot corpus" JSON so the
            # viewer can show an honest "PDF Not Available" banner.
            return Response(
                upstream.content,
                status=404,
                content_type=upstream.headers.get("Content-Type", "application/json"),
                headers={"Access-Control-Allow-Origin": "*"},
            )
        content_type = upstream.headers.get("Content-Type") or "application/pdf"
        # Prefer PDF content-type even when upstream omits it after redirects.
        if filename.lower().endswith(".pdf") and "html" in content_type.lower():
            content_type = "application/pdf"
        return Response(
            upstream.iter_content(chunk_size=65536),
            status=upstream.status_code,
            content_type=content_type,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except Exception as exc:
        return Response(
            f'{{"error":"{str(exc)[:200]}"}}',
            status=502,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def proxy_chat():
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        return resp
    try:
        upstream = _requests.post(
            _API_TARGET + "/api/chat",
            json=request.get_json(silent=True) or {},
            headers={k: v for k, v in request.headers if k.lower() != "host"},
            stream=True,
            # P0: Ollama 0.8B + queue can exceed 120s on multi-query demos
            timeout=(10, 180),
        )
        def generate():
            try:
                # Flush each chunk immediately so tokens reach the browser as
                # they are produced instead of being buffered into one frame.
                for chunk in upstream.iter_content(chunk_size=_STREAM_CHUNK_BYTES):
                    if chunk:
                        yield chunk
            except Exception:
                pass
            finally:
                upstream.close()
        resp = Response(
            generate(),
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "text/event-stream"),
            headers={
                "Access-Control-Allow-Origin": "*",
                # Disable proxy/HTTP buffering so the typewriter stream is live.
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache, no-transform",
            },
        )
        resp.direct_passthrough = True
        return resp
    except Exception as exc:
        return Response(f'{{"error":"{str(exc)[:200]}"}}', status=502, mimetype="application/json", headers={"Access-Control-Allow-Origin": "*"})


@app.route("/api/readiness", methods=["GET"])
def proxy_readiness():
    try:
        upstream = _requests.get(_API_TARGET + "/api/readiness", timeout=10)
        return Response(upstream.content, status=upstream.status_code, content_type=upstream.headers.get("Content-Type", "application/json"), headers={"Access-Control-Allow-Origin": "*"})
    except Exception as exc:
        return Response('{"status":"down"}', status=502, mimetype="application/json", headers={"Access-Control-Allow-Origin": "*"})


@app.route("/api/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
def proxy_all(subpath):
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        return resp
    try:
        method = request.method
        url = f"{_API_TARGET}/api/{subpath}"
        headers = {k: v for k, v in request.headers if k.lower() != "host"}
        if method == "GET":
            upstream = _requests.get(url, params=request.args, headers=headers, timeout=30)
        else:
            upstream = _requests.request(method, url, json=request.get_json(silent=True), headers=headers, timeout=30)
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "application/json"),
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except Exception as exc:
        return Response(f'{{"error":"{str(exc)[:200]}"}}', status=502, mimetype="application/json", headers={"Access-Control-Allow-Origin": "*"})


@app.route("/<path:filename>")
def static_files(filename):
    """Serves static resources within the chat_ui directory.

    Never intercepts /pdfs/* or /api/* — those have dedicated proxy routes above.
    """
    try:
        os.utime(_WATCHDOG, None)
    except Exception:
        pass
    # Defensive: if a reverse-proxy rewrites oddly, do not 404-HTML a PDF path.
    if filename.startswith("pdfs/") or filename.startswith("api/"):
        return Response(
            '{"error":"route misconfigured — use /pdfs/ or /api/ proxies"}',
            status=404,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )
    return send_from_directory(str(STATIC_DIR), filename)

if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Archipelago Chat UI Server                      ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Open: http://localhost:5152                      ║")
    print("╚══════════════════════════════════════════════════╝\n")
    port_val = int(os.environ.get("PORT", "5152"))
    app.run(host=os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1"), port=port_val, debug=False)
