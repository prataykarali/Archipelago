"""Local-only Flask HTTP server (127.0.0.1 ONLY) for the S5-C3 annotation workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request

from .constants import (
    ALLOWED_HOST,
    DEFAULT_BACKUP_DIR,
    DEFAULT_SUBMISSIONS_DIR,
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_UNPROCESSABLE_ENTITY,
    VALID_GRADES,
)
from .loader import assert_blinding_clean
from .models import (
    AnnotationSession,
    JudgmentRecord,
    LoadedPool,
    utc_now_iso,
)
from .storage import (
    ExportValidationError,
    create_timestamped_backup,
    export_submission,
    load_or_create_session,
    save_session,
)
from .ui_template import render_workbench_html
from .validation import (
    validate_pair_judgment,
    validate_provenance,
    validate_session,
)


def assert_loopback_host(host: str) -> str:
    """Enforce that the local annotation workbench binds ONLY to 127.0.0.1."""
    normalized = host.strip()
    if normalized != ALLOWED_HOST:
        raise ValueError(
            f"Refusing non-loopback host {host!r}. "
            f"The local annotation workbench must bind strictly to {ALLOWED_HOST!r}."
        )
    return normalized


def _serialize_pair_with_state(
    pool: LoadedPool, session: AnnotationSession, pair_id: str
) -> dict[str, Any]:
    """Combine immutable blinded pair data with current judgment & validation status."""
    pair = pool.pairs_by_id[pair_id]
    judgment = session.judgments.get(pair_id) or JudgmentRecord(pair_id=pair_id)
    val = validate_pair_judgment(pair, session.judgments.get(pair_id))
    data = pair.to_public_dict()
    data["judgment"] = judgment.to_dict()
    data["validation"] = val.to_dict()
    return data


def _parse_grade(raw_grade: Any) -> int | None:
    """Parse optional relevance grade; raise ValueError on invalid values."""
    if raw_grade is None or raw_grade == "":
        return None
    if isinstance(raw_grade, bool):
        raise ValueError("relevance_grade cannot be a boolean.")
    grade = int(raw_grade)
    if grade not in VALID_GRADES:
        raise ValueError("relevance_grade must be 0, 1, or 2.")
    return grade


def create_app(
    *,
    pool: LoadedPool,
    session_path: Path,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    submissions_dir: Path = DEFAULT_SUBMISSIONS_DIR,
) -> Flask:
    """Create the local-only Flask application for human annotation."""
    html_page = render_workbench_html()
    assert_blinding_clean(html_page, "workbench HTML/CSS/JS template")

    session: AnnotationSession = load_or_create_session(pool, session_path)
    app = Flask(__name__)

    @app.get("/")
    def index() -> Response:
        return Response(html_page, status=HTTP_OK, mimetype="text/html; charset=utf-8")

    @app.get("/api/readiness")
    def readiness() -> tuple[Response, int]:
        return (
            jsonify(
                {
                    "ready": True,
                    "host_policy": ALLOWED_HOST,
                    "total_pairs": len(pool.pairs),
                    "pool_sha256": pool.pool_sha256,
                }
            ),
            HTTP_OK,
        )

    @app.get("/api/pairs")
    def list_pairs() -> tuple[Response, int]:
        report = validate_session(pool, session, require_all_complete=False)
        items = [
            _serialize_pair_with_state(pool, session, pair.pair_id)
            for pair in pool.pairs
        ]
        return (
            jsonify(
                {
                    "pool_version": pool.pool_version,
                    "pool_sha256": pool.pool_sha256,
                    "pairs": items,
                    "summary": report.to_dict(),
                    "provenance": session.provenance.to_dict(),
                }
            ),
            HTTP_OK,
        )

    @app.post("/api/pairs/<pair_id>")
    def update_pair(pair_id: str) -> tuple[Response, int]:
        if pair_id not in pool.pairs_by_id:
            return jsonify({"error": f"Unknown pair_id: {pair_id}"}), HTTP_NOT_FOUND

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON object body required."}), HTTP_BAD_REQUEST

        try:
            grade = _parse_grade(payload.get("relevance_grade"))
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), HTTP_BAD_REQUEST

        record = JudgmentRecord(
            pair_id=pair_id,
            relevance_grade=grade,
            supporting_quotation=str(payload.get("supporting_quotation") or ""),
            confidence=str(payload.get("confidence") or "").strip().upper(),
            reviewer_notes=str(payload.get("reviewer_notes") or ""),
            flagged=bool(payload.get("flagged", False)),
            updated_at_utc=utc_now_iso(),
        )
        session.judgments[pair_id] = record
        save_result = save_session(
            session, session_path, backup_dir=backup_dir, create_backup=True
        )
        pair_val = validate_pair_judgment(pool.pairs_by_id[pair_id], record)
        summary = validate_session(pool, session, require_all_complete=False)
        return (
            jsonify(
                {
                    "judgment": record.to_dict(),
                    "validation": pair_val.to_dict(),
                    "summary": summary.to_dict(),
                    "save": {
                        "session_path": str(save_result.session_path),
                        "session_sha256": save_result.session_sha256,
                        "backup_path": str(save_result.backup_path)
                        if save_result.backup_path
                        else "",
                        "backup_sha256": save_result.backup_sha256 or "",
                        "saved_at_utc": save_result.saved_at_utc,
                    },
                }
            ),
            HTTP_OK,
        )

    @app.post("/api/provenance")
    def update_provenance() -> tuple[Response, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON object body required."}), HTTP_BAD_REQUEST

        prov = session.provenance
        prov.reviewer_identity_or_pseudonym = str(
            payload.get("reviewer_identity_or_pseudonym") or ""
        ).strip()
        prov.provenance_class = str(payload.get("provenance_class") or "").strip()
        prov.assistance_declaration = str(
            payload.get("assistance_declaration") or ""
        ).strip()
        prov.review_start_date_utc = str(
            payload.get("review_start_date_utc") or ""
        ).strip()
        confirmed = bool(payload.get("human_attestation_confirmed", False))
        prov.human_attestation_confirmed = confirmed

        # Only record a human signature timestamp when the human explicitly confirms.
        if confirmed:
            now = utc_now_iso()
            prov.signed_by_human_at_utc = now
            prov.review_completion_date_utc = now
        else:
            prov.signed_by_human_at_utc = ""
            prov.review_completion_date_utc = ""

        save_result = save_session(
            session, session_path, backup_dir=backup_dir, create_backup=True
        )
        prov_errors = validate_provenance(prov)
        summary = validate_session(pool, session, require_all_complete=False)
        return (
            jsonify(
                {
                    "provenance": prov.to_dict(),
                    "provenance_valid": len(prov_errors) == 0,
                    "provenance_errors": list(prov_errors),
                    "summary": summary.to_dict(),
                    "save": {
                        "session_sha256": save_result.session_sha256,
                        "backup_sha256": save_result.backup_sha256 or "",
                    },
                }
            ),
            HTTP_OK,
        )

    @app.get("/api/validate")
    def validate_endpoint() -> tuple[Response, int]:
        report = validate_session(pool, session, require_all_complete=True)
        return jsonify(report.to_dict()), HTTP_OK

    @app.post("/api/backup")
    def backup_endpoint() -> tuple[Response, int]:
        backup_path, backup_sha = create_timestamped_backup(
            session, backup_dir=backup_dir, prefix=session_path.stem
        )
        return (
            jsonify(
                {
                    "backup_path": str(backup_path),
                    "backup_sha256": backup_sha,
                    "created_at_utc": utc_now_iso(),
                }
            ),
            HTTP_OK,
        )

    @app.post("/api/export")
    def export_endpoint() -> tuple[Response, int]:
        payload = request.get_json(silent=True) or {}
        allow_partial = bool(payload.get("allow_partial", False))
        prefix = payload.get("filename_prefix")
        try:
            result = export_submission(
                pool,
                session,
                output_dir=submissions_dir,
                backup_dir=backup_dir,
                filename_prefix=str(prefix) if prefix else None,
                allow_partial=allow_partial,
            )
        except ExportValidationError as exc:
            return (
                jsonify(
                    {
                        "error": str(exc),
                        "validation": exc.report.to_dict(),
                    }
                ),
                HTTP_UNPROCESSABLE_ENTITY,
            )

        return (
            jsonify(
                {
                    "json_path": str(result.json_path),
                    "json_sha256": result.json_sha256,
                    "csv_path": str(result.csv_path),
                    "csv_sha256": result.csv_sha256,
                    "manifest_path": str(result.manifest_path),
                    "manifest_sha256": result.manifest_sha256,
                    "backup_path": str(result.backup_path),
                    "backup_sha256": result.backup_sha256,
                    "exported_at_utc": result.exported_at_utc,
                }
            ),
            HTTP_OK,
        )

    return app
