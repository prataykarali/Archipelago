"""Secret-protected, bounded entry point for an opt-in S5 scheduler."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import os
from secrets import compare_digest

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

from ..context import AppContext

LOGGER = logging.getLogger(__name__)
MAX_MONITORS_PER_TICK = 1


def register(app: Flask, _ctx: AppContext) -> None:
    """Register the bounded S5 scheduled monitor tick endpoint."""

    @app.get("/api/internal/s5-monitor-tick")
    def s5_monitor_tick() -> ResponseReturnValue:
        secret = os.getenv("CRON_SECRET", "")
        if not secret:
            return jsonify({"error": "scheduler_not_configured"}), 503
        if not compare_digest(request.headers.get("Authorization", ""), f"Bearer {secret}"):
            return jsonify({"error": "unauthorized"}), 401
        if os.getenv("ARCHIPELAGO_S5_SCHEDULER_ENABLED") != "1":
            return jsonify({"error": "scheduler_disabled"}), 503
        from archipelago.scholarly.intelligence.monitor import run_monitor
        from archipelago.scholarly.intelligence.postgres_storage import PostgresResearchStore
        from archipelago.scholarly.intelligence.storage import durable_storage_configured

        if not durable_storage_configured():
            return jsonify({"error": "research_storage_not_configured"}), 503

        triggered_at = datetime.now(UTC).isoformat()
        ua = request.headers.get("User-Agent", "").lower()
        trigger_source = "vercel_cron" if "vercel-cron" in ua else "authorized_scheduler_bearer"
        try:
            store = PostgresResearchStore()
            monitor_ids = store.due_monitor_ids(MAX_MONITORS_PER_TICK)
            details = []
            for monitor_id in monitor_ids:
                res = run_monitor(monitor_id, store)
                details.append(
                    {
                        "monitor_id": monitor_id,
                        "status": res.get("status"),
                        "run_id": res.get("run_id"),
                    }
                )
            outcomes = [str(item["status"]) for item in details]
        except Exception:
            LOGGER.exception("S5 scheduled monitor tick failed")
            return jsonify({"error": "scheduler_unavailable"}), 503
        return jsonify(
            {
                "processed": len(outcomes),
                "outcomes": outcomes,
                "triggered_at": triggered_at,
                "trigger_source": trigger_source,
                "details": details,
            }
        )
