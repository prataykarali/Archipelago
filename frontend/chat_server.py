"""
Archipelago Chat UI Server
Serves the premium, standalone chat workspace UI on port 5152.
"""

from flask import Flask, send_from_directory, request, Response, jsonify
import os
import sys
import mimetypes
from pathlib import Path
import requests as _requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
REPO_ROOT = BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")  # reads .env locally; no-op on Northflank

mimetypes.add_type("video/mp4", ".mp4")

_WATCHDOG = "/tmp/archipelago_last_request"
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
# Default matches the inference_app pilot port (:5151). Override via
# ARCHIPELAGO_INFERENCE_URL (e.g. legacy :5051 boxen).
_API_TARGET = os.environ.get("ARCHIPELAGO_INFERENCE_URL", "http://127.0.0.1:5051")


# CORS configuration
@app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response

def _no_cache_html(filename: str):
    """Serve an HTML shell from chat_ui with cache-busting headers."""
    try:
        os.utime(_WATCHDOG, None)
    except Exception:
        pass
    resp = send_from_directory(str(STATIC_DIR), filename)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/")
def index():
    """Serves the landing page (Built for the curious) with direct entry into chat and library."""
    return _no_cache_html("landing.html")


@app.route("/landing")
def landing():
    """Serves the cinematic landing page."""
    return _no_cache_html("landing.html")


@app.route("/login")
def login():
    """Serve the Supabase-backed Archipelago sign-in page."""
    return _no_cache_html("login.html")


@app.route("/auth_bridge.js")
def auth_bridge():
    """Serve browser auth wiring with no-cache headers."""
    return _no_cache_html("auth_bridge.js")


@app.route("/chat")
@app.route("/chat/")
def chat_ui():
    """Serves the main Chat interface index.html on the same port."""
    return _no_cache_html("index.html")


@app.route("/library")
@app.route("/library/")
def library_details():
    """Serves library details (current institutional data snapshot)."""
    return _no_cache_html("library.html")


@app.route("/performance")
@app.route("/performance/")
def performance_dashboard():
    """Serves the Performance Metrics ops dashboard."""
    return _no_cache_html("performance.html")


@app.route("/safety")
@app.route("/safety/")
def safety_dashboard():
    """Serves the Safety Layer / Routing Gate dashboard."""
    return _no_cache_html("safety.html")


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


