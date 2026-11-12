"""Secret-protected, bounded entry point for an opt-in S5 scheduler."""

from __future__ import annotations

import logging
import os
from secrets import compare_digest

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from ..context import AppContext

LOGGER = logging.getLogger(__name__)
MAX_MONITORS_PER_TICK = 1


def register(app: Flask, _ctx: AppContext) -> None:
    """Register a worker trigger; no schedule is activated by this route."""

    @app.get("/api/internal/s5-monitor-tick")  # type: ignore[misc]
    def s5_monitor_tick() -> ResponseReturnValue:
        secret = os.getenv("CRON_SECRET", "")
        if not secret:
            return jsonify({"error": "scheduler_not_configured"}), 503
        if not compare_digest(request.headers.get("Authorization", ""), f"Bearer {secret}"):
            return jsonify({"error": "unauthorized"}), 401
        if os.getenv("ARCHIPELAGO_S5_SCHEDULER_ENABLED") != "1":
            return jsonify({"error": "scheduler_disabled"}), 503
        if not os.getenv("ARCHIPELAGO_RESEARCH_DATABASE_URL"):
            return jsonify({"error": "research_storage_not_configured"}), 503
        from archipelago.scholarly.intelligence.monitor import run_monitor
        from archipelago.scholarly.intelligence.postgres_storage import PostgresResearchStore

        try:
            store = PostgresResearchStore()
            monitor_ids = store.due_monitor_ids(MAX_MONITORS_PER_TICK)
            outcomes = [run_monitor(monitor_id, store)["status"] for monitor_id in monitor_ids]
        except Exception:
            LOGGER.exception("S5 scheduled monitor tick failed")
            return jsonify({"error": "scheduler_unavailable"}), 503
        return jsonify({"processed": len(outcomes), "outcomes": outcomes})
