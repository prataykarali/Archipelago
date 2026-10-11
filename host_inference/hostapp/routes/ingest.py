"""Ingestion routes for hosted Archipelago application.

Librarian endpoints to upload papers, submit book chapters for indexing,
and poll ingestion job status.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

from ..config import MAX_CONTENT_LENGTH_BYTES
from ..context import AppContext

try:
    from ingestion_jobs import JobStatus
    from ingestion_worker import get_worker, job_store
except ImportError:
    JobStatus = None
    job_store = None
    get_worker = None

BYTES_PER_MIB = 1024 * 1024


def _worker_available() -> bool:
    """Only an explicitly enabled deployment with a real worker accepts uploads."""
    return bool(
        os.getenv("ARCHIPELAGO_INGESTION_ENABLED", "0") == "1"
        and job_store is not None
        and get_worker is not None
    )


def register(app: Flask, ctx: AppContext) -> None:
    """Register ingestion routes on ``app``."""

    @app.get("/api/ingest/capabilities")
    def ingestion_capabilities():
        return jsonify(
            {
                "upload_api_enabled": _worker_available(),
                "delete_api_enabled": False,
                "librarian_only": True,
                "student_upload_enabled": False,
                "max_file_size_mb": MAX_CONTENT_LENGTH_BYTES // BYTES_PER_MIB,
                "supported_formats": ["pdf", "md", "markdown", "txt"],
            }
        ), 200

    @app.post("/api/ingest")
    def ingest_upload():
        if not _worker_available():
            return jsonify(
                {"error": "unavailable", "detail": "The ingestion worker is not enabled."}
            ), 503

        if "file" not in request.files:
            return jsonify({"error": "No file part in request"}), 400
        f = request.files["file"]
        if not f or f.filename == "":
            return jsonify({"error": "No file selected"}), 400

        filename = secure_filename(f.filename or "upload.pdf")
        allowed = (".pdf", ".md", ".markdown", ".txt")
        if not any(filename.lower().endswith(ext) for ext in allowed):
            return jsonify(
                {"error": "Supported formats: PDF, Markdown (.md), plain text (.txt)"}
            ), 400

        f.seek(0, 2)
        size_bytes = f.tell()
        f.seek(0)
        if size_bytes > MAX_CONTENT_LENGTH_BYTES:
            return jsonify({"error": "File exceeds the upload size limit"}), 413

        file_bytes = f.read()
        job = job_store.create_job(filename)
        upload_path = job_store.job_dir(job.job_id) / f"upload{Path(filename).suffix.lower()}"
        try:
            upload_path.write_bytes(file_bytes)
            get_worker().enqueue(job.job_id)
        except (OSError, RuntimeError) as exc:
            job_store.update_status(job.job_id, JobStatus.FAILED, error=str(exc))
            return jsonify(
                {"error": "ingestion_failed", "detail": "The upload could not be queued."}
            ), 503
        return jsonify({"job_id": job.job_id, "status": "queued", "filename": filename}), 202

    @app.post("/api/ingest/index")
    def ingest_index():
        return jsonify(
            {"error": "not_implemented", "detail": "Hosted TOC indexing is not available."}
        ), 501

    @app.get("/api/ingest/<job_id>")
    def ingest_status(job_id: str):
        if job_store:
            record = job_store.get_job(job_id)
            if record is not None:
                return jsonify(
                    {
                        "job_id": record.job_id,
                        "status": getattr(record.status, "value", str(record.status)).lower(),
                        "source_filename": record.source_filename,
                        "progress": record.progress,
                        "error": record.error,
                        "result": record.result,
                    }
                ), 200
        return jsonify({"error": "not_found", "detail": "No ingestion job has that ID."}), 404

    @app.get("/api/ingest")
    def ingest_list():
        if job_store:
            try:
                jobs = job_store.list_jobs()
                return jsonify({"jobs": jobs}), 200
            except OSError:
                return jsonify({"error": "storage_unavailable"}), 503
        return jsonify(
            {"error": "unavailable", "detail": "The ingestion worker is not installed."}
        ), 503
