"""Supabase session routes.

One concern: telling the browser how to authenticate, issuing the session
cookie, and reporting the current principal.  Secrets never reach the client —
only the publishable key.
"""

from __future__ import annotations

import os

from flask import Flask, Response, jsonify, request

from ..config import (
    CSRF_COOKIE_NAME,
    ELEVATED_ROLES,
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
)
from ..context import AppContext
from ..security import auth_failure_code, is_safe_redirect_target

PRODUCTION_ENVS = {"production", "prod"}
ALLOWLISTED_REDIRECT_ORIGINS: tuple[str, ...] = ()


def _is_secure_cookie() -> bool:
    if os.getenv("ARCHIPELAGO_ENV", "production").lower() in PRODUCTION_ENVS:
        return True
    if os.getenv("VERCEL"):
        return True
    if request.is_secure:
        return True
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
    return forwarded_proto == "https"


def _set_private_no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
    return response


def _session_cookie_max_age() -> int:
    raw = os.getenv("ARCHIPELAGO_SESSION_MAX_AGE_SECONDS", "").strip()
    if raw:
        try:
            return max(60, int(float(raw)))
        except ValueError:
            pass
    return SESSION_COOKIE_MAX_AGE


def _set_session_cookies(response: Response, token: str, csrf_token: str) -> None:
    is_secure = _is_secure_cookie()
    max_age = _session_cookie_max_age()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
        path="/",
    )
    if csrf_token:
        response.set_cookie(
            CSRF_COOKIE_NAME,
            csrf_token,
            max_age=max_age,
            httponly=False,
            secure=is_secure,
            samesite="Lax",
            path="/",
        )


def _logout_response(ctx: AppContext) -> Response | tuple[Response, int]:
    header = request.headers.get("Authorization", "")
    bearer = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
    try:
        for tok in {bearer, cookie_token}:
            if tok:
                ctx.auth.end_session(tok)
    except RuntimeError:
        return _set_private_no_store(
            jsonify({"error": "unavailable", "detail": "Session revocation is unavailable."})
        ), 503
    is_secure = _is_secure_cookie()
    response = jsonify({"authenticated": False, "logged_out": True})
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=is_secure,
        samesite="Lax",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        httponly=False,
        secure=is_secure,
        samesite="Lax",
    )
    response.headers["Clear-Site-Data"] = '"cookies", "storage"'
    return _set_private_no_store(response)


