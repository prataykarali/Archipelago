"""Small research transport for the second Vercel project."""

from __future__ import annotations

import atexit
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
import os
from secrets import compare_digest
import signal
import sys
import threading
import time
from urllib.parse import urlsplit

from discovery import discover
from flask import Flask, Response, g, jsonify, request, send_from_directory
from koha_snapshot import load_snapshot
from librarian_store import RECORD_TYPES, list_records, save_record
from opac_live import lookup_book, search_books
import requests
from research_pages import PAGE_DETAILS, UI, render_research_page
from storage import close_storage_resources, revoke_token, topic_inventory, verify_user
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

app = Flask(__name__, static_folder=None)
RESEARCH_SUPABASE_URL = "https://edokbtmhztkhndmxetpy.supabase.co"
if os.getenv("VERCEL") and os.getenv("SUPABASE_URL", "").rstrip("/") != RESEARCH_SUPABASE_URL:
    raise RuntimeError("Research service requires Supabase Research Staging")
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
PROXY_TIMEOUT_SECONDS = 120
REDIRECT_MIN_STATUS = 300
REDIRECT_MAX_STATUS = 400
RATE_LIMIT_WINDOW_SECONDS = 60.0
RATE_LIMIT_MAX_READS = 120
RATE_LIMIT_MAX_MUTATIONS = 30
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, deque[float]] = {}
_SHUTDOWN_COND = threading.Condition()
_SHUTTING_DOWN = False
_IN_FLIGHT_REQUESTS = 0
_SHUTDOWN_CALLBACKS: list[Callable[[], object]] = []
_CALLBACKS_EXECUTED = False


def is_shutting_down() -> bool:
    """Return True once graceful shutdown has been initiated."""
    with _SHUTDOWN_COND:
        return _SHUTTING_DOWN


def in_flight_requests() -> int:
    """Return the number of currently active requests."""
    with _SHUTDOWN_COND:
        return _IN_FLIGHT_REQUESTS


def register_shutdown_callback(callback: Callable[[], object]) -> None:
    """Register a cleanup hook to run after in-flight requests drain."""
    with _SHUTDOWN_COND:
        if callback not in _SHUTDOWN_CALLBACKS:
            _SHUTDOWN_CALLBACKS.append(callback)


def initiate_shutdown(drain_timeout: float = 5.0) -> dict[str, object]:
    """Enter draining state, wait for active requests, and run cleanup callbacks."""
    global _SHUTTING_DOWN, _CALLBACKS_EXECUTED
    deadline = time.monotonic() + max(0.0, drain_timeout)
    with _SHUTDOWN_COND:
        _SHUTTING_DOWN = True
        while _IN_FLIGHT_REQUESTS > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            _SHUTDOWN_COND.wait(timeout=remaining)
        remaining_in_flight = _IN_FLIGHT_REQUESTS
        if not _CALLBACKS_EXECUTED:
            _CALLBACKS_EXECUTED = True
            callbacks = list(_SHUTDOWN_CALLBACKS)
        else:
            callbacks = []
    for cb in callbacks:
        try:
            cb()
        except Exception:
            app.logger.warning("Shutdown callback failed: %s", getattr(cb, "__name__", "callback"))
    return {"status": "shutting_down", "in_flight": remaining_in_flight}


def reset_shutdown_state() -> None:
    """Reset shutdown state (used by test suites)."""
    global _SHUTTING_DOWN, _IN_FLIGHT_REQUESTS, _CALLBACKS_EXECUTED
    with _SHUTDOWN_COND:
        _SHUTTING_DOWN = False
        _IN_FLIGHT_REQUESTS = 0
        _CALLBACKS_EXECUTED = False