@app.route("/api/auth/config", methods=["GET"])
@app.route("/api/auth/me", methods=["GET"])
def proxy_auth() -> Response:
    """Relay browser auth configuration and identity to inference, with local fallback."""
    try:
        upstream = _requests.get(
            _API_TARGET + request.path,
            headers={k: v for k, v in request.headers if k.lower() != "host"},
            timeout=15,
        )
        if upstream.status_code == 200:
            return Response(
                upstream.content,
                status=upstream.status_code,
                content_type=upstream.headers.get("Content-Type", "application/json"),
                headers={"Access-Control-Allow-Origin": "*"},
            )
    except _requests.RequestException:
        pass

    # Upstream failed or returned non-200; fall back to local supabase_auth
    try:
        from src.archipelago import supabase_auth
        if request.path == "/api/auth/config":
            return jsonify(supabase_auth.public_config())
        elif request.path == "/api/auth/me":
            if not supabase_auth.is_auth_required():
                return jsonify({"authenticated": False, "auth_required": False})
            principal, error = supabase_auth.authenticate_request(request)
            if principal is None:
                return jsonify({"error": "unauthorized", "detail": error}), 401
            return jsonify({
                "authenticated": True,
                "user_id": principal.user_id,
                "username": principal.username,
                "role": principal.role,
            })
    except Exception as exc:
        app.logger.warning("Local supabase_auth error: %s", exc)

    return Response(
        '{"error":"authentication service unavailable"}',
        status=502,
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.route("/api/users", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/users/<user_id>", methods=["PUT", "DELETE", "OPTIONS"])
def manage_users_api(user_id=None):
    """User management endpoints for librarian and administrator."""
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-User-Role,X-User-Name,X-User-Id"
        return resp

    from src.archipelago import supabase_auth
    principal, auth_err = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": auth_err or "Authentication required"}), 401

    if request.method == "GET":
        users, err = supabase_auth.list_managed_users(principal)
        if err:
            return jsonify({"error": "forbidden", "detail": err}), 403
        return jsonify({"users": users, "requester": {"role": principal.role, "user_id": principal.user_id}})

    elif request.method == "POST":
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.create_managed_user(principal, data)
        if err:
            return jsonify({"error": "bad_request", "detail": err}), 400
        return jsonify({"success": True, "user": user}), 201

    elif request.method == "PUT":
        if not user_id:
            return jsonify({"error": "missing_user_id"}), 400
        data = request.get_json(silent=True) or {}
        user, err = supabase_auth.update_managed_user(principal, user_id, data)
        if err:
            return jsonify({"error": "update_failed", "detail": err}), 400
        return jsonify({"success": True, "user": user})

    elif request.method == "DELETE":
        if not user_id:
            return jsonify({"error": "missing_user_id"}), 400
        ok, err = supabase_auth.delete_managed_user(principal, user_id)
        if err:
            return jsonify({"error": "delete_failed", "detail": err}), 400
        return jsonify({"success": True})

    return jsonify({"error": "method_not_allowed"}), 405




@app.route("/api/chat/diagnostic-mcqs", methods=["GET", "POST", "OPTIONS"])
def proxy_diagnostic_mcqs():
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        return resp
    try:
        url = f"{_API_TARGET}/api/chat/diagnostic-mcqs"
        if request.method == "GET":
            upstream = _requests.get(url, params=request.args, timeout=15)
        else:
            upstream = _requests.post(url, json=request.get_json(silent=True) or {}, timeout=15)
        return Response(upstream.content, status=upstream.status_code, content_type=upstream.headers.get("Content-Type", "application/json"), headers={"Access-Control-Allow-Origin": "*"})
    except Exception as exc:
        return jsonify({"success": False, "available": False, "error": str(exc), "badge": "Personalized assessment temporarily unavailable."}), 200


@app.route("/api/chat/verify-mcq", methods=["POST", "OPTIONS"])
def proxy_verify_mcq():
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        return resp
    try:
        url = f"{_API_TARGET}/api/chat/verify-mcq"
        upstream = _requests.post(url, json=request.get_json(silent=True) or {}, timeout=30)
        return Response(upstream.content, status=upstream.status_code, content_type=upstream.headers.get("Content-Type", "application/json"), headers={"Access-Control-Allow-Origin": "*"})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


@app.route("/api/chat/adaptive-step", methods=["POST", "OPTIONS"])
def proxy_adaptive_step():
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        return resp
    try:
        url = f"{_API_TARGET}/api/chat/adaptive-step"
        upstream = _requests.post(url, json=request.get_json(silent=True) or {}, timeout=30)
        return Response(upstream.content, status=upstream.status_code, content_type=upstream.headers.get("Content-Type", "application/json"), headers={"Access-Control-Allow-Origin": "*"})
    except Exception as exc:
        return jsonify({"completed": False, "error": str(exc)}), 502


@app.route("/api/readiness", methods=["GET"])
def proxy_readiness():
    try:
        upstream = _requests.get(_API_TARGET + "/api/readiness", timeout=10)
        return Response(upstream.content, status=upstream.status_code, content_type=upstream.headers.get("Content-Type", "application/json"), headers={"Access-Control-Allow-Origin": "*"})
    except Exception as exc:
        return Response('{"status":"down"}', status=502, mimetype="application/json", headers={"Access-Control-Allow-Origin": "*"})


@app.route("/api/library/data")
def library_data():
    """Returns library catalog + e-book shelf + full resource inventory (no secrets).

    Mirrors root chat_server.py so /library hydrates without the root server.
    Always returns JSON (never blank the page on import errors).
    """
    try:
        from archipelago.inference.library_catalog_api import build_library_data_payload

        return jsonify(build_library_data_payload(REPO_ROOT))
    except Exception as exc:
        # Fallback: read CSVs directly so the library page still shows books.
        app.logger.exception("library_catalog_api failed; using CSV fallback: %s", exc)
        return jsonify(_library_data_csv_fallback(REPO_ROOT))


def _library_data_csv_fallback(repo_root: Path) -> dict:
    """Minimal catalog payload from docs/library CSVs (no archipelago import)."""
    import csv

    docs_dir = repo_root / "docs" / "library"
    derived_dir = docs_dir / "derived"

    def read_csv(path: Path) -> list[dict]:
        if not path.is_file():
            return []
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    subject_counts = read_csv(derived_dir / "subject_title_counts.csv")
    subject_titles = read_csv(derived_dir / "subject_titles.csv")
    journal_issues = read_csv(derived_dir / "journal_issues.csv")
    holdings_slice = read_csv(derived_dir / "holdings_slice.csv")
    hardcopy = read_csv(docs_dir / "hardcopy_textbooks.csv")
    ebooks = read_csv(docs_dir / "ebooks_and_reference.csv")
    inventory = read_csv(derived_dir / "resource_inventory.csv")

    ebook_shelf = []
    for row in ebooks:
        item = dict(row)
        item["id"] = (row.get("id") or "").strip()
        item["readable"] = str(row.get("readable") or "0").strip() in {"1", "true", "yes"}
        item["has_pdf"] = bool((row.get("pdf") or "").strip())
        item["is_pearson"] = (row.get("source") or "") == "pearson_elibrary"
        ebook_shelf.append(item)

    unique_journals = {
        (row.get("journal_title") or "").strip().lower()
        for row in journal_issues
        if (row.get("journal_title") or "").strip()
    }
    total_copies = 0
    available_copies = 0
    for row in holdings_slice:
        try:
            total_copies += int(row.get("no_of_copies") or "0")
            available_copies += int(row.get("available_copies") or "0")
        except ValueError:
            pass

    return {
        "subject_counts": subject_counts,
        "subject_titles": subject_titles,
        "journals": {
            "titles_count": len(unique_journals),
            "issues_count": len(journal_issues),
            "issues": journal_issues,
        },
        "holdings": {
            "total_copies": total_copies,
            "available_copies": available_copies,
            "slice": holdings_slice,
        },
        "hardcopy_textbooks": hardcopy,
        "ebooks_and_reference": ebooks,
        "ebook_shelf": ebook_shelf,
        "resource_inventory": inventory,
        "resource_inventory_stats": {
            "total": len(inventory),
            "books": sum(1 for r in inventory if r.get("kind") == "book"),
            "papers": sum(1 for r in inventory if r.get("kind") == "paper"),
            "ebooks": sum(1 for r in inventory if r.get("kind") == "ebook"),
            "hardcopy": sum(1 for r in inventory if r.get("kind") == "hardcopy"),
            "with_local_pdf": sum(
                1 for r in inventory if r.get("has_local_pdf") == "1"
            ),
        },
        "pearson_ebook_status": read_csv(derived_dir / "pearson_ebook_status.csv"),
        "pearson_portal": {
            "name": "Pearson eLibrary",
            "url": "https://elibrary.in.pearson.com/",
            "access_note": "Institutional login via Central Library (credentials not shown here).",
        },
    }


# ── Librarian Ingestion & Staging Workflow Endpoints ─────────────────────────

@app.route("/api/librarian/upload", methods=["POST", "OPTIONS"])
def librarian_upload():
    """Accept multipart file upload and spawn background librarian worker."""
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Archipelago-Token,X-Librarian-Token"
        return resp

    if "file" not in request.files:
        return jsonify({"error": "Missing 'file' in multipart form data"}), 400

    uploaded_file = request.files["file"]
    filename = uploaded_file.filename or "uploaded_document.pdf"
    file_bytes = uploaded_file.read()

    title = request.form.get("title") or filename.rsplit(".", 1)[0]
    author = request.form.get("author") or "Unknown Author"
    isbn = request.form.get("isbn") or "N/A"
    domain = request.form.get("domain") or "General Engineering"

    from archipelago.ingestion.librarian_worker import start_upload_job

    job_id = start_upload_job(
        file_bytes=file_bytes,
        filename=filename,
        title=title,
        author=author,
        isbn=isbn,
        domain=domain,
    )

    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "message": f"Upload '{filename}' accepted. Background ingestion initiated.",
    }), 202


