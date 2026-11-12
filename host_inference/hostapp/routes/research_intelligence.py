"""Authenticated metadata search, snapshots, graph and Excel export."""

from __future__ import annotations

import importlib.util
import logging
import os
from typing import Any, cast
import uuid

from flask import Flask, jsonify, request, send_file
from flask.typing import ResponseReturnValue

from ..context import AppContext

LOGGER = logging.getLogger(__name__)
MONITOR_ROLES = frozenset({"faculty", "librarian", "administrator"})


def _principal() -> dict[str, str]:
    return cast(dict[str, str], vars(request)["archipelago_principal"])


def _run(run_id: uuid.UUID) -> dict[str, Any] | None:
    from archipelago.scholarly.intelligence.storage import hosted_store

    principal = _principal()
    return hosted_store().get_run(str(run_id), str(principal["id"]))


def register(app: Flask, _ctx: AppContext) -> None:
    """Register S5 routes without touching research intake or academic upload."""

    @app.before_request  # type: ignore[misc]
    def intelligence_runtime_guard() -> ResponseReturnValue | None:
        if (
            request.path.startswith("/api/research/intelligence/")
            and importlib.util.find_spec("archipelago") is None
        ):
            return jsonify({"error": "research_runtime_unavailable"}), 503
        if (
            request.path.startswith("/api/research/intelligence/")
            and os.getenv("VERCEL")
            and not os.getenv("ARCHIPELAGO_RESEARCH_DATABASE_URL")
        ):
            return jsonify({"error": "research_storage_not_configured"}), 503
        return None

    @app.get("/api/research/intelligence/readiness")  # type: ignore[misc]
    def intelligence_readiness() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.postgres_storage import PostgresResearchStore

        if not os.getenv("ARCHIPELAGO_RESEARCH_DATABASE_URL"):
            return jsonify({"ready": False, "error": "research_storage_not_configured"}), 503
        try:
            ready = PostgresResearchStore().check_ready()
        except Exception:
            LOGGER.exception("Research storage readiness failed")
            return jsonify({"ready": False, "error": "research_storage_unavailable"}), 503
        return (
            (jsonify({"ready": True}), 200)
            if ready
            else (jsonify({"ready": False, "error": "research_schema_missing"}), 503)
        )

    @app.post("/api/research/intelligence/search")  # type: ignore[misc]
    def intelligence_search() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.search import discover
        from archipelago.scholarly.intelligence.storage import hosted_store

        payload = request.get_json(silent=True)
        try:
            result = discover(payload if isinstance(payload, dict) else {})
            if not any(source["status"] in {"live", "live_empty"} for source in result["sources"]):
                return jsonify(
                    {"error": "providers_unavailable", "sources": result["sources"]}
                ), 503
            run_id = hosted_store().save_run(str(_principal()["id"]), result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, RuntimeError):
            LOGGER.exception("Research intelligence search unavailable")
            return jsonify({"error": "search_unavailable"}), 503
        return jsonify({"run_id": run_id, **result})

    @app.get("/api/research/intelligence/runs")  # type: ignore[misc]
    def intelligence_runs() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store

        return jsonify({"runs": hosted_store().list_runs(str(_principal()["id"]))})

    @app.get("/api/research/intelligence/runs/<uuid:run_id>")  # type: ignore[misc]
    def intelligence_run(run_id: uuid.UUID) -> ResponseReturnValue:
        run = _run(run_id)
        return jsonify(run) if run else (jsonify({"error": "not_found"}), 404)

    @app.get("/api/research/intelligence/runs/<uuid:run_id>/graph")  # type: ignore[misc]
    def intelligence_graph(run_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.graph import build_graph

        run = _run(run_id)
        return jsonify(build_graph(run)) if run else (jsonify({"error": "not_found"}), 404)

    @app.get("/api/research/intelligence/runs/<uuid:run_id>/xlsx")  # type: ignore[misc]
    def intelligence_xlsx(run_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.workbook import build_workbook

        run = _run(run_id)
        if not run:
            return jsonify({"error": "not_found"}), 404
        return send_file(
            build_workbook(run),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"research-{run_id}.xlsx",
        )

    @app.post("/api/research/intelligence/monitors")  # type: ignore[misc]
    def intelligence_monitor() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.search import validate_options
        from archipelago.scholarly.intelligence.storage import (
            DEFAULT_CADENCE_HOURS,
            hosted_store,
            validate_cadence,
        )

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True)
        try:
            options = validate_options(payload if isinstance(payload, dict) else {})
            cadence_hours = validate_cadence(
                payload.get("cadence_hours", DEFAULT_CADENCE_HOURS)
                if isinstance(payload, dict)
                else DEFAULT_CADENCE_HOURS
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        monitor_id = hosted_store().save_monitor(str(_principal()["id"]), options, cadence_hours)
        return jsonify({"monitor_id": monitor_id, "enabled": False}), 201

    @app.get("/api/research/intelligence/monitors")  # type: ignore[misc]
    def intelligence_monitors() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        return jsonify({"monitors": hosted_store().list_monitors(str(_principal()["id"]))})

    @app.patch("/api/research/intelligence/monitors/<uuid:monitor_id>")  # type: ignore[misc]
    def intelligence_monitor_activation(monitor_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store, validate_cadence

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_monitor_update"}), 400
        store = hosted_store()
        owner = str(_principal()["id"])
        if "cadence_hours" in payload:
            try:
                cadence = validate_cadence(payload["cadence_hours"])
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            if not store.set_monitor_cadence(str(monitor_id), owner, cadence):
                return jsonify({"error": "not_found"}), 404
        if "enabled" in payload:
            if not isinstance(payload["enabled"], bool):
                return jsonify({"error": "invalid_enabled"}), 400
            if not store.set_monitor_enabled(str(monitor_id), owner, payload["enabled"]):
                return jsonify({"error": "not_found"}), 404
        if not any(key in payload for key in ("enabled", "cadence_hours")):
            return jsonify({"error": "invalid_monitor_update"}), 400
        return jsonify({"monitor_id": str(monitor_id), "updated": True})

    @app.delete("/api/research/intelligence/monitors/<uuid:monitor_id>")  # type: ignore[misc]
    def intelligence_monitor_delete(monitor_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        deleted = hosted_store().delete_monitor(str(monitor_id), str(_principal()["id"]))
        return (
            (jsonify({"deleted": True}), 200) if deleted else (jsonify({"error": "not_found"}), 404)
        )

    @app.get("/api/research/intelligence/monitors/<uuid:monitor_id>/history")  # type: ignore[misc]
    def intelligence_monitor_history(monitor_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        store = hosted_store()
        owner = str(_principal()["id"])
        if not any(row["id"] == str(monitor_id) for row in store.list_monitors(owner)):
            return jsonify({"error": "not_found"}), 404
        return jsonify({"history": store.list_history(str(monitor_id), owner)})

    @app.get("/api/research/intelligence/updates")  # type: ignore[misc]
    def intelligence_updates() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        return jsonify({"updates": hosted_store().list_events(str(_principal()["id"]))})

    @app.post("/api/research/intelligence/monitors/<uuid:monitor_id>/run")  # type: ignore[misc]
    def intelligence_monitor_run(monitor_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.monitor import run_monitor
        from archipelago.scholarly.intelligence.storage import hosted_store

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        store = hosted_store()
        if not store.make_monitor_due(str(monitor_id), str(_principal()["id"])):
            return jsonify({"error": "not_found_or_disabled"}), 404
        result = run_monitor(str(monitor_id), store)
        return jsonify(result), 200 if result["status"] != "failed" else 503
