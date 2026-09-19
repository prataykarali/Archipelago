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

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    pass

import requests as _requests

mimetypes.add_type("video/mp4", ".mp4")

_STREAM_CHUNK_BYTES = 64 * 1024  # 64 KiB chunks for streaming proxy responses
_DEFAULT_INFERENCE_CHAT_URL = "http://127.0.0.1:5051/api/chat"
_raw_inf_url = os.environ.get("ARCHIPELAGO_INFERENCE_URL", _DEFAULT_INFERENCE_CHAT_URL).rstrip("/")
INFERENCE_CHAT_URL = _raw_inf_url if _raw_inf_url.endswith("/api/chat") else f"{_raw_inf_url}/api/chat"

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
    """Serves the landing page (Built for the curious) with direct entry into chat and library."""
    return send_from_directory(str(STATIC_DIR), "landing.html")


@app.route("/landing")
def landing():
    """Serves the cinematic landing page."""
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


@app.route("/api/chat/diagnostic-mcqs", methods=["GET", "POST", "OPTIONS"])
def chat_diagnostic_mcqs_proxy() -> ResponseReturnValue:
    """Proxy diagnostic MCQs requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/diagnostic-mcqs"
    try:
        if request.method == "GET":
            upstream = _requests.get(target, params=request.args, timeout=5)
        else:
            upstream = _requests.post(target, json=request.get_json(silent=True) or {}, timeout=5)
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for diagnostic-mcqs: %s", exc)
        return {
            "success": False,
            "available": False,
            "badge": "Personalized assessment temporarily unavailable.",
            "error": str(exc),
        }, 200
    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )


@app.route("/api/chat/telemetry", methods=["POST", "OPTIONS"])
def chat_telemetry_proxy() -> ResponseReturnValue:
    """Proxy telemetry tracking events to upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/telemetry"
    try:
        upstream = _requests.post(target, json=request.get_json(silent=True) or {}, timeout=5)
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "application/json"),
        )
    except Exception as exc:
        return {"logged": False, "error": str(exc)}, 200


