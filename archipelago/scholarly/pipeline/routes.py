"""Staff-only research job API shared by local Flask applications."""

from __future__ import annotations

import os
import re
from typing import Any
import uuid

from flask import Flask, g, jsonify, request

from archipelago.scholarly.access import (
    MANAGER_ROLES,
    ResearchCapability,
    audit_action,
    require_research,
)
from archipelago.scholarly.pipeline.postgres_store import PostgresResearchStore, StoreUnavailable

MAX_TOPIC_CHARS = 200
ENABLED_ENV = "ARCHIPELAGO_RESEARCH_ENABLED"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def _store() -> PostgresResearchStore | None:
    if os.getenv(ENABLED_ENV, "0").lower() not in {"1", "true", "yes"}:
        return None
    try:
        return PostgresResearchStore()
    except StoreUnavailable:
        return None


def _job_for_user(store: PostgresResearchStore, job_id: str) -> dict[str, Any] | None:
    job = store.get_job(job_id)
    if job is None:
        return None
    principal = g.archipelago_principal
    if job["user_id"] != principal.user_id and principal.role not in MANAGER_ROLES:
        return None
    return job


def register_research_routes(app: Flask) -> None:
    """Install job endpoints; feature flag stays off until release validation."""

    @app.post("/api/research/jobs")
    @require_research(ResearchCapability.JOB_CREATE)
    def create_research_job() -> Any:
        payload = request.get_json(silent=True) or {}
        topic = str(payload.get("topic") or "").strip()
        if not topic or len(topic) > MAX_TOPIC_CHARS:
            return jsonify({"error": "invalid_topic"}), 400
        store = _store()
        if store is None:
            audit_action(
                user_id=g.archipelago_principal.user_id,
                role=g.archipelago_principal.role,
                action="job_create",
                result="research_disabled",
                topic=topic,
            )
            return jsonify({"error": "research_disabled"}), 503
        principal = g.archipelago_principal
        key = request.headers.get("Idempotency-Key", "").strip() or str(uuid.uuid4())
        if len(key) > MAX_TOPIC_CHARS:
            return jsonify({"error": "invalid_idempotency_key"}), 400
        job = store.create_job(
            user_id=principal.user_id,
            role=principal.role,
            topic=topic,
            idempotency_key=key,
        )
        if job["topic"] != topic:
            store.audit(
                user_id=principal.user_id,
                role=principal.role,
                action="job_create",
                result="idempotency_conflict",
                job_id=str(job["job_id"]),
                topic=topic,
            )
            return jsonify({"error": "idempotency_conflict"}), 409
        store.audit(
            user_id=principal.user_id,
            role=principal.role,
            action="job_create",
            result="accepted",
            job_id=str(job["job_id"]),
            topic=topic,
        )
        audit_action(
            user_id=principal.user_id,
            role=principal.role,
            action="job_create",
            result="accepted",
            research_job_id=str(job["job_id"]),
            topic=topic,
        )
        return jsonify(job), 202

    @app.get("/api/research/jobs/<uuid:job_id>")
    @require_research(ResearchCapability.SEARCH)
    def get_research_job(job_id: uuid.UUID) -> Any:
        store = _store()
        if store is None:
            return jsonify({"error": "research_disabled"}), 503
        job = _job_for_user(store, str(job_id))
        return (jsonify(job), 200) if job else (jsonify({"error": "not_found"}), 404)

    @app.get("/api/research/jobs/<uuid:job_id>/sources")
    @require_research(ResearchCapability.SOURCE_HEALTH)
    def get_research_sources(job_id: uuid.UUID) -> Any:
        store = _store()
        if store is None:
            return jsonify({"error": "research_disabled"}), 503
        job = _job_for_user(store, str(job_id))
        if job is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"sources": store.source_summaries(str(job_id))})

    @app.get("/api/research/jobs/<uuid:job_id>/papers/<uuid:paper_id>/features")
    @require_research(ResearchCapability.FEATURE_READ)
    def get_research_features(job_id: uuid.UUID, paper_id: uuid.UUID) -> Any:
        store = _store()
        if store is None:
            return jsonify({"error": "research_disabled"}), 503
        if _job_for_user(store, str(job_id)) is None or not store.job_has_paper(
            str(job_id), str(paper_id)
        ):
            return jsonify({"error": "not_found"}), 404
        return jsonify({"features": store.get_features(str(job_id), str(paper_id))})

    @app.get("/api/research/jobs/<uuid:job_id>/papers/<uuid:paper_id>/evidence")
    @require_research(ResearchCapability.EVIDENCE_READ)
    def get_research_evidence(job_id: uuid.UUID, paper_id: uuid.UUID) -> Any:
        store = _store()
        if store is None:
            return jsonify({"error": "research_disabled"}), 503
        if _job_for_user(store, str(job_id)) is None or not store.job_has_paper(
            str(job_id), str(paper_id)
        ):
            return jsonify({"error": "not_found"}), 404
        return jsonify({"evidence": store.get_evidence(str(paper_id))})

    @app.post(
        "/api/research/jobs/<uuid:job_id>/papers/<uuid:paper_id>/evidence/<artifact_sha256>/review"
    )
    @require_research(ResearchCapability.REVIEW)
    def review_research_evidence(
        job_id: uuid.UUID, paper_id: uuid.UUID, artifact_sha256: str
    ) -> Any:
        decision = (request.get_json(silent=True) or {}).get("decision")
        if decision not in {"approve", "reject"} or not SHA256_PATTERN.fullmatch(artifact_sha256):
            return jsonify({"error": "invalid_review"}), 400
        store = _store()
        if store is None:
            return jsonify({"error": "research_disabled"}), 503
        job = _job_for_user(store, str(job_id))
        if job is None:
            return jsonify({"error": "not_found"}), 404
        updated = store.review_evidence(
            str(job_id), str(paper_id), artifact_sha256, approve=decision == "approve"
        )
        if not updated:
            return jsonify({"error": "not_reviewable"}), 409
        principal = g.archipelago_principal
        store.audit(
            user_id=principal.user_id,
            role=principal.role,
            action="evidence_review",
            result=decision,
            job_id=str(job_id),
            topic=job["topic"],
        )
        audit_action(
            user_id=principal.user_id,
            role=principal.role,
            action="evidence_review",
            result=decision,
            research_job_id=str(job_id),
        )
        return jsonify({"verification_state": "validated" if decision == "approve" else "rejected"})

    @app.post("/api/research/topics")
    @require_research(ResearchCapability.TOPIC_TRACK)
    def track_research_topic() -> Any:
        payload = request.get_json(silent=True) or {}
        topic = str(payload.get("topic") or "").strip()
        if not topic or len(topic) > MAX_TOPIC_CHARS:
            return jsonify({"error": "invalid_topic"}), 400
        store = _store()
        if store is None:
            return jsonify({"error": "research_disabled"}), 503
        principal = g.archipelago_principal
        tracked = store.track_topic(user_id=principal.user_id, role=principal.role, topic=topic)
        return jsonify(tracked), 201

    @app.patch("/api/research/topics/<uuid:topic_id>/refresh")
    @require_research(ResearchCapability.REFRESH_CONTROL)
    def set_research_refresh(topic_id: uuid.UUID) -> Any:
        payload = request.get_json(silent=True) or {}
        try:
            raw_hours = payload.get("hours")
            if not isinstance(raw_hours, (int, str)):
                raise ValueError("Missing refresh interval")
            hours = int(raw_hours)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_interval"}), 400
        store = _store()
        if store is None:
            return jsonify({"error": "research_disabled"}), 503
        try:
            updated = store.set_topic_refresh(
                str(topic_id), hours, bool(payload.get("pinned", True))
            )
        except ValueError:
            return jsonify({"error": "invalid_interval"}), 400
        if not updated:
            return jsonify({"error": "not_found"}), 404
        principal = g.archipelago_principal
        store.audit(
            user_id=principal.user_id,
            role=principal.role,
            action="refresh_control",
            result="updated",
            topic=str(topic_id),
        )
        audit_action(
            user_id=principal.user_id,
            role=principal.role,
            action="refresh_control",
            result="updated",
            topic=str(topic_id),
        )
        return jsonify({"updated": True})