def install_signal_handlers(force: bool = False) -> bool:
    """Install safe SIGTERM/SIGINT handlers when running on the main thread."""
    if threading.current_thread() is not threading.main_thread():
        return False
    if not force and ("pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")):
        return False

    prev_handlers: dict[int, object] = {}

    def _handle_signal(signum: int, frame: object) -> None:
        initiate_shutdown(drain_timeout=2.0)
        prev = prev_handlers.get(signum)
        if callable(prev):
            prev(signum, frame)
        elif prev in (signal.SIG_DFL, None):
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            prev_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, _handle_signal)
        return True
    except (ValueError, OSError):
        return False


register_shutdown_callback(close_storage_resources)
atexit.register(initiate_shutdown, 1.0)
install_signal_handlers()
_SAFE_VALIDATION_ERRORS = frozenset(
    {
        "invalid_record",
        "invalid_record_key",
        "invalid_record_type",
        "invalid_title",
        "invalid_status",
        "invalid_shelf",
        "invalid_note",
        "invalid_source_url",
        "source_url_must_be_https",
        "invalid_quantity",
        "invalid_amount",
        "Invalid Koha book ID",
        "Search query must be 2-100 characters",
        "Invalid OPAC search offset",
        "Unexpected OPAC redirect",
        "Too many OPAC redirects",
        "OPAC page exceeds size limit",
        "OPAC record has no title",
        "OPAC returned another book ID",
    }
)


def _client_ip() -> str:
    """Extract client IP from Vercel-trusted headers rather than spoofable first XFF hop."""
    vercel_xff = request.headers.get("x-vercel-forwarded-for", "").strip()
    if vercel_xff:
        return vercel_xff.split(",")[-1].strip()[:64]
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip[:64]
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[-1].strip()[:64]
    return (request.remote_addr or "unknown")[:64]


def _rate_limited(bucket_scope: str, limit: int) -> bool:
    """Enforce per-IP sliding-window rate limits without external bottlenecks."""
    if app.config.get("TESTING"):
        return False
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    key = f"{bucket_scope}:{_client_ip()}"
    with _RATE_LOCK:
        if len(_RATE_BUCKETS) > 2048:
            stale_keys = [k for k, q in _RATE_BUCKETS.items() if not q or q[-1] <= cutoff]
            for k in stale_keys:
                _RATE_BUCKETS.pop(k, None)
        q = _RATE_BUCKETS.setdefault(key, deque())
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def _allowed_origins() -> set[str]:
    """Return explicit allowlisted HTTPS browser origins."""
    origins: set[str] = set()
    configured = os.getenv("ARCHIPELAGO_FRONTEND_ORIGIN", "").strip().rstrip("/")
    if configured and configured != "*" and configured.startswith("https://"):
        origins.add(configured)
    host_origin = request.host_url.rstrip("/")
    if host_origin:
        origins.add(host_origin)
    return origins


def research_backend_origin() -> str:
    """Use this deployment's private inference binding on Vercel."""
    bound = os.getenv("INFERENCE_SERVICE_URL", "").strip().rstrip("/")
    if bound:
        return bound
    if os.getenv("VERCEL"):
        raise ValueError("missing_inference_service_binding")
    candidate = os.getenv("ARCHIPELAGO_RESEARCH_ORIGIN", "").strip().rstrip("/")
    if not candidate:
        raise ValueError("missing_research_origin")
    parsed = urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".vercel.app")
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid_research_origin")
    return candidate


ASSETS = frozenset(
    {
        "research.css",
        "research_layout.css",
        "research_simple.css",
        "research_intelligence.css",
        "research_intelligence.js",
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
        "password_visibility.js",
        "academic_koha.js",
        "academic_opac_live.js",
        "librarian.css",
        "librarian.js",
        "academic_light.css",
    }
)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES


