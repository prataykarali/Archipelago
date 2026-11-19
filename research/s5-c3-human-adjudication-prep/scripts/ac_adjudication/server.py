"""Offline 127.0.0.1-only Flask UI for human A/C disagreement adjudication."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request

from .constants import (
    DEFAULT_UI_PORT,
    GRADE_IRRELEVANT,
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
    HTTP_OK,
    LOOPBACK_HOST,
    MIN_RATIONALE_LENGTH,
    VALID_GRADES,
    WORKSHEET_STATUS_COMPLETED,
    WORKSHEET_STATUS_IN_PROGRESS,
)
from .pool_index import FrozenPool, sha256_bytes
from .provenance import is_valid_human_identifier, validate_adjudicator_provenance
from .ui_template import ADJUDICATION_UI_HTML


def _atomic_write_worksheet(worksheet_path: Path, payload: dict[str, Any]) -> str:
    """Write worksheet JSON atomically and update its `.sha256` sidecar file."""
    worksheet_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    digest = sha256_bytes(rendered)
    tmp_path = worksheet_path.with_suffix(worksheet_path.suffix + ".tmp")
    tmp_path.write_bytes(rendered)
    tmp_path.replace(worksheet_path)
    sha_path = worksheet_path.with_suffix(worksheet_path.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {worksheet_path.name}\n", encoding="utf-8")
    return digest


def _count_completed(worksheet: dict[str, Any]) -> int:
    """Count disagreement items with valid grade, rationale, and adjudicator_id."""
    count = 0
    for item in worksheet.get("disagreements", []):
        grade = item.get("adjudicated_grade")
        rationale = str(item.get("adjudication_rationale", "")).strip()
        adj_id = item.get("adjudicator_id")
        if (
            type(grade) is int
            and grade in VALID_GRADES
            and len(rationale) >= MIN_RATIONALE_LENGTH
            and is_valid_human_identifier(adj_id)
        ):
            count += 1
    return count


def create_adjudication_app(worksheet_path: Path, pool: FrozenPool) -> Flask:
    """Create a strictly offline local Flask application for human A/C adjudication."""
    app = Flask(__name__)

    def _load() -> dict[str, Any]:
        return json.loads(worksheet_path.read_text(encoding="utf-8"))

    @app.get("/")
    def index() -> Response:
        return Response(ADJUDICATION_UI_HTML, mimetype="text/html")

    @app.get("/api/readiness")
    def readiness() -> tuple[Response, int]:
        return jsonify({"ready": True, "mode": "offline_local_adjudication"}), HTTP_OK

    @app.get("/api/worksheet")
    def get_worksheet() -> tuple[Response, int]:
        ws = _load()
        total = len(ws.get("disagreements", []))
        return (
            jsonify(
                {
                    "worksheet": ws,
                    "completed_count": _count_completed(ws),
                    "total_disagreements": total,
                }
            ),
            HTTP_OK,
        )

    @app.post("/api/decision")
    def save_decision() -> tuple[Response, int]:
        body = request.get_json(silent=True) or {}
        pair_id = body.get("pair_id")
        grade = body.get("adjudicated_grade")
        quote = str(body.get("adjudication_evidence_quote", "")).strip()
        rationale = str(body.get("adjudication_rationale", "")).strip()
        adjudicator_id = body.get("adjudicator_id")

        if type(grade) is not int or grade not in VALID_GRADES:
            return jsonify({"error": "adjudicated_grade must be 0, 1, or 2"}), HTTP_BAD_REQUEST
        if len(rationale) < MIN_RATIONALE_LENGTH:
            return (
                jsonify({"error": f"Human rationale must be at least {MIN_RATIONALE_LENGTH} chars"}),
                HTTP_BAD_REQUEST,
            )
        if not is_valid_human_identifier(adjudicator_id):
            return jsonify({"error": "Valid human adjudicator_id is required"}), HTTP_BAD_REQUEST
        if grade == GRADE_IRRELEVANT and quote:
            return jsonify({"error": "Quote must be blank when grade is 0"}), HTTP_BAD_REQUEST
        if grade != GRADE_IRRELEVANT and not quote:
            return jsonify({"error": "Verbatim quote is required for grade 1 or 2"}), HTTP_BAD_REQUEST

        ws = _load()
        target: dict[str, Any] | None = None
        for item in ws.get("disagreements", []):
            if item.get("pair_id") == pair_id:
                target = item
                break
        if target is None:
            return jsonify({"error": f"Unknown disagreement pair_id {pair_id!r}"}), HTTP_NOT_FOUND

        canonical_text = (
            pool.entries_by_pair_id[pair_id].passage_text
            if pair_id in pool.entries_by_pair_id
            else None
        ) or target.get("passage_text")
        if grade != GRADE_IRRELEVANT and canonical_text and quote not in canonical_text:
            return (
                jsonify({"error": "Quote must be an exact verbatim substring of the passage"}),
                HTTP_BAD_REQUEST,
            )

        target["adjudicated_grade"] = grade
        target["adjudication_evidence_quote"] = quote
        target["adjudication_rationale"] = rationale
        target["adjudicator_id"] = str(adjudicator_id).strip()
        target["decision_timestamp_utc"] = datetime.now(UTC).isoformat()

        total = len(ws.get("disagreements", []))
        completed = _count_completed(ws)
        ws["status"] = (
            WORKSHEET_STATUS_COMPLETED if completed == total else WORKSHEET_STATUS_IN_PROGRESS
        )
        digest = _atomic_write_worksheet(worksheet_path, ws)
        return (
            jsonify(
                {
                    "message": f"Saved human decision for {pair_id} ({completed}/{total}).",
                    "worksheet_sha256": digest,
                }
            ),
            HTTP_OK,
        )

    @app.post("/api/provenance")
    def save_provenance() -> tuple[Response, int]:
        body = request.get_json(silent=True) or {}
        ws = _load()
        total = len(ws.get("disagreements", []))
        candidate = {
            "adjudicator_id": body.get("adjudicator_id", ""),
            "provenance_class": body.get("provenance_class", ""),
            "assistance_declaration": body.get("assistance_declaration", ""),
            "human_attestation_signed": body.get("human_attestation_signed", False),
            "attestation_signer": body.get("attestation_signer", ""),
            "signed_timestamp_utc": datetime.now(UTC).isoformat(),
        }
        errors = validate_adjudicator_provenance(candidate, total_disagreements=total)
        if errors:
            return jsonify({"error": "; ".join(errors)}), HTTP_BAD_REQUEST

        ws["adjudicator_provenance"] = candidate
        digest = _atomic_write_worksheet(worksheet_path, ws)
        return (
            jsonify(
                {
                    "message": "Saved signed human adjudicator provenance.",
                    "worksheet_sha256": digest,
                }
            ),
            HTTP_OK,
        )

    return app


def run_local_adjudication_server(
    worksheet_path: Path,
    pool: FrozenPool,
    *,
    host: str = LOOPBACK_HOST,
    port: int = DEFAULT_UI_PORT,
) -> None:
    """Start the offline adjudication server strictly on 127.0.0.1."""
    if host != LOOPBACK_HOST:
        raise ValueError(
            f"Refusing to bind adjudication UI to non-loopback host {host!r}; "
            f"only {LOOPBACK_HOST!r} is permitted."
        )
    app = create_adjudication_app(worksheet_path, pool)
    app.run(host=LOOPBACK_HOST, port=port, debug=False)
