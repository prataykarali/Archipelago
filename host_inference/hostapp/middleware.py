"""Request guard, security headers, CORS and error handlers for the hosted app.

One concern: cross-cutting request policy, registered once against the Flask app.
"""

from __future__ import annotations

from flask import Flask, jsonify, request

from .config import (
    ALLOWED_ORIGINS,
    INGESTION_PREFIXES,
    PUBLIC_API,
    PUBLIC_API_PREFIXES,
)
from .context import AppContext

OPTIONS_NO_CONTENT = 204

CORS_METHODS = "GET,POST,DELETE,OPTIONS"
CORS_HEADERS = "Content-Type,Authorization,X-Requested-With"

# Runtime assets are built with the Tailwind Play CDN, so the policy allows the
# specific CDNs the UI loads rather than 'unsafe-eval'.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'self'; "
    "form-action 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
    "font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob: https:; "
    "connect-src 'self' https://spllaastejfwclllfndp.supabase.co; "
    "frame-src 'self' https://ebooks.elibrary.in.pearson.com https://elibrary.in.pearson.com https://huggingface.co; "
    "worker-src 'self' blob: https://cdnjs.cloudflare.com"
)


def _rate_limited_response(retry_after: int):
    response = jsonify({"error": "rate_limited", "retry_after": retry_after})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


def register_middleware(app: Flask, ctx: AppContext) -> None:
    """Register the request guard, security headers and JSON error handlers."""

    @app.before_request
    def _guard():
        if request.method == "OPTIONS":
            return ("", OPTIONS_NO_CONTENT)
        path = request.path
        if path.startswith(INGESTION_PREFIXES):
            return jsonify(
                {
                    "error": "forbidden",
                    "detail": "Ingestion stays on the local library workstation.",
                }
            ), 403
        # Library browsing, reader routes and chat stay public so an exact
        # book/page link is never blocked by a login redirect.
        if _is_protected_api(path):
            principal, error = ctx.auth.principal()
            if principal is None:
                return jsonify({"error": "unauthorized", "detail": error}), 401
            if principal.get("must_change_password") and path not in {
                "/api/auth/change-password",
                "/api/auth/me",
            }:
                return jsonify({"error": "password_change_required"}), 403
            request.archipelago_principal = principal  # type: ignore[attr-defined]
        if path.startswith("/api/chat") and path != "/api/chat/telemetry":
            return _apply_limit(ctx.limiter.check_chat())
        if path.startswith("/api/") or path.startswith("/open/") or path.startswith("/papers/"):
            return _apply_limit(ctx.limiter.check_api())
        return None

    def _is_protected_api(path: str) -> bool:
        if not path.startswith("/api/"):
            return False
        if path in PUBLIC_API or path.startswith(PUBLIC_API_PREFIXES):
            return False
        return ctx.auth.required()

    def _apply_limit(result: tuple[bool, int]):
        limited, retry_after = result
        return _rate_limited_response(retry_after) if limited else None

    @app.after_request
    def _security_and_cors(response):
        origin = request.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = CORS_HEADERS
            response.headers["Access-Control-Allow-Methods"] = CORS_METHODS
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Archipelago-Mode"] = "inference-only"
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

    @app.errorhandler(429)
    def handle_rate_limit(_error):
        return jsonify(
            {"error": "rate_limited", "detail": "Too many requests. Please slow down."}
        ), 429

    @app.errorhandler(500)
    def handle_internal_error(error):
        app.logger.error("Internal Server Error: %s", error)
        return jsonify(
            {"error": "internal_error", "detail": "An internal server error occurred."}
        ), 500


__all__ = ["register_middleware"]