@app.get("/api/readiness")
def readiness() -> Response | tuple[object, int]:
    """Report whether shared read access is configured without leaking keys."""
    if is_shutting_down():
        resp = jsonify({"ready": False, "status": "shutting_down", "service": "research_transport"})
        resp.headers["Retry-After"] = "5"
        return resp, 503
    configured = all(
        os.getenv(key, "").strip() for key in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY")
    ) and bool(os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    return jsonify({"ready": bool(configured), "service": "research_transport"}), (
        200 if configured else 503
    )


@app.teardown_request
def _finish_in_flight(_exc: BaseException | None = None) -> None:
    """Decrement active in-flight counter and notify any waiting shutdown drain."""
    global _IN_FLIGHT_REQUESTS
    if getattr(g, "_tracked_in_flight", False):
        g._tracked_in_flight = False
        with _SHUTDOWN_COND:
            _IN_FLIGHT_REQUESTS = max(0, _IN_FLIGHT_REQUESTS - 1)
            if _IN_FLIGHT_REQUESTS == 0:
                _SHUTDOWN_COND.notify_all()


@app.after_request
def browser_origin(response: Response) -> Response:
    """Allow the original Archipelago app to call this service with a session."""
    if is_shutting_down() and response.status_code == 503:
        response.headers.setdefault("Retry-After", "5")
    origin = os.getenv("ARCHIPELAGO_FRONTEND_ORIGIN", "").strip().rstrip("/")
    req_origin = request.headers.get("Origin", "").strip().rstrip("/")
    if origin and origin != "*" and origin.startswith("https://") and req_origin == origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, X-CSRF-Token, X-Background-Poll"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        response.headers["Vary"] = "Origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https://edokbtmhztkhndmxetpy.supabase.co wss://edokbtmhztkhndmxetpy.supabase.co https://huggingface.co https://*.hf.space; "
        "frame-ancestors 'self'; object-src 'none'; base-uri 'self'"
    )
    response.headers.setdefault("Cache-Control", "private, no-store")
    return response


@app.before_request
def require_auth() -> Response | tuple[object, int] | None:
    """Protect research records and discovery with the shared user session."""
    global _IN_FLIGHT_REQUESTS
    if request.method == "OPTIONS":
        return "", 204
    with _SHUTDOWN_COND:
        if _SHUTTING_DOWN:
            if request.path == "/api/readiness":
                return None
            resp = jsonify(
                {
                    "error": "service_shutting_down",
                    "status": "shutting_down",
                    "retry_after": 5,
                }
            )
            resp.headers["Retry-After"] = "5"
            return resp, 503
        _IN_FLIGHT_REQUESTS += 1
        g._tracked_in_flight = True
    segments = [seg for seg in request.path.split("/") if seg]
    if any(seg.startswith(".") or seg == ".." for seg in segments) or request.path.lower().endswith(
        "audit.md"
    ):
        return jsonify({"error": "not_found"}), 404
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        req_origin = request.headers.get("Origin", "").strip().rstrip("/")
        if req_origin and req_origin not in _allowed_origins():
            return jsonify({"error": "csrf_origin_mismatch"}), 403
        if _rate_limited("mutation", RATE_LIMIT_MAX_MUTATIONS):
            return jsonify({"error": "rate_limited"}), 429
    elif request.path.startswith("/api/") and _rate_limited("read", RATE_LIMIT_MAX_READS):
        return jsonify({"error": "rate_limited"}), 429
    if request.path in {
        "/api/readiness",
        "/api/research/intake/scheduled",
        "/api/auth/config",
        "/api/auth/logout",
        "/api/auth/handoff-redeem",
        "/api/library/koha",
        "/api/library/koha/scheduled",
    } or (request.path == "/api/auth/session" and request.method == "DELETE"):
        return None
    if request.path in {"/", "/login"} or request.path.lstrip("/") in ASSETS:
        return None
    if request.path == "/assets/research_archipelago_v2.webp":
        return None
    if (
        request.path.startswith("/research")
        or request.path
        in {"/academic/graph", "/analytics", "/academic-automation", "/academic-automation.html"}
        or request.path.startswith("/librarian")
    ):
        return None
    if not (
        request.path.startswith(("/api/research/", "/api/analytics/", "/api/academic-automation/"))
        or request.path
        in {
            "/api/auth/me",
            "/api/auth/session",
            "/api/auth/handoff-ticket",
            "/api/graph/hubs",
            "/api/graph/page",
            "/api/graph/subgraph",
            "/api/library/opac/live",
        }
        or request.path.startswith("/api/librarian/")
    ):
        return jsonify({"error": "not_found"}), 404
    authorization = request.headers.get("Authorization", "")
    token = (
        authorization.removeprefix("Bearer ").strip()
        if authorization.startswith("Bearer ")
        else (
            request.cookies.get("archipelago_token", "").strip()
            or request.cookies.get("archipelago_access_token", "").strip()
            or request.cookies.get("sb-access-token", "").strip()
        )
    )
    try:
        principal = verify_user(token)
    except (requests.RequestException, ValueError):
        return jsonify({"error": "auth_unavailable"}), 503
    if not principal:
        return jsonify({"error": "unauthorized"}), 401
    g.principal = principal
    g.token = token
    return None


