"""Request guard, security headers, CORS and error handlers for the hosted app.

One concern: cross-cutting request policy, registered once against the Flask app.
"""

from __future__ import annotations

import hmac
import os
from urllib.parse import urlsplit

from flask import Flask, jsonify, request

from .config import (
    ALLOWED_ORIGINS,
    CSRF_COOKIE_NAME,
    LIBRARIAN_ROLES,
    PUBLIC_API,
    PUBLIC_API_PREFIXES,
    SESSION_COOKIE_NAME,
)
from .context import AppContext
from .log_redaction import redact
from .research_access import ResearchCapability, allowed, audit_action
from .runtime_state import begin_request, end_request, is_shutting_down, runtime_release_sha
from .security import SAFE_METHODS, auth_failure_code, is_allowed_handoff_origin

OPTIONS_NO_CONTENT = 204
SHUTDOWN_RETRY_AFTER_SEC = 5
HEALTH_PATHS = frozenset({"/health", "/ready", "/api/health", "/api/readiness"})
LOGOUT_PATHS = frozenset({"/api/auth/logout", "/api/auth/session"})

CORS_METHODS = "GET,POST,PATCH,DELETE,OPTIONS"
CORS_HEADERS = "Content-Type,Authorization,X-Requested-With,X-CSRF-Token,X-Background-Poll"
_BLOCKED_SUFFIXES = (
    ".env",
    ".git",
    ".sqlite3",
    ".sqlite",
    ".db",
    ".bak",
    ".old",
    ".orig",
    ".swp",
    ".pyc",
    "audit.md",
)

# Runtime assets are built with the Tailwind Play CDN, so the policy allows the
# specific CDNs the UI loads rather than 'unsafe-eval'.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'self'; "
    "form-action 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://esm.sh; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
    "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; img-src 'self' data: blob: https:; "
    "connect-src 'self' https://edokbtmhztkhndmxetpy.supabase.co https://esm.sh; "
    "frame-src 'self' https://ebooks.elibrary.in.pearson.com https://elibrary.in.pearson.com https://huggingface.co; "
    "worker-src 'self' blob: https://cdnjs.cloudflare.com"
)


def _is_blocked_dotfile_or_artifact(path: str) -> bool:
    """Return True when ``path`` targets dotfiles, backup files, SQLite DBs, or AUDIT.md."""
    if not path or "\\" in path or ".." in path:
        return True
    segments = [seg for seg in path.split("/") if seg]
    if any(seg.startswith(".") or seg.endswith("~") for seg in segments):
        return True
    lowered = path.lower()
    return "stripped_backup" in lowered or lowered.endswith(_BLOCKED_SUFFIXES)


def _origin_from_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _is_trusted_request_origin(origin: str, path: str) -> bool:
    cleaned = (origin or "").strip().rstrip("/")
    if not cleaned or cleaned == "*" or cleaned == "null":
        return False
    host_origin = request.host_url.rstrip("/")
    if cleaned in ALLOWED_ORIGINS or cleaned == host_origin:
        return True
    return path in {
        "/api/auth/handoff-ticket",
        "/api/auth/handoff-redeem",
    } and is_allowed_handoff_origin(cleaned)


def _research_capability(path: str, method: str) -> ResearchCapability:
    """Map hosted research paths to their most privileged action."""
    if path == "/api/research/graph/annotation" and method != "GET":
        return ResearchCapability.GRAPH_EDIT
    if path.endswith("/review"):
        return ResearchCapability.REVIEW
    if path.endswith("/refresh"):
        return ResearchCapability.REFRESH_CONTROL
    if path.endswith("/sources") or path.startswith("/api/research/admin/"):
        return ResearchCapability.SOURCE_HEALTH
    if path.endswith("/features"):
        return ResearchCapability.FEATURE_READ
    if path.endswith("/evidence"):
        return ResearchCapability.EVIDENCE_READ
    if path.startswith("/api/research/connectors/"):
        return ResearchCapability.CONNECTOR_CONFIG
    if path.startswith("/api/research/intelligence/monitors"):
        return ResearchCapability.TOPIC_TRACK
    if path == "/api/research/topics" and method == "POST":
        return ResearchCapability.TOPIC_TRACK
    if path == "/api/research/jobs" and method == "POST":
        return ResearchCapability.JOB_CREATE
    return ResearchCapability.SEARCH


def _rate_limited_response(retry_after: int):
    response = jsonify({"error": "rate_limited", "retry_after": retry_after})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


