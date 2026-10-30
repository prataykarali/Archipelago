"""Small research transport for the second Vercel project."""

from __future__ import annotations

from datetime import UTC, datetime
import os
from secrets import compare_digest

from discovery import discover
from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory
from koha_snapshot import load_snapshot
import requests
from research_pages import PAGE_DETAILS, UI, render_research_page
from storage import topic_inventory, verify_user

app = Flask(__name__, static_folder=None)
DAILY_TOPICS = (
    "optical character recognition",
    "distributed database transactions",
    "computer networks congestion control",
    "graph algorithms and complexity",
    "biomedical signal processing",
    "cybersecurity intrusion detection",
)
TOPICS_PER_RUN = 1
MAX_REQUEST_BYTES = 2_097_152
PROXY_TIMEOUT_SECONDS = 45
REDIRECT_MIN_STATUS = 300
REDIRECT_MAX_STATUS = 400
ORIGINAL_RESEARCH_ORIGIN = "https://archipelago-blond.vercel.app"
ASSETS = frozenset(
    {
        "research.css",
        "research_layout.css",
        "research_simple.css",
        "research_studio.css",
        "research_atlas.css",
        "research_paper.css",
        "research_topic.css",
        "research_common.js",
        "research_home.js",
        "research_okf_ui.js",
        "research_progress.js",
        "research_topics.js",
        "research_paper.js",
        "research_topic.js",
        "auth_bridge.js",
        "research_signin.css",
        "signin.js",
        "academic_koha.js",
    }
)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES


