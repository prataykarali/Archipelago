"""Small research transport for the second Vercel project."""

from __future__ import annotations

from datetime import UTC, datetime
import os
from secrets import compare_digest

from discovery import discover
from flask import Flask, Response, jsonify, request
import requests
from storage import recent_records, verify_user

app = Flask(__name__)
DAILY_TOPICS = (
    "optical character recognition",
    "distributed database transactions",
    "computer networks congestion control",
    "graph algorithms and complexity",
    "biomedical signal processing",
    "cybersecurity intrusion detection",
)
TOPICS_PER_RUN = 1
MAX_REQUEST_BYTES = 4096
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
    if request.path in {"/api/readiness", "/api/research/intake/scheduled"}:
        return None
    if request.path not in {"/api/research/intake/records", "/api/research/discover"}:
        return jsonify({"error": "not_found"}), 404
    authorization = request.headers.get("Authorization", "")
    token = (
        authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
    )
    try:
        valid = verify_user(token)
    except (requests.RequestException, ValueError):
        return jsonify({"error": "auth_unavailable"}), 503
    if not valid:
        return jsonify({"error": "unauthorized"}), 401
    return None


@app.get("/api/research/intake/records")
def records() -> tuple[object, int]:
    """Serve the current shared paper index at request time."""
    try:
        rows = recent_records()
    except (requests.RequestException, RuntimeError, ValueError):
        return jsonify({"error": "storage_unavailable"}), 503
    return jsonify({"records": rows, "count": len(rows)}), 200


@app.post("/api/research/discover")
def discover_topic() -> tuple[object, int]:
    """Fetch candidates for review without saving or ingesting them."""
    payload = request.get_json(silent=True)
    topic = str(payload.get("topic") or "") if isinstance(payload, dict) else ""
    try:
        report = discover(topic)
    except ValueError:
        return jsonify({"error": "invalid_topic"}), 400
    except requests.RequestException:
        return jsonify({"error": "source_unavailable"}), 503
    return jsonify(report), 200


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