@app.route("/api/librarian/jobs/<job_id>", methods=["GET", "OPTIONS"])
def librarian_job_status(job_id: str):
    """Query progress and stage of librarian ingestion job."""
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Archipelago-Token,X-Librarian-Token"
        return resp

    from archipelago.ingestion.librarian_worker import get_job_status

    status = get_job_status(job_id)
    if not status:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404

    return jsonify(status), 200


@app.route("/api/librarian/staging/review", methods=["GET", "OPTIONS"])
def librarian_staging_review():
    """Returns all newly staged Document, Chunk, and Concept entities awaiting approval."""
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Archipelago-Token,X-Librarian-Token"
        return resp

    from archipelago.ingestion.librarian_worker import get_staging_review

    job_id = request.args.get("job_id")
    review = get_staging_review(job_id=job_id)
    return jsonify(review), 200


@app.route("/api/librarian/staging/publish", methods=["POST", "OPTIONS"])
def librarian_staging_publish():
    """Applies librarian edge edits and performs atomic swap to production."""
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Archipelago-Token,X-Librarian-Token"
        return resp

    payload = request.get_json(silent=True) or {}
    approved = payload.get("approved_edges")
    rejected = payload.get("rejected_edges")

    from archipelago.ingestion.librarian_worker import publish_staging

    try:
        res = publish_staging(approved_edges=approved, rejected_edges=rejected)
        return jsonify(res), 200
    except Exception as exc:
        app.logger.error("Publish staging failed: %s", exc, exc_info=True)
        return jsonify({"error": f"Publish failed: {exc}"}), 500