@app.get("/api/readiness")
def readiness() -> tuple[object, int]:
    """Report whether shared read access is configured without leaking keys."""
    configured = all(
        os.getenv(key, "").strip() for key in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY")
    ) and bool(os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    return jsonify({"ready": bool(configured), "service": "research_transport"}), (
        200 if configured else 503
    )


@app.after_request
def browser_origin(response: Response) -> Response:
    """Allow the original Archipelago app to call this service with a session."""
    origin = os.getenv("ARCHIPELAGO_FRONTEND_ORIGIN", "").strip().rstrip("/")
    if origin and request.headers.get("Origin") == origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Vary"] = "Origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.before_request
def require_auth() -> tuple[object, int] | None:
    """Protect research records and discovery with the shared user session."""
    if request.method == "OPTIONS":
        return "", 204
    if request.path in {
        "/api/readiness",
        "/api/research/intake/scheduled",
        "/api/auth/config",
        "/api/library/koha",
        "/api/library/koha/scheduled",
    }:
        return None
    if request.path in {"/", "/login"} or request.path.lstrip("/") in ASSETS:
        return None
    if request.path == "/assets/research_archipelago_v2.webp":
        return None
    if request.path.startswith("/research") or request.path == "/academic/graph":
        return None
    if not (
        request.path.startswith("/api/research/")
        or request.path in {"/api/auth/me", "/api/graph/hubs", "/api/graph/subgraph"}
    ):
        return jsonify({"error": "not_found"}), 404
    authorization = request.headers.get("Authorization", "")
    token = (
        authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
    )
    try:
        principal = verify_user(token)
    except (requests.RequestException, ValueError):
        return jsonify({"error": "auth_unavailable"}), 503
    if not principal:
        return jsonify({"error": "unauthorized"}), 401
    g.principal = principal
    return None


@app.get("/")
def home() -> Response:
    """Open the relocated research workspace."""
    return redirect("/research")


@app.get("/login")
def login_page() -> Response:
    """Sign staff into the same Supabase project on this new origin."""
    return send_from_directory(UI, "signin.html")


@app.get("/research")
@app.get("/research/")
def research_home() -> Response:
    """Render the original research dashboard with OKF and local-job controls."""
    return render_research_page("papers")


@app.get("/research/<page>")
def research_subpage(page: str) -> Response | tuple[object, int]:
    """Render original progress, graph, paper, and topic views."""
    if page not in PAGE_DETAILS:
        return jsonify({"error": "not_found"}), 404
    return render_research_page(page)


@app.get("/academic/graph")
def academic_graph() -> Response:
    """Show the academic graph and its dated Koha library details."""
    return send_from_directory(UI, "academic_graph.html")


@app.get("/<name>")
def research_asset(name: str) -> Response | tuple[object, int]:
    """Serve only the assets used by the original research pages."""
    if name not in ASSETS:
        return jsonify({"error": "not_found"}), 404
    return send_from_directory(UI, name)


@app.get("/assets/research_archipelago_v2.webp")
def research_hero_image() -> Response:
    """Serve the original research hero artwork."""
    return send_from_directory(UI / "assets", "research_archipelago_v2.webp", mimetype="image/webp")


@app.get("/api/library/koha")
def library_koha() -> tuple[object, int]:
    """Serve public bibliographic metadata with explicit export freshness."""
    try:
        snapshot = load_snapshot()
    except (requests.RequestException, RuntimeError, ValueError):
        return jsonify({"error": "storage_unavailable"}), 503
    if snapshot is None:
        return jsonify({"error": "export_not_available"}), 404
    return jsonify(snapshot), 200


@app.get("/api/library/koha/scheduled")
def library_koha_scheduled() -> tuple[object, int]:
    """Check daily freshness; the local workstation publishes new exports."""
    secret = os.getenv("CRON_SECRET", "").strip()
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not secret:
        return jsonify({"error": "schedule_unconfigured"}), 503
    if not supplied or not compare_digest(supplied, secret):
        return jsonify({"error": "unauthorized"}), 401
    try:
        snapshot = load_snapshot()
    except (requests.RequestException, RuntimeError, ValueError):
        return jsonify({"error": "storage_unavailable"}), 503
    if snapshot is None:
        return jsonify({"status": "missing_export"}), 200
    return jsonify(
        {
            "status": "stale_export" if snapshot.get("stale") else "current_export",
            "source_updated_at": snapshot.get("source_updated_at"),
        }
    ), 200


@app.get("/api/auth/config")
def auth_config() -> tuple[object, int]:
    """Give the browser only the public Supabase client configuration."""
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    return jsonify({"configured": bool(url and key), "url": url, "publishableKey": key}), 200


@app.get("/api/auth/me")
def auth_me() -> tuple[object, int]:
    """Identify the active staff account without exposing its token."""
    return jsonify({"authenticated": True, **g.principal}), 200


@app.get("/api/research/topics")
def topics() -> tuple[object, int]:
    """Serve the current topic inventory from shared research storage."""
    try:
        rows = topic_inventory()
    except (requests.RequestException, RuntimeError, ValueError):
        return jsonify({"error": "storage_unavailable"}), 503
    return jsonify({"topics": rows, "count": len(rows)}), 200


@app.route("/api/research/<path:subpath>", methods=["GET", "POST", "PATCH", "DELETE"])
def research_proxy(subpath: str) -> Response | tuple[object, int]:
    """Forward research actions to the existing queue and OKF backend."""
    if any(segment in {".", ".."} for segment in subpath.split("/")):
        return jsonify({"error": "invalid_path"}), 400
    return _forward(f"/api/research/{subpath}")


@app.get("/api/graph/hubs")
@app.get("/api/graph/subgraph")
def graph_proxy() -> Response | tuple[object, int]:
    """Read the existing Academic graph without copying its corpus."""
    return _forward(request.path)


def _forward(path: str) -> Response | tuple[object, int]:
    """Relay a fixed-origin backend request with the verified user token."""
    url = f"{ORIGINAL_RESEARCH_ORIGIN}{path}"
    headers = {
        "Authorization": request.headers.get("Authorization", ""),
        "Accept": "application/json",
    }
    if request.content_type:
        headers["Content-Type"] = request.content_type
    try:
        upstream = requests.request(
            request.method,
            url,
            params=request.args,
            data=request.get_data(),
            headers=headers,
            timeout=PROXY_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    except requests.RequestException:
        return jsonify({"error": "research_backend_unavailable"}), 503
    if REDIRECT_MIN_STATUS <= upstream.status_code < REDIRECT_MAX_STATUS:
        return jsonify({"error": "research_backend_redirected"}), 502
    response = Response(upstream.content, status=upstream.status_code)
    response.headers["Content-Type"] = upstream.headers.get("Content-Type", "application/json")
    return response


@app.get("/api/research/intake/scheduled")
def scheduled_discovery() -> tuple[object, int]:
    """Check one topic each day; leave all candidate ingestion unstarted."""
    secret = os.getenv("CRON_SECRET", "").strip()
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not secret:
        return jsonify({"error": "schedule_unconfigured"}), 503
    if not supplied or not compare_digest(supplied, secret):
        return jsonify({"error": "unauthorized"}), 401
    index = datetime.now(UTC).date().toordinal() * TOPICS_PER_RUN % len(DAILY_TOPICS)
    try:
        report = discover(DAILY_TOPICS[index])
    except (requests.RequestException, ValueError):
        return jsonify({"error": "source_unavailable"}), 503
    return jsonify(report), 200
