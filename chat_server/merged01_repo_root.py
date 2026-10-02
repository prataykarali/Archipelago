"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory
import mimetypes
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent


# This module may be imported as ``chat_server.merged01_repo_root`` (package) or
# via the legacy ``frontend/chat_server.py`` shim. Both live one level below the
# repository root, so step out of either wrapper directory.
_WRAPPER_DIRS = frozenset({"chat_server", "frontend"})
if REPO_ROOT.name in _WRAPPER_DIRS:
    REPO_ROOT = REPO_ROOT.parent


if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass


mimetypes.add_type("video/mp4", ".mp4")


_STREAM_CHUNK_BYTES = 64 * 1024


_DEFAULT_INFERENCE_CHAT_URL = "http://127.0.0.1:5151/api/chat"


_raw_inf_url = os.environ.get("ARCHIPELAGO_INFERENCE_URL", _DEFAULT_INFERENCE_CHAT_URL).rstrip("/")


INFERENCE_CHAT_URL = _raw_inf_url if _raw_inf_url.endswith("/api/chat") else f"{_raw_inf_url}/api/chat"


BASE_DIR = REPO_ROOT


STATIC_DIR = BASE_DIR / "chat_ui"


_ASSET_ROOTS = tuple(
    p for p in (BASE_DIR / "buttons", BASE_DIR / "ui" / "assets") if p.is_dir()
)


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


@app.route("/data/catalogs/<path:filename>")
def serve_catalogs(filename):
    """Serve catalog metadata only to a verified institutional session."""
    if not _has_valid_auth_session():
        return jsonify({"error": "unauthorized"}), 401
    catalog_dir = BASE_DIR / "data" / "catalogs"
    return send_from_directory(str(catalog_dir), filename)


@app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response


_AUTH_PUBLIC_PATHS = frozenset({
    "/api/auth/config",
    "/api/readiness",
    "/api/health",
})


_AUTH_SESSION_PATHS = frozenset({"/api/auth/session"})


_STAFF_API_PREFIXES = ("/api/users", "/api/librarian", "/api/ingest", "/api/documents", "/api/manual/")


def _cookie_options() -> dict[str, object]:
    domain = os.environ.get("ARCHIPELAGO_COOKIE_DOMAIN", "").strip() or None
    production = os.environ.get("ARCHIPELAGO_ENV", "development").strip().lower() in {"production", "prod"}
    secure_setting = os.environ.get("ARCHIPELAGO_COOKIE_SECURE")
    secure = production if secure_setting is None else secure_setting.strip().lower() in {"1", "true", "yes"}
    return {"domain": domain, "secure": secure, "httponly": True, "samesite": "Lax", "path": "/"}


@app.before_request
def require_verified_api_session():
    """Apply one verified-session policy to every private API endpoint."""
    if not request.path.startswith("/api/") or request.method == "OPTIONS":
        return None
    if (
        request.path in _AUTH_PUBLIC_PATHS
        or request.path in _AUTH_SESSION_PATHS
    ):
        return None
    from archipelago import supabase_auth
    if not supabase_auth.is_auth_required():
        return None
    principal, error = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": error}), 401
    g.archipelago_principal = principal
    if request.path.startswith(_STAFF_API_PREFIXES) and principal.role not in {"librarian", "administrator"}:
        return jsonify({"error": "forbidden", "detail": "Librarian or administrator role required"}), 403
    return None


def _inference_auth_headers() -> dict[str, str]:
    principal = getattr(g, "archipelago_principal", None)
    if principal is None:
        return {}
    return {"Authorization": f"Bearer {principal.access_token}"}


def _is_auth_enforced() -> bool:
    from archipelago import supabase_auth
    return supabase_auth.is_auth_required()


def _has_valid_auth_session() -> bool:
    """Verify the Supabase identity before serving protected browser pages."""
    if not _is_auth_enforced():
        return True
    from archipelago import supabase_auth

    principal, _error = supabase_auth.authenticate_request(request)
    return principal is not None


def _session_cookie_response(payload: dict | None = None, status: int = 200):
    response = jsonify(payload or {"authenticated": True})
    response.status_code = status
    return response


@app.route("/api/auth/session", methods=["POST", "DELETE", "OPTIONS"])
def auth_session_cookie():
    """Exchange a verified Supabase bearer token for a secure HttpOnly cookie."""
    if request.method == "OPTIONS":
        return ("", 204)
    response = _session_cookie_response({"authenticated": False})
    cookie_args = _cookie_options()
    if request.method == "DELETE":
        response.delete_cookie("archipelago_token", **cookie_args)
        return response

    from archipelago import supabase_auth
    principal, error = supabase_auth.authenticate_request(request)
    if principal is None:
        return jsonify({"error": "unauthorized", "detail": error}), 401
    response = _session_cookie_response({"authenticated": True, "role": principal.role})
    response.set_cookie(
        "archipelago_token",
        principal.access_token,
        max_age=3600,
        **cookie_args,
    )
    return response