# Dashboard cold-start runs the real router seed suite (can exceed 30s once).
_DASHBOARD_PROXY_TIMEOUT_S = 180
_DEFAULT_API_PROXY_TIMEOUT_S = 30


@app.route("/api/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
def proxy_all(subpath):
    if request.method == "OPTIONS":
        resp = Response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Archipelago-Token,X-Librarian-Token"
        return resp
    try:
        method = request.method
        url = f"{_API_TARGET}/api/{subpath}"
        headers = {k: v for k, v in request.headers if k.lower() != "host"}
        timeout_s = (
            _DASHBOARD_PROXY_TIMEOUT_S
            if str(subpath).startswith("dashboards/")
            else _DEFAULT_API_PROXY_TIMEOUT_S
        )
        if method == "GET":
            upstream = _requests.get(url, params=request.args, headers=headers, timeout=timeout_s)
        elif request.files:
            files = {k: (f.filename, f.stream, f.content_type) for k, f in request.files.items()}
            upstream = _requests.request(
                method,
                url,
                data=request.form,
                files=files,
                headers={k: v for k, v in headers.items() if k.lower() != "content-type"},
                timeout=timeout_s,
            )
        else:
            upstream = _requests.request(
                method,
                url,
                json=request.get_json(silent=True),
                headers=headers,
                timeout=timeout_s,
            )
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
    print("║  Open:         http://localhost:5152             ║")
    print("║  Performance:  http://localhost:5152/performance ║")
    print("║  Safety:       http://localhost:5152/safety      ║")
    print("╚══════════════════════════════════════════════════╝\n")
    port_val = int(os.environ.get("PORT", "5152"))
    app.run(host=os.environ.get("ARCHIPELAGO_BIND", "127.0.0.1"), port=port_val, debug=False)