@app.get("/")
@app.get("/login")
@app.get("/academic/graph")
@app.get("/analytics")
@app.get("/academic-automation")
@app.get("/academic-automation.html")
def static_page() -> Response:
    """Serve the home, login, academic graph, analytics, or automation page."""
    mapping = {
        "/": "home.html",
        "/login": "signin.html",
        "/academic/graph": "academic_graph.html",
        "/analytics": "analytics.html",
    }
    return send_from_directory(UI, mapping.get(request.path, "academic_automation.html"))


@app.get("/research")
@app.get("/research/")
@app.get("/research/<page>")
def research_subpage(page: str = "papers") -> Response | tuple[object, int]:
    """Render metadata-first S5 research views."""
    if page not in PAGE_DETAILS:
        return jsonify({"error": "not_found"}), 404
    return render_research_page(page)


@app.get("/librarian")
@app.get("/librarian/<section>")
def librarian_page(section: str = "overview") -> Response | tuple[object, int]:
    """Serve distinct librarian workspaces using one shared shell."""
    if section == "analytics":
        return send_from_directory(UI, "analytics.html")
    if section not in {"overview", *RECORD_TYPES}:
        return jsonify({"error": "not_found"}), 404
    return send_from_directory(UI, "librarian.html")


@app.get("/librarian-assets/<name>")
def librarian_asset(name: str) -> Response | tuple[object, int]:
    """Serve the research service's own librarian scripts and stylesheet."""
    if name not in {"auth_bridge.js", "librarian.js", "librarian.css"}:
        return jsonify({"error": "not_found"}), 404
    return send_from_directory(UI, name)


@app.route("/api/librarian/<record_type>", methods=["GET", "POST"])
def librarian_records(record_type: str) -> tuple[object, int]:
    """Read staff notes; restrict changes to librarians and administrators."""
    if record_type not in RECORD_TYPES:
        return jsonify({"error": "not_found"}), 404
    allowed_roles = (
        {"librarian", "administrator"}
        if request.method == "POST"
        else {"faculty", "librarian", "administrator"}
    )
    if g.principal["role"] not in allowed_roles:
        return jsonify({"error": "forbidden"}), 403
    try:
        if request.method == "GET":
            return jsonify(
                {"records": list_records(record_type), "source": "archipelago_staff"}
            ), 200
        saved = save_record(record_type, request.get_json(silent=True), g.principal["id"])
    except ValueError as exc:
        msg = str(exc) if str(exc) in _SAFE_VALIDATION_ERRORS else "invalid_record"
        return jsonify({"error": msg}), 400
    except (requests.RequestException, RuntimeError, KeyError, IndexError):
        return jsonify({"error": "storage_unavailable"}), 503
    return jsonify({"record": saved, "source": "archipelago_staff"}), 200


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


