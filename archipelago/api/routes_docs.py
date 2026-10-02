"""Readiness probe and librarian upload routes."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Response, jsonify, request

from archipelago.api import engine_state as state
from archipelago.api.engine_state import (
    _UPLOAD_ALLOWED_SUFFIXES,
    DB_PATH,
    DEFAULT_INGESTION_MODEL,
    DEFAULT_RUNTIME,
    DEFAULT_SYNTHESIS_MODEL,
    app,
)

logger = logging.getLogger("archipelago.api")

SUCCESS_STATUS = 200
BAD_REQUEST_STATUS = 400
QUEUED_STATUS = 202
NO_FILE_ERROR = "No file uploaded. Expected 'file' or 'pdf' form field."
INVALID_FILENAME_ERROR = "Invalid filename"
SUPPORTED_FORMATS_ERROR = "Supported formats: PDF, Markdown (.md), plain text (.txt)"


@app.route("/api/readiness", methods=["GET"])
def api_readiness() -> Response:
    """Health check endpoint reporting DB status, concept count, and LLM state."""
    try:
        from archipelago.inference.llm_gateway import is_llm_available

        llm_ready = is_llm_available()
    except Exception:
        llm_ready = False

    synthesis = state._synthesis
    return jsonify(
        {
            "status": "ready",
            "graph": {
                "concept_count": len(state._concepts_data),
                "kuzu_connected": state._kuzu_conn is not None,
                "database_path": DB_PATH,
            },
            "models": {
                "synthesis_model": (
                    synthesis.synthesis_model if synthesis else DEFAULT_SYNTHESIS_MODEL
                ),
                "ingestion_model": (
                    synthesis.ingestion_model if synthesis else DEFAULT_INGESTION_MODEL
                ),
                "ollama_ready": llm_ready,
                "llm_ready": llm_ready,
            },
            "runtime": DEFAULT_RUNTIME,
        }
    ), SUCCESS_STATUS


@app.route("/api/upload", methods=["POST"])
def api_upload() -> Response:
    """Queue a PDF/Markdown/text upload through the canonical staged worker."""
    if "file" not in request.files and "pdf" not in request.files:
        return jsonify({"error": NO_FILE_ERROR}), BAD_REQUEST_STATUS

    uploaded_file = request.files.get("file") or request.files.get("pdf")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": INVALID_FILENAME_ERROR}), BAD_REQUEST_STATUS

    from werkzeug.utils import secure_filename

    from ingestion_worker import get_worker, job_store

    filename = secure_filename(Path(uploaded_file.filename).name)
    if not filename.lower().endswith(_UPLOAD_ALLOWED_SUFFIXES):
        return jsonify({"error": SUPPORTED_FORMATS_ERROR}), BAD_REQUEST_STATUS

    job = job_store.create_job(filename)
    upload_path = job_store.job_dir(job.job_id) / f"upload{Path(filename).suffix.lower()}"
    uploaded_file.save(str(upload_path))
    get_worker().enqueue(job.job_id)
    logger.info("Queued upload %s as ingestion job %s", filename, job.job_id)

    return jsonify(
        {
            "status": "queued",
            "job_id": job.job_id,
            "filename": filename,
            "message": f"Document '{filename}' queued for staged ingestion.",
        }
    ), QUEUED_STATUS
