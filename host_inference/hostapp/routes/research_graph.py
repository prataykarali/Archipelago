"""Staff-curated details for concepts in the existing institutional graph."""

from __future__ import annotations

from datetime import UTC, datetime
import os
from urllib.parse import urlparse

from flask import Flask, current_app, jsonify, request
from flask.typing import ResponseReturnValue
import requests

from ..context import AppContext
from ..research_access import audit_action

ANNOTATION_PATH = "/rest/v1/research_graph_annotations"
MAX_SUMMARY_LENGTH = 2000
MAX_SOURCE_URL_LENGTH = 500
STORE_TIMEOUT_SECONDS = 8
EDITOR_ROLES = frozenset({"librarian", "administrator"})


def _store_config() -> tuple[str, str]:
    """Return server-only Data API credentials for the existing project."""
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url or not key:
        raise RuntimeError("Graph detail storage is not configured")
    return url, key


def _store_headers(key: str) -> dict[str, str]:
    """Build server-side headers without exposing the key to a browser."""
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def register(app: Flask, ctx: AppContext) -> None:
    """Register read and write routes for curated graph details."""

    @app.get("/api/research/graph/annotation")  # type: ignore[misc]
    def get_annotation() -> ResponseReturnValue:
        concept_id = (request.args.get("concept_id") or "").strip()
        if concept_id not in ctx.engine.graph.nodes:
            return jsonify({"error": "not_found"}), 404
        try:
            url, key = _store_config()
            response = requests.get(
                f"{url}{ANNOTATION_PATH}",
                params={
                    "select": "concept_id,summary,source_url,updated_at",
                    "concept_id": f"eq.{concept_id}",
                    "limit": "1",
                },
                headers=_store_headers(key),
                timeout=STORE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            rows = response.json()
        except (requests.RequestException, RuntimeError, ValueError):
            current_app.logger.exception("Graph annotation read failed")
            return jsonify({"error": "storage_unavailable"}), 503
        return jsonify({"annotation": rows[0] if rows else None})

    @app.post("/api/research/graph/annotation")  # type: ignore[misc]
    def save_annotation() -> ResponseReturnValue:
        principal = getattr(request, "archipelago_principal", None)
        if principal is None or principal.get("role") not in EDITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        # The browser uses a bearer token; rejecting cookie-only mutations
        # prevents a cross-site form from editing a staff account's graph.
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            return jsonify({"error": "bearer_required"}), 401
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_payload"}), 400
        concept_id = str(payload.get("concept_id") or "").strip()
        summary = str(payload.get("summary") or "").strip()
        source_url = str(payload.get("source_url") or "").strip() or None
        if concept_id not in ctx.engine.graph.nodes:
            return jsonify({"error": "not_found"}), 404
        if not summary or len(summary) > MAX_SUMMARY_LENGTH:
            return jsonify({"error": "invalid_summary"}), 400
        if source_url:
            parsed = urlparse(source_url)
            if (
                len(source_url) > MAX_SOURCE_URL_LENGTH
                or parsed.scheme != "https"
                or not parsed.netloc
            ):
                return jsonify({"error": "invalid_source_url"}), 400
        try:
            url, key = _store_config()
            response = requests.post(
                f"{url}{ANNOTATION_PATH}",
                params={"on_conflict": "concept_id"},
                json={
                    "concept_id": concept_id,
                    "summary": summary,
                    "source_url": source_url,
                    "updated_by": principal["id"],
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                headers={
                    **_store_headers(key),
                    "Prefer": "resolution=merge-duplicates,return=representation",
                },
                timeout=STORE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            rows = response.json()
        except (requests.RequestException, RuntimeError, ValueError):
            current_app.logger.exception("Graph annotation save failed")
            return jsonify({"error": "storage_unavailable"}), 503
        audit_action(
            user_id=str(principal["id"]),
            role=str(principal["role"]),
            action="graph_annotation_save",
            result="ok",
        )
        return jsonify({"annotation": rows[0] if rows else None})
