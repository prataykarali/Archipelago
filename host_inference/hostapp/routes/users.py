"""Server-authorized student roster import for the hosted librarian interface."""

from __future__ import annotations

from pathlib import PurePath
import re

from flask import Flask, jsonify, request
import requests

from ..context import AppContext
from ..student_roster import (
    MAX_ROSTER_BYTES,
    audit_import,
    existing_students,
    import_permission,
    parse_roster,
    provision_students,
    service_config,
)

CSV_SUFFIX = ".csv"
CSV_MIME_TYPES = frozenset(
    {"text/csv", "text/plain", "application/csv", "application/vnd.ms-excel"}
)
MAX_SOURCE_LABEL = 160
SOURCE_LABEL = re.compile(r"^[A-Za-z0-9._ -]{1,160}$")


def register(app: Flask, ctx: AppContext) -> None:
    """Register preview and apply routes; both require an approved staff session."""

    @app.post("/api/users/import")
    @app.post("/api/users/import/preview")
    def import_students():
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            return jsonify(
                {"error": "unauthorized", "detail": "A bearer session is required."}
            ), 401
        principal, error = ctx.auth.principal()
        if principal is None:
            return jsonify({"error": "unauthorized", "detail": error}), 401
        if principal.get("role") not in {"administrator", "librarian"}:
            return jsonify({"error": "forbidden", "detail": "Staff access is required."}), 403
        upload = request.files.get("file")
        if (
            upload is None
            or not upload.filename
            or not upload.filename.lower().endswith(CSV_SUFFIX)
            or upload.mimetype not in CSV_MIME_TYPES
        ):
            return jsonify(
                {"error": "invalid_file", "detail": "Choose a CSV spreadsheet export."}
            ), 400
        label = str(request.form.get("source_label", "")).strip()
        if label and not SOURCE_LABEL.fullmatch(label):
            return jsonify(
                {
                    "error": "invalid_source",
                    "detail": "Use letters, digits, spaces, dots, hyphens or underscores in the source label.",
                }
            ), 400
        raw = upload.read(MAX_ROSTER_BYTES + 1)
        try:
            rows = parse_roster(raw)
            url, key, password = service_config()
            permission_id = import_permission(url, key, principal, label)
            if permission_id is None:
                return jsonify(
                    {
                        "error": "forbidden",
                        "detail": "An active administrator grant for this source is required.",
                    }
                ), 403
            existing = existing_students(url, key, rows)
        except ValueError as exc:
            return jsonify({"error": "invalid_csv", "detail": str(exc)}), 400
        except (RuntimeError, requests.RequestException):
            return jsonify(
                {"error": "unavailable", "detail": "Student provisioning is unavailable."}
            ), 503
        pending = len(rows) - len(existing)
        if request.path.endswith("/preview"):
            return jsonify({"received": len(rows), "existing": len(existing), "to_create": pending})
        try:
            created, failed = provision_students(url, key, password, rows, existing)
            filename = PurePath(upload.filename).name[:MAX_SOURCE_LABEL]
            audit_import(
                url, key, principal, permission_id, filename, raw, len(rows), created, failed
            )
        except requests.RequestException:
            return jsonify(
                {
                    "error": "partial_failure",
                    "detail": "Import stopped. Retry the same file; existing accounts will be skipped.",
                }
            ), 503
        status = 200 if failed == 0 else 207
        return jsonify(
            {"received": len(rows), "existing": len(existing), "created": created, "failed": failed}
        ), status
