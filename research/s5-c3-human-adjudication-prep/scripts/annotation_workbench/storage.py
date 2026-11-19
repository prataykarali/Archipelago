"""Private-path atomic storage, timestamped backups, SHA-256 hashing, and export."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .constants import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_SUBMISSIONS_DIR,
    MANIFEST_SCHEMA_VERSION,
    PRIVATE_ANNOTATION_ROOT,
    REPO_ROOT,
    SUBMISSION_CSV_COLUMNS,
    SUBMISSION_SCHEMA_VERSION,
)
from .models import (
    AnnotationSession,
    LoadedPool,
    sha256_bytes,
    sha256_file,
    utc_now_iso,
    utc_timestamp_compact,
)
from .validation import SessionValidationReport, validate_session


class PrivatePathViolationError(ValueError):
    """Raised when a save, backup, or export targets a Git-tracked repo path."""


class ExportValidationError(ValueError):
    """Raised when an export is attempted with incomplete or unsigned data."""

    def __init__(self, message: str, report: SessionValidationReport) -> None:
        super().__init__(message)
        self.report = report


@dataclass(frozen=True)
class SaveArtifactResult:
    """Result returned after saving a session file and timestamped backup."""

    session_path: Path
    session_sha256: str
    backup_path: Path | None
    backup_sha256: str | None
    saved_at_utc: str


@dataclass(frozen=True)
class ExportArtifactResult:
    """Result returned after exporting validated JSON, CSV, manifest, and backup."""

    json_path: Path
    json_sha256: str
    csv_path: Path
    csv_sha256: str
    manifest_path: Path
    manifest_sha256: str
    backup_path: Path
    backup_sha256: str
    exported_at_utc: str


def ensure_private_path(target: Path) -> Path:
    """Ensure target path is NOT inside a Git-tracked repository directory.

    Allowed locations:
    1. Inside `data/annotation_local/` (Git-ignored private root).
    2. Outside the repository root (e.g. pytest `tmp_path` or user private dir).
    """
    resolved = target.resolve()
    repo_resolved = REPO_ROOT.resolve()
    private_resolved = PRIVATE_ANNOTATION_ROOT.resolve()

    try:
        resolved.relative_to(repo_resolved)
    except ValueError:
        return resolved

    try:
        resolved.relative_to(private_resolved)
    except ValueError as exc:
        raise PrivatePathViolationError(
            f"Refusing to write private annotation artifact into tracked repo path: "
            f"{resolved}. Use a path under {private_resolved}."
        ) from exc

    return resolved


def atomic_write_bytes(target: Path, data: bytes) -> str:
    """Atomically write bytes to a private path and return its SHA-256 digest."""
    resolved = ensure_private_path(target)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(resolved.parent), prefix=f".{resolved.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, resolved)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return sha256_bytes(data)


def load_or_create_session(pool: LoadedPool, session_path: Path) -> AnnotationSession:
    """Load an existing private session or initialize a blank one (never auto-signed)."""
    resolved = ensure_private_path(session_path)
    if resolved.exists():
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        session = AnnotationSession.from_dict(payload)
        if session.pool_sha256 and session.pool_sha256 != pool.pool_sha256:
            raise ValueError(
                f"Session {resolved} belongs to pool SHA {session.pool_sha256}, "
                f"expected {pool.pool_sha256}."
            )
        session.pool_version = pool.pool_version
        session.pool_sha256 = pool.pool_sha256
        return session

    return AnnotationSession(
        pool_version=pool.pool_version,
        pool_sha256=pool.pool_sha256,
    )


def create_timestamped_backup(
    session: AnnotationSession,
    *,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    prefix: str = "session_backup",
) -> tuple[Path, str]:
    """Write a timestamped JSON backup plus `.sha256` sidecar under a private path."""
    resolved_dir = ensure_private_path(backup_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_timestamp_compact()
    backup_path = resolved_dir / f"{prefix}_{stamp}.json"
    encoded = (json.dumps(session.to_dict(), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    digest = atomic_write_bytes(backup_path, encoded)
    sidecar = backup_path.with_suffix(".json.sha256")
    atomic_write_bytes(sidecar, f"{digest}  {backup_path.name}\n".encode())
    return backup_path, digest


def save_session(
    session: AnnotationSession,
    session_path: Path,
    *,
    backup_dir: Path | None = DEFAULT_BACKUP_DIR,
    create_backup: bool = True,
) -> SaveArtifactResult:
    """Atomically save session JSON and optionally create a timestamped backup."""
    now = utc_now_iso()
    session.updated_at_utc = now
    encoded = (json.dumps(session.to_dict(), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    session_sha = atomic_write_bytes(session_path, encoded)

    backup_path: Path | None = None
    backup_sha: str | None = None
    if create_backup and backup_dir is not None:
        backup_path, backup_sha = create_timestamped_backup(
            session, backup_dir=backup_dir, prefix=session_path.stem
        )

    return SaveArtifactResult(
        session_path=session_path.resolve(),
        session_sha256=session_sha,
        backup_path=backup_path,
        backup_sha256=backup_sha,
        saved_at_utc=now,
    )


def _safe_filename_prefix(raw_prefix: str) -> str:
    """Sanitize export filename prefix to lowercase alphanumeric + underscore/hyphen."""
    cleaned = "".join(
        ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in raw_prefix.strip()
    ).strip("_")
    return cleaned or "s5c3_human_submission"


def export_submission(
    pool: LoadedPool,
    session: AnnotationSession,
    *,
    output_dir: Path = DEFAULT_SUBMISSIONS_DIR,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    filename_prefix: str | None = None,
    allow_partial: bool = False,
) -> ExportArtifactResult:
    """Validate and export completed human judgments to JSON, CSV, and SHA-256 manifest.

    Never auto-signs or auto-populates human provenance declarations, and never
    modifies original passage text.
    """
    report = validate_session(
        pool, session, require_all_complete=not allow_partial
    )
    if not report.valid_for_export:
        raise ExportValidationError(
            "Cannot export submission: validation failed "
            f"(completed={report.completed_pairs}/{report.total_pairs}, "
            f"provenance_valid={report.provenance_valid}, "
            f"integrity_errors={len(report.integrity_errors)}).",
            report=report,
        )

    resolved_out = ensure_private_path(output_dir)
    resolved_out.mkdir(parents=True, exist_ok=True)

    reviewer_id = session.provenance.reviewer_identity_or_pseudonym
    prefix = _safe_filename_prefix(
        filename_prefix or f"{reviewer_id.lower()}_s5c3"
    )
    exported_at = utc_now_iso()

    records: list[dict[str, Any]] = []
    csv_rows: list[dict[str, str]] = []

    for pair in pool.pairs:
        judgment = session.judgments.get(pair.pair_id)
        if judgment is None or judgment.relevance_grade is None:
            if not allow_partial:
                raise ExportValidationError(
                    f"Missing judgment for {pair.pair_id}.", report=report
                )
            continue

        review_date = (
            judgment.updated_at_utc
            or session.provenance.review_completion_date_utc
            or session.provenance.signed_by_human_at_utc
        )
        record = {
            "pair_id": pair.pair_id,
            "query_id": pair.query_id,
            "domain": pair.domain,
            "query_text": pair.query_text,
            "candidate_passage_id": pair.candidate_passage_id,
            "candidate_doc_id": pair.candidate_doc_id,
            "candidate_chunk_id": pair.candidate_chunk_id,
            "candidate_page_number": pair.candidate_page_number,
            "passage_sha256": pair.passage_sha256,
            "relevance_grade": judgment.relevance_grade,
            "supporting_quotation": judgment.supporting_quotation,
            "confidence": judgment.confidence,
            "reviewer_notes": judgment.reviewer_notes,
            "reviewer_id": reviewer_id,
            "provenance_class": session.provenance.provenance_class,
            "review_date_utc": review_date,
            "passage_text_unchanged_verified": True,
        }
        records.append(record)
        csv_rows.append(
            {
                "pair_id": pair.pair_id,
                "query_id": pair.query_id,
                "domain": pair.domain,
                "query_text": pair.query_text,
                "candidate_passage_id": pair.candidate_passage_id,
                "candidate_doc_id": pair.candidate_doc_id,
                "candidate_chunk_id": pair.candidate_chunk_id,
                "candidate_page_number": str(pair.candidate_page_number),
                "passage_sha256": pair.passage_sha256,
                "relevance_grade": str(judgment.relevance_grade),
                "supporting_quotation": judgment.supporting_quotation,
                "confidence": judgment.confidence,
                "reviewer_notes": judgment.reviewer_notes,
                "reviewer_id": reviewer_id,
                "provenance_class": session.provenance.provenance_class,
                "review_date_utc": review_date,
            }
        )

    provenance_out = session.provenance.to_dict()
    provenance_out["review_completion_status"] = report.review_completion_status

    json_payload = {
        "schema_version": SUBMISSION_SCHEMA_VERSION,
        "exported_at_utc": exported_at,
        "pool_version": pool.pool_version,
        "pool_sha256": pool.pool_sha256,
        "randomization_seed": pool.randomization_seed,
        "total_pool_pairs": len(pool.pairs),
        "exported_pairs": len(records),
        "allow_partial": allow_partial,
        "provenance": provenance_out,
        "records": records,
    }

    json_path = resolved_out / f"{prefix}_submission.json"
    json_bytes = (json.dumps(json_payload, indent=2) + "\n").encode("utf-8")
    json_sha = atomic_write_bytes(json_path, json_bytes)

    csv_path = resolved_out / f"{prefix}_submission.csv"
    csv_buffer_lines: list[str] = []

    class _LineCollector:
        def write(self, text: str) -> int:
            csv_buffer_lines.append(text)
            return len(text)

    writer = csv.DictWriter(_LineCollector(), fieldnames=list(SUBMISSION_CSV_COLUMNS))
    writer.writeheader()
    writer.writerows(csv_rows)
    csv_sha = atomic_write_bytes(csv_path, "".join(csv_buffer_lines).encode("utf-8"))

    backup_path, backup_sha = create_timestamped_backup(
        session, backup_dir=backup_dir, prefix=f"{prefix}_export_snapshot"
    )

    manifest_payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "exported_at_utc": exported_at,
        "pool_sha256": pool.pool_sha256,
        "files": {
            json_path.name: {"path": str(json_path), "sha256": json_sha},
            csv_path.name: {"path": str(csv_path), "sha256": csv_sha},
            backup_path.name: {"path": str(backup_path), "sha256": backup_sha},
        },
        "source_pool_file_sha256": sha256_file(pool.pool_path),
    }
    manifest_path = resolved_out / f"{prefix}_sha256_manifest.json"
    manifest_bytes = (json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    manifest_sha = atomic_write_bytes(manifest_path, manifest_bytes)

    return ExportArtifactResult(
        json_path=json_path,
        json_sha256=json_sha,
        csv_path=csv_path,
        csv_sha256=csv_sha,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha,
        backup_path=backup_path,
        backup_sha256=backup_sha,
        exported_at_utc=exported_at,
    )
