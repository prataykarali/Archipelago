"""Unit tests for API response status codes and error handling.

Tests 401 Unauthorized, 403 Forbidden, 404 Not Found, 429 Rate Limiting,
and 503 Service Unavailable / Shutdown handling.
"""

from __future__ import annotations

import pytest
from flask import Flask, jsonify
from archipelago.middleware.rate_limiter import RateLimiter, rate_limit
import archipelago.middleware.shutdown as shutdown_module


@pytest.fixture
def test_app() -> Flask:
    """Configures a minimal test app with middleware."""
    app = Flask(__name__)
    shutdown_module.setup_shutdown_handlers(app)

    @app.route("/api/test-rate-limit")
    @rate_limit(tier="anonymous")
    def limited_endpoint():
        return jsonify({"status": "ok"})

    @app.route("/api/protected-admin")
    def admin_endpoint():
        from flask import request
        auth = request.headers.get("Authorization")
        if not auth:
            return jsonify({"error": "Unauthorized"}), 401
        if "admin" not in auth:
            return jsonify({"error": "Forbidden"}), 403
        return jsonify({"status": "admin_granted"})

    return app


@pytest.mark.unit
def test_401_unauthorized(test_app: Flask) -> None:
    """Missing credentials return 401."""
    client = test_app.test_client()
    resp = client.get("/api/protected-admin")
    assert resp.status_code == 401


@pytest.mark.unit
def test_403_forbidden(test_app: Flask) -> None:
    """Non-admin credentials accessing admin route return 403."""
    client = test_app.test_client()
    resp = client.get("/api/protected-admin", headers={"Authorization": "Bearer student-token"})
    assert resp.status_code == 403


@pytest.mark.unit
def test_404_not_found(test_app: Flask) -> None:
    """Non-existent endpoints return standard 404."""
    client = test_app.test_client()
    resp = client.get("/api/non_existent_route_xyz")
    assert resp.status_code == 404


@pytest.mark.unit
def test_429_rate_limiting(test_app: Flask) -> None:
    """Exceeding requests returns HTTP 429 with Retry-After header."""
    client = test_app.test_client()
    # Anonymous tier limit is 5 req/min
    responses = [client.get("/api/test-rate-limit") for _ in range(7)]
    statuses = [r.status_code for r in responses]
    assert 429 in statuses
    r429 = next(r for r in responses if r.status_code == 429)
    assert "Retry-After" in r429.headers


@pytest.mark.unit
def test_503_graceful_shutdown(test_app: Flask) -> None:
    """When service is shutting down, endpoints return 503 Service Unavailable."""
    client = test_app.test_client()
    shutdown_module.is_shutting_down = True
    try:
        resp = client.get("/api/test-rate-limit")
        assert resp.status_code == 503
    finally:
        shutdown_module.is_shutting_down = False
