from __future__ import annotations

import functools
import hmac
import os

from flask import g, jsonify, request

from archipelago import supabase_auth


def _extract_bearer_token() -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :].strip()
    return None


def _extract_token() -> str | None:
    return (
        _extract_bearer_token()
        or request.headers.get("X-API-Token")
        or request.headers.get("X-Librarian-Token")
    )


def load_user() -> None:
    """Set Flask principal globals from centrally verified credentials only."""
    g.authenticated = False
    g.user_role = None
    g.user_id = None
    g.archipelago_principal = None

    principal, _error = supabase_auth.authenticate_request(request)
    if principal is None:
        return

    g.archipelago_principal = principal
    g.authenticated = True
    g.user_role = principal.role
    g.user_id = principal.user_id


def require_auth(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return fn(*args, **kwargs)
        if not getattr(g, "authenticated", False):
            return jsonify({"error": "unauthorized", "detail": "Authentication required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def require_admin(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return fn(*args, **kwargs)
        principal = getattr(g, "archipelago_principal", None)
        if principal is None:
            principal, _error = supabase_auth.authenticate_request(request)
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": "Authentication required"}), 401
        if principal.role != "administrator":
            return jsonify({"error": "forbidden", "detail": "Administrator role required"}), 403
        return fn(*args, **kwargs)

    return wrapper


def librarian_token_expected() -> str:
    """Return the configured service token; an empty value never grants access."""
    return (
        os.environ.get("ARCHIPELAGO_LIBRARIAN_TOKEN", "").strip()
        or os.environ.get("ARCHIPELAGO_TOKEN", "").strip()
    )


def is_librarian_request() -> bool:
    """Return True only when a configured shared librarian token is presented."""
    expected = librarian_token_expected()
    provided = _extract_token()
    return bool(expected and provided and hmac.compare_digest(provided, expected))


def require_librarian(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return fn(*args, **kwargs)

        principal = getattr(g, "archipelago_principal", None)
        if principal is None:
            principal, auth_error = supabase_auth.authenticate_request(request)
        else:
            auth_error = None

        if principal is not None:
            if principal.role in {"librarian", "administrator"}:
                return fn(*args, **kwargs)
            return jsonify({
                "error": "forbidden",
                "detail": "Librarian or administrator role required",
            }), 403

        expected = librarian_token_expected()
        provided = _extract_token()
        if expected and provided and hmac.compare_digest(provided, expected):
            return fn(*args, **kwargs)
        if expected:
            return jsonify({
                "error": "unauthorized",
                "detail": "Librarian authentication required.",
            }), 401

        if (
            not supabase_auth.is_auth_required()
            and supabase_auth.is_dev_auth_allowed()
            and os.environ.get("ARCHIPELAGO_ALLOW_OPEN_MUTATIONS", "0").strip().lower()
            in {"1", "true", "yes"}
        ):
            return fn(*args, **kwargs)

        return jsonify({
            "error": "unauthorized",
            "detail": auth_error or "Librarian or administrator role required",
        }), 401

    return wrapper


require_token = require_librarian


def require_student_or_open(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return fn(*args, **kwargs)
        if not supabase_auth.is_auth_required():
            return fn(*args, **kwargs)
        principal, auth_error = supabase_auth.authenticate_request(request)
        if principal is None:
            return jsonify({
                "error": "unauthorized",
                "detail": auth_error or "A verified Supabase session is required",
            }), 401
        g.archipelago_principal = principal
        g.authenticated = True
        g.user_role = principal.role
        g.user_id = principal.user_id
        return fn(*args, **kwargs)

    return wrapper
