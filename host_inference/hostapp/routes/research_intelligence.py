"""Authenticated metadata search, snapshots, graph and Excel export."""

from __future__ import annotations

import importlib.util
import logging
import uuid

from flask import Flask, jsonify, request, send_file
from flask.typing import ResponseReturnValue

from ..context import AppContext

LOGGER = logging.getLogger(__name__)
MANAGER_ROLES = frozenset({"librarian", "administrator"})
MONITOR_ROLES = frozenset({"faculty", "librarian", "administrator"})


def _principal() -> dict[str, str]:
    return vars(request)["archipelago_principal"]


def _run(run_id: uuid.UUID) -> dict | None:
    from archipelago.scholarly.intelligence.storage import ResearchStore

    principal = _principal()
    return ResearchStore().get_run(
        str(run_id), str(principal["id"]), principal["role"] in MANAGER_ROLES
    )


def register(app: Flask, _ctx: AppContext) -> None:
    """Register S5 routes without touching research intake or academic upload."""

    @app.before_request
    def intelligence_runtime_guard() -> ResponseReturnValue | None:
        if (
            request.path.startswith("/api/research/intelligence/")
            and importlib.util.find_spec("archipelago") is None
        ):
            return jsonify({"error": "research_runtime_unavailable"}), 503
        return None

    @app.post("/api/research/intelligence/search")  # type: ignore[misc]
    def intelligence_search() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.search import discover
        from archipelago.scholarly.intelligence.storage import ResearchStore

        payload = request.get_json(silent=True)
        try:
            result = discover(payload if isinstance(payload, dict) else {})
            if not any(source["status"] in {"live", "live_empty"} for source in result["sources"]):
                return jsonify(
                    {"error": "providers_unavailable", "sources": result["sources"]}
                ), 503
            run_id = ResearchStore().save_run(str(_principal()["id"]), result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, RuntimeError):
            LOGGER.exception("Research intelligence search unavailable")
            return jsonify({"error": "search_unavailable"}), 503
        return jsonify({"run_id": run_id, **result})

    @app.get("/api/research/intelligence/runs")  # type: ignore[misc]
    def intelligence_runs() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import ResearchStore

        return jsonify({"runs": ResearchStore().list_runs(str(_principal()["id"]))})

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
        from archipelago.scholarly.intelligence.storage import ResearchStore

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True)
        try:
            options = validate_options(payload if isinstance(payload, dict) else {})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        monitor_id = ResearchStore().save_monitor(str(_principal()["id"]), options)
        return jsonify({"monitor_id": monitor_id, "enabled": False}), 201

    @app.get("/api/research/intelligence/monitors")  # type: ignore[misc]
    def intelligence_monitors() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import ResearchStore

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        return jsonify({"monitors": ResearchStore().list_monitors(str(_principal()["id"]))})

    @app.patch("/api/research/intelligence/monitors/<uuid:monitor_id>")  # type: ignore[misc]
    def intelligence_monitor_activation(monitor_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import ResearchStore

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True)
        enabled = payload.get("enabled") if isinstance(payload, dict) else None
        if not isinstance(enabled, bool):
            return jsonify({"error": "invalid_enabled"}), 400
        updated = ResearchStore().set_monitor_enabled(
            str(monitor_id), str(_principal()["id"]), enabled
        )
        return (
            (jsonify({"monitor_id": str(monitor_id), "enabled": enabled}), 200)
            if updated
            else (jsonify({"error": "not_found"}), 404)
        )
