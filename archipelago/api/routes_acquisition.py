"""Librarian routes: unmet-demand digest and the acquisition review plan.

Two endpoints, both behind the existing librarian auth boundary (the
``/api/ingest`` prefix is already staff-gated in ``archipelago.api.bootstrap``),
because both expose what the library does *not* hold — an internal procurement
signal, not a student-facing answer.

``/api/librarian/demand-digest`` answers "what is being asked for and not
stocked". ``/api/librarian/acquisition-plan`` adds "what could we buy", matched
against the Pearson catalogue the institution already pays for.  Neither route
purchases anything or writes to the OPAC: every candidate carries
``action_required: librarian_review``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Response, jsonify, request

from archipelago.api.engine_state import app

logger = logging.getLogger("archipelago.api.librarian")

SUCCESS_STATUS = 200
ERROR_STATUS = 500

#: Where the hosted engine persists unmet demand. Overridable so a deployment
#: can mount institutional state on a volume.
DEMAND_DIGEST_ENV = "ARCHIPELAGO_STATE_DIR"
DEMAND_DIGEST_RELPATH = Path("data") / "demand_digest.json"

#: Floor on the digest for a plan to be actionable: one mention is curiosity.
DEFAULT_MIN_DEMAND_COUNT = 2

#: Cap on returned candidates, so one popular request cannot blow up the page.
MAX_PLAN_ROWS = 25


def _digest_rows(min_count: int = 1) -> list[dict]:
    """Unmet-demand rows, most requested first. Empty when none are recorded.

    Read here rather than imported from ``host_inference``: the hosted engine is
    a separate deployable that must not become an import-time dependency here.
    """
    import os

    override = os.environ.get(DEMAND_DIGEST_ENV, "").strip()
    path = Path(override) / DEMAND_DIGEST_RELPATH if override else DEMAND_DIGEST_RELPATH
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable demand digest %s: %s", path, exc)
        return []
    titles = raw.get("titles") if isinstance(raw, dict) else None
    rows = [row for row in (titles or {}).values() if isinstance(row, dict)]
    rows = [row for row in rows if int(row.get("count") or 0) >= min_count]
    rows.sort(key=lambda row: (-int(row.get("count") or 0), str(row.get("last_seen") or "")))
    return rows


@app.route("/api/librarian/demand-digest", methods=["GET"])
def librarian_demand_digest() -> Response:
    """Unmet titles the students keep asking for, most requested first."""
    try:
        raw_min = request.args.get("min_count", "")
        min_count = max(1, int(raw_min)) if raw_min.isdigit() else 1
    except (TypeError, ValueError):
        min_count = 1
    rows = _digest_rows(min_count)
    return jsonify(
        {
            "status": "success",
            "min_count": min_count,
            "count": len(rows),
            "titles": rows,
            "note": "Titles asked for that the catalogue does not hold. "
            "Repeated asking is the acquisition signal.",
        }
    ), SUCCESS_STATUS


@app.route("/api/librarian/acquisition-plan", methods=["GET"])
def librarian_acquisition_plan() -> Response:
    """Unmet demand matched against buyable sources, for librarian review."""
    from archipelago.ingestion.acquisition_discovery import discovery_plan

    raw_min = request.args.get("min_count", "")
    try:
        min_count = max(1, int(raw_min)) if raw_min.isdigit() else DEFAULT_MIN_DEMAND_COUNT
    except (TypeError, ValueError):
        min_count = DEFAULT_MIN_DEMAND_COUNT
    dataset_id = request.args.get("apify_dataset", "")

    plan = discovery_plan(_digest_rows(min_count), include_apify_dataset=dataset_id)
    plan["status"] = "success"
    plan["min_count"] = min_count
    plan["note"] = (
        "Review list only. Nothing is purchased and no record is written to the "
        "OPAC; each candidate carries action_required=librarian_review."
    )
    plan["rows"] = plan["rows"][:MAX_PLAN_ROWS]
    return jsonify(plan), SUCCESS_STATUS


__all__ = [
    "DEFAULT_MIN_DEMAND_COUNT",
    "DEMAND_DIGEST_ENV",
    "DEMAND_DIGEST_RELPATH",
    "MAX_PLAN_ROWS",
    "librarian_acquisition_plan",
    "librarian_demand_digest",
]