@app.get("/api/library/opac/live")
def library_opac_live() -> tuple[object, int]:
    """Fetch one public OPAC query on demand for an authenticated staff user."""
    if g.principal["role"] not in {"faculty", "librarian", "administrator"}:
        return jsonify({"error": "forbidden"}), 403
    biblionumber = request.args.get("biblionumber", "").strip()
    query = request.args.get("q", "").strip()
    if bool(biblionumber) == bool(query):
        return jsonify({"error": "provide_book_id_or_query"}), 400
    try:
        result = lookup_book(biblionumber) if biblionumber else search_books(query)
    except ValueError as exc:
        msg = str(exc) if str(exc) in _SAFE_VALIDATION_ERRORS else "invalid_opac_query"
        return jsonify({"error": msg}), 400
    except requests.RequestException:
        try:
            snapshot = load_snapshot()
            holdings = snapshot.get("holdings", []) if snapshot else []
            if biblionumber:
                match = next(
                    (row for row in holdings if row.get("biblionumber") == biblionumber),
                    None,
                )
                if match:
                    return jsonify(
                        {
                            "biblionumber": biblionumber,
                            "title": match.get("Title", ""),
                            "source_url": match.get("opac_url", ""),
                            "snapshot_record": match,
                            "is_live": False,
                            "source_kind": "dated_koha_export",
                            "source_updated_at": snapshot.get("source_updated_at"),
                            "stale": snapshot.get("stale", True),
                            "notice": "Live OPAC unavailable; showing dated Koha export snapshot (not verified live availability).",
                        }
                    ), 200
            if query:
                q_lower = query.casefold()
                matches = [
                    row
                    for row in holdings
                    if q_lower in str(row.get("Title", "")).casefold()
                    or q_lower in str(row.get("Author", "")).casefold()
                    or q_lower in str(row.get("Subject", "")).casefold()
                    or q_lower in str(row.get("ISBN", "")).casefold()
                ][:20]
                return jsonify(
                    {
                        "query": query,
                        "results": matches,
                        "is_live": False,
                        "source_kind": "dated_koha_export",
                        "source_updated_at": snapshot.get("source_updated_at")
                        if snapshot
                        else None,
                        "stale": snapshot.get("stale", True) if snapshot else True,
                        "notice": "Live OPAC unavailable; showing dated Koha export snapshot (not verified live availability).",
                    }
                ), 200
        except (requests.RequestException, RuntimeError, ValueError, TypeError):
            app.logger.warning("OPAC fallback unavailable")
        return jsonify({"error": "opac_unavailable"}), 503
    return jsonify(result), 200


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
    return jsonify(
        {"configured": bool(url and key), "required": True, "url": url, "publishableKey": key}
    ), 200


@app.get("/api/auth/me")
def auth_me() -> tuple[object, int]:
    """Identify the active staff account without exposing its token."""
    principal = g.principal if isinstance(g.principal, dict) else {}
    return jsonify({"authenticated": True, **principal}), 200


@app.route("/api/auth/session", methods=["POST", "DELETE"])
@app.post("/api/auth/logout")
def auth_session() -> Response | tuple[object, int]:
    """Manage or terminate the HttpOnly staff session cookie on this origin."""
    if request.method == "DELETE" or request.path == "/api/auth/logout":
        authorization = request.headers.get("Authorization", "")
        token = (
            authorization.removeprefix("Bearer ").strip()
            if authorization.startswith("Bearer ")
            else request.cookies.get("archipelago_token", "").strip()
        )
        revoke_token(token)
        resp = jsonify({"authenticated": False})
        for cookie_name in ("archipelago_token", "archipelago_access_token", "sb-access-token"):
            resp.delete_cookie(cookie_name, path="/", samesite="Lax")
        resp.headers["Clear-Site-Data"] = '"cookies", "storage"'
        return resp, 200
    principal = g.principal if isinstance(g.principal, dict) else {}
    resp = jsonify({"authenticated": True, "role": principal.get("role", "")})
    token = getattr(g, "token", "")
    if token:
        resp.set_cookie(
            "archipelago_token",
            token,
            max_age=3600,
            httponly=True,
            secure=os.getenv("ARCHIPELAGO_ENV", "production").lower() in {"production", "prod"},
            samesite="Lax",
            path="/",
        )
    return resp, 200