@app.route("/api/chat/verify-mcq", methods=["POST", "OPTIONS"])
def chat_verify_mcq_proxy() -> ResponseReturnValue:
    """Proxy diagnostic MCQ verification requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/verify-mcq"
    try:
        upstream = _requests.post(
            target,
            json=request.get_json(silent=True) or {},
            timeout=30,
        )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for verify-mcq: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )


@app.route("/api/chat/adaptive-step", methods=["POST", "OPTIONS"])
def chat_adaptive_step_proxy() -> ResponseReturnValue:
    """Proxy diagnostic adaptive-step requests to the upstream inference server."""
    if request.method == "OPTIONS":
        return ("", 204)
    base = _inference_base()
    target = f"{base}/api/chat/adaptive-step"
    try:
        upstream = _requests.post(
            target,
            json=request.get_json(silent=True) or {},
            timeout=30,
        )
    except Exception as exc:
        app.logger.warning("Inference upstream unreachable for adaptive-step: %s", exc)
        return {"error": f"inference upstream unreachable: {exc}"}, 502
    return Response(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
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

@app.route("/api/auth/config", methods=["GET"])
@app.route("/api/auth/me", methods=["GET"])
def auth_proxy_or_local():
    """Relay browser auth configuration and identity, with local fallback."""
    from src.archipelago import supabase_auth
    if request.path == "/api/auth/config":
        return jsonify(supabase_auth.public_config())
    elif request.path == "/api/auth/me":
        principal, error = supabase_auth.authenticate_request(request)
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": error}), 401
        return jsonify({
            "authenticated": True,
            "user_id": principal.user_id,
            "username": principal.username,
            "role": principal.role,
        })


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


# ── Librarian Ingestion & Staging Workflow Endpoints ─────────────────────────

@app.route("/api/librarian/upload", methods=["POST", "OPTIONS"])
def librarian_upload():
    """Accept multipart file upload and spawn background librarian worker."""
    if request.method == "OPTIONS":
        return ("", 204)

    if "file" not in request.files:
        return {"error": "Missing 'file' in multipart form data"}, 400

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

    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Upload '{filename}' accepted. Background ingestion initiated.",
    }, 202


@app.route("/api/librarian/jobs/<job_id>", methods=["GET", "OPTIONS"])
def librarian_job_status(job_id: str):
    """Query progress and stage of librarian ingestion job."""
    if request.method == "OPTIONS":
        return ("", 204)

    from archipelago.ingestion.librarian_worker import get_job_status

    status = get_job_status(job_id)
    if not status:
        return {"error": f"Job '{job_id}' not found"}, 404

    return status, 200


@app.route("/api/librarian/staging/review", methods=["GET", "OPTIONS"])
def librarian_staging_review():
    """Returns all newly staged Document, Chunk, and Concept entities awaiting approval."""
    if request.method == "OPTIONS":
        return ("", 204)

    from archipelago.ingestion.librarian_worker import get_staging_review

    job_id = request.args.get("job_id")
    review = get_staging_review(job_id=job_id)
    return review, 200


@app.route("/api/librarian/staging/publish", methods=["POST", "OPTIONS"])
def librarian_staging_publish():
    """Applies librarian edge edits and performs atomic swap to production."""
    if request.method == "OPTIONS":
        return ("", 204)

    payload = request.get_json(silent=True) or {}
    approved = payload.get("approved_edges")
    rejected = payload.get("rejected_edges")

    from archipelago.ingestion.librarian_worker import publish_staging

    try:
        res = publish_staging(approved_edges=approved, rejected_edges=rejected)
        return res, 200
    except Exception as exc:
        app.logger.error("Publish staging failed: %s", exc, exc_info=True)
        return {"error": f"Publish failed: {exc}"}, 500


@app.route("/api/graph/subgraph", methods=["GET", "OPTIONS"])
def graph_subgraph():
    """Serve bounded subgraph with styling metadata for interactive visualization."""
    if request.method == "OPTIONS":
        return ("", 204)

    target_id = request.args.get("target_id") or request.args.get("concept_id") or "linear_algebra"
    secondary_target_id = request.args.get("secondary_target_id")
    mode = request.args.get("mode") or "mode_c"
    max_nodes = int(request.args.get("max_nodes", 10))
    min_nodes = int(request.args.get("min_nodes", 5))

    from src.archipelago.graph.subgraph import generate_bounded_subgraph
    from archipelago.graph.engine import KuzuGraphEngine

    db_path = BASE_DIR / "okf_graph.db"
    conn = None
    engine = None
    if db_path.exists():
        try:
            engine = KuzuGraphEngine(db_path=db_path, read_only=True)
            conn = engine.conn
        except Exception:
            pass

    try:
        subgraph = generate_bounded_subgraph(
            target_id=target_id,
            secondary_target_id=secondary_target_id,
            mode=mode,
            max_nodes=max_nodes,
            min_nodes=min_nodes,
            kuzu_conn=conn,
        )
        data = subgraph.to_dict()

        # Enrich nodes with difficulty color and badge
        diff_colors = {
            "foundational": "#10b981",  # emerald green
            "intermediate": "#3b82f6",  # blue
            "advanced": "#8b5cf6",      # purple
            "expert": "#ec4899",        # pink
        }
        for n in data.get("nodes", []):
            diff = (n.get("difficulty") or "intermediate").lower()
            n["color"] = diff_colors.get(diff, "#3b82f6")
            n["badge"] = f"[{diff.capitalize()}]"

        # Enrich edge semantics
        edge_styles = {
            "REQUIRES": {"style": "solid", "color": "#f59e0b", "label": "REQUIRES (Prerequisite)"},
            "UNLOCKS": {"style": "dashed", "color": "#10b981", "label": "UNLOCKS (Progression)"},
            "RELATED": {"style": "dotted", "color": "#9ca3af", "label": "RELATED (Association)"},
            "PROVIDES_TEXT": {"style": "dashed", "color": "#06b6d4", "label": "PROVIDES_TEXT"},
            "MENTIONS": {"style": "dotted", "color": "#64748b", "label": "MENTIONS"},
        }
        for e in data.get("edges", []):
            rel = (e.get("relation") or "REQUIRES").upper()
            style_info = edge_styles.get(rel, {"style": "solid", "color": "#f59e0b", "label": rel})
            e["style"] = style_info["style"]
            e["color"] = style_info["color"]
            e["label"] = style_info["label"]

        return data, 200
    except Exception as exc:
        app.logger.warning("Error generating subgraph: %s", exc)
        return {"error": f"Subgraph generation failed: {exc}"}, 500
    finally:
        if engine:
            try:
                engine.close()
            except Exception:
                pass


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
