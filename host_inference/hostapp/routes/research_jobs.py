"""Staff research questions queued for the user's local GPU workstation."""

from __future__ import annotations

import logging
import uuid

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue
import requests

from ..context import AppContext
from ..research_access import audit_action
from ..research_job_store import (
    enqueue_job,
    get_job,
    get_paper_okf,
    latest_job,
    list_job_okf,
    list_job_papers,
    worker_status,
)

DEFAULT_PAPERS = 25
MIN_PAPERS = 20
MAX_PAPERS = 30
MAX_TOPIC_CHARS = 200
MANAGER_ROLES = frozenset({"librarian", "administrator"})
LOGGER = logging.getLogger(__name__)
RATE_ERRORS = {
    "invalid_research_job": (400, "Choose a topic and 20 to 30 papers for local ingestion."),
    "research_rate_limited": (429, "Research limit reached. Try again later."),
    "research_job_in_progress": (409, "Your previous research job is still queued or running."),
    "research_queue_full": (503, "The research queue is full. Try again later."),
}


def _principal() -> dict[str, str]:
    return vars(request)["archipelago_principal"]


def _authorized_job(job_id: str) -> dict | None:
    job = get_job(job_id)
    principal = _principal()
    if job and (str(job["user_id"]) == str(principal["id"]) or principal["role"] in MANAGER_ROLES):
        return job
    return None


def register(app: Flask, _ctx: AppContext) -> None:
    """Expose enqueue, progress, worker health, and completed paper results."""

    @app.post("/api/research/jobs")  # type: ignore[misc]
    def create_research_job() -> ResponseReturnValue:
        payload = request.get_json(silent=True)
        topic = str(payload.get("topic") or "").strip() if isinstance(payload, dict) else ""
        limit = payload.get("paper_limit", DEFAULT_PAPERS) if isinstance(payload, dict) else 0
        if (
            not 3 <= len(topic) <= MAX_TOPIC_CHARS
            or not isinstance(limit, int)
            or isinstance(limit, bool)
        ):
            return jsonify({"error": "invalid_research_request"}), 400
        if not MIN_PAPERS <= limit <= MAX_PAPERS:
            return jsonify({"error": "invalid_paper_limit"}), 400
        principal = _principal()
        try:
            job = enqueue_job(str(principal["id"]), str(principal["role"]), topic, limit)
            worker = worker_status()
        except ValueError as exc:
            code, detail = RATE_ERRORS.get(str(exc), (400, "Invalid research request."))
            return jsonify({"error": str(exc), "detail": detail}), code
        except (requests.RequestException, RuntimeError):
            LOGGER.exception("Research queue unavailable")
            return jsonify({"error": "research_queue_unavailable"}), 503
        audit_action(
            user_id=str(principal["id"]),
            role=str(principal["role"]),
            action="job_create",
            result="queued",
            research_job_id=str(job["job_id"]),
            topic=topic,
        )
        return jsonify({"job": job, "worker": worker}), 202

    @app.get("/api/research/jobs/worker")  # type: ignore[misc]
    def research_worker_status() -> ResponseReturnValue:
        try:
            return jsonify(worker_status())
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research worker status unavailable")
            return jsonify({"online": False, "state": "status_unavailable"}), 503

    @app.get("/api/research/jobs/latest")  # type: ignore[misc]
    def research_latest_job() -> ResponseReturnValue:
        try:
            principal = _principal()
            job = latest_job(None if principal["role"] in MANAGER_ROLES else str(principal["id"]))
            return jsonify({"job": job, "worker": worker_status()})
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research job lookup unavailable")
            return jsonify({"error": "research_queue_unavailable"}), 503

    @app.get("/api/research/jobs/<uuid:job_id>")  # type: ignore[misc]
    def research_job(job_id: uuid.UUID) -> ResponseReturnValue:
        try:
            job = _authorized_job(str(job_id))
            if not job:
                return jsonify({"error": "not_found"}), 404
            return jsonify({"job": job, "worker": worker_status()})
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research job read unavailable")
            return jsonify({"error": "research_queue_unavailable"}), 503

    @app.get("/api/research/jobs/<uuid:job_id>/papers")  # type: ignore[misc]
    def research_job_papers(job_id: uuid.UUID) -> ResponseReturnValue:
        try:
            if not _authorized_job(str(job_id)):
                return jsonify({"error": "not_found"}), 404
            return jsonify({"papers": list_job_papers(str(job_id))})
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research paper results unavailable")
            return jsonify({"error": "research_queue_unavailable"}), 503

    @app.get("/api/research/jobs/<uuid:job_id>/export")  # type: ignore[misc]
    def research_job_export(job_id: uuid.UUID) -> ResponseReturnValue:
        """Return a complete, authorized OKF bundle for one ingestion session."""
        try:
            job = _authorized_job(str(job_id))
            if not job:
                return jsonify({"error": "not_found"}), 404
            papers = list_job_okf(str(job_id))
            return jsonify(
                {
                    "schema": "archipelago-research-session-v1",
                    "job": job,
                    "paper_count": len(papers),
                    "papers": papers,
                }
            )
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research session export unavailable")
            return jsonify({"error": "research_queue_unavailable"}), 503

    @app.get("/api/research/jobs/<uuid:job_id>/papers/<uuid:paper_id>/okf")  # type: ignore[misc]
    def research_job_okf(job_id: uuid.UUID, paper_id: uuid.UUID) -> ResponseReturnValue:
        try:
            if not _authorized_job(str(job_id)):
                return jsonify({"error": "not_found"}), 404
            okf = get_paper_okf(str(job_id), str(paper_id))
            return jsonify(okf) if okf else (jsonify({"error": "not_found"}), 404)
        except (requests.RequestException, RuntimeError, ValueError):
            LOGGER.exception("Research OKF result unavailable")
            return jsonify({"error": "research_queue_unavailable"}), 503
