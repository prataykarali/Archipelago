"""Authenticated metadata search, snapshots, graph and Excel export."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from http import HTTPStatus
import importlib.util
import logging
import os
import re
from typing import Any, cast
import uuid

from flask import Flask, jsonify, request, send_file
from flask.typing import ResponseReturnValue

from ..context import AppContext
from ..user_traffic import record_user_action

LOGGER = logging.getLogger(__name__)
MANAGER_ROLES = frozenset({"librarian", "administrator"})
MONITOR_ROLES = frozenset({"faculty", "librarian", "administrator"})
CURRENT_EXPORT_FORMAT = "rich30.v1"
ALLOWED_SEARCH_ROLES = frozenset({"student", "faculty", "librarian", "administrator"})
PUBLIC_RESEARCH_PATHS = frozenset(
    {
        "/api/research/intake/metrics",
        "/api/research/intake/activity",
    }
)
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_EXPORT_PAPERS = 250
MAX_IMPORT_CONTENT_CHARS = 500_000
MAX_CELL_CHARS = 32000
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.\-]")


def _retired_run(run: dict[str, Any] | None) -> bool:
    """Keep saved runs accessible across versions and users."""
    return False


def _retired_response() -> tuple[Any, int]:
    return jsonify(
        {
            "error": "legacy_run_retired",
            "message": "Run a fresh topic search to use the current Excel format.",
        }
    ), HTTPStatus.GONE


def _safe_workbook_cell(value: Any) -> Any:
    """Prevent spreadsheet formula execution from untrusted metadata."""
    if value is None or isinstance(value, (int, float, bool, date)):
        return value
    text = str(value)[:MAX_CELL_CHARS]
    stripped = text.lstrip(" \t\r\n")
    if text.startswith(_FORMULA_PREFIXES) or stripped.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _install_workbook_cell_guard() -> None:
    try:
        from archipelago.scholarly.intelligence import workbook

        workbook.safe_cell = _safe_workbook_cell
    except Exception:
        pass


_install_workbook_cell_guard()


def _sanitize_export_value(value: Any) -> Any:
    """Recursively neutralize formula-leading strings while keeping numeric/bool values intact."""
    if isinstance(value, str):
        return _safe_workbook_cell(value)
    if isinstance(value, list):
        return [_sanitize_export_value(item) for item in value]
    if isinstance(value, dict):
        return {k: _sanitize_export_value(v) for k, v in value.items()}
    return value


def _prepare_run_for_workbook(run: dict[str, Any]) -> dict[str, Any]:
    """Bound paper count and sanitize string cells without altering schema or numeric metrics."""
    prepared = deepcopy(run)
    papers = prepared.get("papers")
    if isinstance(papers, list) and len(papers) > MAX_EXPORT_PAPERS:
        prepared["papers"] = papers[:MAX_EXPORT_PAPERS]
    return cast(dict[str, Any], _sanitize_export_value(prepared))


def _resolve_principal(ctx: AppContext | None = None) -> dict[str, str] | None:
    principal = getattr(request, "archipelago_principal", None)
    if principal is None and ctx is not None and getattr(ctx, "auth", None) is not None:
        principal, _err = ctx.auth.principal()
        if isinstance(principal, dict):
            request.archipelago_principal = principal  # type: ignore[attr-defined]
    if principal is not None and isinstance(principal, dict):
        if not str(principal.get("id") or "").strip():
            principal["id"] = "00000000-0000-0000-0000-000000000000"
            request.archipelago_principal = principal
        return cast(dict[str, str], principal)
    if ctx is not None and getattr(ctx, "auth", None) is not None and not ctx.auth.required():
        fallback: dict[str, str] = {
            "id": "00000000-0000-0000-0000-000000000000",
            "role": "student",
            "username": "guest",
            "token": "",
        }
        request.archipelago_principal = fallback  # type: ignore[attr-defined]
        return fallback
    return None


def _principal() -> dict[str, str]:
    resolved = _resolve_principal()
    if resolved is None:
        return {
            "id": "00000000-0000-0000-0000-000000000000",
            "role": "student",
            "username": "guest",
            "token": "",
        }
    return resolved


def _run(run_id: uuid.UUID) -> dict[str, Any] | None:
    from archipelago.scholarly.intelligence.storage import hosted_store

    principal = _resolve_principal()
    owner_id = str(principal["id"]) if principal and principal.get("id") else None
    role = str(principal.get("role") or "") if principal else ""
    return hosted_store().get_run(str(run_id), owner_id, manager=(role in MANAGER_ROLES))


def register(app: Flask, _ctx: AppContext) -> None:
    """Register S5 routes without touching research intake or academic upload."""

    @app.before_request  # type: ignore[misc]
    def intelligence_runtime_guard() -> ResponseReturnValue | None:
        if not request.path.startswith("/api/research/intelligence/"):
            return None
        principal = _resolve_principal(_ctx)
        if principal is None:
            if not _ctx.auth.required():
                request.archipelago_principal = {  # type: ignore[attr-defined]
                    "id": "00000000-0000-0000-0000-000000000000",
                    "role": "student",
                    "username": "guest",
                    "token": "",
                }
                return None
            return jsonify({"error": "unauthorized"}), 401
        role = str(principal.get("role") or "")
        if role not in ALLOWED_SEARCH_ROLES:
            return jsonify({"error": "forbidden"}), 403
        if (
            request.path.startswith("/api/research/intelligence/monitors")
            or request.path == "/api/research/intelligence/updates"
        ) and role not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        if importlib.util.find_spec("archipelago") is None:
            return jsonify({"error": "research_runtime_unavailable"}), 503
        from archipelago.scholarly.intelligence.storage import durable_storage_configured

        if os.getenv("VERCEL") and not durable_storage_configured():
            return jsonify({"error": "research_storage_not_configured"}), 503
        return None

    @app.after_request  # type: ignore[misc]
    def research_private_cache_headers(response):
        if request.path.startswith("/api/research/") and request.path not in PUBLIC_RESEARCH_PATHS:
            response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Vary"] = "Authorization, Cookie"
        return response

    @app.get("/api/research/intelligence/readiness")  # type: ignore[misc]
    def intelligence_readiness() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.postgres_storage import PostgresResearchStore
        from archipelago.scholarly.intelligence.storage import durable_storage_configured

        if not durable_storage_configured():
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
        record_user_action(
            "research_search",
            str((payload or {}).get("topic") or "") if isinstance(payload, dict) else "",
        )
        try:
            request_id = (
                str(uuid.UUID(str(payload.get("client_request_id"))))
                if isinstance(payload, dict) and payload.get("client_request_id")
                else None
            )
            result = discover(payload if isinstance(payload, dict) else {})
            if not any(
                source["status"] in {"live", "live_partial", "live_empty"}
                for source in result["sources"]
            ):
                return jsonify(
                    {"error": "providers_unavailable", "sources": result["sources"]}
                ), 503
            if request_id:
                result["client_request_id"] = request_id
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

        try:
            principal = _resolve_principal(_ctx)
            owner_id = str(principal["id"]) if principal and principal.get("id") else None
            runs = hosted_store().list_runs(owner_id)
        except (OSError, RuntimeError):
            LOGGER.exception("Research runs read unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        return jsonify({"runs": runs})

    @app.get("/api/research/intelligence/search-status/<uuid:request_id>")  # type: ignore[misc]
    def intelligence_search_status(request_id: uuid.UUID) -> ResponseReturnValue:
        """Locate a completed search after its browser request was interrupted."""
        from archipelago.scholarly.intelligence.storage import hosted_store

        store = hosted_store()
        principal = _resolve_principal(_ctx)
        owner = str(principal["id"]) if principal and principal.get("id") else None
        for summary in store.list_runs(owner):
            run = store.get_run(str(summary["run_id"]), owner)
            if run and run.get("client_request_id") == str(request_id):
                return jsonify({"status": "completed", "run_id": summary["run_id"]})
        return jsonify({"status": "pending"})

    @app.get("/api/research/intelligence/runs/<uuid:run_id>")  # type: ignore[misc]
    def intelligence_run(run_id: uuid.UUID) -> ResponseReturnValue:
        try:
            run = _run(run_id)
        except (OSError, RuntimeError):
            LOGGER.exception("Research run read unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        if _retired_run(run):
            return _retired_response()
        return jsonify(run) if run else (jsonify({"error": "not_found"}), 404)

    @app.get("/api/research/intelligence/runs/<uuid:run_id>/graph")  # type: ignore[misc]
    def intelligence_graph(run_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.graph import build_graph

        try:
            run = _run(run_id)
        except (OSError, RuntimeError):
            LOGGER.exception("Research graph read unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        if _retired_run(run):
            return _retired_response()
        return jsonify(build_graph(run)) if run else (jsonify({"error": "not_found"}), 404)

    @app.get("/api/research/intelligence/runs/<uuid:run_id>/xlsx")  # type: ignore[misc]
    def intelligence_xlsx(run_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence import workbook

        mode = (request.args.get("mode") or "standard").strip().lower()
        if mode not in {"standard", "advanced"}:
            return jsonify({"error": "invalid_export_mode"}), 400
        workbook.safe_cell = _safe_workbook_cell
        try:
            run = _run(run_id)
        except (OSError, RuntimeError):
            LOGGER.exception("Research workbook read unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        if _retired_run(run):
            return _retired_response()
        if not run:
            return jsonify({"error": "not_found"}), 404
        topic = str((run.get("options") or {}).get("topic") or "research")
        slug = re.sub(r"[^a-z0-9]+", "-", topic.casefold()).strip("-")[:48] or "research"
        date_str = _SAFE_FILENAME_RE.sub("_", str(run.get("retrieved_at") or "")[:10] or "export")
        safe_name = _SAFE_FILENAME_RE.sub("_", f"archipelago-{slug}-{date_str}-{mode}.xlsx")
        stream = workbook.build_workbook(_prepare_run_for_workbook(run), mode=mode)
        response = send_file(
            stream,
            mimetype=XLSX_MIME,
            as_attachment=True,
            download_name=safe_name,
        )
        if mode == "standard":
            response.headers["X-Archipelago-Export-Schema"] = "paper-venue-v2"
        response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Vary"] = "Authorization, Cookie"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/research/intelligence/runs/<uuid:run_id>/preview")  # type: ignore[misc]
    def intelligence_preview(run_id: uuid.UUID) -> ResponseReturnValue:
        """Return the three rankable sheets for the run owner."""
        from archipelago.scholarly.intelligence.ranking_preview import preview_run

        try:
            run = _run(run_id)
        except (OSError, RuntimeError):
            LOGGER.exception("Research preview read unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        if _retired_run(run):
            return _retired_response()
        return jsonify(preview_run(run)) if run else (jsonify({"error": "not_found"}), 404)

    @app.get("/api/research/intelligence/runs/<uuid:run_id>/dossier")  # type: ignore[misc]
    def intelligence_dossier(run_id: uuid.UUID) -> ResponseReturnValue:
        """Return aligned topic and paper details for the run."""
        from archipelago.scholarly.intelligence.run_dossier import build_run_dossier
        from archipelago.scholarly.intelligence.storage import hosted_store

        try:
            # _run applies owner scoping for students/faculty and grants manager
            # access only to authorized librarian/administrator roles.
            run = _run(run_id)
        except (OSError, RuntimeError):
            LOGGER.exception("Research dossier read unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        if _retired_run(run):
            return _retired_response()
        return jsonify(build_run_dossier(run)) if run else (jsonify({"error": "not_found"}), 404)

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
        record_user_action(
            "research_search",
            str((payload or {}).get("topic") or "") if isinstance(payload, dict) else "",
        )
        try:
            options = validate_options(payload if isinstance(payload, dict) else {})
            cadence_hours = validate_cadence(
                payload.get("cadence_hours", DEFAULT_CADENCE_HOURS)
                if isinstance(payload, dict)
                else DEFAULT_CADENCE_HOURS
            )
            monitor_id = hosted_store().save_monitor(str(_principal()["id"]), options, cadence_hours)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, RuntimeError):
            LOGGER.exception("Research monitor creation unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        return jsonify({"monitor_id": monitor_id, "enabled": False}), 201

    @app.get("/api/research/intelligence/monitors")  # type: ignore[misc]
    def intelligence_monitors() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        try:
            monitors = hosted_store().list_monitors(str(_principal()["id"]))
        except (OSError, RuntimeError):
            LOGGER.exception("Research monitors read unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        return jsonify({"monitors": monitors})

    @app.patch("/api/research/intelligence/monitors/<uuid:monitor_id>")  # type: ignore[misc]
    def intelligence_monitor_activation(monitor_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store, validate_cadence

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True)
        record_user_action(
            "research_search",
            str((payload or {}).get("topic") or "") if isinstance(payload, dict) else "",
        )
        if not isinstance(payload, dict):
            return jsonify({"error": "invalid_monitor_update"}), 400
        store = hosted_store()
        owner = str(_principal()["id"])
        try:
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
        except (OSError, RuntimeError):
            LOGGER.exception("Research monitor update unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        if not any(key in payload for key in ("enabled", "cadence_hours")):
            return jsonify({"error": "invalid_monitor_update"}), 400
        return jsonify({"monitor_id": str(monitor_id), "updated": True})

    @app.delete("/api/research/intelligence/monitors/<uuid:monitor_id>")  # type: ignore[misc]
    def intelligence_monitor_delete(monitor_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        try:
            deleted = hosted_store().delete_monitor(str(monitor_id), str(_principal()["id"]))
        except (OSError, RuntimeError):
            LOGGER.exception("Research monitor delete unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
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
        try:
            if not any(row["id"] == str(monitor_id) for row in store.list_monitors(owner)):
                return jsonify({"error": "not_found"}), 404
            history = store.list_history(str(monitor_id), owner)
        except (OSError, RuntimeError):
            LOGGER.exception("Research monitor history unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        return jsonify({"history": history})

    @app.get("/api/research/intelligence/updates")  # type: ignore[misc]
    def intelligence_updates() -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.storage import hosted_store

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        try:
            updates = hosted_store().list_events(str(_principal()["id"]))
        except (OSError, RuntimeError):
            LOGGER.exception("Research updates read unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        return jsonify({"updates": updates})

    @app.post("/api/research/intelligence/monitors/<uuid:monitor_id>/run")  # type: ignore[misc]
    def intelligence_monitor_run(monitor_id: uuid.UUID) -> ResponseReturnValue:
        from archipelago.scholarly.intelligence.monitor import run_monitor
        from archipelago.scholarly.intelligence.storage import hosted_store

        if _principal()["role"] not in MONITOR_ROLES:
            return jsonify({"error": "forbidden"}), 403
        store = hosted_store()
        try:
            if not store.make_monitor_due(str(monitor_id), str(_principal()["id"])):
                return jsonify({"error": "not_found_or_disabled"}), 404
            result = run_monitor(str(monitor_id), store)
        except (OSError, RuntimeError):
            LOGGER.exception("Research monitor execution unavailable")
            return jsonify({"error": "research_storage_unavailable"}), 503
        return jsonify(result), 200 if result["status"] != "failed" else 503

    @app.post("/api/research/intelligence/import")  # type: ignore[misc]
    def intelligence_import() -> ResponseReturnValue:
        from archipelago.scholarly.discovery.scholar_import import import_scholar_citations

        payload = request.get_json(silent=True)
        record_user_action(
            "research_search",
            str((payload or {}).get("topic") or "") if isinstance(payload, dict) else "",
        ) or {}
        if not isinstance(payload, dict) or not str(payload.get("content") or "").strip():
            return jsonify({"error": "empty_import_payload"}), 400
        raw_content = str(payload["content"])
        if len(raw_content) > MAX_IMPORT_CONTENT_CHARS:
            return jsonify({"error": "import_payload_too_large"}), 413
        fmt = str(payload.get("format") or "auto")[:32]
        res = import_scholar_citations(raw_content, fmt=fmt)
        status = 200 if res.get("records") else 400
        return jsonify(res), status
