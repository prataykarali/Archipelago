"""Owner-only memory controls and aggregate-only staff learning diagnostics."""

from __future__ import annotations

from flask import jsonify, request

from ..learning_memory import RETENTION_SECONDS, LearningMemory
from .diagnostics import OWNER_COOKIE, _owner

STAFF_ROLES = frozenset({"faculty", "librarian", "administrator", "admin"})


def settings_response(memory: LearningMemory):
    """Get or delete current browser memory without accepting a supplied owner ID."""
    nonce = request.cookies.get(OWNER_COOKIE)
    if request.method == "DELETE":
        if nonce:
            memory.delete(_owner(nonce))
        response = jsonify({"enabled": False, "deleted": True})
    else:
        record = memory.load(_owner(nonce)) if nonce else {}
        response = jsonify(
            {
                "enabled": bool(record),
                "concepts": len(record.get("mastery", {})),
                "retention_days": RETENTION_SECONDS // 86400,
            }
        )
    response.headers["Cache-Control"] = "no-store, private"
    return response


def register(app, ctx) -> None:
    """Expose aggregates to verified staff only; never individual student/session records."""

    @app.get("/api/staff/learning-summary")
    def summary():
        principal, _error = ctx.auth.principal()
        if principal is None or principal.get("role") not in STAFF_ROLES:
            return jsonify({"error": "A verified faculty or librarian session is required."}), 403
        memory = app.extensions["learning_memory"]
        rows = memory.aggregate()
        graph = ctx.engine.graph
        rows = [
            {**row, "concept_label": graph.label(row["concept_id"])}
            for row in rows
            if row["concept_id"] in graph.nodes
        ]
        response = jsonify(
            {
                "minimum_cohort": 5,
                "gaps": rows,
                "individual_records": False,
                "note": "Consenting browser profiles only; not a count of distinct students.",
            }
        )
        response.headers["Cache-Control"] = "no-store, private"
        return response
