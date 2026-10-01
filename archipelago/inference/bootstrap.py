"""Wire Flask routes and one shared auth boundary onto state.app."""
from flask import g, jsonify, request

from archipelago.inference import routes_misc  # noqa: F401
from archipelago.inference import routes_chat  # noqa: F401
from archipelago.inference import routes_page_view  # noqa: F401
from archipelago.inference.state import app
from archipelago.inference.routes_chat import init_concepts_data
from archipelago.auth import load_user
from archipelago import supabase_auth

app.before_request(load_user)

_PUBLIC_PATHS = frozenset({
    "/api/readiness",
    "/api/health",
    "/api/ingest/capabilities",
    "/api/auth/config",
    "/api/page-view",
    "/api/chat",
    "/api/chat/telemetry",
    "/api/chat/diagnostic-mcqs",
    "/api/chat/verify-mcq",
    "/api/chat/adaptive-step",
})
_STAFF_PREFIXES = ("/api/users", "/api/ingest", "/api/documents", "/api/manual/")


@app.before_request
def enforce_verified_session():
    """Require a Supabase principal for private inference APIs."""
    if request.method == "OPTIONS" or request.path in _PUBLIC_PATHS:
        return None
    if request.path.startswith("/api/internal/"):
        return None  # Each internal route performs its own loopback-peer check.
    if not supabase_auth.is_auth_required():
        return None

    principal = getattr(g, "archipelago_principal", None)
    if principal is None:
        principal, error = supabase_auth.authenticate_request(request)
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": error}), 401
        g.archipelago_principal = principal

    if request.path.startswith(_STAFF_PREFIXES) and principal.role not in {"librarian", "administrator"}:
        return jsonify({"error": "forbidden", "detail": "Librarian or administrator role required"}), 403
    return None