@app.post("/api/auth/handoff-ticket")
@app.post("/api/auth/handoff-redeem")
def auth_handoff_proxy() -> Response | tuple[object, int]:
    """Forward server-mediated session handoff exchange to the primary backend."""
    return _forward(request.path)


@app.get("/api/research/topics")
def topics() -> tuple[object, int]:
    """Serve the current topic inventory from shared research storage."""
    if g.principal["role"] not in {"faculty", "librarian", "administrator"}:
        return jsonify({"error": "forbidden"}), 403
    try:
        rows = topic_inventory()
    except (requests.RequestException, RuntimeError, ValueError):
        return jsonify({"error": "storage_unavailable"}), 503
    return jsonify({"topics": rows, "count": len(rows)}), 200


@app.route("/api/research/<path:subpath>", methods=["GET", "POST", "PATCH", "DELETE"])
@app.route("/api/analytics/<path:subpath>", methods=["GET", "POST"])
@app.route("/api/academic-automation/<path:subpath>", methods=["GET", "POST"])
def research_proxy(subpath: str) -> Response | tuple[object, int]:
    """Forward research, analytics, and academic-automation actions to the backend."""
    if any(segment in {".", ".."} for segment in subpath.split("/")):
        return jsonify({"error": "invalid_path"}), 400
    return _forward(request.path)


@app.get("/api/graph/hubs")
@app.get("/api/graph/subgraph")
@app.get("/api/graph/page")
def graph_proxy() -> Response | tuple[object, int]:
    """Read the existing Academic graph without copying its corpus."""
    return _forward(request.path)


def _forward(path: str) -> Response | tuple[object, int]:
    """Relay a fixed-origin backend request with the verified user token."""
    try:
        url = f"{research_backend_origin()}{path}"
    except ValueError:
        return jsonify({"error": "research_backend_misconfigured"}), 503
    headers = {
        "Authorization": request.headers.get("Authorization", ""),
        "Accept": "application/json",
    }
    for passthrough in ("Cookie", "Origin", "Referer", "X-CSRF-Token", "X-Background-Poll"):
        val = request.headers.get(passthrough, "").strip()
        if val:
            headers[passthrough] = val
    bypass_secret = os.getenv("ARCHIPELAGO_RESEARCH_BYPASS_SECRET", "").strip()
    if bypass_secret:
        headers["x-vercel-protection-bypass"] = bypass_secret
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
    disposition = upstream.headers.get("Content-Disposition", "").strip()
    if disposition.startswith("attachment;"):
        response.headers["Content-Disposition"] = disposition
    raw_headers = getattr(getattr(upstream, "raw", None), "headers", None)
    if raw_headers is not None and callable(getattr(raw_headers, "getlist", None)):
        cookie_vals = raw_headers.getlist("Set-Cookie")
        if isinstance(cookie_vals, (list, tuple)):
            for cookie_val in cookie_vals:
                response.headers.add("Set-Cookie", cookie_val)
    elif isinstance(upstream.headers.get("Set-Cookie"), str):
        response.headers.add("Set-Cookie", upstream.headers["Set-Cookie"])
    return response


@app.errorhandler(RequestEntityTooLarge)
def handle_payload_too_large(_exc: RequestEntityTooLarge) -> tuple[object, int]:
    """Return a clean JSON error when request payload exceeds MAX_CONTENT_LENGTH."""
    return jsonify({"error": "payload_too_large"}), 413


@app.errorhandler(Exception)
def handle_unexpected_error(exc: Exception) -> Response | tuple[object, int]:
    """Return generic JSON on unexpected errors without leaking stack traces."""
    if isinstance(exc, HTTPException):
        return jsonify({"error": exc.name.lower().replace(" ", "_")}), exc.code or 500
    app.logger.error("Unhandled error in research transport: %s", type(exc).__name__)
    return jsonify({"error": "internal_error"}), 500


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