def _shutting_down_response(is_health_probe: bool = False):
    if is_health_probe:
        payload = {
            "ok": False,
            "status": "shutting_down",
            "detail": "Server is draining in-flight requests for graceful shutdown.",
        }
    else:
        payload = {
            "error": "service_unavailable",
            "status": "shutting_down",
            "detail": "Server is shutting down. Please retry shortly.",
            "retry_after": SHUTDOWN_RETRY_AFTER_SEC,
        }
    response = jsonify(payload)
    response.status_code = 503
    response.headers["Retry-After"] = str(SHUTDOWN_RETRY_AFTER_SEC)
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _check_csrf(ctx: AppContext, path: str):
    """Enforce Origin/Referer and CSRF checks on state-changing requests."""
    if request.method in SAFE_METHODS:
        return None
    origin = request.headers.get("Origin", "").strip()
    referer = request.headers.get("Referer", "").strip()
    sec_fetch_site = request.headers.get("Sec-Fetch-Site", "").strip().lower()

    origin_trusted = bool(origin) and _is_trusted_request_origin(origin, path)
    if origin and not origin_trusted:
        return jsonify(
            {"error": "forbidden", "detail": "CSRF validation failed: untrusted Origin."}
        ), 403

    referer_origin = _origin_from_url(referer) if referer else ""
    referer_trusted = bool(referer_origin) and _is_trusted_request_origin(referer_origin, path)
    if referer and not referer_trusted:
        return jsonify(
            {"error": "forbidden", "detail": "CSRF validation failed: untrusted Referer."}
        ), 403

    if sec_fetch_site == "cross-site" and not origin_trusted:
        return jsonify(
            {"error": "forbidden", "detail": "CSRF validation failed: cross-site request blocked."}
        ), 403

    cookie_token = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
    has_bearer = request.headers.get("Authorization", "").startswith("Bearer ")
    if cookie_token and not has_bearer:
        csrf_header = request.headers.get("X-CSRF-Token", "").strip()
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME, "").strip()
        verify_fn = getattr(ctx.auth, "verify_csrf_token", None)
        csrf_valid = False
        if csrf_header:
            if (callable(verify_fn) and verify_fn(cookie_token, csrf_header)) or (
                csrf_cookie and hmac.compare_digest(csrf_cookie, csrf_header)
            ):
                csrf_valid = True
            else:
                return jsonify(
                    {"error": "forbidden", "detail": "CSRF validation failed: invalid CSRF token."}
                ), 403
        is_logout = path == "/api/auth/logout" or (
            path == "/api/auth/session" and request.method == "DELETE"
        )
        has_custom_header = bool(request.headers.get("X-Requested-With", "").strip())
        if not is_logout and not (
            csrf_valid or has_custom_header or origin_trusted or referer_trusted
        ):
            return jsonify(
                {
                    "error": "forbidden",
                    "detail": "CSRF validation failed for cookie-authenticated mutation.",
                }
            ), 403
    return None


def _is_protected_reader_path(path: str) -> bool:
    """Require the same authentication on every alias of the hosted PDF/reader routes."""
    return path == "/read" or path.startswith(("/read/", "/open/", "/papers/", "/pdfs/"))