def register(app: Flask, ctx: AppContext) -> None:
    """Register auth routes on ``app``."""

    @app.get("/api/auth/config")
    def auth_config():
        url, key = ctx.auth.supabase()
        configured = bool(url and key)
        return _set_private_no_store(
            jsonify(
                {
                    "configured": configured,
                    "required": ctx.auth.required(),
                    "url": url if configured else None,
                    "publishableKey": key if configured else None,
                    "chatUrl": None,
                    "graphUrl": None,
                }
            )
        )

    @app.route("/api/auth/session", methods=["POST", "DELETE", "OPTIONS"])
    def auth_session():
        if request.method == "DELETE":
            return _logout_response(ctx)
        body = request.get_json(silent=True)
        body_dict = body if isinstance(body, dict) else {}
        requested_redirect = (
            request.args.get("next")
            or request.args.get("redirect")
            or body_dict.get("next")
            or body_dict.get("redirect")
        )
        if requested_redirect is not None and not is_safe_redirect_target(
            str(requested_redirect), allowlisted_origins=ALLOWLISTED_REDIRECT_ORIGINS
        ):
            return _set_private_no_store(
                jsonify({"error": "bad_request", "detail": "Invalid redirect target."})
            ), 400
        principal, error = ctx.auth.principal()
        if principal is None:
            return _set_private_no_store(jsonify({"error": "unauthorized", "detail": error})), 401
        existing_cookie = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
        rotate = getattr(ctx.auth, "rotate_session", None)
        csrf_token = (
            rotate(principal.get("token", ""), previous_token=existing_cookie)
            if callable(rotate)
            else ""
        )
        payload = {
            "authenticated": True,
            "role": principal["role"],
            "csrf_token": csrf_token,
        }
        if requested_redirect is not None:
            payload["redirect"] = str(requested_redirect)
        response = jsonify(payload)
        _set_session_cookies(response, principal.get("token", ""), csrf_token)
        return _set_private_no_store(response)

    @app.route("/api/auth/logout", methods=["POST", "DELETE", "OPTIONS"])
    def auth_logout():
        return _logout_response(ctx)

    @app.post("/api/auth/handoff-ticket")
    def auth_handoff_ticket():
        principal, error = ctx.auth.principal()
        if principal is None or not principal.get("id"):
            return _set_private_no_store(
                jsonify({"error": "unauthorized", "detail": error or "Session required."})
            ), 401
        if principal.get("role") not in ELEVATED_ROLES:
            return _set_private_no_store(
                jsonify({"error": "forbidden", "detail": "A staff account is required."})
            ), 403
        body = request.get_json(silent=True)
        body_dict = body if isinstance(body, dict) else {}
        target_origin = str(body_dict.get("target_origin") or body_dict.get("target") or "").strip()
        nonce = str(body_dict.get("nonce") or body_dict.get("state") or "").strip()
        issue = getattr(ctx.auth, "issue_handoff_ticket", None)
        if not callable(issue):
            return _set_private_no_store(
                jsonify({"error": "unavailable", "detail": "Session handoff is unavailable."})
            ), 503
        ticket_payload, ticket_error = issue(principal, target_origin, nonce=nonce)
        if ticket_payload is None:
            return _set_private_no_store(
                jsonify({"error": "bad_request", "detail": ticket_error})
            ), 400
        ticket_payload["state"] = ticket_payload.get("nonce", "")
        return _set_private_no_store(jsonify(ticket_payload))

    @app.post("/api/auth/handoff-redeem")
    def auth_handoff_redeem():
        body = request.get_json(silent=True)
        body_dict = body if isinstance(body, dict) else {}
        ticket = str(body_dict.get("ticket") or "").strip()
        nonce = str(body_dict.get("nonce") or body_dict.get("state") or "").strip()
        caller_origin = (
            request.headers.get("Origin", "").strip()
            or str(body_dict.get("target_origin") or body_dict.get("origin") or "").strip()
        )
        redeem = getattr(ctx.auth, "redeem_handoff_ticket", None)
        if not callable(redeem):
            return _set_private_no_store(
                jsonify({"error": "unavailable", "detail": "Session handoff is unavailable."})
            ), 503
        principal, error = redeem(ticket, origin=caller_origin, nonce=nonce)
        if principal is None:
            return _set_private_no_store(jsonify({"error": "unauthorized", "detail": error})), 401
        existing_cookie = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
        rotate = getattr(ctx.auth, "rotate_session", None)
        csrf_token = (
            rotate(principal.get("token", ""), previous_token=existing_cookie)
            if callable(rotate)
            else ""
        )
        response = jsonify(
            {
                "authenticated": True,
                "id": principal["id"],
                "role": principal["role"],
                "username": principal["username"],
                "csrf_token": csrf_token,
                "nonce": principal.get("nonce", ""),
                "state": principal.get("nonce", ""),
            }
        )
        _set_session_cookies(response, principal.get("token", ""), csrf_token)
        return _set_private_no_store(response)

    @app.get("/api/auth/me")
    def auth_me():
        if not ctx.auth.required():
            return _set_private_no_store(
                jsonify({"authenticated": False, "role": "student", "open": True})
            )
        principal, error = ctx.auth.principal()
        if principal is None:
            reason = auth_failure_code(error)
            return _set_private_no_store(
                jsonify({"authenticated": False, "detail": error, "reason": reason})
            ), 503 if reason == "upstream_unavailable" else 401
        csrf_for = getattr(ctx.auth, "csrf_token_for", None)
        csrf_token = csrf_for(principal.get("token", "")) if callable(csrf_for) else ""
        return _set_private_no_store(
            jsonify(
                {
                    "authenticated": True,
                    "id": principal["id"],
                    "role": principal["role"],
                    "username": principal["username"],
                    "csrf_token": csrf_token,
                }
            )
        )

    @app.post("/api/auth/keepalive")
    def auth_keepalive():
        """Record genuine user interaction (never called by passive background timers)."""
        if not ctx.auth.required():
            return _set_private_no_store(jsonify({"authenticated": False, "open": True}))
        if request.headers.get("X-User-Interaction", "").strip() != "1":
            return _set_private_no_store(
                jsonify({"error": "bad_request", "detail": "User interaction header required."})
            ), 400
        principal, error = ctx.auth.principal()
        if principal is None:
            reason = auth_failure_code(error)
            return _set_private_no_store(
                jsonify({"authenticated": False, "detail": error, "reason": reason})
            ), 503 if reason == "upstream_unavailable" else 401
        return _set_private_no_store(jsonify({"authenticated": True, "active": True}))