def register_middleware(app: Flask, ctx: AppContext) -> None:
    """Register the request guard, security headers and JSON error handlers."""

    @app.before_request
    def _guard():
        path = request.path
        if is_shutting_down() or not begin_request():
            return _shutting_down_response(is_health_probe=path in HEALTH_PATHS)
        request._archipelago_in_flight = True  # type: ignore[attr-defined]
        if request.method == "OPTIONS":
            return ("", OPTIONS_NO_CONTENT)
        if _is_blocked_dotfile_or_artifact(path):
            return jsonify({"error": "not_found"}), 404
        csrf_rejection = _check_csrf(ctx, path)
        if csrf_rejection is not None:
            return csrf_rejection
        if (
            path.startswith("/api/research/") and path not in PUBLIC_API
        ) or path == "/api/scholarly/snapshot":
            principal, _error = ctx.auth.principal()
            if principal is None or not principal.get("id"):
                audit_action(
                    user_id=None, role=None, action="research_access", result="unauthorized"
                )
                return jsonify({"error": "unauthorized"}), 401
            capability = _research_capability(path, request.method)
            student_metadata = (
                path.startswith("/api/research/intelligence/")
                and principal.get("role") == "student"
                and capability == ResearchCapability.SEARCH
            )
            if not student_metadata and not allowed(principal.get("role"), capability):
                audit_action(
                    user_id=str(principal["id"]),
                    role=principal.get("role"),
                    action=capability.value,
                    result="forbidden",
                )
                return jsonify({"error": "forbidden"}), 403
            request.archipelago_principal = principal  # type: ignore[attr-defined]
        if path.startswith("/api/ingest") and path != "/api/ingest/capabilities":
            principal, error = ctx.auth.principal()
            if principal is None:
                return jsonify({"error": "unauthorized", "detail": error}), 401
            if principal.get("role") not in LIBRARIAN_ROLES:
                return jsonify(
                    {
                        "error": "forbidden",
                        "detail": "A librarian or administrator session is required.",
                    }
                ), 403
        # Protect all PDF and reader route aliases when authentication is enabled.
        # An alternate path must never bypass the normal private-library guard.
        if _is_protected_api(path) or (ctx.auth.required() and _is_protected_reader_path(path)):
            principal, error = ctx.auth.principal()
            if principal is None:
                return jsonify(
                    {"error": "unauthorized", "detail": error, "reason": auth_failure_code(error)}
                ), 401
            request.archipelago_principal = principal  # type: ignore[attr-defined]
        if path.startswith("/api/chat"):
            return _apply_limit(ctx.limiter.check_chat())
        if (
            path.startswith("/api/auth/")
            and request.method not in SAFE_METHODS
            and path != "/api/auth/logout"
            and not (path == "/api/auth/session" and request.method == "DELETE")
        ):
            check_auth = getattr(ctx.limiter, "check_auth", ctx.limiter.check_api)
            return _apply_limit(check_auth())
        if path.startswith("/api/") or _is_protected_reader_path(path):
            return _apply_limit(ctx.limiter.check_api())
        return None

    @app.teardown_request
    def _release_in_flight(_exc=None):
        if getattr(request, "_archipelago_in_flight", False):
            request._archipelago_in_flight = False  # type: ignore[attr-defined]
            end_request()

    def _is_protected_api(path: str) -> bool:
        if not path.startswith("/api/"):
            return False
        if path == "/api/internal/s5-monitor-tick":
            return False  # The route requires CRON_SECRET instead of a user session.
        if path in PUBLIC_API or path.startswith(PUBLIC_API_PREFIXES):
            return False
        return ctx.auth.required()

    def _apply_limit(result: tuple[bool, int]):
        limited, retry_after = result
        return _rate_limited_response(retry_after) if limited else None

    @app.after_request
    def _security_and_cors(response):
        quota = getattr(request, "archipelago_quota", None)
        if quota:
            response.headers["X-Queries-Remaining"] = str(quota["remaining"])
            response.headers["X-Queries-Used"] = str(quota["used"])
            if "limit" in quota:
                response.headers["X-Queries-Limit"] = str(quota["limit"])
        origin = request.headers.get("Origin", "").strip()
        if (
            origin
            and origin != "*"
            and (
                origin in ALLOWED_ORIGINS
                or (
                    request.path in {"/api/auth/handoff-ticket", "/api/auth/handoff-redeem"}
                    and is_allowed_handoff_origin(origin)
                )
            )
        ):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = CORS_HEADERS
            response.headers["Access-Control-Allow-Methods"] = CORS_METHODS
            response.headers.add("Vary", "Origin")
        has_auth = (
            bool(request.headers.get("Authorization"))
            or bool(request.cookies.get(SESSION_COOKIE_NAME))
            or getattr(request, "archipelago_principal", None) is not None
        )
        if request.path.startswith("/api/") or has_auth:
            existing_cc = response.headers.get("Cache-Control", "")
            if not existing_cc or ("no-store" not in existing_cc and "public" not in existing_cc):
                response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        csp = CONTENT_SECURITY_POLICY
        supabase_origin = _origin_from_url(os.getenv("SUPABASE_URL", ""))
        if supabase_origin and supabase_origin not in csp:
            csp = csp.replace(
                "connect-src 'self'",
                f"connect-src 'self' {supabase_origin}",
                1,
            )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Archipelago-Mode"] = "inference-only"
        response.headers["X-Archipelago-Release"] = runtime_release_sha()
        return response

    @app.errorhandler(400)
    def handle_bad_request(_error):
        return jsonify(
            {"error": "bad_request", "detail": "The request was invalid or malformed."}
        ), 400

    @app.errorhandler(403)
    def handle_forbidden(_error):
        return jsonify(
            {"error": "forbidden", "detail": "Access to this resource is prohibited."}
        ), 403

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify(
            {"error": "not_found", "detail": "The requested resource could not be found."}
        ), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(_error):
        return jsonify(
            {
                "error": "method_not_allowed",
                "detail": "The HTTP method is not allowed for this endpoint.",
            }
        ), 405

    @app.errorhandler(413)
    def handle_payload_too_large(_error):
        return jsonify(
            {
                "error": "payload_too_large",
                "detail": "The request payload exceeds the maximum allowed size.",
            }
        ), 413

    @app.errorhandler(429)
    def handle_rate_limit(_error):
        return jsonify(
            {"error": "rate_limited", "detail": "Too many requests. Please slow down."}
        ), 429

    @app.errorhandler(500)
    def handle_internal_error(error):
        app.logger.error("Internal Server Error: %s", redact(str(error)))
        return jsonify(
            {"error": "internal_error", "detail": "An internal server error occurred."}
        ), 500


__all__ = ["register_middleware"]
